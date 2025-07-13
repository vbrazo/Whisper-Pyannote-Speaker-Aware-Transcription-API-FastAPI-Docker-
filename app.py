import os
import json
import asyncio
import tempfile
import shutil
from datetime import datetime
from typing import Optional
from pathlib import Path

import whisper
import torch
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook

# Initialize FastAPI app
app = FastAPI(title="Whisper + Pyannote Audio Processing API", version="1.0.0")

# Security
security = HTTPBasic()

# Templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables for models
whisper_model = None
diarization_pipeline = None

# Basic auth credentials (in production, use environment variables)
VALID_USERNAME = "admin"
VALID_PASSWORD = "password123"

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate basic auth credentials"""
    if credentials.username != VALID_USERNAME or credentials.password != VALID_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def load_models():
    """Load Whisper and Pyannote models"""
    global whisper_model, diarization_pipeline
    
    print("Loading Whisper model...")
    whisper_model = whisper.load_model("base")
    
    print("Loading Pyannote diarization pipeline...")
    # You'll need to get a token from https://huggingface.co/pyannote/speaker-diarization
    # and set it as environment variable: HF_TOKEN
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("Warning: HF_TOKEN not set. Diarization will not work.")
        diarization_pipeline = None
    else:
        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization@2.1",
            use_auth_token=hf_token
        )

@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    load_models()

async def transcribe_audio(audio_path: str, language: str = "en") -> dict:
    """Transcribe audio using Whisper"""
    try:
        print(f"Transcribing audio with language: {language}")
        result = whisper_model.transcribe(
            audio_path,
            language=language if language != "auto" else None,
            task="transcribe"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

async def diarize_speakers(audio_path: str) -> dict:
    """Diarize speakers using pyannote.audio"""
    if diarization_pipeline is None:
        raise HTTPException(status_code=500, detail="Diarization pipeline not loaded. Set HF_TOKEN environment variable.")
    
    try:
        print("Running speaker diarization...")
        diarization = diarization_pipeline(audio_path)
        
        # Convert diarization to segments
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        
        return {"segments": segments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diarization failed: {str(e)}")

def merge_transcript_and_diarization(transcript: dict, diarization: dict) -> dict:
    """Merge transcript segments with speaker diarization"""
    transcript_segments = transcript.get("segments", [])
    diarization_segments = diarization.get("segments", [])
    
    merged_segments = []
    
    for ts in transcript_segments:
        segment_start = ts["start"]
        segment_end = ts["end"]
        text = ts["text"]
        
        # Find overlapping diarization segments
        speakers = []
        for ds in diarization_segments:
            if (ds["start"] <= segment_end and ds["end"] >= segment_start):
                # Calculate overlap
                overlap_start = max(ds["start"], segment_start)
                overlap_end = min(ds["end"], segment_end)
                overlap_duration = overlap_end - overlap_start
                
                speakers.append({
                    "speaker": ds["speaker"],
                    "overlap_duration": overlap_duration
                })
        
        # Find the speaker with the most overlap
        if speakers:
            primary_speaker = max(speakers, key=lambda x: x["overlap_duration"])
            speaker = primary_speaker["speaker"]
        else:
            speaker = "unknown"
        
        merged_segments.append({
            "start": segment_start,
            "end": segment_end,
            "text": text,
            "speaker": speaker
        })
    
    return {
        "language": transcript.get("language", "unknown"),
        "segments": merged_segments
    }

async def send_webhook(webhook_url: str, data: dict):
    """Send webhook with processed data"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            response.raise_for_status()
            print(f"Webhook sent successfully to {webhook_url}")
            return True
    except Exception as e:
        print(f"Webhook failed: {str(e)}")
        return False

@app.get("/", response_class=HTMLResponse)
async def index(request):
    """Serve the upload form"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process")
async def process_audio(
    file: UploadFile = File(...),
    language: str = Form("en"),
    webhook_url: Optional[str] = Form(None),
    username: str = Depends(get_current_user)
):
    """Process audio file with transcription and diarization"""
    
    # Validate file type
    allowed_extensions = {".wav", ".mp3", ".m4a", ".m4v", ".flac", ".ogg"}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Save uploaded file
        audio_path = temp_path / f"input{file_extension}"
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Track processing steps
        processing_steps = {
            "upload": datetime.utcnow().isoformat(),
            "transcription": None,
            "diarization": None,
            "merge": None,
            "webhook": None
        }
        
        try:
            # Step 1: Transcribe
            print("Starting transcription...")
            transcript_result = await transcribe_audio(str(audio_path), language)
            processing_steps["transcription"] = datetime.utcnow().isoformat()
            
            # Save transcript
            transcript_file = temp_path / "transcript.json"
            with open(transcript_file, "w") as f:
                json.dump(transcript_result, f, indent=2)
            
            # Step 2: Diarize
            print("Starting diarization...")
            diarization_result = await diarize_speakers(str(audio_path))
            processing_steps["diarization"] = datetime.utcnow().isoformat()
            
            # Save diarization
            diarization_file = temp_path / "diarization.json"
            with open(diarization_file, "w") as f:
                json.dump(diarization_result, f, indent=2)
            
            # Step 3: Merge
            print("Merging transcript and diarization...")
            merged_result = merge_transcript_and_diarization(transcript_result, diarization_result)
            processing_steps["merge"] = datetime.utcnow().isoformat()
            
            # Save merged result
            merged_file = temp_path / "merged.json"
            with open(merged_file, "w") as f:
                json.dump(merged_result, f, indent=2)
            
            # Step 4: Send webhook if provided
            webhook_success = None
            if webhook_url:
                print(f"Sending webhook to {webhook_url}...")
                webhook_success = await send_webhook(webhook_url, merged_result)
                processing_steps["webhook"] = datetime.utcnow().isoformat()
            
            # Read files for response
            with open(transcript_file, "r") as f:
                transcript_content = json.load(f)
            
            with open(diarization_file, "r") as f:
                diarization_content = json.load(f)
            
            with open(merged_file, "r") as f:
                merged_content = json.load(f)
            
            return JSONResponse({
                "status": "success",
                "processing_steps": processing_steps,
                "transcript_file": transcript_content,
                "diarization_file": diarization_content,
                "merged_file": merged_content,
                "webhook_sent": webhook_success if webhook_url else None,
                "file_info": {
                    "original_name": file.filename,
                    "size": file.size,
                    "content_type": file.content_type
                }
            })
            
        except Exception as e:
            processing_steps["error"] = datetime.utcnow().isoformat()
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed: {str(e)}"
            )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "models_loaded": {
        "whisper": whisper_model is not None,
        "pyannote": diarization_pipeline is not None
    }}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 