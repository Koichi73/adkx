from google.adk.agents.llm_agent import Agent

greet_agent = Agent(
    model='gemini-3.1-flash-lite-preview',
    name='greet_agent',
    description='A sub-agent to greet the user.',
    instruction="Please greet the user.",
)

# no root_agent, only sub-agents are tested in this case.
