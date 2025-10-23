import assemblyai as aai
import os
from dotenv import load_dotenv

load_dotenv()
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

async def process_audio(audio_data: bytes) -> str:
    """Transcribe audio using AssemblyAI"""
    try:
        with open("temp_audio.wav", "wb") as f:
            f.write(audio_data)
        
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe("temp_audio.wav")
        
        os.remove("temp_audio.wav")
        
        return transcript.text
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""
