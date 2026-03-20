from google.adk.agents.llm_agent import Agent

root_agent = Agent(
    model='gemini-3-flash-preview',
    name='root_agent',
    instruction="""Output following line:
    It is {time} in {city} right now.
    """,
)
