from google.adk.agents.llm_agent import Agent
from google.adk.tools import ToolContext

def get_time_and_city(tool_context: ToolContext) -> dict:
    info = tool_context.state.get("info")
    return {"time": info["time"], "city": info["city"]}

root_agent = Agent(
    model='gemini-3.1-flash-lite-preview',
    name='root_agent',
    instruction="Use `get_time_and_city` tool and output the result.",
    tools=[get_time_and_city]
)
