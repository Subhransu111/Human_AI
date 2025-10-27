import assemblyai as aai
import os
from dotenv import load_dotenv
from typing import Tuple, Optional

load_dotenv()
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

# Return a tuple
async def process_audio(audio_data: bytes) -> Tuple[Optional[str], str]:
    """
    Transcribe audio using AssemblyAI with language detection.
    Returns a tuple containing the transcript text (or None on error)
    and the detected language code (defaulting to 'en').
    """
    if not aai.settings.api_key:
        print("!!! AssemblyAI API Key not set.")
        return None, "en" 

    try:
        
        config = aai.TranscriptionConfig(language_detection=True)
        transcriber = aai.Transcriber(config=config)

        print("Sending audio to AssemblyAI for transcription...")
        transcript = transcriber.transcribe(audio_data)

        if transcript.status == aai.TranscriptStatus.error:
            print(f"!!! AssemblyAI Transcription error: {transcript.error}")
            return None, "en" 

        # 2. Get detected language (default to 'en' if detection fails)
        detected_language = transcript.language_code or "en"
        print(f"AssemblyAI Transcription successful. Text: '{transcript.text[:50]}...', Detected Lang: '{detected_language}'")

        # 3. Return BOTH text and language code
        return transcript.text, detected_language

    except Exception as e:
        print(f"!!! Unexpected error during AssemblyAI transcription: {e}")
        import traceback
        traceback.print_exc()
        return None, "en" # Return None for text, default lang on unexpected errors