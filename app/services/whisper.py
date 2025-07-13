from faster_whisper import WhisperModel
from fastapi import HTTPException
from typing import Dict, Any

from app.core.config import settings
import torch

# Global whisper model
whisper_model = None

def load_whisper_model():
    """Load Faster Whisper model"""
    global whisper_model
    device = "cuda" if settings.RUN_MODE == "gpu" and torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"Loading Faster Whisper model on device: {device} with compute_type: {compute_type}")
    whisper_model = WhisperModel(
        settings.WHISPER_MODEL, 
        device=device, 
        compute_type=compute_type
    )
    print(f"✅ Faster Whisper model '{settings.WHISPER_MODEL}' loaded")

def get_whisper_model():
    """Get the loaded Faster Whisper model"""
    global whisper_model
    if whisper_model is None:
        load_whisper_model()
    return whisper_model

async def transcribe_audio(audio_path: str, language: str = "en") -> Dict[str, Any]:
    """Transcribe audio using Faster Whisper"""
    try:
        print(f"Transcribing audio with language: {language}")
        model = get_whisper_model()
        
        # Use language=None for auto-detection if language is "auto"
        whisper_language = None if language == "auto" else language
        
        # Transcribe with Faster Whisper
        segments, info = model.transcribe(
            audio_path,
            language=whisper_language,
            task="transcribe"
        )
        
        # Convert segments to the expected format
        segments_list = []
        for segment in segments:
            segments_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "words": [
                    {
                        "start": word.start,
                        "end": word.end,
                        "word": word.word
                    } for word in segment.words
                ] if hasattr(segment, 'words') and segment.words else []
            })
        
        # Return in the same format as OpenAI Whisper
        result = {
            "text": " ".join([seg["text"] for seg in segments_list]),
            "segments": segments_list,
            "language": info.language if hasattr(info, 'language') else language
        }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}") 