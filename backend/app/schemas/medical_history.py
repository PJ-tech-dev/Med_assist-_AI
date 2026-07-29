from beanie import PydanticObjectId
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class MedicalHistoryCreate(BaseModel):
    diagnosis: str
    visit_date: date
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    notes: Optional[str] = None
    attachments: Optional[str] = None  # JSON string of file paths

    @field_validator("visit_date")
    @classmethod
    def validate_visit_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("visit_date cannot be in the future")
        return v

    @field_validator("diagnosis")
    @classmethod
    def validate_diagnosis(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("diagnosis cannot be empty")
        return v.strip()


class MedicalHistoryUpdate(BaseModel):
    diagnosis: Optional[str] = None
    visit_date: Optional[date] = None
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    notes: Optional[str] = None
    attachments: Optional[str] = None

    @field_validator("visit_date")
    @classmethod
    def validate_visit_date(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("visit_date cannot be in the future")
        return v


class MedicalHistoryResponse(BaseModel):
    id: PydanticObjectId
    patient_id: PydanticObjectId
    diagnosis: str
    visit_date: date
    doctor_name: Optional[str]
    hospital_name: Optional[str]
    notes: Optional[str]
    attachments: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
