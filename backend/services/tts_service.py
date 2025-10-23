from elevenlabs.client import ElevenLabs
import os
import base64
from dotenv import load_dotenv

load_dotenv()
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

async def text_to_speech(text: str, voice_id: str) -> str:
    """Convert text to speech and return base64 encoded audio"""
    try:
        audio = elevenlabs_client.text_to_speech.convert(
            text=text,
            voice_id=voice_id
        )
        
        audio_bytes = b''.join(audio)
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        return audio_base64
    except Exception as e:
        print(f"TTS error: {e}")
        return ""
