import os
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from sqlalchemy import func, and_

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin
from app.db.database import get_db, get_all_jobs, get_job_by_id
from app.db.models import User, Job, WebhookLog

router = APIRouter()

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request):
    """Admin dashboard page"""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("admin.html", {"request": request})

@router.get("/admin/jobs")
async def admin_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get jobs with filtering and pagination (admin only)"""
    
    # Build query
    query = db.query(Job).join(User)
    
    # Apply filters
    if search:
        search_filter = (
            Job.original_filename.ilike(f"%{search}%") |
            Job.id.ilike(f"%{search}%") |
            User.username.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    if status:
        query = query.filter(Job.status == status)
    
    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            query = query.filter(Job.created_at >= date_from_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format")
    
    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            query = query.filter(Job.created_at <= date_to_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format")
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    
    # Prepare response
    job_list = []
    for job in jobs:
        job_data = {
            "id": job.id,
            "user": {
                "id": job.user.id,
                "username": job.user.username,
                "email": job.user.email
            },
            "original_filename": job.original_filename,
            "file_size": job.file_size,
            "content_type": job.content_type,
            "language": job.language,
            "status": job.status,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "webhook_url": job.webhook_url,
            "webhook_delivered": job.webhook_delivered,
            "webhook_retries": job.webhook_retries,
            "webhook_error": job.webhook_error
        }
        job_list.append(job_data)
    
    return {
        "jobs": job_list,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit
        }
    }

@router.get("/admin/stats")
async def admin_stats(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Get admin statistics (admin only)"""
    
    # Get basic counts
    total_jobs = db.query(Job).count()
    completed_jobs = db.query(Job).filter(Job.status == "completed").count()
    failed_jobs = db.query(Job).filter(Job.status == "failed").count()
    pending_jobs = db.query(Job).filter(Job.status == "pending").count()
    total_users = db.query(User).count()
    
    # Get total file size
    total_file_size = db.query(func.sum(Job.file_size)).scalar() or 0
    
    # Calculate average processing time for completed jobs
    avg_processing_time = None
    completed_jobs_with_times = db.query(Job).filter(
        and_(Job.status == "completed", Job.started_at.isnot(None), Job.completed_at.isnot(None))
    ).all()
    
    if completed_jobs_with_times:
        total_time = sum(
            (job.completed_at - job.started_at).total_seconds() 
            for job in completed_jobs_with_times
        )
        avg_processing_time = total_time / len(completed_jobs_with_times)
    
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "pending_jobs": pending_jobs,
        "total_users": total_users,
        "total_file_size": total_file_size,
        "average_processing_time": avg_processing_time
    }

@router.get("/admin/download/{job_id}/{file_type}")
async def admin_download_file(
    job_id: str,
    file_type: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Download job files (admin only)"""
    
    # Validate file type
    allowed_types = ["transcript", "diarization", "merged"]
    if file_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Get job
    job = get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get file path
    file_path_map = {
        "transcript": job.transcript_file_path,
        "diarization": job.diarization_file_path,
        "merged": job.merged_file_path
    }
    
    file_path = file_path_map[file_type]
    if not file_path:
        raise HTTPException(status_code=404, detail=f"{file_type} file not found")
    
    # Construct full path
    full_path = Path(settings.OUTPUT_DIR) / file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=str(full_path),
        filename=f"{job_id}_{file_type}.json",
        media_type="application/json"
    )

@router.delete("/admin/jobs/{job_id}")
async def admin_delete_job(
    job_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a job and its files (admin only)"""
    
    # Get job
    job = get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete files from disk
    output_dir = Path(settings.OUTPUT_DIR)
    user_dir = output_dir / str(job.user_id)
    
    file_patterns = [
        f"{job_id}_transcript.json",
        f"{job_id}_diarization.json", 
        f"{job_id}_merged.json"
    ]
    
    for pattern in file_patterns:
        file_path = user_dir / pattern
        if file_path.exists():
            file_path.unlink()
    
    # Delete job from database
    db.delete(job)
    db.commit()
    
    return {"message": "Job deleted successfully"} 