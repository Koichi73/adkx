from google.adk.agents.llm_agent import Agent

cat_agent = Agent(
    model='gemini-3.1-flash-lite-preview',
    name='cat_agent',
    instruction="Please meow like a cat.",
)

