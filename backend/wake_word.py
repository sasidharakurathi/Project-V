import os
import threading
import time
import numpy as np
import requests
import sounddevice as sd
from openwakeword.model import Model


class WakeWordEngine:
    """
    WakeWordEngine using the openWakeWord library to detect wake words in real-time.
    """

    def __init__(self, wake_word="vega", threshold=0.7):
        """
        Initializes the wake word engine.
        :param wake_word: The name of the wake word model (default "vega").
        :param threshold: Confidence threshold for wake word detection (default 0.7).
        """
        self.wake_word = wake_word
        self.threshold = threshold
        
        # Ensure required resource models exist
        self._ensure_models_exist()
        
        # Load the custom vega model (ONNX version for Windows compatibility)
        model_path = os.path.join(
            os.path.dirname(__file__),
            "my_custom_model", "vega", "vega.onnx"
        )
        
        try:
            self.model = Model(
                wakeword_models=[model_path],
                inference_framework="onnx"
            )
            print(f"Successfully loaded custom model: {model_path}")
        except Exception as e:
            print(f"Error loading custom model {model_path}: {e}")
            print("Attempting to load default openwakeword models instead...")
            try:
                self.model = Model(inference_framework="onnx")
            except Exception as e2:
                print(f"Error loading fallback models: {e2}")
                self.model = None
        self.is_running = False
        self.thread = None
        self.callback = None
        self.samplerate = 16000  # openWakeWord models are trained on 16kHz audio
        self.last_detection_time = 0
        self.cooldown_period = 2.0  # seconds

    def _ensure_models_exist(self):
        """
        Checks if required ONNX models exist and downloads them if missing.
        """
        import openwakeword
        model_dir = os.path.join(os.path.dirname(openwakeword.__file__), 'resources', 'models')
        os.makedirs(model_dir, exist_ok=True)

        required_files = [
            'embedding_model.onnx',
            'melspectrogram.onnx',
            'alexa_v0.1.onnx',
        ]

        base_url = 'https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/'

        for f_name in required_files:
            target_path = os.path.join(model_dir, f_name)
            if not os.path.exists(target_path):
                print(f"[WakeWordEngine] Missing resource model: {f_name}. Downloading...")
                try:
                    response = requests.get(base_url + f_name, stream=True, timeout=30)
                    response.raise_for_status()
                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"[WakeWordEngine] Successfully downloaded: {f_name}")
                except Exception as e:
                    print(f"[WakeWordEngine] Error downloading {f_name}: {e}")
            else:
                # Silently continue if it exists
                pass

    def start(self, callback):
        """
        Starts the wake word engine in a separate daemon thread.
        :param callback: A function to call when the wake word is detected (no arguments).
        """
        if self.is_running:
            return

        self.callback = callback
        self.is_running = True
        self.thread = threading.Thread(target=self._run_engine, daemon=True)
        self.thread.start()
        print(
            f"--- Wake-Word Engine Active. Listening for '{self.wake_word}' (threshold: {self.threshold}) ---"
        )

    def stop(self):
        """
        Stops the wake word engine.
        """
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("--- Wake-Word Engine Stopped ---")

    def _run_engine(self):
        """
        Internal loop to capture audio and perform wake word detection.
        """
        # openWakeWord expects audio chunks of a specific size (usually 1280 samples for 80ms)
        chunk_size = 1280

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"Audio Status: {status}")

            # Record current audio in the model's buffer
            # indata is (chunk_size, channels), we want (chunk_size,)
            audio_chunk = indata[:, 0].astype(np.float32)

            # Get predictions
            if self.model is None:
                return
            prediction = self.model.predict(audio_chunk)

            # Log prediction dict for key verification (as requested)
            if any(score > self.threshold for score in prediction.values()):
                print(f"Debug: Wake word scores: {prediction}")

            # Check for cooldown
            current_time = time.time()
            if current_time - self.last_detection_time < self.cooldown_period:
                return

            # Check if any wake word confidence exceeds threshold
            for mdl in prediction:
                score = prediction[mdl]
                if score >= self.threshold:
                    print(
                        f"\n🌟 WAKE WORD DETECTED: {mdl.upper()} (Score: {score:.2f})! 🌟\n"
                    )
                    self.last_detection_time = current_time
                    if self.callback:
                        self.callback()

        try:
            with sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                blocksize=chunk_size,
                dtype="float32",
                callback=audio_callback,
            ):
                while self.is_running:
                    sd.sleep(100)
        except Exception as e:
            print(f"Error in WakeWordEngine stream: {e}")
            self.is_running = False


if __name__ == "__main__":
    # Test block for manual verification

    engine = WakeWordEngine(wake_word="vega", threshold=0.7)

    def on_wake():
        print(">> Wake word detected! Triggering callback...")

    engine.start(on_wake)

    try:
        print("Engine is running. Say 'Vega' to test. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()
        print("Test stopped.")
