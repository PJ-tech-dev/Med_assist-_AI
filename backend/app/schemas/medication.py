from beanie import PydanticObjectId
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class MedicationCreate(BaseModel):
    medicine_name: str
    dosage: str
    frequency: str
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True
    prescribing_doctor: Optional[str] = None

    @field_validator("medicine_name", "dosage", "frequency")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @model_validator(mode="after")
    def validate_dates(self) -> "MedicationCreate":
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class MedicationUpdate(BaseModel):
    medicine_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    prescribing_doctor: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "MedicationUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class MedicationResponse(BaseModel):
    id: PydanticObjectId
    patient_id: PydanticObjectId
    medicine_name: str
    dosage: str
    frequency: str
    start_date: date
    end_date: Optional[date]
    is_active: bool
    prescribing_doctor: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
