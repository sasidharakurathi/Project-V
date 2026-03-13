"""
scene_shift.py — SceneShift Loop Agent for VEGA Desktop Assistant
Detects work-mode transitions (FOCUS, CALL, BROWSE, UNWIND) by observing
active window titles, and autonomously applies the saved scene layout.
"""

import asyncio
import json
import time
import subprocess
import threading
import logging
from typing import Optional, List

logger = logging.getLogger("VegaBackend.SceneShift")

import psutil
import aiosqlite
import win32gui
import win32process
import os
import base64
import io
import mss
from PIL import Image
from google import genai

# pycaw for volume + audio device control
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL

    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False

# ─────────────────────────────────────────────
# Heuristic Rules — No API call needed for these
# ─────────────────────────────────────────────
HEURISTIC_RULES = {
    "CALL": [
        "zoom",
        "teams",
        "meet.google",
        "slack",
        "webex",
        "discord",
        "skype",
        "whereby",
    ],
    "FOCUS": [
        "visual studio code",
        "vscode",
        "code",
        "pycharm",
        "cursor",
        "intellij",
        "vim",
        "terminal",
        "powershell",
        "wsl",
        "cmd",
        "notepad++",
        "sublime",
        "eclipse",
        "android studio",
    ],
    "UNWIND": [
        "youtube",
        "netflix",
        "spotify",
        "steam",
        "vlc",
        "mpv",
        "prime video",
        "disney+",
        "hbo",
        "twitch",
    ],
    "BROWSE": ["chrome", "firefox", "edge", "brave", "opera", "safari"],
}

# Badge colors emitted to the HUD
SCENE_COLORS = {
    "FOCUS": "#a855f7",  # Purple (Zen/Code)
    "CALL": "#22c55e",  # Green (Active)
    "BROWSE": "#00e5ff",  # Cyan (Info)
    "UNWIND": "#ff9d00",  # Amber (Relax)
    "IDLE": "#64748b",  # Gray (Standby)
}


# ─────────────────────────────────────────────
# Helper: get all visible window titles
# ─────────────────────────────────────────────
def get_active_window_titles() -> list[str]:
    """Returns a list of all currently open window titles."""
    titles = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and len(title) > 2:
                titles.append(title.lower())

    win32gui.EnumWindows(callback, None)
    # logger.debug(f"Titles captured: {titles}")
    return titles


# ─────────────────────────────────────────────
# Heuristics Classifier
# ─────────────────────────────────────────────
def classify_by_heuristics(titles: list[str]) -> Optional[str]:
    """
    Fast, zero-latency classification using window title keywords.
    Returns a mode string or None if no match.
    Priority order: CALL > FOCUS > UNWIND > BROWSE.
    """
    combined = " ".join(titles)
    for mode in ["CALL", "FOCUS", "UNWIND", "BROWSE"]:
        for keyword in HEURISTIC_RULES[mode]:
            if keyword in combined:
                logger.info(f"Heuristic match found: '{keyword}' -> {mode}")
                return mode
    return None


# ─────────────────────────────────────────────
# Gemini Fallback Classifier (async)
# ─────────────────────────────────────────────
async def classify_by_gemini(titles: list[str], gemini_client) -> Optional[str]:
    """
    Calls Gemini to classify the mode when heuristics fail.
    Only called at most once per 30 seconds.
    """
    if not gemini_client:
        return None

    try:
        sample = titles[:15]  # Limit to top 15 windows to save tokens
        prompt = (
            f"You are a work-mode classifier for an AI desktop assistant.\n"
            f"Given these active Windows window titles: {json.dumps(sample)}\n"
            f"Classify the user's current mode as exactly one of: FOCUS, CALL, BROWSE, UNWIND.\n"
            f"Respond with ONLY the mode name, nothing else."
        )

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        mode = response.text.strip().upper()
        if mode in ["FOCUS", "CALL", "BROWSE", "UNWIND"]:
            return mode
    except Exception as e:
        print(f"[SceneShift] Gemini fallback error: {e}")

    return None


async def classify_scene_visually(api_key: str) -> str | None:
    """
    Captures screen and uses Gemini 2.5 Flash to classify the scene visually.
    """
    try:
        # Check vega_config.json for vision_enabled
        config_path = os.path.join(os.path.dirname(__file__), "vega_config.json")
        with open(config_path, "r") as f:
            config = json.load(f)
            if not config.get("vision_enabled", False):
                return None

        # Capture screen
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        encoded_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # Send to Gemini
        client = genai.Client(api_key=api_key)
        prompt = (
            "Classify the user's current activity as exactly ONE word from this list: "
            "coding, video_call, browsing, entertainment, writing, idle. "
            "Return ONLY the single classification word, nothing else."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                {"mime_type": "image/png", "data": encoded_image}
            ]
        )

        result = response.text.strip().lower()
        # Map visual categories to scene modes
        mapping = {
            "coding": "FOCUS",
            "video_call": "CALL",
            "browsing": "BROWSE",
            "entertainment": "UNWIND",
            "writing": "FOCUS",
            "idle": "IDLE"
        }
        return mapping.get(result)

    except Exception:
        return None


# ─────────────────────────────────────────────
# Scene Executor
# ─────────────────────────────────────────────
async def apply_scene(mode: str, db_path: str) -> bool:
    """
    Loads a saved scene from SQLite and executes it:
    - Snaps windows (if layout is saved)
    - Sets system volume
    - Launches required apps
    Returns True if scene was found and executed.
    """
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS scenes (
                    name TEXT PRIMARY KEY,
                    windows TEXT,
                    volume INTEGER,
                    audio_device TEXT,
                    apps TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            async with db.execute(
                "SELECT windows, volume, audio_device, apps FROM scenes WHERE name = ?",
                (mode,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            # Scene not yet configured by user, skip silently
            return False

        windows_layout = json.loads(row[0]) if row[0] else []
        volume = row[1]
        audio_device = row[2]
        apps = json.loads(row[3]) if row[3] else []

        # Set volume
        if volume is not None and PYCAW_AVAILABLE:
            try:
                sessions = AudioUtilities.GetSpeakers()
                interface = sessions.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
                volume_ctrl = interface.QueryInterface(IAudioEndpointVolume)
                # Convert 0-100 to 0.0-1.0 scalar
                volume_ctrl.SetMasterVolumeLevelScalar(volume / 100.0, None)
                print(f"[SceneShift] Volume set to {volume}%")
            except Exception as e:
                print(f"[SceneShift] Volume control error: {e}")

        # Launch apps
        for app in apps:
            try:
                subprocess.Popen(app, shell=True)
                print(f"[SceneShift] Launched: {app}")
            except Exception as e:
                print(f"[SceneShift] Failed to launch {app}: {e}")

        logger.info(f"Scene '{mode}' applied.")
        return True

    except Exception as e:
        logger.error(f"apply_scene error: {e}")
        return False


async def save_scene(
    name: str,
    volume: Optional[int],
    apps: list[str],
    audio_device: Optional[str],
    db_path: str,
) -> None:
    """Saves a scene configuration to the SQLite DB."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS scenes (
                name TEXT PRIMARY KEY,
                windows TEXT,
                volume INTEGER,
                audio_device TEXT,
                apps TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        await db.execute(
            """
            INSERT OR REPLACE INTO scenes (name, windows, volume, audio_device, apps)
            VALUES (?, ?, ?, ?, ?)
        """,
            (name, json.dumps([]), volume, audio_device, json.dumps(apps)),
        )
        await db.commit()
    logger.info(f"Scene '{name}' saved.")


async def list_scenes(db_path: str) -> list[dict]:
    """Fetches all saved scenes from SQLite."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS scenes (
                    name TEXT PRIMARY KEY,
                    windows TEXT,
                    volume INTEGER,
                    audio_device TEXT,
                    apps TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            async with db.execute(
                "SELECT name, volume, audio_device, apps, created_at FROM scenes"
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            {
                "name": row[0],
                "volume": row[1],
                "audio_device": row[2],
                "apps": json.loads(row[3]) if row[3] else [],
                "created_at": row[4],
            }
            for row in rows
        ]
    except Exception:
        return []


# ─────────────────────────────────────────────
# Main SceneShift Detector Class
# ─────────────────────────────────────────────
class SceneShiftDetector:
    """
    Background loop agent that detects work-mode transitions and
    autonomously applies the matching saved scene layout.
    """

    POLL_INTERVAL = 2  # seconds between each mode check
    GEMINI_COOLDOWN = 30  # seconds minimum between Gemini API calls

    def __init__(
        self, sio, loop: asyncio.AbstractEventLoop, db_path: str, gemini_client=None
    ):
        self.sio = sio
        self.loop = loop
        self.db_path = db_path
        self.gemini_client = gemini_client

        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._current_mode: Optional[str] = None
        self._last_gemini_call: float = 0.0
        self._last_visual_call: float = 0.0
        self.VISUAL_COOLDOWN = 45  # seconds

    async def start(self):
        """Starts the background scene detection task."""
        if self._is_running:
            return
        self._is_running = True
        logger.info("Starting background mode detection task...")
        # Since we use sio.start_background_task, we run directly in the parent loop
        await self._async_loop()

    def stop(self):
        """Stops the background detection."""
        self._is_running = False
        logger.info("Stopped.")

    async def _async_loop(self):
        """The core async polling loop."""
        logger.info("Loop entered - background monitoring ACTIVE.")
        while self._is_running:
            try:
                # logger.debug("Cycle start...")
                await self._check_and_apply()
            except Exception as e:
                logger.error(f"Loop error: {e}")

            await asyncio.sleep(self.POLL_INTERVAL)

    async def _check_and_apply(self):
        """Single iteration: detect mode, apply scene if changed."""
        titles = get_active_window_titles()
        if not titles:
            # Low-level check: is it really empty or isEnumWindows failing?
            return

        # 1. Fast heuristic classification
        detected_mode = classify_by_heuristics(titles)

        # 2. Gemini fallback (rate-limited)
        if not detected_mode:
            elapsed = time.time() - self._last_gemini_call
            if elapsed >= self.GEMINI_COOLDOWN:
                self._last_gemini_call = time.time()
                detected_mode = await classify_by_gemini(titles, self.gemini_client)

        # 3. Visual Classification Override (rate-limited to 45s)
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            elapsed_visual = time.time() - self._last_visual_call
            if elapsed_visual >= self.VISUAL_COOLDOWN:
                self._last_visual_call = time.time()
                visual_result = await classify_scene_visually(api_key)
                if visual_result and visual_result != detected_mode:
                    print(f"[SceneShift] Visual override: {visual_result}")
                    logger.info(f"Visual override: {visual_result}")
                    detected_mode = visual_result

        if not detected_mode:
            return  # Could not classify — do nothing

        # 4. Only act if mode actually changed
        if detected_mode == self._current_mode:
            return

        old_mode = self._current_mode
        self._current_mode = detected_mode
        print(f"[SceneShift] Mode transition: {old_mode} -> {detected_mode}")
        logger.info(f"Mode transition: {old_mode} -> {detected_mode}")

        # 4. Apply the scene
        await apply_scene(detected_mode, self.db_path)

        # 5. Notify the HUD
        if self.sio:
            await self.sio.emit(
                "scene_change",
                {
                    "mode": detected_mode,
                    "color": SCENE_COLORS.get(detected_mode, "#64748b"),
                },
            )
