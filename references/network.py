import time
import psutil
from typing import Any, Dict

last_net_io = None
last_net_time = 0


def get_network_info() -> Dict[str, Any]:
    """
    Gather Network information.

    Returns:
        Dict[str, Any]: Dictionary with Network information structured for ADK/Frontend
    """
    global last_net_io, last_net_time

    try:
        current_net_io = psutil.net_io_counters()
        current_time = time.time()

        up_speed = 0.0
        down_speed = 0.0

        if last_net_io is not None and last_net_time > 0:
            dt = current_time - last_net_time
            if dt > 0:
                # Convert to Mbps
                up_speed = (
                    (current_net_io.bytes_sent - last_net_io.bytes_sent) * 8
                ) / (1024 * 1024 * dt)
                down_speed = (
                    (current_net_io.bytes_recv - last_net_io.bytes_recv) * 8
                ) / (1024 * 1024 * dt)

        last_net_io = current_net_io
        last_net_time = current_time

        return {
            "result": {
                "bytes_sent": current_net_io.bytes_sent,
                "bytes_recv": current_net_io.bytes_recv,
                "packets_sent": current_net_io.packets_sent,
                "packets_recv": current_net_io.packets_recv,
            },
            "stats": {
                "upload_mbps": max(0.0, up_speed),
                "download_mbps": max(0.0, down_speed),
            },
            "additional_info": {"collection_timestamp": current_time},
        }
    except Exception as e:
        return {
            "result": {"error": str(e)},
            "stats": {"upload_mbps": 0.0, "download_mbps": 0.0},
            "additional_info": {"error_type": str(type(e).__name__)},
        }
