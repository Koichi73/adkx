from google.adk.agents.llm_agent import Agent

greet_agent = Agent(
    model='gemini-3-flash-preview',
    name='greet_agent',
    description='A sub-agent to greet the user.',
    instruction="""Output following line:
    Hello! It is {time} in {city} right now.
    """,
)

root_agent = Agent(
    model='gemini-3-flash-preview',
    name='root_agent',
    instruction="""Use th greet_agent to greet the user.
    """,
    sub_agents=[greet_agent]
)

