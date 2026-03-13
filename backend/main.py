import asyncio
import os
import sys
import logging
import base64
import datetime

# Configure file logging
log_file = os.path.join(os.path.dirname(__file__), "vega_system.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PID:%(process)d] [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("VegaBackend")


class StreamToLogger:
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ""
        self._is_logging = False

    def write(self, buf):
        if self._is_logging:
            return
        try:
            self._is_logging = True
            for line in buf.rstrip().splitlines():
                self.logger.log(self.log_level, line.rstrip())
        finally:
            self._is_logging = False

    def flush(self):
        pass

    def isatty(self):
        return False


sys.stdout = StreamToLogger(logger, logging.INFO)
sys.stderr = StreamToLogger(logger, logging.ERROR)

import psutil
import socketio
import threading
import time
import json
import aiosqlite
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from wake_word import WakeWordEngine
from orchestrator import ADKOrchestrator
from context_observer import ContextObserver
from scene_shift import SceneShiftDetector, list_scenes, save_scene, apply_scene

# Add references folder for telemetry
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "references"))
)
from cpu import get_cpu_info
from memory import get_memory_info
from disk import get_disk_info
from gpu import get_gpu_info
from network import get_network_info
from battery import get_battery_info


main_loop = None
adk_orchestrator = None
context_observer = None
scene_detector = None


async def on_wake_word_detected():
    print("Wake word callback triggered!")
    if adk_orchestrator:
        adk_orchestrator.on_wake_word_detected()
    await sio.emit("wake_word_detected", {})


def start_listening_thread():
    engine = WakeWordEngine(wake_word="vega")
    engine.start(
        lambda: asyncio.run_coroutine_threadsafe(on_wake_word_detected(), main_loop)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop, adk_orchestrator, context_observer
    main_loop = asyncio.get_running_loop()

    # Initialize orchestrator
    adk_orchestrator = ADKOrchestrator(socket_io_server=sio, loop=main_loop)

    # background tasks
    sio.start_background_task(telemetry_loop)
    asyncio.create_task(watchdog_loop())

    context_observer = ContextObserver(
        sio=sio, orchestrator_loop=main_loop, check_interval=10
    )
    asyncio.create_task(context_observer.start())

    db_path = os.path.join(os.path.dirname(__file__), "vega_sessions.db")
    global scene_detector
    scene_detector = SceneShiftDetector(
        sio=sio,
        loop=main_loop,
        db_path=db_path,
        gemini_client=adk_orchestrator.client if adk_orchestrator else None,
    )
    asyncio.create_task(scene_detector.start())

    # Wake word
    listener_thread = threading.Thread(target=start_listening_thread, daemon=True)
    listener_thread.start()

    print("[Vega System] All backend agents initialized and running.")

    # Startup Greeting Logic
    async def _handle_startup_greeting():
        await asyncio.sleep(2.0)
        hour = datetime.datetime.now().hour
        greeting = ""
        if 6 <= hour < 12:
            greeting = "Good morning. VEGA online."
        elif 12 <= hour < 18:
            greeting = "Afternoon. VEGA online."
        elif 18 <= hour < 24:
            greeting = "Evening. VEGA online. Working late?"
        else:
            greeting = "VEGA online. Hope this is worth it."

        if adk_orchestrator:
            try:
                import base64

                audio_bytes, audio_format = await adk_orchestrator._generate_tts_audio(
                    greeting
                )
                if audio_bytes:
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    # Emit log and speak event.
                    await sio.emit("log", {"message": f"[Vega]: {greeting}"})
                    await sio.emit(
                        "speak",
                        {"audio": audio_b64, "format": audio_format, "silent": True},
                    )
                else:
                    await sio.emit("log", {"message": f"[Vega]: {greeting}"})
            except Exception as e:
                print(f"Startup greeting error: {e}")

    asyncio.create_task(_handle_startup_greeting())

    yield

    logger.info("Lifecycle: Backend shutdown initiated.")
    if context_observer:
        context_observer.stop()
    if scene_detector:
        scene_detector.stop()


app = FastAPI(title="Windows AI Assistant API", lifespan=lifespan)
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AIRequest(BaseModel):
    query: str


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/ask")
def ask_assistant(request: AIRequest):
    return {"response": f"Received query: {request.query}"}


@app.post("/api/shutdown")
def shutdown_server():
    print("Shutdown request received from frontend. Terminating...")
    import signal

    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting down"}


LAST_PING_TIME = time.time()


@app.get("/api/ping")
def handle_ping():
    global LAST_PING_TIME
    LAST_PING_TIME = time.time()
    return {"status": "alive"}


# --- SOCKET.IO EVENTS ---


@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")
    await sio.emit("log", {"message": f"Client connection established"}, room=sid)

    global scene_detector
    if scene_detector and scene_detector._current_mode:
        from scene_shift import SCENE_COLORS

        mode = scene_detector._current_mode
        await sio.emit(
            "scene_change",
            {"mode": mode, "color": SCENE_COLORS.get(mode, "#64748b")},
            room=sid,
        )


@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")


@sio.event
async def user_command(sid, data):
    if adk_orchestrator:
        text = data.get("text", "")
        if text:
            adk_orchestrator.process_text_command(text)


@sio.event
async def user_audio(sid, data):
    """Restore audio command handling."""
    if adk_orchestrator and isinstance(data, bytes):
        adk_orchestrator.process_audio_command(data)


@sio.on("interrupt")
async def handle_interrupt(sid, data=None):
    """Restore interrupt handling."""
    if adk_orchestrator:
        adk_orchestrator.request_interrupt()
    await sio.emit("state_change", {"state": "IDLE"})
    logger.info("[VEGA] Interrupted by user")


async def telemetry_loop():
    while True:
        try:
            payload = {
                "cpu": get_cpu_info(),
                "memory": get_memory_info(),
                "disk": get_disk_info(),
                "gpu": get_gpu_info(),
                "network": get_network_info(),
                "battery": get_battery_info(),
            }
            await sio.emit("telemetry", payload)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Telemetry error: {e}")
            await asyncio.sleep(5)


async def watchdog_loop():
    global LAST_PING_TIME
    import signal

    while True:
        await asyncio.sleep(5)
        if time.time() - LAST_PING_TIME > 60:
            logger.warning(
                f"[Backend Watchdog] No heartbeat from frontend. Self-terminating..."
            )
            os.kill(os.getpid(), signal.SIGTERM)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(socket_app, host="127.0.0.1", port=8000, log_config=None)
