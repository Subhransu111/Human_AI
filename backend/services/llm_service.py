import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def generate_response(user_message: str, detected_language: str, context: dict) -> str:
    """Generate context-aware response using Groq, instructing language."""

    if not groq_client.api_key:
        print("!!! Groq API Key not configured. Cannot generate response.")
        return "Sorry, I cannot process your request right now due to a configuration issue."

    emotion = context.get('current_emotion', 'neutral')
    history = context.get('history', [])
    repeated_issues = detect_repeated_patterns(history, emotion) # Assuming this function exists

    # --- 2. CREATE LANGUAGE INSTRUCTION ---
    language_map = {'en': 'English', 'hi': 'Hindi', 'or': 'Odia'}
    language_name = language_map.get(detected_language, 'English') # Default to English
    language_instruction = f"Respond concisely (2-3 sentences max) in {language_name}."

    system_prompt = build_system_prompt(emotion, repeated_issues, history, language_instruction)

    print(f"Generating Groq response. Language: {language_name}. System Prompt: '{system_prompt[:100]}...'")
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model="llama-3.1-8b-instant", # Or your preferred model
            max_tokens=200,
            temperature=0.8
        )

        response_content = response.choices[0].message.content
        print(f"Groq response received: '{response_content[:100]}...'")
        return response_content

    except Exception as e:
        print(f"!!! Error calling Groq API: {e}")
        # Return a user-friendly error message
        return f"Sorry, I encountered an error trying to generate a response in {language_name}."


# --- detect_repeated_patterns FUNCTION (Unchanged) ---
def detect_repeated_patterns(history: list, current_emotion: str) -> list:
    """Detect if user is repeating same emotional issue (example implementation)."""
    # ... (Keep your existing logic here) ...
    repeated = []
    if len(history) < 3: return repeated
    recent = history[:10]
    emotion_counts = {}
    for conv in recent:
        emo = conv.get('emotion') # Safely get emotion
        if emo: emotion_counts[emo] = emotion_counts.get(emo, 0) + 1
    if emotion_counts.get(current_emotion, 0) >= 3:
        repeated.append({'type': 'repeated_emotion', 'emotion': current_emotion, 'count': emotion_counts[current_emotion]})
    return repeated


# --- 4. MODIFY build_system_prompt FUNCTION SIGNATURE ---
def build_system_prompt(emotion: str, repeated_issues: list, history: list, language_instruction: str) -> str:
    """Build context-aware system prompt, including language instruction."""
    base_prompt = """You are a compassionate AI companion providing emotional support.
Remember user history and emotional patterns. Keep responses concise and natural.
Sound like a caring friend, not a robot."""

    emotion_guides = {
        'happy': "User is happy! Celebrate.",
        'positive': "User is positive. Be upbeat.",
        'neutral': "User seems neutral. Be balanced.",
        'sad': "User is sad. Be deeply empathetic.",
        'angry': "User is frustrated. Be calm and understanding."
    }

    prompt = base_prompt + "\n\n" + language_instruction
    prompt += "\n" + emotion_guides.get(emotion, "Be empathetic.")

    if repeated_issues:
        for issue in repeated_issues:
            if issue['type'] == 'repeated_emotion':
                prompt += f"\nNote: The user has been feeling {issue['emotion']} frequently ({issue['count']} recent times). Gently acknowledge this pattern, but also encourage positive changes with care."

    return prompt