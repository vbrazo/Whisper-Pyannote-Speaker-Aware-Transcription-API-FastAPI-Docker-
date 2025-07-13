import whisper
from fastapi import HTTPException
from typing import Dict, Any

from app.core.config import settings
import torch

# Global whisper model
whisper_model = None

def load_whisper_model():
    """Load Whisper model"""
    global whisper_model
    device = "cuda" if settings.is_gpu and torch.cuda.is_available() else "cpu"
    print(f"Loading Whisper model on device: {device}")
    whisper_model = whisper.load_model(settings.WHISPER_MODEL, device=device)
    print(f"✅ Whisper model '{settings.WHISPER_MODEL}' loaded")

def get_whisper_model():
    """Get the loaded Whisper model"""
    global whisper_model
    if whisper_model is None:
        load_whisper_model()
    return whisper_model

async def transcribe_audio(audio_path: str, language: str = "en") -> Dict[str, Any]:
    """Transcribe audio using Whisper"""
    try:
        print(f"Transcribing audio with language: {language}")
        model = get_whisper_model()
        result = model.transcribe(
            audio_path,
            language=language if language != "auto" else None,
            task="transcribe"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}") 