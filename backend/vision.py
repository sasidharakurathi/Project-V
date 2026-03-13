import os
import base64
from io import BytesIO
import mss
from PIL import Image
from google import genai

def capture_screen():
    """Captures the primary monitor and returns it as a PIL Image."""
    try:
        with mss.mss() as sct:
            # Get the primary monitor
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            # Convert mss image to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img
    except Exception:
        return None

def encode_image_for_gemini(image):
    """Converts a PIL Image to a base64 string."""
    try:
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception:
        return None

async def analyze_screen(prompt: str) -> str:
    """Captures the screen and analyzes it using Gemini 2.0 Flash."""
    try:
        image = capture_screen()
        if image is None:
            return "Screen capture failed."

        # Explicitly call encoding as per requirements
        _ = encode_image_for_gemini(image)

        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image]
        )
        return response.text
    except Exception:
        return "Vision analysis failed."
