from typing import Optional
from datetime import datetime, timezone
from beanie import Document, PydanticObjectId, Indexed
from pydantic import Field
from app.models.base import TimestampMixin

class HealthMetrics(Document, TimestampMixin):
    # Owner
    patient_id: Indexed(PydanticObjectId)

    # Blood Pressure (mmHg)
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None

    # Cardiovascular
    heart_rate: Optional[float] = None

    # Metabolic
    blood_glucose: Optional[float] = None
    body_temperature: Optional[float] = None

    # Respiratory
    spo2: Optional[float] = None
    respiratory_rate: Optional[float] = None

    # Anthropometric
    weight: Optional[float] = None
    height: Optional[float] = None
    bmi: Optional[float] = None

    # Metadata
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    device_source: Optional[str] = None
    notes: Optional[str] = None

    class Settings:
        name = "health_metrics"