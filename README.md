# News Search Agent

This project implements a news search agent using the Tavily API to fetch and display news articles. The agent is built using the Google ADK (Agent Development Kit), following practices outlined in the [ADK Quickstart](https://google.github.io/adk-docs/get-started/quickstart/).

## Features

*   Searches for news articles on specified topics.
*   Retrieves approximately 15 articles per search.
*   For each article, it provides:
    *   Title
    *   Detailed content summary (approximately 50-60 lines)
    *   URL
*   Presents results in a clear and organized manner.

## Prerequisites

*   Python 3.9+
*   `pip` for installing Python packages
*   Node.js and `npx` (for running the `tavily-mcp` server, which is a Node.js package)

## Project Structure

The project follows a structure similar to the one recommended in the ADK Quickstart:

```
. (parent_folder / your workspace root)
├── .gitignore
├── news_search_agent/
│   ├── __init__.py      # Makes 'news_search_agent' a Python package
│   └── agent.py         # Main agent logic
├── .env                 # Optional: For Google LLM API keys (e.g., GOOGLE_API_KEY)
└── README.md            # This file
```

## Setup

1.  **Clone the repository (if applicable) or ensure you have the project files.**

2.  **Create and activate a virtual environment (recommended):**
    Run these commands from your workspace root.
    ```bash
    python -m venv .venv
    # On macOS/Linux:
    source .venv/bin/activate
    # On Windows CMD:
    # .venv\Scripts\activate.bat
    # On Windows PowerShell:
    # .venv\Scripts\Activate.ps1
    ```

3.  **Install dependencies:**
    Ensure your virtual environment is activated.
    ```bash
    pip install google-adk tavily-python
    # (A requirements.txt can be generated later with `pip freeze > requirements.txt`)
    ```

4.  **Ensure `news_search_agent/__init__.py` exists:**
    This file makes the `news_search_agent` directory a Python package. It should contain:
    ```python
    from . import agent
    ```

5.  **Set up API Keys:**

    *   **Tavily API Key (for News Search):**
        This key is required for the Tavily news search functionality. It's configured directly within `news_search_agent/agent.py` in the `StdioServerParameters` for the `MCPToolset`:
        ```python
        # news_search_agent/agent.py
        # ...
        env={
            "TAVILY_API_KEY": "YOUR_TAVILY_API_KEY" # Replace with your actual Tavily key
        }
        # ...
        ```
        Replace `"YOUR_TAVILY_API_KEY"` with your actual key from [Tavily AI](https://app.tavily.com/).

    *   **Google LLM API Key (for the Agent's LLM):**
        The ADK agent itself (e.g., `LlmAgent`) requires credentials to interact with a Google Large Language Model (like Gemini). This is typically managed using a `.env` file in your project root (e.g., alongside `README.md`) or in the agent's directory (`news_search_agent/.env`).
        Create a `.env` file with the following content, replacing the placeholder with your actual Google API key obtained from [Google AI Studio](https://aistudio.google.com/):

        ```env
        # .env
        GOOGLE_GENAI_USE_VERTEXAI=FALSE
        GOOGLE_API_KEY=PASTE_YOUR_GOOGLE_API_KEY_HERE
        ```
        Alternatively, if you are using Vertex AI:
        ```env
        # .env
        GOOGLE_GENAI_USE_VERTEXAI=TRUE
        GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
        GOOGLE_CLOUD_LOCATION=YOUR_LOCATION
        ```
        The ADK will automatically load these variables if a `.env` file is present. The `agent.py` provided in this project does not explicitly load `.env` as ADK handles it, but for the MCP tool's environment, the Tavily key is passed directly.

## Running the Agent

Navigate to the parent directory of your agent project (i.e., your workspace root where the `news_search_agent` folder is located).

1.  **Using ADK Web (Recommended for Dev):**
    Run the following command to launch the interactive development UI:
    ```bash
    adk web
    ```
    Open the URL provided (usually `http://localhost:8000`) in your browser. Select "news_search_agent" from the agent dropdown to interact with it.

2.  **Using ADK Run (Terminal):**
    To chat with your agent directly in the terminal:
    ```bash
    adk run news_search_agent
    ```
    To exit, use `Cmd/Ctrl+C`.

Follow the ADK documentation for more advanced ways to run and deploy agents.

## How it Works

The core logic resides in `news_search_agent/agent.py`. It defines an `LlmAgent` configured with specific instructions to:
1.  Utilize the `tavily-mcp` tool for news searches.
2.  Request a specific number of articles (around 15).
3.  Specify the format of the output (title, detailed summary, URL).
4.  Define the desired length of the content summary (50-60 lines).

The connection to the Tavily search capabilities is established through the Model Context Protocol (MCP):

*   **Tavily MCP Server (`tavily-mcp`):** This project uses `tavily-mcp`, an MCP server that provides tools like `tavily-search`. As seen in `news_search_agent/agent.py`, it is launched using `npx` (`npx -y tavily-mcp@0.1.3`). The Tavily API key is passed as an environment variable to this `npx` process. More info: [tavily-mcp npm page](https://www.npmjs.com/package/tavily-mcp).

*   **Google ADK `MCPToolset`:** The ADK interacts with MCP servers via `MCPToolset`. In `news_search_agent/agent.py`, `MCPToolset.from_server()` with `StdioServerParameters` connects to the local `tavily-mcp` server. This makes Tavily's tools available to the ADK agent. More info: [ADK documentation on MCP tools](https://google.github.io/adk-docs/tools/mcp-tools/#step-2-update-create_agent).
    *   **Note on Configuration:** While some MCP clients use JSON for configuration, this project configures the connection programmatically in `agent.py` using `StdioServerParameters`.

This setup allows the `LlmAgent` to delegate search tasks to Tavily.

## Customization

*   **Search Queries:** Modify your prompts to the agent.
*   **Output Format:** Adjust the `instruction` in `LlmAgent` in `agent.py`.
*   **Model:** The agent uses `gemini-2.0-flash`. Change as needed.
*   **API Keys:** Ensure your API keys are correctly set up. 