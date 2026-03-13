import json
import os

# Path to the profile JSON file in the same directory
PROFILE_PATH = os.path.join(os.path.dirname(__file__), "vega_profile.json")

# Default profile schema
DEFAULT_PROFILE = {
    "name": "Sasidhar",
    "preferred_browser": "chrome",
    "work_hours_start": "09:30",
    "work_hours_end": "18:30",
    "frequently_used_apps": [],
    "last_session_summary": ""
}

def load_profile() -> dict:
    """
    Loads the user profile from vega_profile.json.
    Creates the file with defaults if it doesn't exist.
    """
    try:
        if not os.path.exists(PROFILE_PATH):
            with open(PROFILE_PATH, 'w') as f:
                json.dump(DEFAULT_PROFILE, f, indent=2)
            return DEFAULT_PROFILE.copy()
        
        with open(PROFILE_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        # Return default dictionary silently on any error
        return DEFAULT_PROFILE.copy()

def update_profile(key: str, value) -> None:
    """
    Updates a specific key in the user profile and saves it.
    """
    try:
        profile = load_profile()
        profile[key] = value
        with open(PROFILE_PATH, 'w') as f:
            json.dump(profile, f, indent=2)
    except Exception as e:
        # Print error and continue silently
        print(f"Error updating profile: {e}")

def get_profile_header() -> str:
    """
    Returns a formatted string for LLM prompt injection.
    Omits the name line if the name is empty.
    """
    profile = load_profile()
    
    parts = []
    
    # Omit name line if empty
    name = profile.get("name", "")
    if name:
        parts.append(f"Operator name: {name}.")
    
    browser = profile.get("preferred_browser", "chrome")
    parts.append(f"Preferred browser: {browser}.")
    
    start = profile.get("work_hours_start", "09:00")
    end = profile.get("work_hours_end", "18:00")
    parts.append(f"Work hours: {start} to {end}.")
    
    apps = profile.get("frequently_used_apps", [])
    apps_list = ", ".join(apps) if apps else "None"
    parts.append(f"Frequently used apps: {apps_list}.")
    
    return "\n".join(parts)
