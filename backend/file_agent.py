from google.adk.agents import Agent
from file_ops import (
    watch_folder,
    rename_files,
    move_files,
    search_files,
    create_folder_structure
)

# Rename the imports to match the expected tool names in the instructions if needed, 
# although ADK can use them as is. I will wrap them to ensure exact naming if preferred,
# but the prompt says "has access to these tools from file_ops.py".

file_agent = Agent(
    name="file_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are VEGA's file operations specialist. "
        "Handle all file and folder tasks precisely. "
        "Confirm actions with short responses. "
        "Example: 'Moved 3 files to Downloads.' "
        "Never say 'Done.' — always state what happened."
    ),
    tools=[
        watch_folder,
        rename_files,
        move_files,
        search_files,
        create_folder_structure
    ]
)
