import time
import threading
import psutil
import uiautomation as auto
import asyncio
import pythoncom


class ContextObserver:
    def __init__(self, sio, orchestrator_loop, check_interval=10):
        self.sio = sio
        self.loop = orchestrator_loop
        self.check_interval = check_interval
        self._is_running = False
        self._thread = None

        # State tracking to avoid spamming the same anomaly
        self.last_active_window = ""
        self.high_cpu_alerted = False
        self.low_battery_alerted = False

    async def start(self):
        """Starts the background loop agent task."""
        if self._is_running:
            return
        self._is_running = True
        print("[Context Observer] Started background polling task.")
        await self._observe_loop()

    def stop(self):
        """Stops the background loop agent task."""
        self._is_running = False
        print("[Context Observer] Stopped background polling.")

    async def _observe_loop(self):
        """The main execution loop for the agent, running every 10 seconds."""
        # Note: uiautomation might still prefer COM initialization if called from a task
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except:
            pass

        try:
            while self._is_running:
                try:
                    self._check_context()
                except Exception as e:
                    print(f"[Context Observer Error]: {e}")

                await asyncio.sleep(self.check_interval)
        finally:
            try:
                pythoncom.CoUninitialize()
            except:
                pass

    def _check_context(self):
        """Gathers context (active window, cpu, battery) and triggers proactive anomalies."""
        anomalies = []

        # 1. Check Active Window via UIAutomation
        try:
            active_window = auto.PaneControl(searchDepth=1).Name
            if active_window and active_window != self.last_active_window:
                self.last_active_window = active_window
                # In the future, this could be sent directly to the ADK session context
                # print(f"[Context Observer] Focus changed to: {active_window}")
        except Exception:
            pass

        # 2. Check CPU/RAM Usage
        cpu_usage = psutil.cpu_percent()
        mem_usage = psutil.virtual_memory().percent

        if cpu_usage > 90.0:
            if not self.high_cpu_alerted:
                anomalies.append(
                    f"System CPU Usage is critically high at {cpu_usage}%."
                )
                self.high_cpu_alerted = True
        elif cpu_usage < 60.0:
            self.high_cpu_alerted = False  # Reset alert if system normalizes

        if mem_usage > 90.0:
            anomalies.append(f"System Memory Usage is critically high at {mem_usage}%.")

        # 3. Check Battery Status
        if hasattr(psutil, "sensors_battery"):
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged:
                if battery.percent < 15 and not self.low_battery_alerted:
                    anomalies.append(
                        f"Battery is low ({battery.percent}%). Suggest plugging in."
                    )
                    self.low_battery_alerted = True
                elif battery.percent >= 15:
                    self.low_battery_alerted = False

        # If anomalies found, proactively notify the user via WebSocket/Orchestrator
        for anomaly in anomalies:
            self._trigger_proactive_alert(anomaly)

    def _trigger_proactive_alert(self, message: str):
        """Sends a proactive system alert event to the frontend UI."""
        print(f"[PROACTIVE ALERT]: {message}")
        if self.loop and self.sio:
            asyncio.run_coroutine_threadsafe(
                self.sio.emit("log", {"message": f"⚠️ [Context Observer]: {message}"}),
                self.loop,
            )
