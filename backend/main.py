from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile,
    File, Header, Request
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict

from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Float
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from datetime import datetime
from jose import jwt, JWTError
from urllib.request import urlopen
import json
from functools import lru_cache

import os
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
import traceback

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./ai_companion.db"

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"!!! CRITICAL: Failed to create database engine: {e}")
    engine = None
    SessionLocal = None
    Base = object

if Base is not object:
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
        user_id = Column(Integer, index=True)
        user_message = Column(Text, nullable=True)
        assistant_message = Column(Text, nullable=True)
        emotion = Column(String, nullable=True)
        emotion_score = Column(Float, nullable=True)
        voice_used = Column(String, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow, index=True)

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"!!! WARNING: Error creating database tables: {e}")
else:
    User = None
    Conversation = None

class UserResponse(BaseModel):
    id: int
    auth0_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    picture: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class Message(BaseModel):
    type: str
    text: Optional[str] = None
    emotion: Optional[str] = None
    timestamp: Optional[datetime] = None

class HistoryResponse(BaseModel):
    messages: List[Message]

@lru_cache(maxsize=1)
def get_auth0_public_key():
    if not AUTH0_DOMAIN:
        return None
    jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
    try:
        with urlopen(jwks_url) as response:
            jwks = json.loads(response.read())
        return jwks
    except Exception as e:
        print(f"!!! Error fetching Auth0 JWKS keys: {e}")
        return None

def verify_token(authorization: Optional[str] = Header(None)) -> Dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")

    token = parts[1]

    jwks = get_auth0_public_key()
    if not jwks:
        raise HTTPException(status_code=503, detail="Could not fetch verification keys")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token header: {str(e)}")

    rsa_key = {}
    key_found = False
    for key in jwks.get("keys", []):
        if key.get("kid") == unverified_header.get("kid"):
            rsa_key = { "kty": key["kty"], "kid": key["kid"], "use": key["use"], "n": key["n"], "e": key["e"] }
            key_found = True
            break

    if not key_found:
        raise HTTPException(status_code=401, detail="Could not find matching key to verify token")

    if not AUTH0_AUDIENCE or not AUTH0_DOMAIN:
         raise HTTPException(status_code=500, detail="Server configuration error")

    issuer_url = f'https://{AUTH0_DOMAIN}/'
    try:
        payload = jwt.decode(
            token, rsa_key, algorithms=["RS256"],
            audience=AUTH0_AUDIENCE, issuer=issuer_url
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTClaimsError as e:
        raise HTTPException(status_code=401, detail=f"Token claims validation failed: {str(e)}")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Token verification failed: {str(e)}")

def get_db():
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database connection not available")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    payload: dict = Depends(verify_token),
    db: Session = Depends(get_db)
) -> User:
    if User is None:
         raise HTTPException(status_code=500, detail="User profile system unavailable")

    auth0_id = payload.get("sub")
    if not auth0_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    if not user:
        user = User(
            auth0_id=auth0_id,
            email=payload.get("email"),
            name=payload.get("name") or payload.get("nickname"),
            picture=payload.get("picture")
        )
        try:
            db.add(user); db.commit(); db.refresh(user)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Could not create user profile.")
    return user

app = FastAPI(title="AI Companion API")

if not FRONTEND_URL:
    print("!!! WARNING: FRONTEND_URL environment variable not set. CORS might block requests.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

services_available = False
try:
    from services.audio_service import process_audio
    # *** IMPORTANT: Make sure this uses the correct function name from your emotion_service.py ***
    # If you updated it to get_voice_for_emotion_and_language, import that name instead.
    from services.emotion_service import analyze_emotion, get_voice_for_emotion_and_language # Corrected name
    from services.llm_service import generate_response # Ensure this accepts language
    from services.tts_service import text_to_speech # Ensure this uses Murf AI
    services_available = True
except ImportError as e:
    print(f"!!! WARNING: Failed to import AI services: {e}.")
    async def process_audio(data): return None, None # Needs to return tuple if using lang detect
    def analyze_emotion(text): return {'emotion': 'neutral', 'score': 0.0}
    def get_voice_for_emotion_and_language(emo, lang, txt): return None # Corrected name
    async def generate_response(txt, lang, ctx): return "Service unavailable." # Needs lang
    async def text_to_speech(txt, vid): return None
except Exception as e:
    print(f"!!! WARNING: Error initializing AI services during import: {e}")
    async def process_audio(data): return None, None
    def analyze_emotion(text): return {'emotion': 'neutral', 'score': 0.0}
    def get_voice_for_emotion_and_language(emo, lang, txt): return None
    async def generate_response(txt, lang, ctx): return "Service unavailable."
    async def text_to_speech(txt, vid): return None

@app.get("/")
async def root():
    return {"status": "AI Companion API is running", "auth": "Auth0"}

@app.get("/api/user", response_model=UserResponse)
async def get_user_info_route(user: User = Depends(get_current_user)):
    return user

@app.get("/api/history", response_model=HistoryResponse)
async def get_history_route(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if Conversation is None:
         raise HTTPException(status_code=500, detail="History unavailable")
    try:
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user.id
        ).order_by(Conversation.created_at.asc()).all()
        messages = []
        for conv in conversations:
            messages.append(Message(type="user", text=conv.user_message, emotion=conv.emotion, timestamp=conv.created_at))
            messages.append(Message(type="assistant", text=conv.assistant_message, emotion=conv.emotion, timestamp=conv.created_at))
        return HistoryResponse(messages=messages)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Could not retrieve conversation history.")

@app.post("/api/process-audio")
async def process_audio_route(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not services_available:
        raise HTTPException(status_code=503, detail="AI services are temporarily unavailable.")
    if Conversation is None:
         raise HTTPException(status_code=500, detail="History unavailable")

    transcription = None
    detected_language = 'en' # Default language
    response_text = None
    emotion_data = {}
    voice_id = None
    audio_base64 = None

    try:
        audio_data = await audio.read()
        if len(audio_data) == 0:
             raise HTTPException(status_code=400, detail="Received empty audio file.")

        transcription, detected_language = await process_audio(audio_data) # Expect tuple
        if not transcription:
            raise HTTPException(status_code=400, detail="Could not transcribe audio")
        detected_language = detected_language or 'en' # Ensure default if detection fails

        emotion_data = analyze_emotion(transcription)

        user_history_db = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.created_at.desc()).limit(10).all()
        history_for_llm = [{"role": "user", "content": conv.user_message, "emotion": conv.emotion} for conv in reversed(user_history_db)]
        context = {"current_emotion": emotion_data.get('emotion', 'neutral'), "current_emotion_score": emotion_data.get('score', 0.0), "history": history_for_llm}

        response_text = await generate_response(transcription, detected_language, context) # Pass language
        if not response_text: raise HTTPException(status_code=500, detail="AI failed to generate a response.")

        voice_id = get_voice_for_emotion_and_language(emotion_data.get('emotion', 'neutral'), detected_language, response_text) # Pass language
        if voice_id:
            audio_base64 = await text_to_speech(response_text, voice_id)
            if not audio_base64: print("!!! TTS failed, returning response without audio.")
        else: print("No voice selected for TTS.")

        try:
            conversation = Conversation(
                user_id=user.id, user_message=transcription, assistant_message=response_text,
                emotion=emotion_data.get('emotion', 'neutral'), emotion_score=emotion_data.get('score'), voice_used=voice_id
            )
            db.add(conversation); db.commit()
        except Exception as db_error:
            db.rollback(); print(f"!!! Error saving conversation: {db_error}")

        return {
            "transcription": transcription, "response": response_text,
            "emotion": emotion_data.get('emotion', 'neutral'), "voice": voice_id,
            "audio": audio_base64
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your request.")