from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # OAuth fields
    oauth_provider = Column(String, nullable=True)  # 'google', 'github', etc.
    oauth_id = Column(String, nullable=True)
    
    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")

class Job(Base):
    """Job model for tracking transcription jobs"""
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # File information
    original_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False)
    
    # Processing parameters
    language = Column(String, default="en")
    webhook_url = Column(String, nullable=True)
    
    # Processing status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Processing steps timestamps
    upload_timestamp = Column(DateTime(timezone=True), nullable=True)
    transcription_timestamp = Column(DateTime(timezone=True), nullable=True)
    diarization_timestamp = Column(DateTime(timezone=True), nullable=True)
    merge_timestamp = Column(DateTime(timezone=True), nullable=True)
    webhook_timestamp = Column(DateTime(timezone=True), nullable=True)
    
    # File paths (relative to output directory)
    transcript_file_path = Column(String, nullable=True)
    diarization_file_path = Column(String, nullable=True)
    merged_file_path = Column(String, nullable=True)
    
    # Webhook tracking
    webhook_delivered = Column(Boolean, default=False)
    webhook_retries = Column(Integer, default=0)
    webhook_last_attempt = Column(DateTime(timezone=True), nullable=True)
    webhook_error = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="jobs")

class WebhookLog(Base):
    """Webhook delivery logs"""
    __tablename__ = "webhook_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    webhook_url = Column(String, nullable=False)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("Job") 