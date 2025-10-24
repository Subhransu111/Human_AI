# ============================================
# backend/main.py - FINAL VERSION FOR VERCEL
# ============================================

# --- Core FastAPI & Dependencies ---
from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile,
    File, Header, Request # Removed Form, Added Request
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse # For potential future custom error handling
from typing import Optional, List, Dict # For type hinting

# --- Database (SQLAlchemy) ---
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Float
# Use declarative_base from sqlalchemy.orm in modern SQLAlchemy
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from datetime import datetime

# --- Authentication (JOSE for JWT) ---
from jose import jwt, JWTError
from urllib.request import urlopen
import json
from functools import lru_cache

# --- Standard Libraries & Environment ---
import os
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict # Updated for Pydantic v2
import traceback # For detailed error logging

# --- Load Environment Variables ---
# Loads .env locally, Vercel uses its own environment variables
load_dotenv()

# --- Auth0 Configuration ---
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
# IMPORTANT: Set FRONTEND_URL in Vercel backend project settings
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173") # Default for local

# --- Database Setup ---
DATABASE_URL = os.getenv("DATABASE_URL") # Rely on Vercel to provide this for Neon/Postgres
if not DATABASE_URL:
    print("!!! WARNING: DATABASE_URL not found. Using local SQLite.")
    DATABASE_URL = "sqlite:///./ai_companion.db" # Fallback for local

connect_args = {}
# Only add check_same_thread for SQLite
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    print("Using SQLite database.")
else:
    print("Using PostgreSQL database (presumably).")

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print("Database engine and session created.")
except Exception as e:
    print(f"!!! CRITICAL: Failed to create database engine: {e}")
    # Consider exiting if DB connection fails on startup
    engine = None
    SessionLocal = None
    Base = object # Use a dummy object if Base couldn't be created

# --- Database Models ---
if Base is not object: # Only define models if Base was created
    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True, index=True)
        auth0_id = Column(String, unique=True, index=True, nullable=False)
        email = Column(String, unique=True, index=True, nullable=True)
        name = Column(String, nullable=True)
        picture = Column(String, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class Conversation(Base):
        __tablename__ = "conversations"
        id = Column(Integer, primary_key=True, index=True)
        user_id = Column(Integer, index=True) # Add index for faster lookups
        user_message = Column(Text, nullable=True)
        assistant_message = Column(Text, nullable=True)
        emotion = Column(String, nullable=True)
        emotion_score = Column(Float, nullable=True)
        voice_used = Column(String, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow, index=True) # Index for sorting

    # --- Create Tables ---
    try:
        print("Attempting to create database tables...")
        Base.metadata.create_all(bind=engine)
        print("Database tables created/checked successfully.")
    except Exception as e:
        print(f"!!! WARNING: Error creating database tables: {e}")
        # App might still run but DB operations will fail
else:
    print("!!! Skipping model definition due to database engine failure.")
    User = None
    Conversation = None

# --- Pydantic Schemas (for API responses) ---
class UserResponse(BaseModel):
    id: int
    auth0_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    picture: Optional[str] = None

    # Pydantic v2 configuration
    model_config = ConfigDict(from_attributes=True)

class Message(BaseModel):
    type: str
    text: Optional[str] = None
    emotion: Optional[str] = None
    timestamp: Optional[datetime] = None # Use datetime for consistency

class HistoryResponse(BaseModel):
    messages: List[Message]

# --- Auth0 JWKS Fetching ---
@lru_cache(maxsize=1)
def get_auth0_public_key():
    if not AUTH0_DOMAIN:
        print("!!! AUTH0_DOMAIN environment variable not set. Cannot fetch JWKS.")
        return None
    jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
    print(f"Fetching JWKS keys from: {jwks_url}")
    try:
        with urlopen(jwks_url) as response:
            jwks = json.loads(response.read())
        print("Successfully fetched JWKS keys.")
        return jwks
    except Exception as e:
        print(f"!!! Error fetching Auth0 JWKS keys: {e}")
        return None

# --- FastAPI Dependency: Verify Auth0 Token ---
def verify_token(authorization: Optional[str] = Header(None)) -> Dict:
    """
    FastAPI dependency: Extracts and verifies Auth0 JWT from Authorization header.
    Returns the token payload if valid. Raises HTTPException otherwise.
    """
    print(f"--- verify_token dependency called ---")
    if not authorization:
        print("!!! verify_token: No Authorization header received.")
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        print(f"!!! verify_token: Invalid header format. Parts: {len(parts)}, Start: {parts[0] if parts else 'N/A'}")
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")

    token = parts[1]
    print(f"Extracted Token: {token[:10]}...{token[-5:]}")

    jwks = get_auth0_public_key()
    if not jwks:
        print("!!! verify_token: JWKS keys unavailable for verification.")
        raise HTTPException(status_code=503, detail="Could not fetch verification keys")

    try:
        unverified_header = jwt.get_unverified_header(token)
        print(f"Token KID: {unverified_header.get('kid')}")
    except JWTError as e:
        print(f"!!! verify_token: Invalid token header: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token header: {str(e)}")

    rsa_key = {}
    key_found = False
    for key in jwks.get("keys", []):
        if key.get("kid") == unverified_header.get("kid"):
            rsa_key = { "kty": key["kty"], "kid": key["kid"], "use": key["use"], "n": key["n"], "e": key["e"] }
            key_found = True
            print("Found matching JWKS key.")
            break

    if not key_found:
        print(f"!!! verify_token: Could not find matching key (kid: {unverified_header.get('kid')}) in JWKS.")
        raise HTTPException(status_code=401, detail="Could not find matching key to verify token")

    if not AUTH0_AUDIENCE or not AUTH0_DOMAIN:
         print("!!! verify_token: Server configuration error: AUTH0_AUDIENCE or AUTH0_DOMAIN missing.")
         raise HTTPException(status_code=500, detail="Server configuration error")

    issuer_url = f'https://{AUTH0_DOMAIN}/'
    print(f"Decoding token with audience='{AUTH0_AUDIENCE}', issuer='{issuer_url}'")
    try:
        payload = jwt.decode(
            token, rsa_key, algorithms=["RS256"],
            audience=AUTH0_AUDIENCE, issuer=issuer_url
        )
        print("Token decoded successfully.")
        return payload
    except jwt.ExpiredSignatureError:
        print("!!! verify_token: Token has expired.")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTClaimsError as e:
        print(f"!!! verify_token: Token claims validation failed: {e}")
        raise HTTPException(status_code=401, detail=f"Token claims validation failed: {str(e)}")
    except JWTError as e: # Catch other JWT errors during decode
        print(f"!!! verify_token: Invalid token during decode: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        print(f"!!! verify_token: Unexpected error during decode: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Token verification failed: {str(e)}")

# --- FastAPI Dependency: Get Database Session ---
def get_db():
    if not SessionLocal:
        print("!!! get_db: Database session not configured.")
        raise HTTPException(status_code=500, detail="Database connection not available")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FastAPI Dependency: Get Current User ---
def get_current_user(
    payload: dict = Depends(verify_token), # Depends on successful token verification
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency: Gets user from DB based on token payload 'sub'.
    Creates user if they don't exist. Requires DB models to be defined.
    """
    if User is None: # Check if User model failed to load
         print("!!! get_current_user: User model not available.")
         raise HTTPException(status_code=500, detail="User profile system unavailable")

    auth0_id = payload.get("sub")
    print(f"get_current_user: Looking for user with auth0_id: {auth0_id}")

    if not auth0_id:
        print("!!! get_current_user: Invalid token payload (no 'sub' claim).")
        raise HTTPException(status_code=401, detail="Invalid token payload") # Should be caught by verify_token, but good check

    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    if not user:
        print(f"Creating new user profile for auth0_id: {auth0_id}")
        user = User(
            auth0_id=auth0_id,
            email=payload.get("email"),
            name=payload.get("name") or payload.get("nickname"),
            picture=payload.get("picture")
        )
        try:
            db.add(user); db.commit(); db.refresh(user)
            print(f"New user created with DB ID: {user.id}")
        except Exception as e:
            db.rollback()
            print(f"!!! get_current_user: Error creating user in DB: {e}")
            raise HTTPException(status_code=500, detail="Could not create user profile.")
    else:
        print(f"Found existing user with DB ID: {user.id}")
    return user

# --- FastAPI App Instance & Middleware ---
app = FastAPI(title="AI Companion API")

print(f"Configuring CORS. Allowing origin: {FRONTEND_URL}")
if not FRONTEND_URL:
    print("!!! WARNING: FRONTEND_URL environment variable not set. CORS might block requests.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL else [], # Only allow specific origin
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"], # Be specific if possible
    allow_headers=["Authorization", "Content-Type"], # Only allow necessary headers
)

# --- Import AI Services ---
# Wrapped in try-except to allow app startup even if a service key is missing
services_available = False
try:
    from services.audio_service import process_audio
    from services.emotion_service import analyze_emotion, get_voice_for_emotion
    from services.llm_service import generate_response
    from services.tts_service import text_to_speech
    services_available = True
    print("AI services imported successfully.")
except ImportError as e:
    print(f"!!! WARNING: Failed to import AI services: {e}. Check service files and dependencies.")
    # Define dummy functions so routes don't crash with NameError
    async def process_audio(data): return None
    def analyze_emotion(text): return {'emotion': 'neutral', 'score': 0.0}
    def get_voice_for_emotion(emo, txt): return None
    async def generate_response(txt, ctx): return "Service unavailable."
    async def text_to_speech(txt, vid): return None
except Exception as e: # Catch other potential errors during import (e.g., API key init issues)
    print(f"!!! WARNING: Error initializing AI services during import: {e}")
    # Define dummy functions
    async def process_audio(data): return None
    def analyze_emotion(text): return {'emotion': 'neutral', 'score': 0.0}
    def get_voice_for_emotion(emo, txt): return None
    async def generate_response(txt, ctx): return "Service unavailable."
    async def text_to_speech(txt, vid): return None


# --- API Routes ---

# Public Root Route
@app.get("/")
async def root():
    print("GET / requested")
    return {"status": "AI Companion API is running", "auth": "Auth0"}

# Protected Route: Get User Info
@app.get("/api/user", response_model=UserResponse)
async def get_user_info_route(user: User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user."""
    print(f"GET /api/user requested by user DB ID: {user.id}")
    return user

# Protected Route: Get History
@app.get("/api/history", response_model=HistoryResponse)
async def get_history_route(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns the conversation history for the authenticated user."""
    print(f"GET /api/history requested by user DB ID: {user.id}")
    if Conversation is None: # Check if DB model failed to load
         raise HTTPException(status_code=500, detail="History unavailable")
    try:
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user.id
        ).order_by(Conversation.created_at.asc()).all() # Fetch in ascending order
        print(f"Found {len(conversations)} conversations for user {user.id}")
        messages = []
        for conv in conversations:
            messages.append(Message(type="user", text=conv.user_message, emotion=conv.emotion, timestamp=conv.created_at))
            messages.append(Message(type="assistant", text=conv.assistant_message, emotion=conv.emotion, timestamp=conv.created_at))
        return HistoryResponse(messages=messages)
    except Exception as e:
        print(f"!!! Error fetching history for user {user.id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Could not retrieve conversation history.")

# Protected Route: Process Audio
@app.post("/api/process-audio")
async def process_audio_route(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handles audio upload, transcription, analysis, LLM interaction, TTS,
    and saves the conversation turn.
    """
    print(f"POST /api/process-audio received from user DB ID: {user.id}, Filename: {audio.filename}, Content-Type: {audio.content_type}")
    if not services_available:
        print("!!! /api/process-audio: AI services unavailable due to import errors.")
        raise HTTPException(status_code=503, detail="AI services are temporarily unavailable.")
    if Conversation is None: # Check if DB model failed to load
         raise HTTPException(status_code=500, detail="History unavailable")

    transcription = None # Initialize variables
    response_text = None
    emotion_data = {}
    voice_id = None
    audio_base64 = None

    try:
        audio_data = await audio.read()
        print(f"Read {len(audio_data)} bytes of audio data.")
        if len(audio_data) == 0:
             raise HTTPException(status_code=400, detail="Received empty audio file.")

        # --- Pipeline Steps ---
        print("1. Starting transcription...")
        transcription = await process_audio(audio_data)
        if not transcription:
            print("!!! Transcription failed or returned empty.")
            raise HTTPException(status_code=400, detail="Could not transcribe audio")
        print(f"Transcription: '{transcription}'")

        print("2. Analyzing emotion...")
        emotion_data = analyze_emotion(transcription)
        print(f"Emotion: {emotion_data}")

        print("3. Fetching history for context...")
        user_history_db = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.created_at.desc()).limit(10).all()
        history_for_llm = [{"role": "user", "content": conv.user_message, "emotion": conv.emotion} for conv in reversed(user_history_db)]
        context = {"current_emotion": emotion_data.get('emotion', 'neutral'), "current_emotion_score": emotion_data.get('score', 0.0), "history": history_for_llm}
        print(f"Context size: {len(history_for_llm)} turns.")

        print("4. Generating LLM response...")
        response_text = await generate_response(transcription, context)
        if not response_text: raise HTTPException(status_code=500, detail="AI failed to generate a response.")
        print(f"LLM Response: '{response_text}'")

        print("5. Selecting voice and synthesizing speech...")
        voice_id = get_voice_for_emotion(emotion_data.get('emotion', 'neutral'), response_text)
        print(f"Voice ID: {voice_id}")
        if voice_id:
            audio_base64 = await text_to_speech(response_text, voice_id)
            if not audio_base64: print("!!! TTS failed, returning response without audio.")
            else: print(f"Generated TTS audio (base64 length: {len(audio_base64)}).")
        else: print("No voice selected for TTS.")

        # --- Save Conversation (Optional: Move after returning response if latency is critical) ---
        print("6. Saving conversation to DB...")
        try:
            conversation = Conversation(
                user_id=user.id, user_message=transcription, assistant_message=response_text,
                emotion=emotion_data.get('emotion', 'neutral'), emotion_score=emotion_data.get('score'), voice_used=voice_id
            )
            db.add(conversation); db.commit()
            print("Conversation saved.")
        except Exception as db_error:
            db.rollback(); print(f"!!! Error saving conversation: {db_error}") # Log but don't fail request

        # --- Return Response ---
        print("7. Returning response to frontend.")
        return {
            "transcription": transcription, "response": response_text,
            "emotion": emotion_data.get('emotion', 'neutral'), "voice": voice_id,
            "audio": audio_base64
        }

    except HTTPException as http_exc:
        # Re-raise specific HTTP errors
        print(f"!!! HTTPException during audio processing: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Catch all other unexpected errors
        print(f"!!! Unexpected Error during audio processing for user {user.id}: {e}")
        traceback.print_exc()
        # Return a generic error to the frontend
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your request.")

# Note: The if __name__ == "__main__": block is generally ignored by Vercel,
# but can be useful for running locally if needed. Uvicorn is usually started via Procfile or start command.