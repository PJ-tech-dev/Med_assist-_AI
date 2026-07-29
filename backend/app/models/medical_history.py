from typing import Optional
from datetime import date
from beanie import Document, PydanticObjectId, Indexed
from app.models.base import TimestampMixin

class MedicalHistory(Document, TimestampMixin):
    patient_id: Indexed(PydanticObjectId)

    diagnosis: str
    visit_date: date
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    notes: Optional[str] = None
    attachments: Optional[str] = None

    is_deleted: bool = False

    class Settings:
        name = "medical_histories"