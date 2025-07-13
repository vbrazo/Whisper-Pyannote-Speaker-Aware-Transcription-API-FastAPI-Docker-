import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user_from_session, init_test_user
from app.db.database import get_db, init_db
from app.services.whisper import load_whisper_model
from app.services.diarize import load_diarization_pipeline
from app.api import process, admin, auth

app = FastAPI(title="Whisper + Pyannote Audio Processing API", version="2.0.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=settings.SESSION_MAX_AGE,
    same_site=settings.SESSION_SAME_SITE
)

templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(process.router, tags=["process"])
app.include_router(admin.router, tags=["admin"])
app.include_router(auth.router, tags=["auth"])

@app.on_event("startup")
async def startup_event():
    """Initialize models and database on startup"""
    load_whisper_model()
    load_diarization_pipeline()
    
    init_db()
    
    db = next(get_db())
    init_test_user(db)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user = Depends(get_current_user_from_session)):
    """Main upload interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from app.services.whisper import get_whisper_model
    from app.services.diarize import get_diarization_pipeline
    
    whisper_loaded = get_whisper_model() is not None
    pyannote_loaded = get_diarization_pipeline() is not None
    
    return {
        "status": "healthy",
        "models_loaded": {
            "whisper": whisper_loaded,
            "pyannote": pyannote_loaded
        }
    }