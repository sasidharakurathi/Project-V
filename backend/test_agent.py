import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

load_dotenv()


def get_system_status() -> str:
    return "Systen is OK."


agent = Agent(
    name="vega_orchestrator",
    model="gemini-2.5-flash",
    instruction="Hello. Say hello briefly.",
    tools=[get_system_status],
)

runner = Runner(
    app_name="vega_app",
    agent=agent,
    session_service=InMemorySessionService(),
    auto_create_session=True,
)

try:
    message = types.Content(role="user", parts=[types.Part.from_text(text="Hey Siri")])
    events = runner.run(user_id="user_1", session_id="session_1", new_message=message)
    for event in events:
        print(f"Event: {event.type}")
        if event.content and event.content.parts:
            for p in event.content.parts:
                print(f"Content: {p.text}")
        if event.actions and event.actions.tool_calls:
            print(f"Tool calls: {event.actions.tool_calls}")

except Exception as e:
    import traceback

    traceback.print_exc()
