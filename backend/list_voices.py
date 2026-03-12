from google.cloud import texttospeech
import os
from dotenv import load_dotenv

load_dotenv()

def list_all_voices():
    client = texttospeech.TextToSpeechClient()
    voices = client.list_voices().voices
    
    print(f"{'Voice name':<40} | {'Gender':<10}")
    print("-" * 55)
    for voice in voices:
        if "en-US" in voice.name and "Chirp3" in voice.name:
            gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name
            print(f"{voice.name:<40} | {gender:<10}")

if __name__ == "__main__":
    list_all_voices()
