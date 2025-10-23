from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from functools import lru_cache
from jose import jwt, JWTError
from urllib.request import urlopen

load_dotenv()

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ai_companion.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    auth0_id = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    user_message = Column(Text)
    assistant_message = Column(Text)
    emotion = Column(String)
    emotion_score = Column(Float)
    voice_used = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Pydantic Schemas
class UserResponse(BaseModel):
    id: int
    auth0_id: str
    name: str
    email: str
    picture: str = None
    
    class Config:
        from_attributes = True

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")



@lru_cache(maxsize=1)
def get_auth0_public_key():
    """Get Auth0 public key for token verification"""
    try:
        jsonurl = urlopen(f'https://{AUTH0_DOMAIN}/.well-known/jwks.json')
        jwks = json.loads(jsonurl.read())
        return jwks
    except Exception as e:
        print(f"Error fetching Auth0 keys: {e}")
        return None

def verify_auth0_token(token: str):
    """Verify Auth0 JWT token"""
    try:
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        
        jwks = get_auth0_public_key()
        if not jwks:
            raise HTTPException(status_code=401, detail="Could not verify token")
        
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
        
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Could not find key")
        
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f'https://{AUTH0_DOMAIN}/'
        )
        
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

def get_current_user(token: str, db: Session) -> User:
    """Get current user from Auth0 token"""
    payload = verify_auth0_token(token)
    auth0_id = payload.get("sub")
    
    if not auth0_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    
    if not user:
        user = User(
            auth0_id=auth0_id,
            email=payload.get("email"),
            name=payload.get("name", "User"),
            picture=payload.get("picture")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# FastAPI App
app = FastAPI(title="AI Companion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import services
from services.audio_service import process_audio
from services.emotion_service import analyze_emotion, get_voice_for_emotion
from services.llm_service import generate_response
from services.tts_service import text_to_speech

# Routes
@app.get("/")
async def root():
    return {"status": "AI Companion API is running", "auth": "Auth0"}

@app.get("/api/user")
async def get_user_info(token: str = None, db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")

@app.get("/api/history")
async def get_history(token: str = None, db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    user = get_current_user(token, db)
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user.id
    ).order_by(Conversation.created_at).all()
    
    messages = []
    for conv in conversations:
        messages.append({
            "type": "user",
            "text": conv.user_message,
            "emotion": conv.emotion,
            "timestamp": conv.created_at.isoformat()
        })
        messages.append({
            "type": "assistant",
            "text": conv.assistant_message,
            "emotion": conv.emotion,
            "timestamp": conv.created_at.isoformat()
        })
    
    return {"messages": messages}

@app.post("/api/process-audio")
async def process_audio_endpoint(
    audio: UploadFile = File(...),
    token: str = Form(...),
    db: Session = Depends(get_db)
):
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    user = get_current_user(token, db)
    
    try:
        audio_data = await audio.read()
        transcription = await process_audio(audio_data)
        
        if not transcription:
            raise HTTPException(status_code=400, detail="Could not transcribe audio")
        
        emotion_data = analyze_emotion(transcription)
        
        user_history = db.query(Conversation).filter(
            Conversation.user_id == user.id
        ).order_by(Conversation.created_at.desc()).limit(10).all()
        
        context = {
            "current_emotion": emotion_data['emotion'],
            "current_emotion_score": emotion_data['score'],
            "history": [
                {
                    "emotion": conv.emotion,
                    "message": conv.user_message,
                    "date": conv.created_at.isoformat()
                }
                for conv in user_history
            ]
        }
        
        response_text = await generate_response(transcription, context)
        voice_id = get_voice_for_emotion(emotion_data['emotion'], response_text)
        audio_base64 = await text_to_speech(response_text, voice_id)
        
        conversation = Conversation(
            user_id=user.id,
            user_message=transcription,
            assistant_message=response_text,
            emotion=emotion_data['emotion'],
            emotion_score=emotion_data['score'],
            voice_used=voice_id
        )
        db.add(conversation)
        db.commit()
        
        return {
            "transcription": transcription,
            "response": response_text,
            "emotion": emotion_data['emotion'],
            "voice": voice_id,
            "audio": audio_base64
        }
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)