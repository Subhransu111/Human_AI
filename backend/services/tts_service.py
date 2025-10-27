import requests
import os
import base64
from dotenv import load_dotenv
import traceback 
from typing import Optional 

load_dotenv()
MURF_API_KEY = os.getenv("MURF_API_KEY")
MURF_API_URL = "https://api.murf.ai/v1/speech/generate"

async def text_to_speech(text: str, voice_id: Optional[str]) -> Optional[str]:
    """Convert text to speech using Murf AI REST API and return base64 encoded MP3 audio"""
    if not MURF_API_KEY:
        print("!!! MURF_API_KEY environment variable not set.")
        return None
    if not voice_id:
        print("!!! No Murf AI voice_id provided.")
        return None
    if not text:
        print("!!! Empty text provided for TTS.")
        return None

    headers = {
        "Authorization": f"Bearer {MURF_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "text": text,
        "voiceId": voice_id,
        "format": "MP3",        
        "sampleRate": 24000     
        
    }
    print(f"Sending TTS request to Murf AI ({MURF_API_URL}) with voice ID: {voice_id}")

    try:
        response = requests.post(MURF_API_URL, headers=headers, json=payload)
        response.raise_for_status() 
        response_data = response.json()
        audio_url = response_data.get("audioFile") 

        if audio_url:
            print(f"Fetching generated audio from Murf URL: {audio_url}")
            audio_response = requests.get(audio_url)
            audio_response.raise_for_status()

         
            content_type = audio_response.headers.get("Content-Type", "").lower()
            print(f"Downloaded audio content type: {content_type}")
            if "audio" not in content_type:
                 print(f"!!! Warning: Downloaded file might not be audio. URL: {audio_url}")
                 

            audio_bytes = audio_response.content
            if not audio_bytes:
                 print("!!! Fetched audio file is empty.")
                 return None

            
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            print(f"Successfully fetched and encoded Murf AI audio ({len(audio_bytes)} bytes).")
            return audio_base64
        else:
            print(f"!!! Murf AI response did not contain 'audioFile' URL: {response_data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"!!! Error calling Murf AI API or fetching audio: {e}")
        if e.response is not None:
             print(f"!!! Murf AI Error Response: {e.response.status_code} - {e.response.text[:500]}") # Log more details
        return None
    except Exception as e:
        print(f"!!! Unexpected error during Murf AI TTS: {e}")
        traceback.print_exc()
        return None