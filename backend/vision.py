import os
import io
import mss
from PIL import Image
from google import genai
from google.genai import types

def capture_screen():
    """Captures the primary monitor and returns it as a PIL Image."""
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img
    except Exception:
        return None

async def analyze_screen(prompt: str) -> str:
    """Captures, compresses, and analyzes the screen using Gemini 2.5 Flash."""
    try:
        img = capture_screen()
        if img is None:
            return "Screen capture failed."

        # Resize if wider than 1280
        if img.width > 1280:
            ratio = 1280 / img.width
            new_h = int(img.height * ratio)
            img = img.resize((1280, new_h), Image.LANCZOS)

        # Convert to compressed JPEG in memory
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=60)
        image_bytes = buffer.getvalue()

        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ]
        )
        return response.text
    except Exception as e:
        print(f"[Vision Error]: {e}")
        return "Vision analysis failed."
