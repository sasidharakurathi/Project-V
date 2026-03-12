import time
import psutil
from typing import Any, Dict


def get_battery_info() -> Dict[str, Any]:
    """
    Gather Battery information.

    Returns:
        Dict[str, Any]: Dictionary with Battery information structured for ADK/Frontend
    """
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return {
                "result": {"error": "No battery detected"},
                "stats": {"percent": 100, "power_plugged": True},
                "additional_info": {"collection_timestamp": time.time()},
            }

        return {
            "result": {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "secsleft": battery.secsleft,
            },
            "stats": {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
            },
            "additional_info": {"collection_timestamp": time.time()},
        }
    except Exception as e:
        return {
            "result": {"error": str(e)},
            "stats": {"percent": 100, "power_plugged": True},
            "additional_info": {"error_type": str(type(e).__name__)},
        }
