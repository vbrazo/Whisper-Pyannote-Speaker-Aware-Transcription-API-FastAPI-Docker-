import os
import json
import tempfile
import shutil
from datetime import datetime
from typing import Optional
from pathlib import Path
import httpx

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_auth
from app.db.database import get_db, create_job, update_job_status, update_job_timestamps, update_job_files, update_webhook_status, log_webhook_attempt
from app.db.models import User
from app.services.whisper import transcribe_audio
from app.services.diarize import diarize_speakers
from app.services.merge import merge_transcript_and_diarization

router = APIRouter()

# File storage configuration
OUTPUT_DIR = Path(settings.OUTPUT_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

def get_user_output_dir(user_id: int) -> Path:
    """Get user-specific output directory"""
    user_dir = OUTPUT_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)
    return user_dir

def save_job_files(job_id: str, user_id: int, transcript_data: dict, diarization_data: dict, merged_data: dict) -> dict:
    """Save job files and return file paths"""
    user_dir = get_user_output_dir(user_id)
    
    # Save transcript file
    transcript_path = user_dir / f"{job_id}_transcript.json"
    with open(transcript_path, 'w') as f:
        json.dump(transcript_data, f, indent=2)
    
    # Save diarization file
    diarization_path = user_dir / f"{job_id}_diarization.json"
    with open(diarization_path, 'w') as f:
        json.dump(diarization_data, f, indent=2)
    
    # Save merged file
    merged_path = user_dir / f"{job_id}_merged.json"
    with open(merged_path, 'w') as f:
        json.dump(merged_data, f, indent=2)
    
    return {
        "transcript_path": str(transcript_path.relative_to(OUTPUT_DIR)),
        "diarization_path": str(diarization_path.relative_to(OUTPUT_DIR)),
        "merged_path": str(merged_path.relative_to(OUTPUT_DIR))
    }

async def send_webhook(webhook_url: str, data: dict, job_id: str, db: Session):
    """Send webhook with processed data and log attempts"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=settings.WEBHOOK_TIMEOUT
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

@router.post("/process")
async def process_audio(
    file: UploadFile = File(...),
    language: str = Form("en"),
    webhook_url: Optional[str] = Form(None),
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Process audio file with transcription and diarization"""
    
    # Validate file type
    allowed_types = ["audio/wav", "audio/mp3", "audio/m4a", "audio/m4v", "audio/flac", "audio/ogg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Create job
    job = create_job(
        db=db,
        user_id=current_user.id,
        original_filename=file.filename,
        file_size=file.size,
        content_type=file.content_type,
        language=language,
        webhook_url=webhook_url
    )
    
    try:
        # Update job status to processing
        update_job_status(db, job.id, "processing")
        update_job_timestamps(db, job.id, started_at=datetime.utcnow())
        
        # Save uploaded file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}")
        try:
            shutil.copyfileobj(file.file, temp_file)
            temp_file.close()
            
            # Update upload timestamp
            update_job_timestamps(db, job.id, upload_timestamp=datetime.utcnow())
            
            # Transcribe audio
            transcript_data = await transcribe_audio(temp_file.name, language)
            update_job_timestamps(db, job.id, transcription_timestamp=datetime.utcnow())
            
            # Diarize speakers
            diarization_data = await diarize_speakers(temp_file.name)
            update_job_timestamps(db, job.id, diarization_timestamp=datetime.utcnow())
            
            # Merge transcript and diarization
            merged_data = merge_transcript_and_diarization(transcript_data, diarization_data)
            update_job_timestamps(db, job.id, merge_timestamp=datetime.utcnow())
            
            # Save files
            file_paths = save_job_files(job.id, current_user.id, transcript_data, diarization_data, merged_data)
            update_job_files(
                db, job.id,
                transcript_path=file_paths["transcript_path"],
                diarization_path=file_paths["diarization_path"],
                merged_path=file_paths["merged_path"]
            )
            
            # Send webhook if provided
            webhook_sent = False
            if webhook_url:
                webhook_data = {
                    "status": "success",
                    "job_id": job.id,
                    "transcript_file": transcript_data,
                    "diarization_file": diarization_data,
                    "merged_file": merged_data,
                    "file_info": {
                        "original_name": file.filename,
                        "size": file.size,
                        "content_type": file.content_type
                    }
                }
                webhook_sent = await send_webhook(webhook_url, webhook_data, job.id, db)
                update_job_timestamps(db, job.id, webhook_timestamp=datetime.utcnow())
            
            # Update job status to completed
            update_job_status(db, job.id, "completed")
            update_job_timestamps(db, job.id, completed_at=datetime.utcnow())
            
            # Prepare response
            processing_steps = {
                "upload": job.upload_timestamp.isoformat() if job.upload_timestamp else None,
                "transcription": job.transcription_timestamp.isoformat() if job.transcription_timestamp else None,
                "diarization": job.diarization_timestamp.isoformat() if job.diarization_timestamp else None,
                "merge": job.merge_timestamp.isoformat() if job.merge_timestamp else None,
                "webhook": job.webhook_timestamp.isoformat() if job.webhook_timestamp else None
            }
            
            return {
                "status": "success",
                "processing_steps": processing_steps,
                "transcript_file": transcript_data,
                "diarization_file": diarization_data,
                "merged_file": merged_data,
                "webhook_sent": webhook_sent,
                "file_info": {
                    "original_name": file.filename,
                    "size": file.size,
                    "content_type": file.content_type
                }
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
                
    except Exception as e:
        error_message = str(e)
        update_job_status(db, job.id, "failed", error_message)
        raise HTTPException(status_code=500, detail=f"Processing failed: {error_message}") 