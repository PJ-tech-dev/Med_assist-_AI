from typing import Optional, Dict, Any
from datetime import datetime, timezone
from beanie import Document, PydanticObjectId, Indexed
from pydantic import Field
from app.models.base import TimestampMixin

class MedicalReport(Document, TimestampMixin):
    patient_id: Indexed(PydanticObjectId)
    user_id: Indexed(PydanticObjectId)

    # File metadata
    filename: str
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    file_path: Optional[str] = None

    # Report classification
    report_type: Optional[str] = None

    # Extracted content
    raw_text: Optional[str] = None
    ocr_confidence: Optional[float] = None

    # Timestamps
    upload_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Soft delete
    is_deleted: bool = False

    class Settings:
        name = "medical_reports"

class ReportAnalysisResult(Document, TimestampMixin):
    report_id: Indexed(PydanticObjectId)

    # Structured output
    structured_results: Optional[Dict[str, Any]] = None

    # Summary fields
    summary: Optional[str] = None
    patient_friendly_summary: Optional[str] = None
    abnormalities_count: int = 0
    confidence: float = 0.0
    risk_level: Optional[str] = None

    class Settings:
        name = "report_analysis_results"