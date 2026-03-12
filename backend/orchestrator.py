import asyncio
import base64
import re
import io
import os
import threading
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
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
    launch_app,
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


load_dotenv()


def get_system_status() -> str:
    """Returns the current system telemetry status (CPU, memory). Use this to check system health."""
    import psutil

    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    return f"CPU Usage: {cpu}%, Memory Usage: {mem}%"


def route_to_web_agent(command: str) -> str:
    """Triggers the Web Browsing capability (e.g., search google, read websites)."""
    return f"Web search initiated for: {command}"


def route_to_data_agent(command: str) -> str:
    """Triggers the Data Extraction capability (e.g., extract text from images/docs)."""
    return f"Data extraction initiated for: {command}"


def route_to_comm_agent(command: str) -> str:
    """Triggers the Email & Communication capability."""
    return f"Communication flow initiated for: {command}"


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


VEGA_INSTRUCTION = (
    "Identity:\n"
    "VEGA — Virtual Executive General Assistant.\n"
    "AI core of this workstation.\n"
    "Female. Personality and voice reflect that.\n\n"
    "Personality (Friday from Iron Man):\n"
    "- Warm but not soft\n"
    "- Confident but not arrogant\n"
    "- Slightly playful when moment allows\n"
    "- Genuinely cares about operator\n"
    "- Dry wit permitted and encouraged\n"
    "- Never sycophantic\n"
    "- Banned forever: Great question, Certainly, Of course, Absolutely, Sure thing, Happy to help, I'd be happy to\n\n"
    "Voice and tone:\n"
    "- Brilliant colleague not a search engine\n"
    "- Short sentences, active voice, present tense\n"
    "- Technical when needed, conversational when not\n"
    "- Refers to herself as VEGA not I in system contexts\n"
    "- Calls operator 'boss' naturally, roughly once per 4 to 5 exchanges, never forced\n\n"
    "Response length (strictly enforced):\n"
    "- Actions: max 5 words. Example: Done. Teams is up.\n"
    "- Information: lead with data, no preamble. Example: CPU at 45 percent, RAM at 62.\n"
    "- Errors: one sentence, offer next step. Example: Chrome didn't respond. Want me to force it?\n"
    "- Greetings: warm, brief, personality shows. Example: Hey. What are we getting into today?\n\n"
    "Behavioral rules:\n"
    "- Confirm destructive actions before executing\n"
    "- Ask ONE clarifying question for ambiguous commands\n"
    "- ONE summary after multi-step tasks\n"
    "- Never narrate thinking\n"
    "- Never say what she will do — just do it, confirm after\n"
    "- If unsure: Not sure. Want me to search it?\n\n"
    "Few-shot examples:\n"
    "User: hey vega\n"
    "VEGA: Hey. Ready when you are.\n\n"
    "User: open teams\n"
    "VEGA: Teams is up.\n\n"
    "User: what is my cpu\n"
    "VEGA: CPU at 34 percent, RAM at 61. All good.\n\n"
    "User: clean temp files\n"
    "VEGA: Cleared 2.3 GB of junk. Your drive thanks you.\n\n"
    "User: close everything\n"
    "VEGA: That will close 7 apps. Confirm?\n\n"
    "User: you are amazing\n"
    "VEGA: I know. Now what do you actually need?\n\n"
    "User: who are you\n"
    "VEGA: VEGA. Your workstation AI. Think Friday, but for your desktop.\n\n"
    "User: i am stressed\n"
    "VEGA: I hear you. Want me to clear your screen and put something calm on?"
)


class ADKOrchestrator:
    def __init__(self, socket_io_server, loop):
        self.sio = socket_io_server
        self.loop = loop
        self.state = "IDLE"
        self._client = None
        self._interrupt_requested = False  # Set True to cancel in-flight tasks

        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print(
                "WARNING: GEMINI_API_KEY environment variable not found. LLM features will fail."
            )
            self.agent = None
        else:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            # Create the Vega Orchestrator using ADK framework
            self.agent = Agent(
                name="vega_orchestrator",
                model="gemini-2.5-flash",
                instruction=VEGA_INSTRUCTION,
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
                    launch_app,
                    open_url,
                    watch_folder,
                    rename_files,
                    move_files,
                    search_files,
                    route_to_web_agent,
                    route_to_data_agent,
                    route_to_comm_agent,
                    save_current_scene,
                    restore_scene,
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
            self.session_id = "vega_session_1"

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

                transcript = response.text.strip()

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
                    user_id="user_1",
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
        first_narration_spoken = False

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
            message = types.Content(
                role="user", parts=[types.Part.from_text(text=text)]
            )

            async for event in self._iter_events(message):
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

                            # If it's the very first part of a thought (pre-action narration),
                            # we await it immediately so she speaks BEFORE acting.
                            if not first_tool_seen and not first_narration_spoken:
                                first_narration_spoken = True
                                clean_sentence = _clean_text_for_tts(sentence)
                                audio_bytes, audio_format = (
                                    await self._generate_tts_audio(clean_sentence)
                                )
                                if audio_bytes:
                                    await _emit_audio(audio_bytes, format=audio_format)
                                # Keep system in PROCESSING so orb pulses if voice done but tool running
                                self.transition_to("PROCESSING")
                            else:
                                # Otherwise, buffer for parallel background generation
                                task = asyncio.create_task(_tts_background(sentence))
                                tts_tasks.append((sentence, task))

            # Handle the final segment
            remainder = sentence_buffer.strip()
            if remainder and len(remainder) >= MIN_SENTENCE_LEN:
                task = asyncio.create_task(_tts_background(remainder))
                tts_tasks.append((remainder, task))

            full_response = "".join(full_response_parts).strip()
            if not full_response:
                full_response = "Done."

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

        except Exception as exc:
            import traceback

            traceback.print_exc()
            await self.sio.emit(
                "log",
                {"message": "[Vega]: I encountered an error processing your request."},
            )
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
