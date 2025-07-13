from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserBase(BaseModel):
    """Base user schema"""
    email: str
    username: str
    is_active: bool = True
    is_admin: bool = False


class UserCreate(UserBase):
    """User creation schema"""
    password: str


class User(UserBase):
    """User response schema"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    oauth_provider: Optional[str] = None
    oauth_id: Optional[str] = None

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    """Base job schema"""
    original_filename: str
    file_size: int
    content_type: str
    language: str = "en"
    webhook_url: Optional[str] = None


class JobCreate(JobBase):
    """Job creation schema"""
    user_id: int


class JobUpdate(BaseModel):
    """Job update schema"""
    status: Optional[JobStatus] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    upload_timestamp: Optional[datetime] = None
    transcription_timestamp: Optional[datetime] = None
    diarization_timestamp: Optional[datetime] = None
    merge_timestamp: Optional[datetime] = None
    webhook_timestamp: Optional[datetime] = None
    transcript_file_path: Optional[str] = None
    diarization_file_path: Optional[str] = None
    merged_file_path: Optional[str] = None
    webhook_delivered: Optional[bool] = None
    webhook_retries: Optional[int] = None
    webhook_last_attempt: Optional[datetime] = None
    webhook_error: Optional[str] = None


class Job(JobBase):
    """Job response schema"""
    id: str
    user_id: int
    status: JobStatus
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    upload_timestamp: Optional[datetime] = None
    transcription_timestamp: Optional[datetime] = None
    diarization_timestamp: Optional[datetime] = None
    merge_timestamp: Optional[datetime] = None
    webhook_timestamp: Optional[datetime] = None
    transcript_file_path: Optional[str] = None
    diarization_file_path: Optional[str] = None
    merged_file_path: Optional[str] = None
    webhook_delivered: bool = False
    webhook_retries: int = 0
    webhook_last_attempt: Optional[datetime] = None
    webhook_error: Optional[str] = None

    class Config:
        from_attributes = True


class WebhookLogBase(BaseModel):
    """Base webhook log schema"""
    job_id: str
    webhook_url: str
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    attempt_number: int = 1


class WebhookLogCreate(WebhookLogBase):
    """Webhook log creation schema"""
    pass


class WebhookLog(WebhookLogBase):
    """Webhook log response schema"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Processing schemas
class TranscriptSegment(BaseModel):
    """Transcript segment schema"""
    start: float
    end: float
    text: str


class TranscriptFile(BaseModel):
    """Transcript file schema"""
    text: str
    segments: List[TranscriptSegment]


class DiarizationSegment(BaseModel):
    """Diarization segment schema"""
    start: float
    end: float
    speaker: str


class DiarizationFile(BaseModel):
    """Diarization file schema"""
    segments: List[DiarizationSegment]


class MergedSegment(BaseModel):
    """Merged segment schema"""
    start: float
    end: float
    text: str
    speaker: str


class MergedFile(BaseModel):
    """Merged file schema"""
    language: str
    segments: List[MergedSegment]


class ProcessingSteps(BaseModel):
    """Processing steps timestamps schema"""
    upload: Optional[datetime] = None
    transcription: Optional[datetime] = None
    diarization: Optional[datetime] = None
    merge: Optional[datetime] = None
    webhook: Optional[datetime] = None


class FileInfo(BaseModel):
    """File information schema"""
    original_name: str
    size: int
    content_type: str


class ProcessResponse(BaseModel):
    """Process endpoint response schema"""
    status: str
    processing_steps: ProcessingSteps
    transcript_file: TranscriptFile
    diarization_file: DiarizationFile
    merged_file: MergedFile
    webhook_sent: bool
    file_info: FileInfo


class HealthResponse(BaseModel):
    """Health check response schema"""
    status: str
    models_loaded: dict[str, bool]


# Admin schemas
class JobFilter(BaseModel):
    """Job filtering schema"""
    page: int = 1
    limit: int = 20
    search: Optional[str] = None
    status: Optional[JobStatus] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class AdminStats(BaseModel):
    """Admin statistics schema"""
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    pending_jobs: int
    total_users: int
    total_file_size: int
    average_processing_time: Optional[float] = None 