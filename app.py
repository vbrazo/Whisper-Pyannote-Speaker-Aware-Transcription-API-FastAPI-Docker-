import os
import json
import asyncio
import tempfile
import shutil
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import uuid

import whisper
import torch
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, status, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.sessions import SessionMiddleware
import httpx
from pyannote.audio import Pipeline
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from models import User, Job, WebhookLog
from database import get_db, init_db, create_job, update_job_status, update_job_timestamps, update_job_files, update_webhook_status, log_webhook_attempt
from auth import (
    get_current_user_from_session, require_auth, require_admin, 
    authenticate_user, create_user, init_test_user,
    google_login, google_callback, github_login, github_callback, logout
)

# Initialize FastAPI app
app = FastAPI(title="Whisper + Pyannote Audio Processing API", version="2.0.0")

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"),
    max_age=3600,  # 1 hour
    same_site="lax"
)

# Templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables for models
whisper_model = None
diarization_pipeline = None

# File storage configuration
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

def load_models():
    """Load Whisper and Pyannote models"""
    global whisper_model, diarization_pipeline
    
    print("Loading Whisper model...")
    whisper_model = whisper.load_model("base")
    
    print("Loading Pyannote diarization pipeline...")
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
    """Initialize models and database on startup"""
    load_models()
    init_db()
    
    # Initialize test user
    db = next(get_db())
    init_test_user(db)

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
        
        speakers = []
        for ds in diarization_segments:
            if (ds["start"] <= segment_end and ds["end"] >= segment_start):
                overlap_start = max(ds["start"], segment_start)
                overlap_end = min(ds["end"], segment_end)
                overlap_duration = overlap_end - overlap_start
                
                speakers.append({
                    "speaker": ds["speaker"],
                    "overlap_duration": overlap_duration
                })
        
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

async def send_webhook(webhook_url: str, data: dict, job_id: str, db: Session):
    """Send webhook with processed data and log attempts"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            
            # Log the attempt
            log_webhook_attempt(
                db=db,
                job_id=job_id,
                webhook_url=webhook_url,
                status_code=response.status_code,
                response_body=response.text[:500] if response.text else None
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                update_webhook_status(db, job_id, True)
                print(f"Webhook sent successfully to {webhook_url}")
                return True
            else:
                update_webhook_status(db, job_id, False, error=f"HTTP {response.status_code}")
                print(f"Webhook failed with status {response.status_code}")
                return False
                
    except Exception as e:
        error_msg = str(e)
        log_webhook_attempt(
            db=db,
            job_id=job_id,
            webhook_url=webhook_url,
            error_message=error_msg
        )
        update_webhook_status(db, job_id, False, error=error_msg)
        print(f"Webhook failed: {error_msg}")
        return False

def get_user_output_dir(user_id: int) -> Path:
    """Get user-specific output directory"""
    user_dir = OUTPUT_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)
    return user_dir

def save_job_files(job_id: str, user_id: int, transcript_data: dict, diarization_data: dict, merged_data: dict) -> dict:
    """Save job files to user-specific directory"""
    user_dir = get_user_output_dir(user_id)
    job_dir = user_dir / job_id
    job_dir.mkdir(exist_ok=True)
    
    # Save files
    transcript_path = job_dir / "transcript.json"
    diarization_path = job_dir / "diarization.json"
    merged_path = job_dir / "merged.json"
    
    with open(transcript_path, "w") as f:
        json.dump(transcript_data, f, indent=2)
    
    with open(diarization_path, "w") as f:
        json.dump(diarization_data, f, indent=2)
    
    with open(merged_path, "w") as f:
        json.dump(merged_data, f, indent=2)
    
    return {
        "transcript_path": str(transcript_path.relative_to(OUTPUT_DIR)),
        "diarization_path": str(diarization_path.relative_to(OUTPUT_DIR)),
        "merged_path": str(merged_path.relative_to(OUTPUT_DIR))
    }

# Authentication routes
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle username/password login"""
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Set session
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email
    
    return RedirectResponse(url="/", status_code=302)

@app.get("/auth/google")
async def google_auth(request: Request):
    """Initiate Google OAuth"""
    return await google_login(request)

@app.get("/auth/google/callback")
async def google_auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    return await google_callback(request, db)

@app.get("/auth/github")
async def github_auth(request: Request):
    """Initiate GitHub OAuth"""
    return await github_login(request)

@app.get("/auth/github/callback")
async def github_auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    return await github_callback(request, db)

@app.get("/logout")
async def logout_route(request: Request):
    """Logout user"""
    return logout(request)

# Main application routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: Optional[User] = Depends(get_current_user_from_session)):
    """Serve the main page - redirect to login if not authenticated"""
    if not current_user:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("index.html", {"request": request, "current_user": current_user})

@app.post("/process")
async def process_audio(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("en"),
    webhook_url: Optional[str] = Form(None),
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
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
    
    # Create job record
    job = create_job(
        db=db,
        user_id=current_user.id,
        original_filename=file.filename,
        file_size=file.size,
        content_type=file.content_type,
        language=language,
        webhook_url=webhook_url
    )
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Save uploaded file
        audio_path = temp_path / f"input{file_extension}"
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        try:
            # Update job status to processing
            update_job_status(db, job.id, "processing")
            update_job_timestamps(db, job.id, upload_timestamp=datetime.utcnow())
            
            # Step 1: Transcribe
            print("Starting transcription...")
            transcript_result = await transcribe_audio(str(audio_path), language)
            update_job_timestamps(db, job.id, transcription_timestamp=datetime.utcnow())
            
            # Step 2: Diarize
            print("Starting diarization...")
            diarization_result = await diarize_speakers(str(audio_path))
            update_job_timestamps(db, job.id, diarization_timestamp=datetime.utcnow())
            
            # Step 3: Merge
            print("Merging transcript and diarization...")
            merged_result = merge_transcript_and_diarization(transcript_result, diarization_result)
            update_job_timestamps(db, job.id, merge_timestamp=datetime.utcnow())
            
            # Step 4: Save files
            file_paths = save_job_files(
                job.id, 
                current_user.id, 
                transcript_result, 
                diarization_result, 
                merged_result
            )
            
            # Update job with file paths
            update_job_files(
                db, job.id,
                transcript_path=file_paths["transcript_path"],
                diarization_path=file_paths["diarization_path"],
                merged_path=file_paths["merged_path"]
            )
            
            # Step 5: Send webhook if provided
            webhook_success = None
            if webhook_url:
                print(f"Sending webhook to {webhook_url}...")
                webhook_success = await send_webhook(webhook_url, merged_result, job.id, db)
                update_job_timestamps(db, job.id, webhook_timestamp=datetime.utcnow())
            
            # Update job status to completed
            update_job_status(db, job.id, "completed")
            update_job_timestamps(db, job.id, completed_at=datetime.utcnow())
            
            return JSONResponse({
                "status": "success",
                "job_id": job.id,
                "transcript_file": transcript_result,
                "diarization_file": diarization_result,
                "merged_file": merged_result,
                "webhook_sent": webhook_success if webhook_url else None,
                "file_info": {
                    "original_name": file.filename,
                    "size": file.size,
                    "content_type": file.content_type
                }
            })
            
        except Exception as e:
            # Update job status to failed
            update_job_status(db, job.id, "failed", error_message=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed: {str(e)}"
            )

# Admin routes
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, current_user: User = Depends(require_admin)):
    """Admin dashboard"""
    return templates.TemplateResponse("admin.html", {"request": request, "current_user": current_user})

@app.get("/admin/jobs")
async def admin_jobs(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get jobs with filtering and pagination"""
    from sqlalchemy import and_, or_
    from models import Job, User
    
    # Build query
    query = db.query(Job).join(User)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Job.original_filename.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    if status:
        query = query.filter(Job.status == status)
    
    if date_from:
        query = query.filter(Job.created_at >= date_from)
    
    if date_to:
        query = query.filter(Job.created_at <= date_to)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    jobs = query.offset(offset).limit(limit).all()
    
    # Format response
    job_data = []
    for job in jobs:
        job_data.append({
            "id": job.id,
            "user_email": job.user.email,
            "original_filename": job.original_filename,
            "language": job.language,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "file_size": job.file_size,
            "webhook_url": job.webhook_url,
            "webhook_delivered": job.webhook_delivered,
            "error_message": job.error_message
        })
    
    return {
        "jobs": job_data,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }

@app.get("/admin/stats")
async def admin_stats(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Get admin statistics"""
    from models import Job
    from sqlalchemy import func
    
    # Get counts by status
    status_counts = db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    
    stats = {
        "total": 0,
        "completed": 0,
        "processing": 0,
        "failed": 0,
        "pending": 0
    }
    
    for status, count in status_counts:
        stats[status] = count
        stats["total"] += count
    
    return stats

@app.get("/admin/download/{job_id}/{file_type}")
async def admin_download_file(
    job_id: str,
    file_type: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Download job files"""
    from database import get_job_by_id
    
    job = get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Determine file path based on file type
    if file_type == "transcript" and job.transcript_file_path:
        file_path = OUTPUT_DIR / job.transcript_file_path
    elif file_type == "diarization" and job.diarization_file_path:
        file_path = OUTPUT_DIR / job.diarization_file_path
    elif file_type == "merged" and job.merged_file_path:
        file_path = OUTPUT_DIR / job.merged_file_path
    else:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=f"{job_id}_{file_type}.json",
        media_type="application/json"
    )

@app.delete("/admin/jobs/{job_id}")
async def admin_delete_job(
    job_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a job and its files"""
    from database import get_job_by_id
    
    job = get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete files
    if job.transcript_file_path:
        file_path = OUTPUT_DIR / job.transcript_file_path
        if file_path.exists():
            file_path.unlink()
    
    if job.diarization_file_path:
        file_path = OUTPUT_DIR / job.diarization_file_path
        if file_path.exists():
            file_path.unlink()
    
    if job.merged_file_path:
        file_path = OUTPUT_DIR / job.merged_file_path
        if file_path.exists():
            file_path.unlink()
    
    # Delete job directory
    job_dir = OUTPUT_DIR / str(job.user_id) / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    
    # Delete from database
    db.delete(job)
    db.commit()
    
    return {"status": "success", "message": "Job deleted successfully"}

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