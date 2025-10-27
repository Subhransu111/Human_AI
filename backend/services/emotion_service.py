from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
import os
from typing import Optional


script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'nltk_data')
if os.path.isdir(data_dir):
    # Prepend the path to prioritize it, Vercel might have system NLTK paths
    if data_dir not in nltk.data.path:
        nltk.data.path.insert(0, data_dir) # Use insert(0, ...) instead of append
        print(f"NLTK data path added: {data_dir}")
    else:
        print(f"NLTK data path already configured: {data_dir}")
else:
    print(f"!!! WARNING: NLTK data directory not found at {data_dir}. Emotion analysis might fail.")

# --- Initialize Sentiment Analyzer ---
sia = None 
try:
    
    nltk.data.find('sentiment/vader_lexicon.zip')
    sia = SentimentIntensityAnalyzer()
    print("SentimentIntensityAnalyzer initialized successfully.")
except LookupError:
    print("!!! CRITICAL ERROR: vader_lexicon not found in NLTK data paths. Emotion analysis will not work.")
except Exception as e:
    print(f"!!! CRITICAL ERROR: Failed to initialize SentimentIntensityAnalyzer: {e}")


# --- Emotion Analysis Function ---
def analyze_emotion(text: str) -> dict:
    """Analyze emotion from text using VADER."""
    default_result = {'emotion': 'neutral', 'score': 0.0, 'confidence': 0.0}
    if not sia:
        print("!!! analyze_emotion: SentimentIntensityAnalyzer not available.")
        return default_result

    if not text: # Handle empty input gracefully
        print("!!! analyze_emotion: Received empty text.")
        return default_result

    print(f"Analyzing emotion for text: '{text[:50]}...'")
    try:
        scores = sia.polarity_scores(text)
        compound = scores['compound']

        # Determine emotion based on compound score
        if compound >= 0.5:
            emotion = "happy"
        elif compound >= 0.1:
            emotion = "positive"
        elif compound > -0.1: # Threshold for neutral
            emotion = "neutral"
        elif compound >= -0.5: # Threshold for sad
            emotion = "sad"
        else: # Everything else is angry/negative
            emotion = "angry"

        result = {
            'emotion': emotion,
            'score': round(compound, 2),
            # Simple confidence proxy: absolute difference between positive and negative scores
            'confidence': round(abs(scores.get('pos', 0.0) - scores.get('neg', 0.0)), 2)
        }
        print(f"Emotion analysis result: {result}")
        return result
    except Exception as e:
        print(f"!!! Error during emotion analysis: {e}")
        return default_result # Return default on any analysis error


# --- Murf AI Voice Selection Logic ---
def get_voice_for_emotion_and_language(emotion: str, language: str, message: str) -> Optional[str]:
    """Select Murf AI voice ID based on emotion and detected language."""
    print(f"Selecting voice for emotion='{emotion}', language='{language}'")

    voice_map_en = {
        'happy':    'en-IN-arohi',     
        'positive': 'en-IN-alia',   
        'neutral':  'en-IN-isha',   
        'sad':      'en-IN-priya',       
        'angry':    'en-IN-eashwar',      
    }
    voice_map_hi = {
        'happy':    'hi-IN-ayushi',      
        'positive': 'hi-IN-shweta',  
        'neutral':  'hi-IN-shweta',    
        'sad':      'hi-IN-shweta',        
        'angry':    'hi-IN-shweta',    
    }
    

    default_voice_en = voice_map_en.get('neutral', 'en-IN-isha') # Ensure 'neutral' key exists or provide a hardcoded valid ID
    default_voice_hi = voice_map_hi.get('neutral', 'hi-IN-shweta') # Ensure 'neutral' key exists or provide a hardcoded valid ID
    # default_voice_or = voice_map_or.get('neutral', 'murf_or_fallback_id') # If Odia exists

    selected_map = {}
    default_voice = default_voice_en # Default to English overall if language unknown

    # Select the correct map based on language code
    lang_code_lower = language.lower() if language else 'en' # Handle None language, default to 'en'

    if lang_code_lower.startswith('hi'): # Match 'hi' or 'hi-IN' etc.
        print("Using Hindi voice map.")
        selected_map = voice_map_hi
        default_voice = default_voice_hi
    elif lang_code_lower.startswith('or'):
        # selected_map = voice_map_or # If Odia exists
        # default_voice = default_voice_or
        print(f"Warning: Odia ('or') detected, but no specific Odia voice map defined. Falling back to English.")
        selected_map = voice_map_en # Fallback to English for now
        default_voice = default_voice_en
    else: # Default to English for 'en' or any other unrecognized code
        print(f"Using English voice map (language: '{lang_code_lower}').")
        selected_map = voice_map_en
        default_voice = default_voice_en

    # Basic scolding logic (can be refined) - Currently only overrides for English/Hindi examples
    scold_keywords = ['repeated', 'again', 'pattern', 'notice', 'tendency', 'keep doing']
    is_scolding = any(keyword in message.lower() for keyword in scold_keywords if message) # Check if message exists

    voice_id = selected_map.get(emotion)

    # Example override for scolding (adjust voice IDs as needed)
    if is_scolding and emotion in ['sad', 'angry']:
        print("Scolding detected, attempting to override voice.")
        if lang_code_lower.startswith('hi'):
            # Use a specific calm/assertive Hindi voice if available, otherwise fallback
            voice_id = voice_map_hi.get('neutral', default_voice_hi) # Example: fallback to neutral Hindi
            print("Overriding with Hindi neutral/calm voice.")
        else: # Default to English scolding voice (or neutral)
             voice_id = voice_map_en.get('neutral', default_voice_en) # Example: fallback to neutral English
             print("Overriding with English neutral/calm voice.")

    # Fallback if specific emotion voice not found in the selected map
    if not voice_id:
        print(f"Voice for emotion '{emotion}' not found in map for language '{lang_code_lower}'. Using default.")
        voice_id = default_voice

    # Final check: Ensure we have a valid voice ID string before returning
    if not voice_id or not isinstance(voice_id, str) or 'placeholder' in voice_id or 'replace' in voice_id.lower():
        print(f"!!! ERROR: Could not determine a valid voice ID. Default was '{default_voice}'. Final result was '{voice_id}'. Check placeholder IDs.")
        # Return None to indicate TTS failure upstream.
        return None

    print(f"Selected Murf AI Voice ID: {voice_id}")
    return voice_id