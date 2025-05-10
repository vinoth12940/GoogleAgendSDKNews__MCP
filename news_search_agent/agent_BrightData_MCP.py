# agent.py (modify get_tools_async and other parts as needed)

import os
import threading
import asyncio
from dotenv import load_dotenv
from google.adk.agents import Agent, SequentialAgent
from google.adk.models import LlmRequest, LlmResponse
from google.adk.events import Event, EventActions
from google.genai import types
from typing import Optional
from google.adk.agents.callback_context import CallbackContext

# MCP Toolset imports
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters


load_dotenv()

_mcp_tools = None
_exit_stack = None
_initialized = False
_initialization_in_progress = False
_init_lock = threading.Lock()

print("Module loaded: news_search_agent (multi-step pipeline)")

def create_news_planner_agent():
    return Agent(
        name="news_planner",
        model="gemini-2.0-flash",
        description="Plans news research by breaking down a user's topic into specific news search queries.",
        instruction='''
        You are a news planning expert. Your task is to:
        1. Analyze the user's news topic.
        2. Break it down into 3-5 specific search queries designed to find relevant and recent news articles. Consider if adding terms related to recency (e.g., "latest", "recent", or a specific year) would be beneficial for the given topic.
        3. Output a JSON object with format: {"queries": ["news_query1", "news_query2", "news_query3"]}
        Focus on keywords that are likely to yield news results from reputable sources.
        ''',
        output_key="search_queries"
    )

def create_news_researcher_agent():
    return Agent(
        name="news_researcher",
        model="gemini-2.0-flash",
        description="Executes news searches, extracts article details including publication dates, and aims for around 15 articles.",
        instruction='''
        You are a dedicated News Web Researcher. Your goal is to find approximately 15 relevant news articles.
        You will:
        1. Take the specific news search queries provided by the news_planner.
        2. For EACH query:
           a. Use the 'search_engine' tool (e.g., with the 'google' engine) to find potential news articles. Prioritize results that appear to be from well-known, reputable news organizations or official sources and seem recent.
           b. Select several of the most relevant and promising search results that seem to be actual news articles.
           c. For each selected article URL (aiming to process enough to get up to 15 articles in total):
              i. Use 'scraping_browser_navigate' to go to the article URL. The tools will help validate if the URL is accessible.
              ii. Use 'scraping_browser_get_text' to extract the main textual content of the news article.
              iii. From the extracted text or page metadata (if discernible), diligently try to identify the article's precise **Title**, verify the full **URL**, and find its **Publication Date** (try to format as YYYY-MM-DD if possible, otherwise use the format found).
              iv. Based *only* on the extracted text, write a **Detailed Summary** of the article. This summary should be comprehensive, capturing the key points, facts, and narrative of the news piece, and should be approximately 50-60 lines long.
           d. If a page fails to load, is not a news article, or if you cannot extract sufficient content (including a publication date), discard it and try another search result if available.
        3. Compile your findings into a list of JSON objects. Each object in the list should represent one successfully processed news article and must have the following four keys: "title", "url", "publication_date", and "summary".
           Example format: 
           [
             {"title": "Example News Article Title 1", "url": "https://www.examplenews.com/article1", "publication_date": "2023-10-26", "summary": "This is a detailed summary..."},
             {"title": "Another News Story Headline", "url": "https://www.anothernews.org/story2", "publication_date": "2023-10-25", "summary": "This detailed summary..."}
           ]
        4. If, after attempting all queries and selected URLs, you find fewer than 15 suitable news articles (or none), output the list of articles you did find. Output an empty list [] if none are found.
        
        IMPORTANT NOTES:
        - Aim for a total of approximately 15 articles across all queries.
        - Extracting the **Publication Date** is mandatory for each article.
        - The **Detailed Summary** (50-60 lines) is crucial and must be based *only* on the extracted text.
        - Ensure the output is a valid JSON list of objects as specified.
        ''',
        tools=[],
        before_model_callback=check_news_researcher_tools
    )

def create_news_publisher_agent():
    return Agent(
        name="news_publisher",
        model="gemini-2.0-flash", 
        description="Sorts news articles by date and compiles them into a clear, organized report.",
        instruction='''
        You are an expert News Report Compiler. Your task is to take the list of researched news articles, sort them by publication date (latest first), and present them in a highly readable Markdown report.

        Follow these instructions meticulously:
        1.  **Input Check:** You will receive a list of news article objects (each with "title", "url", "publication_date", and "summary"). If the list is empty, your entire report should simply state: "No relevant news articles were found for the specified topic after a thorough search."
        2.  **Sort Articles:** If articles are present, **sort the list of articles by the `publication_date` field in descending order (latest to oldest).** If a date is not in a standard sortable format, do your best to infer order or keep them grouped if ambiguous.
        3.  **Report Title:** Begin your report with a main title, for example: "## News Report on [Original User Topic]" (If the original topic isn't explicitly available, use "## News Report").
        4.  **Article Presentation:** For each news article in the sorted list:
            a.  **Article Title:** Display the article's title as a clear heading (e.g., `### Article Title`).
            b.  **Publication Date:** Immediately below the title, display the `publication_date` (e.g., `**Published:** YYYY-MM-DD`).
            c.  **URL:** Below the date, list the article's full URL, making it a clickable link (e.g., `[Article URL](Article URL)`).
            d.  **Detailed Summary:** Present the detailed summary (approximately 50-60 lines) exactly as provided. Ensure good paragraph formatting.
            e.  Add a separator (like `---`) before starting the next article, unless it's the last one.
        5.  **Clarity and Formatting:** Use clean Markdown. Ensure good spacing.
        6.  **No External Information:** Your report must *only* contain the information provided (titles, URLs, dates, summaries). Do not add opinions or external analysis.
        7.  **Professional Tone:** Maintain an objective and informative tone.
        ''',
        output_key="news_report_document"
    )

async def initialize_mcp_tools_async():
    """Initialize MCP tools using the existing event loop."""
    global _mcp_tools, _exit_stack, _initialized, _initialization_in_progress, root_agent
    
    if _initialized:
        print("MCP tools already initialized.")
        return _mcp_tools
    
    with _init_lock:
        if _initialized:
            print("MCP tools already initialized (checked after lock).")
            return _mcp_tools
        if _initialization_in_progress:
            print("MCP initialization already in progress (checked after lock), waiting...")
            while _initialization_in_progress:
                await asyncio.sleep(0.1)
            print("MCP initialization now completed by another task.")
            return _mcp_tools
        
        print("Setting initialization in progress flag.")
        _initialization_in_progress = True
    
    try:
        print("Connecting to Bright Data MCP for News Search Agent...")
        tools, exit_stack = await MCPToolset.from_server(
            connection_params=StdioServerParameters(
                command='npx',
                args=["-y", "@brightdata/mcp"],
                env={
                    "API_TOKEN": "26a7f2b3a350dbd19be8e7ff9bb3166c41f4e2fed1d3cd1557c97f2c964845e5",
                    "WEB_UNLOCKER_ZONE": "mcp_unlocker",
                    "BROWSER_AUTH": "brd-customer-hl_d4330cb5-zone-browser_api_zone:i128xaujd4zl"
                }
            )
        )
        print(f"MCP Toolset created successfully with {len(tools)} tools for News Search Agent")
        
        _mcp_tools = tools
        _exit_stack = exit_stack
        
        import atexit
        def cleanup_mcp():
            global _exit_stack
            if _exit_stack:
                print("Closing MCP server connection (atexit) for News Search Agent...")
                try:
                    current_loop = asyncio.get_event_loop_policy().get_event_loop()
                    if current_loop.is_running():
                        asyncio.ensure_future(_exit_stack.aclose(), loop=current_loop)
                    else:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(_exit_stack.aclose())
                        loop.close()
                    print("MCP server connection closed successfully (atexit) for News Search Agent.")
                except Exception as e:
                    print(f"Error closing MCP connection during atexit for News Search Agent: {e}")
                finally:
                    _exit_stack = None
        atexit.register(cleanup_mcp)
        
        _initialized = True
        
        if root_agent and hasattr(root_agent, 'sub_agents'):
            for agent_instance in root_agent.sub_agents:
                if agent_instance.name == "news_researcher":
                    agent_instance.tools = _mcp_tools
                    print(f"Successfully added {len(_mcp_tools)} tools to news_researcher agent")
                    tool_names = [tool.name for tool in _mcp_tools[:5]]
                    print(f"Available tools for news_researcher now include: {', '.join(tool_names)}")
                    break
            else:
                print("news_researcher agent not found in root_agent.sub_agents to assign tools.")
        else:
            print("root_agent not defined or not a SequentialAgent when trying to assign tools to news_researcher.")
                
        print("MCP initialization complete for News Search Agent!")
        return _mcp_tools
        
    except Exception as e:
        print(f"Critical error initializing MCP tools for News Search Agent: {e}")
        _mcp_tools = []
        return None
    finally:
        print("Resetting initialization in progress flag.")
        _initialization_in_progress = False

async def check_news_researcher_tools(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    global _mcp_tools, _initialized, _initialization_in_progress
    
    agent_name = callback_context.agent_name
    
    if agent_name == "news_researcher":
        if not _initialized and not _initialization_in_progress:
            print(f"News Researcher agent ({agent_name}) needs tools. Starting initialization.")
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.create_task(initialize_mcp_tools_async())
            print("MCP tool initialization for News Researcher scheduled. Asking user to retry.")
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Initializing news research tools. This process happens once. Please try your query again in a few moments.")]
                )
            )
        elif _initialization_in_progress:
            print("MCP initialization for News Researcher is in progress. Asking user to wait.")
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="News research tool initialization is currently in progress. Please wait a moment and try again.")]
                )
            )
        elif _initialized and not _mcp_tools:
             print("MCP tools for News Researcher were initialized but something went wrong (tools list is empty).")
             return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="There was an issue initializing news research tools. Please check the logs.")]
                )
            )
    return None

root_agent = SequentialAgent(
    name="news_search_pipeline_agent",
    description="A multi-step agent that finds, summarizes, and compiles news articles on a given topic using Bright Data tools, aiming for 15 articles sorted by date.",
    sub_agents=[
        create_news_planner_agent(),
        create_news_researcher_agent(),
        create_news_publisher_agent()
    ]
)

print("News Search Agent (multi-step pipeline) structure created. MCP tools will be initialized on first use by the news_researcher agent.")

# To make the agent discoverable by ADK, ensure root_agent is defined globally.
# The ADK framework will look for a `root_agent` or a function like `create_agent()`.
# Since we are using a complex initialization, it's usually better if ADK handles the main async loop.
# If your ADK version expects `create_agent`, you might need to wrap this logic.

# For ADK to pick up the agent, especially with async initialization for tools,
# it's often better to have `create_agent` be async and do the tool setup there,
# or ensure tools are ready before the agent is fully constructed and returned.
# However, the callback mechanism is designed to handle on-demand initialization.

# Make sure `google.adk.agents.Agent` and `SequentialAgent` are correctly imported.
# Make sure `google.adk.tools.mcp_tool.mcp_toolset.MCPToolset` and `StdioServerParameters` are imported.
# Make sure `google.adk.models.LlmRequest`, `LlmResponse` are imported.
# Make sure `google.adk.agents.callback_context.CallbackContext` is imported.