from elevenlabs.client import ElevenLabs
from elevenlabs import play
import os

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

audio = client.generate(
    text="Hello there! This is a quick voice test from ElevenLabs.",
    voice="Sarah",
    model="eleven_monolingual_v1"
)

play(audio)

