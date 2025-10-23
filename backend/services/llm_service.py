import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def generate_response(user_message: str, context: dict) -> str:
    """Generate context-aware response"""
    emotion = context['current_emotion']
    history = context['history']
    
    repeated_issues = detect_repeated_patterns(history, emotion)
    system_prompt = build_system_prompt(emotion, repeated_issues, history)
    
    response = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        model="llama-3.1-8b-instant",
        max_tokens=200,
        temperature=0.8
    )
    
    return response.choices[0].message.content

def detect_repeated_patterns(history: list, current_emotion: str) -> list:
    """Detect if user is repeating same emotional issue"""
    repeated = []
    
    if len(history) < 3:
        return repeated
    
    recent = history[:10]
    emotion_counts = {}
    
    for conv in recent:
        emotion = conv['emotion']
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    if emotion_counts.get(current_emotion, 0) >= 3:
        repeated.append({
            'type': 'repeated_emotion',
            'emotion': current_emotion,
            'count': emotion_counts[current_emotion]
        })
    
    return repeated

def build_system_prompt(emotion: str, repeated_issues: list, history: list) -> str:
    """Build context-aware system prompt"""
    base_prompt = """You are a compassionate AI companion who provides emotional support with genuine care.
You remember the user's history and emotional patterns. 
Keep responses concise (2-3 sentences max) and natural.
Sound like a caring friend, not a robot."""
    
    emotion_guides = {
        'happy': "The user is happy! Celebrate with them.",
        'positive': "The user is in a good mood. Be upbeat.",
        'neutral': "The user seems neutral. Be balanced.",
        'sad': "The user is sad. Be deeply empathetic and comforting.",
        'angry': "The user is frustrated. Be calm and understanding."
    }
    
    prompt = base_prompt + "\n\n" + emotion_guides.get(emotion, "Be empathetic")
    
    if repeated_issues:
        for issue in repeated_issues:
            if issue['type'] == 'repeated_emotion':
                prompt += f"\n\nThe user has been feeling {issue['emotion']} frequently ({issue['count']} times). "
                prompt += "Gently acknowledge this pattern with care, but also encourage positive changes. "
                prompt += "Be loving but honest - sometimes people need a gentle nudge."
    
    if history:
        prompt += f"\n\nUser's recent emotions: "
        prompt += ", ".join([h['emotion'] for h in history[:5]])
    
    return prompt
