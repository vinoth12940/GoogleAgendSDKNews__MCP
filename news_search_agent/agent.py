# agent.py (modify get_tools_async and other parts as needed)

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

async def create_agent():
  """Gets tools from MCP Server."""

  tools, exit_stack = await MCPToolset.from_server(
      connection_params=StdioServerParameters(
          command='npx',
          args=["-y",
                "tavily-mcp@0.1.3",
          ],
          # Pass the API key as an environment variable to the npx process
          env={
              "TAVILY_API_KEY": "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"
          }
      )
  )


  agent = LlmAgent(
        model='gemini-2.0-flash',  # Adjust if needed
        name='NewsSearch_assistant',
        instruction='You are a news search assistant. You can use the tavily-mcp tool to search for news articles on various topics. Please return around 15 articles. For each article, provide the title, a detailed summary of the content (approximately 50-60 lines), and the URL. Present the results in a clear, organized manner. If the search returns no results, apologize and suggest trying a different topic or keyword.',
        tools=tools,
  )
  return agent, exit_stack

# Define the root_agent used by ADK
root_agent = create_agent()