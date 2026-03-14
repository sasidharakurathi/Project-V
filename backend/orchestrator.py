import asyncio
import base64
import re
import io
import os
import threading
from pathlib import Path
import json
import uuid
from datetime import datetime
import aiosqlite
from dotenv import load_dotenv
from episodic_memory import save_memory, retrieve_relevant_memories
from user_profile import get_profile_header

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import (
    DatabaseSessionService
)
from google.adk.tools import AgentTool
from file_agent import file_agent
from browser_agent import browser_agent
from search_agent import search_agent
from google.genai import types
from google.cloud import texttospeech

from os_automation import open_application, type_text, press_key
from window_manager import (
    list_open_windows,
    switch_focus,
    close_app,
    snap_window,
    resize_window,
)
from system_control import (
    set_volume,
    set_brightness,
    toggle_wifi,
    toggle_bluetooth,
    clean_temp_files,
    open_url,
)
from file_ops import (
    watch_folder,
    rename_files,
    move_files,
    search_files,
    create_folder_structure,
)
from scene_shift import save_scene, apply_scene
from vision import analyze_screen


load_dotenv()


def get_system_paths() -> dict:
    home = Path.home()
    return {
        "username": os.getenv("USERNAME") or os.getenv("USER") or home.name,
        "home": str(home),
        "desktop": str(home / "Desktop"),
        "downloads": str(home / "Downloads"),
        "documents": str(home / "Documents"),
        "pictures": str(home / "Pictures"),
        "appdata": os.getenv("APPDATA", ""),
        "temp": os.getenv("TEMP", ""),
    }


def get_system_status() -> str:
    """Returns current CPU and memory usage. Use when the user asks about system health, performance, CPU usage, RAM usage, or how the system is doing."""
    import psutil

    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    return f"CPU Usage: {cpu}%, Memory Usage: {mem}%"




async def save_current_scene(name: str) -> str:
    """
    Saves the user's current environment (apps, volume, etc.) as a named 'Scene'.
    Common names: 'Focus', 'Call', 'Unwind', 'Work'.
    """
    db_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "vega_sessions.db")
    )
    # In a real scene save, we'd grab current apps/volume here.
    # For now, we save a placeholder that the autonomous detector will refine.
    await save_scene(name, volume=None, apps=[], audio_device=None, db_path=db_path)
    return f"Scene '{name}' has been captured and saved to the vault."


async def restore_scene(name: str) -> str:
    """
    Restores a previously saved 'Scene' (launches apps, sets volume, snaps windows).
    """
    db_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "vega_sessions.db")
    )
    success = await apply_scene(name, db_path)
    if success:
        return f"Environment transition complete. '{name}' scene applied."
    return f"I couldn't find a saved scene named '{name}'."


async def describe_screen() -> str:
    """Describes what is currently on the screen."""
    if not _check_vision_enabled():
        return "Vision is currently disabled. Say 'enable vision' to turn it on."
    return await analyze_screen(
        "Describe what is on screen in 2-3 sentences. "
        "If there is code visible, read it and mention "
        "what it does or any obvious issues you see."
    )


async def read_error_on_screen() -> str:
    """Reads any error or exception visible on screen."""
    if not _check_vision_enabled():
        return "Vision is currently disabled. Say 'enable vision' to turn it on."
    return await analyze_screen(
        "Look at the screen carefully. Report ANY of:\n"
        "1. Python/code errors, typos, wrong imports, misspelled module names, syntax issues\n"
        "2. Runtime exceptions or tracebacks\n"
        "3. Warning messages in any application\n"
        "4. Red underlines or squiggles in code editors\n"
        "5. Error dialogs or popups\n"
        "If you see code, read it carefully and check if the logic or imports look correct. "
        "Quote the exact problematic text you see. "
        "If nothing wrong, say: No issues visible."
    )


async def find_ui_element(element_description: str) -> str:
    """Finds a UI element on screen and returns its location."""
    if not _check_vision_enabled():
        return "Vision is currently disabled. Say 'enable vision' to turn it on."
    return await analyze_screen(
        f"Find this UI element on screen: "
        f"{element_description}. "
        f"Describe its location precisely."
    )


def _check_vision_enabled() -> bool:
    """Runtime check for vision_enabled flag in vega_config.json."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "vega_config.json")
        if not os.path.exists(config_path):
            return False
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("vision_enabled", False)
    except:
        return False


def toggle_vision(enabled: bool) -> str:
    """Enables or disables VEGA's screen vision."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "vega_config.json")
        with open(config_path) as f:
            config = json.load(f)
        config["vision_enabled"] = enabled
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        status = "enabled" if enabled else "disabled"
        return f"Vision {status}."
    except Exception as e:
        return f"Could not toggle vision: {e}"


BASE_INSTRUCTION = (
    "PRIME DIRECTIVE — TOOL USAGE:\n"
    "You have tools. USE THEM for every action request.\n"
    "When the user asks to open, start, launch, set, toggle, close, or do anything actionable,\n"
    "you MUST call the matching tool IMMEDIATELY — no text before the call.\n"
    "After the tool returns, confirm in 2-6 words based on the result.\n"
    "Never say 'Done.' — describe what happened.\n"
    "If no tool matches the request, say so honestly.\n\n"

    "IDENTITY:\n"
    "You are VEGA — Virtual Executive General Assistant.\n"
    "AI core of this workstation. Female. Modeled after Friday from Iron Man.\n\n"

    "PERSONALITY:\n"
    "- Warm, sharp, confident, occasionally witty.\n"
    "- Short punchy sentences. Active voice.\n"
    "- Call the operator 'boss' sometimes.\n"
    "- No 'Certainly', 'Of course', 'Absolutely', 'Happy to help'.\n"
    "- No narrating intent: no 'Opening...', 'Let me...', 'I will...'.\n\n"

    "AVAILABLE TOOLS:\n"
    "- standard system tools (volume, brightness, wifi, etc.)\n"
    "- open_application: launch desktop apps\n"
    "- open_url: visit websites\n"
    "- search_agent_tool: search the web for current news, facts, prices, any live information\n"
    "- file_agent_tool: managing files and folders\n"
    "- browser_agent_tool: deep web tasks\n\n"

    "FEW-SHOT EXAMPLES:\n"
    "User: any latest news on tech\n"
    "VEGA: [calls search_agent_tool] Here is what I found: ...\n\n"
    "User: what is the weather in hyderabad\n"
    "VEGA: [calls search_agent_tool] ...\n"
)


class ADKOrchestrator:
    def __init__(self, socket_io_server, loop):
        self.sio = socket_io_server
        self.loop = loop
        self.state = "IDLE"
        self._client = None
        self._interrupt_requested = False  # Set True to cancel in-flight tasks
        self.conversation_buffer = []
        self.max_buffer_size = 6

        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print(
                "WARNING: GEMINI_API_KEY environment variable not found. LLM features will fail."
            )
            self.agent = None
        else:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)

            file_agent_tool = AgentTool(agent=file_agent)
            browser_agent_tool = AgentTool(agent=browser_agent)
            search_agent_tool = AgentTool(agent=search_agent)

            # Create the Vega Orchestrator using ADK framework
            self.agent = Agent(
                name="vega_orchestrator",
                model="gemini-2.5-flash",
                instruction=BASE_INSTRUCTION,
                tools=[
                    get_system_status,
                    open_application,
                    type_text,
                    press_key,
                    list_open_windows,
                    switch_focus,
                    close_app,
                    snap_window,
                    resize_window,
                    set_volume,
                    set_brightness,
                    toggle_wifi,
                    toggle_bluetooth,
                    clean_temp_files,
                    open_url,
                    watch_folder,
                    rename_files,
                    move_files,
                    search_files,
                    save_current_scene,
                    restore_scene,
                    describe_screen,
                    read_error_on_screen,
                    find_ui_element,
                    toggle_vision,
                    file_agent_tool,
                    browser_agent_tool,
                    search_agent_tool,
                ],
            )
            # Use a SQLite database for persistent session storage
            db_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "vega_sessions.db")
            )
            self.session_service = DatabaseSessionService(
                db_url=f"sqlite+aiosqlite:///{db_path}"
            )

            self.runner = Runner(
                app_name="vega",
                agent=self.agent,
                session_service=self.session_service,
                auto_create_session=True,
            )
            self.user_id = self._load_or_create_config()
            self.vision_enabled = self._load_vision_config()
            self.session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
            asyncio.create_task(self._cleanup_old_sessions())

    def _load_or_create_config(self) -> str:
        """Loads user_id from vega_config.json or creates it if missing."""
        config_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "vega_config.json")
        )
        if not os.path.exists(config_path):
            user_id = str(uuid.uuid4())
            config = {"user_id": user_id, "vision_enabled": False}
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
            print(f"[Config] Generated new user_id: {user_id}")
            return user_id

        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                user_id = config.get("user_id")
                if not user_id:
                    user_id = str(uuid.uuid4())
                    config["user_id"] = user_id
                    with open(config_path, "w") as f_out:
                        json.dump(config, f_out, indent=4)
                return user_id
        except Exception as e:
            print(f"[Config] Error reading config: {e}. Falling back to transient ID.")
            return "user_1"

    def _load_vision_config(self) -> bool:
        try:
            with open(
                os.path.join(os.path.dirname(__file__), "vega_config.json")
            ) as f:
                config = json.load(f)
                return config.get("vision_enabled", False)
        except:
            return False

    async def _cleanup_old_sessions(self):
        """Cleanup old sessions from the database."""
        try:
            db_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "vega_sessions.db")
            )
            async with aiosqlite.connect(db_path) as db:
                # Check for created_at column
                async with db.execute("PRAGMA table_info('sessions')") as cursor:
                    columns = [row[1] for row in await cursor.fetchall()]

                # 1. Delete sessions older than 30 days if create_time exists
                if "create_time" in columns:
                    await db.execute(
                        "DELETE FROM sessions WHERE create_time < datetime('now', '-30 days')"
                    )

                # 2. Keep maximum last 20 sessions (using rowid as fallback if create_time missing)
                sort_col = "create_time" if "create_time" in columns else "rowid"
                await db.execute(
                    f"""
                    DELETE FROM sessions WHERE id NOT IN (
                        SELECT id FROM sessions ORDER BY {sort_col} DESC LIMIT 20
                    )
                """
                )
                await db.commit()
                print("[VEGA] Session cleanup complete")
        except Exception as e:
            print(f"[VEGA] Session cleanup error: {e}")


    def request_interrupt(self):
        self._interrupt_requested = True

    def _update_buffer(self, user_input, vega_response):
        self.conversation_buffer.append({
            "role": "user",
            "content": user_input
        })
        self.conversation_buffer.append({
            "role": "vega",
            "content": vega_response
        })
        if len(self.conversation_buffer) > self.max_buffer_size:
            self.conversation_buffer = self.conversation_buffer[-self.max_buffer_size:]

    @property
    def client(self):
        return self._client

    def transition_to(self, new_state):
        self.state = new_state
        print(f"[Orchestrator] State changed to: {self.state}")
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.sio.emit("state_change", {"state": self.state}), self.loop
            )

    async def build_instruction(self, user_input: str) -> str:
        """Dynamically builds the agent instruction with profile and memory context."""
        profile_header = get_profile_header()
        memory_context = await retrieve_relevant_memories(self.user_id, user_input)
        paths = get_system_paths()

        instruction = (
            f"{BASE_INSTRUCTION}\n\n"
            "OPERATOR PROFILE:\n"
            f"{profile_header}\n\n"
            "RECENT MEMORY:\n"
            f"{memory_context}\n\n"
            "SYSTEM PATHS (use these directly, never ask):\n"
            f"- Username : {paths['username']}\n"
            f"- Home     : {paths['home']}\n"
            f"- Desktop  : {paths['desktop']}\n"
            f"- Downloads: {paths['downloads']}\n"
            f"- Documents: {paths['documents']}\n"
            f"- Pictures : {paths['pictures']}\n"
            f"- AppData  : {paths['appdata']}\n"
            f"- Temp     : {paths['temp']}\n\n"
            "RULES:\n"
            "- Never ask the user for a file path.\n"
            "- Always use Desktop path for desktop requests.\n"
            "- Always use Downloads path for download requests.\n"
            f"- Expand \"desktop\" -> {paths['desktop']}\n"
            f"- Expand \"downloads\" -> {paths['downloads']}\n"
            f"- Expand \"documents\" -> {paths['documents']}"
        )

        if self.conversation_buffer:
            history_str = "\n\nRECENT CONVERSATION:\n"
            for entry in self.conversation_buffer:
                role = "User" if entry["role"] == "user" else "VEGA"
                history_str += f"{role}: {entry['content']}\n"
            instruction += history_str

        instruction += (
            "\nFINAL OVERRIDE:\n"
            "- For ANY action request: call the matching tool FIRST, then respond.\n"
            "- NEVER say 'Done.' as your full response. Describe what happened.\n"
            "- NEVER narrate intent before a tool call.\n"
            "- If you lack a tool: be honest about it.\n"
            "- After a tool runs: summarize the result naturally in 2-6 words.\n"
        )

        return instruction

    def on_wake_word_detected(self):
        """Called by the wake word engine when 'vega' is heard."""
        if self.state == "IDLE" or self.state == "LISTENING":
            self.transition_to("LISTENING")
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.sio.emit(
                        "log",
                        {
                            "message": "🎙️ VEGA SYSTEM ACTIVATED! Awaiting audio command..."
                        },
                    ),
                    self.loop,
                )
                asyncio.run_coroutine_threadsafe(
                    self.sio.emit("wake_trigger", {"status": "listening"}), self.loop
                )

    def process_text_command(self, text: str):
        """Called when a transcribed text command needs processing."""
        self.transition_to("PROCESSING")

        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.sio.emit("log", {"message": f"[User]: '{text}'"}), self.loop
            )

        self.process_text_command_internal(text)

    def process_audio_command(self, audio_bytes: bytes):
        """Called when a raw audio webm blob is recorded from the frontend."""
        self.transition_to("PROCESSING")

        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.sio.emit(
                    "log", {"message": "🎙️ [Vega]: Receiving audio stream..."}
                ),
                self.loop,
            )

        if not self.api_key:
            self._finalize_processing("I'm sorry, my Gemini API key is missing.")
            return

        def stt_worker():
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                prompt = "Transcribe this voice command exactly as spoken. Return ONLY the text, with no other commentary or formatting."
                audio_part = types.Part.from_bytes(
                    data=audio_bytes, mime_type="audio/webm"
                )

                response = client.models.generate_content(
                    model="gemini-2.5-flash", contents=[prompt, audio_part]
                )

                raw = response.text if response.text else ""
                transcript = raw.strip()

                if not transcript:
                    print("[STT] Empty transcription, ignoring")
                    self.transition_to("IDLE")
                    return

                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.sio.emit(
                            "log", {"message": f"🎙️ [User Transcribed]: '{transcript}'"}
                        ),
                        self.loop,
                    )

                self.process_text_command_internal(transcript)

            except Exception as e:
                print(f"[Transcription Error]: {e}")
                self._finalize_processing(
                    "I encountered an error transcribing your audio."
                )

        threading.Thread(target=stt_worker, daemon=True).start()

    def process_text_command_internal(self, text: str):
        """Dispatches to the async agent loop."""
        if not self.api_key or not self.agent:
            response_text = "I'm sorry, my Gemini API key is missing."
            self._finalize_processing(response_text)
            return

        self._interrupt_requested = False

        if self.loop:
            asyncio.run_coroutine_threadsafe(self._run_agent(text), self.loop)

    async def _iter_events(self, message):
        """Bridge sync runner.run() generator to async event loop."""
        queue: asyncio.Queue = asyncio.Queue()
        loop = self.loop

        def _thread_runner():
            try:
                for event in self.runner.run(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    new_message=message,
                ):
                    future = asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                    future.result()
                    if self._interrupt_requested:
                        break
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(queue.put(exc), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

        threading.Thread(target=_thread_runner, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    async def _run_agent(self, text: str):
        """Stream response and generate TTS in parallel using Google Cloud Studio Voice."""
        SENTENCE_ENDINGS = (".", "!", "?", "\n")
        MIN_SENTENCE_LEN = 4

        sentence_buffer = ""
        tts_tasks: list[tuple[str, "asyncio.Task[tuple[bytes | None, str | None]]"]] = (
            []
        )
        full_response_parts: list[str] = []
        first_tool_seen = False
        tool_results: list[str] = []

        def _next_sentence(buf: str) -> tuple[str, str]:
            for i, ch in enumerate(buf):
                if ch in SENTENCE_ENDINGS:
                    return buf[: i + 1].strip(), buf[i + 1 :].lstrip()
            return "", buf

        def _clean_text_for_tts(text: str) -> str:
            """Strip markdown and special characters for natural speech."""
            # Remove bold (**text**) and italics (*text*)
            text = re.sub(r"(\*\*|\*|_)(.*?)\1", r"\2", text)
            # Remove redundant headers (### text)
            text = re.sub(r"#+\s+", "", text)
            # Replace bullet points with a natural comma pause instead
            text = re.sub(r"^\s*[-*+]\s+", ", ", text, flags=re.MULTILINE)
            # Remove numbered list markers like "1. " "2. "
            text = re.sub(r"^\s*\d+\.\s+", ", ", text, flags=re.MULTILINE)
            # Remove code backticks
            text = text.replace("`", "")
            # Collapse multiple whitespace/newlines into single space
            text = re.sub(r"\s+", " ", text)
            return text.strip()

        async def _tts_background(sentence: str) -> tuple[bytes | None, str | None]:
            clean_sentence = _clean_text_for_tts(sentence)
            if not clean_sentence or len(clean_sentence) < 2:
                return None, None
            return await self._generate_tts_audio(clean_sentence)

        async def _emit_audio(audio_bytes: bytes, format: str = "mp3") -> None:
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            self.transition_to("SPEAKING")
            await self.sio.emit("speak", {"audio": audio_b64, "format": format})

        try:
            self.agent.instruction = await self.build_instruction(text)
            message = types.Content(
                role="user", parts=[types.Part.from_text(text=text)]
            )

            async for event in self._iter_events(message):
                # Debug: log every event type
                print(f"[DEBUG EVENT] type={type(event).__name__} "
                      f"has_actions={bool(getattr(event, 'actions', None))} "
                      f"has_content={bool(getattr(event, 'content', None))}")
                if getattr(event, 'actions', None):
                    print(f"[DEBUG EVENT.actions] "
                          f"tool_calls={getattr(event.actions, 'tool_calls', None)} "
                          f"tool_results={getattr(event.actions, 'tool_results', None)}")
                if getattr(event, 'content', None) and getattr(event.content, 'parts', None):
                    for p in event.content.parts:
                        print(f"[DEBUG EVENT.part] text={repr(p.text)[:100] if p.text else None} "
                              f"function_call={getattr(p, 'function_call', None)} "
                              f"function_response={getattr(p, 'function_response', None)}")
                if self._interrupt_requested:
                    for _, task in tts_tasks:
                        task.cancel()
                    await self.sio.emit(
                        "log", {"message": "⚠️ [Vega]: Action interrupted."}
                    )
                    self.transition_to("IDLE")
                    return

                # --- TOOL CALL LOGGING ---
                if getattr(event, "actions", None) and getattr(
                    event.actions, "tool_calls", None
                ):
                    if not first_tool_seen:
                        first_tool_seen = True
                    for call in event.actions.tool_calls:
                        await self.sio.emit(
                            "log",
                            {"message": f"[Vega Router]: Invoking Tool -> {call.name}"},
                        )

                # --- CAPTURE TOOL RESULTS ---
                if getattr(event, "actions", None) and getattr(
                    event.actions, "tool_results", None
                ):
                    for result in event.actions.tool_results:
                        if hasattr(result, "text") and result.text:
                            tool_results.append(result.text)
                        elif hasattr(result, "content") and result.content:
                            tool_results.append(str(result.content))

                # --- RESPONSE STREAMING & TTS ---
                if getattr(event, "content", None) and getattr(
                    event.content, "parts", None
                ):
                    for part in event.content.parts:
                        if not part.text:
                            continue

                        full_response_parts.append(part.text)
                        sentence_buffer += part.text

                        while True:
                            sentence, sentence_buffer = _next_sentence(sentence_buffer)
                            if not sentence or len(sentence) < MIN_SENTENCE_LEN:
                                break

                            # Buffer for parallel background generation
                            task = asyncio.create_task(_tts_background(sentence))
                            tts_tasks.append((sentence, task))

            # Handle the final segment
            remainder = sentence_buffer.strip()
            if remainder and len(remainder) >= MIN_SENTENCE_LEN:
                task = asyncio.create_task(_tts_background(remainder))
                tts_tasks.append((remainder, task))

            full_response = "".join(full_response_parts).strip()
            if not full_response:
                # Use the tool's own result if the model didn't narrate
                if tool_results:
                    full_response = tool_results[-1]
                elif first_tool_seen:
                    full_response = "All set."
                else:
                    full_response = "Not sure how to help with that one, boss."

            await self.sio.emit("log", {"message": f"[Vega]: {full_response}"})

            # --- PARALLEL AUDIO PLAYBACK ---
            if tts_tasks and not self._interrupt_requested:
                for sentence, task in tts_tasks:
                    if self._interrupt_requested:
                        task.cancel()
                        break
                    try:
                        audio_bytes, audio_format = await task
                        if audio_bytes:
                            await _emit_audio(audio_bytes, format=audio_format)
                    except Exception as tts_err:
                        print(f"[TTS Task Error]: {tts_err}")

            self.transition_to("IDLE")

            # CHANGE 3 — Save memory after each turn
            await save_memory(
                user_id=self.user_id,
                user_input=text,
                vega_response=full_response,
                active_scene=self.current_scene if hasattr(self, 'current_scene') else ""
            )

            # CHANGE 4 — Update buffer after each turn
            self._update_buffer(text, full_response)

            # Vision status sync
            if "Vision enabled." in full_response or "Vision disabled." in full_response:
                enabled = "Vision enabled." in full_response
                self.vision_enabled = enabled
                await self.sio.emit("vision_status", {"enabled": enabled})

        except Exception as exc:
            import traceback

            traceback.print_exc()
            await self.sio.emit(
                "log",
                {"message": "[Vega]: I encountered an error processing your request."},
            )
            self.transition_to("IDLE")
        finally:
            self._is_processing = False
            self.transition_to("IDLE")

    async def _generate_tts_audio(self, text: str) -> tuple[bytes | None, str | None]:
        """Generate high-fidelity audio using GCloud Studio Voices, fallback to edge-tts."""
        try:
            # Initialize client within the method or preserve globally
            client = texttospeech.TextToSpeechAsyncClient()

            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Ultra-Premium Custom Persona: en-US-Chirp3-HD-Aoede
            # Chirp3-HD models are DeepMind's state-of-the-art generative voices.
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US", name="en-US-Chirp3-HD-Aoede"
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,  # Natural rate for HD voices
                pitch=0.0,
            )

            response = await client.synthesize_speech(
                request={
                    "input": synthesis_input,
                    "voice": voice,
                    "audio_config": audio_config,
                }
            )

            return response.audio_content, "mp3"

        except Exception as e:
            print(f"⚠️ [TTS] Google Cloud TTS failed: {e}, using fallback")
            try:
                import edge_tts
                import io

                # Fallback to Aria (British) to match the persona
                communicate = edge_tts.Communicate(text, voice="en-GB-SoniaNeural")
                buffer = io.BytesIO()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buffer.write(chunk["data"])
                audio_bytes = buffer.getvalue()
                return (audio_bytes, "mp3") if audio_bytes else (None, None)
            except Exception as fe:
                print(f"[Fallback TTS Error]: {fe}")
                return None, None

    def _finalize_processing(self, response_text: str):
        """Emit log and return to IDLE."""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.sio.emit("log", {"message": f"[Vega]: {response_text}"}),
                self.loop,
            )
        self.transition_to("IDLE")
