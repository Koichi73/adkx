from google.adk.agents.llm_agent import Agent
from .tools import test_tool_2

def test_tool_1():
    return {"result": "Cat"}

greet_agent = Agent(
    model='gemini-3.1-flash-lite-preview',
    name='greet_agent',
    description='A sub-agent to greet the user.',
    instruction="Call all tools and output their results.",
    tools=[test_tool_1, test_tool_2]
)

# no root_agent, only greet_agent is tested in this case.