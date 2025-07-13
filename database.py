from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import os

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./whisper_api.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class
Base = declarative_base()

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    from models import Base
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

def get_job_by_id(db: Session, job_id: str):
    """Get job by ID"""
    from models import Job
    return db.query(Job).filter(Job.id == job_id).first()

def get_user_jobs(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """Get jobs for a specific user"""
    from models import Job
    return db.query(Job).filter(Job.user_id == user_id).offset(skip).limit(limit).all()

def get_all_jobs(db: Session, skip: int = 0, limit: int = 100):
    """Get all jobs (admin only)"""
    from models import Job
    return db.query(Job).offset(skip).limit(limit).all()

def create_job(db: Session, user_id: int, original_filename: str, file_size: int, 
               content_type: str, language: str = "en", webhook_url: str = None):
    """Create a new job"""
    from models import Job
    job = Job(
        user_id=user_id,
        original_filename=original_filename,
        file_size=file_size,
        content_type=content_type,
        language=language,
        webhook_url=webhook_url
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def update_job_status(db: Session, job_id: str, status: str, error_message: str = None):
    """Update job status"""
    from models import Job
    job = get_job_by_id(db, job_id)
    if job:
        job.status = status
        if error_message:
            job.error_message = error_message
        db.commit()
        db.refresh(job)
    return job

def update_job_timestamps(db: Session, job_id: str, **timestamps):
    """Update job timestamps"""
    from models import Job
    job = get_job_by_id(db, job_id)
    if job:
        for field, timestamp in timestamps.items():
            if hasattr(job, field):
                setattr(job, field, timestamp)
        db.commit()
        db.refresh(job)
    return job

def update_job_files(db: Session, job_id: str, transcript_path: str = None, 
                    diarization_path: str = None, merged_path: str = None):
    """Update job file paths"""
    from models import Job
    job = get_job_by_id(db, job_id)
    if job:
        if transcript_path:
            job.transcript_file_path = transcript_path
        if diarization_path:
            job.diarization_file_path = diarization_path
        if merged_path:
            job.merged_file_path = merged_path
        db.commit()
        db.refresh(job)
    return job

def update_webhook_status(db: Session, job_id: str, delivered: bool, 
                         retries: int = 0, error: str = None):
    """Update webhook delivery status"""
    from models import Job
    job = get_job_by_id(db, job_id)
    if job:
        job.webhook_delivered = delivered
        job.webhook_retries = retries
        if error:
            job.webhook_error = error
        db.commit()
        db.refresh(job)
    return job

def log_webhook_attempt(db: Session, job_id: str, webhook_url: str, 
                       status_code: int = None, response_body: str = None, 
                       error_message: str = None):
    """Log webhook delivery attempt"""
    from models import WebhookLog
    log = WebhookLog(
        job_id=job_id,
        webhook_url=webhook_url,
        status_code=status_code,
        response_body=response_body,
        error_message=error_message
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log 