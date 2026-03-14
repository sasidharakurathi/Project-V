import time
import uiautomation as auto
import subprocess


def open_application(app_name: str) -> str:
    """Opens any desktop application by name. Use this when the user says 'open [app]', 'start [app]', 'launch [app]', or asks to run any application like spotify, chrome, notepad, teams, discord, calculator, vscode, etc. The app_name should be the simple name of the application."""
    try:
        # Press the Windows key to open the Start menu
        auto.SendKeys("{Win}")
        # Wait a moment for the Start menu and search bar to fully appear
        time.sleep(0.5)

        # Type the app name into the search bar
        auto.SendKeys(app_name)
        # Wait a moment for Windows Search to find the top result
        time.sleep(0.5)

        # Press Enter to open the first matched application
        auto.SendKeys("{Enter}")

        return f"Successfully opened {app_name} via Windows Search."
    except Exception as e:
        return f"Failed to open {app_name}. Error: {e}"


def type_text(text: str) -> str:
    """Types the specified text into the currently active window."""
    try:
        auto.SendKeys(text)
        return f"Typed text: '{text}'"
    except Exception as e:
        return f"Failed to type text due to uiautomation error: {e}"


def press_key(key: str) -> str:
    """Presses a specific keyboard key. Pass clean string names like 'Enter', 'Esc', 'Win', 'Tab', 'Space'."""
    try:
        # Map clean key names to uiautomation bracket format
        formatted_key = key
        if not key.startswith("{") and not key.endswith("}"):
            # Capitalize to match uiautomation formats like {Enter}, {Space}
            formatted_key = f"{{{key.capitalize()}}}"

        auto.SendKeys(formatted_key)
        return f"Pressed keyboard key: {formatted_key}"
    except Exception as e:
        return f"Failed to press key due to uiautomation error: {e}"
