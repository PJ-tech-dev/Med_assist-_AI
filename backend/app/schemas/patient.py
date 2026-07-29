from beanie import PydanticObjectId
from datetime import date, datetime
from typing import Optional
import re

from pydantic import BaseModel, field_validator, model_validator


VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
VALID_GENDERS = {"male", "female", "other"}
PHONE_REGEX = re.compile(r"^\+?[1-9]\d{6,14}$")


def _validate_phone(v: Optional[str]) -> Optional[str]:
    if v and not PHONE_REGEX.match(v):
        raise ValueError("Invalid phone number format")
    return v


class PatientProfileCreate(BaseModel):
    full_name: str
    date_of_birth: date
    gender: str
    blood_group: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    allergies: Optional[str] = None
    chronic_diseases: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v.lower() not in VALID_GENDERS:
            raise ValueError(f"gender must be one of {VALID_GENDERS}")
        return v.lower()

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v: Optional[str]) -> Optional[str]:
        if v and v.upper() not in VALID_BLOOD_GROUPS:
            raise ValueError(f"blood_group must be one of {VALID_BLOOD_GROUPS}")
        return v.upper() if v else v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phones(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)

    @field_validator("height_cm", "weight_kg")
    @classmethod
    def validate_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Value must be positive")
        return v


class PatientProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    allergies: Optional[str] = None
    chronic_diseases: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in VALID_GENDERS:
            raise ValueError(f"gender must be one of {VALID_GENDERS}")
        return v.lower() if v else v

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v: Optional[str]) -> Optional[str]:
        if v and v.upper() not in VALID_BLOOD_GROUPS:
            raise ValueError(f"blood_group must be one of {VALID_BLOOD_GROUPS}")
        return v.upper() if v else v

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phones(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)


class PatientProfileResponse(BaseModel):
    id: PydanticObjectId
    user_id: PydanticObjectId
    full_name: str
    date_of_birth: date
    gender: str
    blood_group: Optional[str]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    phone_number: Optional[str]
    address: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    emergency_contact_relation: Optional[str]
    allergies: Optional[str]
    chronic_diseases: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedPatients(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PatientProfileResponse]
