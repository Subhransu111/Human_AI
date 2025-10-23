from nltk.sentiment import SentimentIntensityAnalyzer
import nltk

try:
    nltk.data.find('vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')

sia = SentimentIntensityAnalyzer()

def analyze_emotion(text: str) -> dict:
    """Analyze emotion from text"""
    scores = sia.polarity_scores(text)
    compound = scores['compound']
    
    if compound >= 0.5:
        emotion = "happy"
    elif compound >= 0.1:
        emotion = "positive"
    elif compound > -0.1:
        emotion = "neutral"
    elif compound >= -0.5:
        emotion = "sad"
    else:
        emotion = "angry"
    
    return {
        'emotion': emotion,
        'score': round(compound, 2),
        'confidence': round(scores['pos'] + scores['neg'], 2)
    }

def get_voice_for_emotion(emotion: str, message: str) -> str:
    """Select ElevenLabs voice based on emotion"""
    scold_keywords = ['repeated', 'again', 'pattern', 'notice', 'tendency']
    is_scolding = any(keyword in message.lower() for keyword in scold_keywords)
    
    voice_map = {
        'happy': 'EXAVITQu4vr4xnSDxMaL',
        'positive': 'EXAVITQu4vr4xnSDxMaL',
        'neutral': 'pNInz6obpgDQGcFmaJgB',
        'sad': 'EXAVITQu4vr4xnSDxMaL',
        'angry': 'pNInz6obpgDQGcFmaJgB'
    }
    
    if is_scolding and emotion in ['sad', 'angry']:
        return 'EXAVITQu4vr4xnSDxMaL'
    
    return voice_map.get(emotion, 'EXAVITQu4vr4xnSDxMaL')
