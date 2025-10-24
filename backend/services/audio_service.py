import assemblyai as aai
import os
from dotenv import load_dotenv

load_dotenv()
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

async def process_audio(audio_data: bytes) -> str:
    """Transcribe audio using AssemblyAI"""
    try:
        # We don't need to save a file.
        # We can pass the raw audio data directly.
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)

        if transcript.status == aai.TranscriptStatus.error:
            print(f"Transcription error: {transcript.error}")
            return ""

        return transcript.text

    except Exception as e:
        
        print(f"Transcription error: {e}")
        return ""
