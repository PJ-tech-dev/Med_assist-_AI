from typing import Optional
from datetime import date
from beanie import Document, PydanticObjectId, Indexed
from app.models.base import TimestampMixin

class Medication(Document, TimestampMixin):
    patient_id: Indexed(PydanticObjectId)

    medicine_name: str
    dosage: str
    frequency: str
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True
    prescribing_doctor: Optional[str] = None

    is_deleted: bool = False

    class Settings:
        name = "medications"