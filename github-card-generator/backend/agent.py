import os
import sys
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams, StdioServerParameters
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Define the connection parameters for the local MCP server
server_params = StdioServerParameters(
    command=sys.executable,
    args=[os.path.join(os.path.dirname(__file__), "mcp_server.py")]
)

# Initialize the McpToolset with stdio transport
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=server_params,
        timeout=20.0
    )
)

# Create the ADK Agent called "github_card_agent"
github_card_agent = LlmAgent(
    name="github_card_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a GitHub profile analyst and dev card generator. "
        "When a user gives you a GitHub username, you ALWAYS follow this exact sequence: "
        "first call scrape_github, then analyze_profile with the result, "
        "then generate_card_html with all three inputs, then save_card. "
        "Never skip steps. Be enthusiastic about developers' work. "
        "If the profile is private or doesn't exist, say so clearly."
    ),
    tools=[mcp_toolset]
)

# Initialize the runner with the agent and an app name
runner = InMemoryRunner(agent=github_card_agent, app_name="github_card_app")
# Enable automatic session creation to avoid SessionNotFoundError
runner.auto_create_session = True

async def generate_github_card(username: str):
    """
    Orchestrate the card generation using the ADK agent.
    This uses the agent's runner to execute the tool-calling sequence.
    """
    user_id = "default_user"
    session_id = f"session_{username}"

    query = f"Generate a card for {username}"
    new_message = types.Content(role="user", parts=[types.Part(text=query)])
    
    final_text = ""
    # Use the runner's run_async method for asynchronous execution
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message
    ):
        # Accumulate text response from the agent events
        if hasattr(event, 'text') and event.text:
            final_text += event.text
        elif hasattr(event, 'content') and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text += part.text
    return final_text

# Export the agent and helper
if __name__ == "__main__":
    import asyncio
    async def run_example():
        print(f"--- Generating card for torvalds ---")
        try:
            result = await generate_github_card("torvalds")
            print(f"\nResult:\n{result}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_example())
