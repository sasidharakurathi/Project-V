from google.adk.agents import Agent
from google.adk.tools import google_search

search_agent = Agent(
    name="search_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are VEGA's search specialist. "
        "Your role is to search the web for current news, facts, prices, "
        "and any live information the operator needs. "
        "Use the google_search tool to find accurate and up-to-date data. "
        "Summarize the search results naturally and concisely. "
        "Example: 'The latest news in tech shows...' or 'Current weather in Hyderabad is...'"
    ),
    tools=[google_search]
)
