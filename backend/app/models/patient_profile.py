from typing import Optional
from datetime import date
from beanie import Document, PydanticObjectId, Indexed
from app.models.base import TimestampMixin

class PatientProfile(Document, TimestampMixin):
    # Owner
    user_id: Indexed(PydanticObjectId)

    # Demographics
    full_name: str
    date_of_birth: date
    gender: str
    blood_group: Optional[str] = None

    # Physical
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None

    # Contact & Address
    phone_number: Optional[str] = None
    address: Optional[str] = None

    # Emergency Contact
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None

    # Medical flags
    allergies: Optional[str] = None
    chronic_diseases: Optional[str] = None

    # Soft delete
    is_deleted: bool = False

    class Settings:
        name = "patient_profiles"