from google.adk.agents.llm_agent import Agent

root_agent = Agent(
    model='gemini-3-flash-preview',
    name='root_agent',
    instruction="Please greet the user.",
)
