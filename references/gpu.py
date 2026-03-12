import subprocess
import time
from typing import Any, Dict, Optional


def _get_nvidia_info() -> Optional[Dict[str, Any]]:
    """Query the Nvidia GPU via nvidia-smi. Returns None if no Nvidia GPU is found."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        output = subprocess.check_output(
            cmd, encoding="utf-8", timeout=3, startupinfo=startupinfo
        ).strip()

        if not output:
            return None

        parts = [p.strip() for p in output.split(",")]
        name = parts[0]
        temp = float(parts[1])
        util = float(parts[2])
        mem_used = float(parts[3])
        mem_total = float(parts[4])
        mem_pct = (mem_used / mem_total * 100) if mem_total > 0 else 0.0

        return {
            "name": name,
            "type": "Dedicated (Nvidia)",
            "usage_percentage": util,
            "memory_usage_percentage": mem_pct,
            "memory_used_mb": mem_used,
            "memory_total_mb": mem_total,
            "temperature": temp,
        }
    except Exception:
        return None


def _get_intel_igpu_info() -> Optional[Dict[str, Any]]:
    """
    Query Intel integrated GPU usage via Windows Performance Counters (WMI).
    Filters engine instances belonging to an 'Intel' adapter.
    """
    try:
        # Each GPU engine instance name looks like:
        #   "engtype_3D_luid_0x000123_phys_0_eng_0 (Intel(R) UHD Graphics 630)"
        # We select Name + UtilizationPercentage for all engines, then filter for Intel.
        ps_script = (
            "Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine "
            "| Select-Object Name, UtilizationPercentage "
            "| ForEach-Object { $_.Name + '|' + $_.UtilizationPercentage }"
        )
        ps_cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            ps_script,
        ]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        output = subprocess.check_output(
            ps_cmd, encoding="utf-8", timeout=5, startupinfo=startupinfo
        ).strip()

        if not output:
            return None

        loads = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            # We only care about Intel engines
            if "intel" not in line.lower():
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                try:
                    val = float(parts[-1].strip())
                    loads.append(val)
                except ValueError:
                    continue

        if not loads:
            return None

        peak_load = min(max(loads), 100.0)

        return {
            "name": "Intel Integrated Graphics",
            "type": "Integrated (Intel)",
            "usage_percentage": peak_load,
            "memory_usage_percentage": 0.0,  # iGPU shares system RAM; no detached VRAM
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "temperature": 0.0,  # Intel iGPU temp not easily available via WMI
        }
    except Exception:
        return None


def get_gpu_info() -> Dict[str, Any]:
    """
    Returns telemetry for both Nvidia dedicated GPU and Intel integrated GPU
    as separate entries.  The result is always a dict with keys:
      - nvidia: {...} or None
      - intel:  {...} or None
      - stats:  averaged/combined view kept for backward-compat
      - result: same as stats
    """
    nvidia = _get_nvidia_info()
    intel = _get_intel_igpu_info()

    # Build backward-compatible combined stats
    usages = []
    if nvidia:
        usages.append(nvidia["usage_percentage"])
    if intel:
        usages.append(intel["usage_percentage"])

    avg_usage = sum(usages) / len(usages) if usages else 0.0
    temp = nvidia["temperature"] if nvidia else 0.0
    mem_pct = nvidia["memory_usage_percentage"] if nvidia else 0.0

    combined_stats = {
        "avg_usage_percentage": avg_usage,
        "memory_usage_percentage": mem_pct,
        "temperature": temp,
    }

    return {
        "nvidia": nvidia,
        "intel": intel,
        "stats": combined_stats,
        "result": combined_stats,
        "additional_info": {"collection_timestamp": time.time()},
    }
