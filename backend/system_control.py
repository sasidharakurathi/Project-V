import os
import subprocess
import shutil
import tempfile
import webbrowser
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import screen_brightness_control as sbc

# Ensure pythoncom is initialized for all COM-dependent functions (pycaw)
import pythoncom


def set_volume(level: int) -> str:
    """Sets the system master volume. Valid levels are 0 to 100."""
    try:
        level = max(0, min(100, level))  # Clamp between 0 and 100

        # Initialize COM for the background thread
        pythoncom.CoInitialize()

        devices = AudioUtilities.GetSpeakers()
        volume = devices.EndpointVolume

        # Scalar volume range is 0.0 to 1.0
        scalar_volume = level / 100.0
        volume.SetMasterVolumeLevelScalar(scalar_volume, None)

        return f"System volume successfully set to {level}%."
    except Exception as e:
        return f"Failed to set volume: {e}"
    finally:
        pythoncom.CoUninitialize()


def set_brightness(level: int) -> str:
    """Sets the primary monitor brightness. Valid levels are 0 to 100."""
    try:
        level = max(0, min(100, level))
        sbc.set_brightness(level)
        return f"Monitor brightness successfully set to {level}%."
    except Exception as e:
        return f"Failed to set brightness: {e}"


def toggle_wifi(state: str) -> str:
    """Toggles the system Wi-Fi adapter. State must be 'on' or 'off'."""
    try:
        state = state.lower()
        if state not in ["on", "off"]:
            return "Invalid state. Must be 'on' or 'off'."

        enable = "Enable" if state == "on" else "Disable"
        # Using netsh as a reliable fallback for wifi toggle across Win versions
        cmd = f'netsh interface set interface name="Wi-Fi" admin={enable}'
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        return f"System Wi-Fi successfully turned {state}."
    except subprocess.CalledProcessError as e:
        return f"Failed to toggle Wi-Fi. It might require elevated privileges or the adapter name might be different. Error: {e.stderr.decode('utf-8')}"
    except Exception as e:
        return f"Failed to toggle Wi-Fi: {e}"


def toggle_bluetooth(state: str) -> str:
    """Toggles system Bluetooth. State must be 'on' or 'off'."""
    try:
        state = state.lower()
        if state not in ["on", "off"]:
            return "Invalid state. Must be 'on' or 'off'."

        # Natively toggle bluetooth using PowerShell
        on_cmd = 'powershell -command "[cmdletbinding()]param() [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Service bthserv | Start-Service"'
        off_cmd = 'powershell -command "[cmdletbinding()]param() [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Service bthserv | Stop-Service -Force"'

        subprocess.run(on_cmd if state == "on" else off_cmd, shell=True, check=True)
        return f"Bluetooth service successfully turned {state}."
    except Exception as e:
        return f"Failed to toggle Bluetooth: {e}"


def clean_temp_files() -> str:
    """Empties the local Windows %TEMP% directory to free up space. Warning: This permanently deletes files."""
    try:
        temp_dir = tempfile.gettempdir()
        deleted_count = 0
        failed_count = 0

        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                deleted_count += 1
            except Exception:
                failed_count += 1

        return f"System cleanup complete. Successfully deleted {deleted_count} temporary items. {failed_count} items could not be deleted (likely in use)."
    except Exception as e:
        return f"Failed to clean temporary files: {e}"




def open_url(url: str) -> str:
    """Opens a website URL in the default browser. Use when the user says 'open [website]', 'go to [url]', 'visit [site]', 'open youtube', 'open google.com', etc. The url should be the website address."""
    try:
        if not url.startswith("http"):
            url = f"https://{url}"
        webbrowser.open(url)
        return f"Opened {url} in browser."
    except Exception as e:
        return f"Failed to open URL '{url}': {e}"
