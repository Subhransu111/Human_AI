import assemblyai as aai
import os
from dotenv import load_dotenv
from typing import Tuple, Optional
import traceback # Import traceback for better error logging

load_dotenv()
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

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
        # Enable Language Detection in config
        config = aai.TranscriptionConfig(language_detection=True)
        transcriber = aai.Transcriber(config=config)

        print("Sending audio to AssemblyAI for transcription...")
        transcript = transcriber.transcribe(audio_data)

        if transcript.status == aai.TranscriptStatus.error:
            print(f"!!! AssemblyAI Transcription error: {transcript.error}")
            return None, "en" # Return None for text, default lang

        # --- CORRECTED LANGUAGE CODE ACCESS ---
        # Check if language detection ran and produced a result
        # The result might be in transcript.config.language_code or transcript.language_code
        # We'll check both and default to 'en'

        detected_language = "en" # Default
        if hasattr(transcript, 'language_code') and transcript.language_code:
            detected_language = transcript.language_code
            print(f"Detected language via transcript.language_code: '{detected_language}'")
        elif hasattr(transcript, 'config') and hasattr(transcript.config, 'language_code') and transcript.config.language_code:
            # Fallback check, might be populated here in some SDK versions/scenarios
            detected_language = transcript.config.language_code
            print(f"Detected language via transcript.config.language_code: '{detected_language}'")
        else:
             print(f"!!! Language code not found directly on transcript or config. Defaulting to 'en'. Transcript status: {transcript.status}")
             # You might want to inspect the transcript object here if detection fails often
             # print(vars(transcript)) # DEBUG: See all attributes of the transcript object

        print(f"AssemblyAI Transcription successful. Text: '{transcript.text[:50]}...'")

        # Return BOTH text and language code
        return transcript.text, detected_language

    except AttributeError as ae:
        # Catch the specific error we saw before, helps pinpoint if the structure changed
        print(f"!!! AttributeError during AssemblyAI processing: {ae}. The Transcript object structure might have changed.")
        traceback.print_exc()
        return None, "en"
    except Exception as e:
        print(f"!!! Unexpected error during AssemblyAI transcription: {e}")
        traceback.print_exc()
        return None, "en"