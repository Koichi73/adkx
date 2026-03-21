from google.adk.agents.llm_agent import Agent

dog_agent = Agent(
    model='gemini-3.1-flash-lite-preview',
    name='dog_agent',
    instruction="Please bark like a dog.",
)
