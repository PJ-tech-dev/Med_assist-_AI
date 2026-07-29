from beanie import PydanticObjectId
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthMetricsBase(BaseModel):
    systolic_bp: Optional[float] = Field(None, ge=0, le=300, description="Systolic Blood Pressure (mmHg)")
    diastolic_bp: Optional[float] = Field(None, ge=0, le=200, description="Diastolic Blood Pressure (mmHg)")
    heart_rate: Optional[float] = Field(None, ge=0, le=300, description="Heart Rate (bpm)")
    blood_glucose: Optional[float] = Field(None, ge=0, le=1000, description="Blood Glucose (mg/dL)")
    body_temperature: Optional[float] = Field(None, ge=30, le=45, description="Body Temperature (°C)")
    spo2: Optional[float] = Field(None, ge=0, le=100, description="Oxygen Saturation (%)")
    respiratory_rate: Optional[float] = Field(None, ge=0, le=100, description="Respiratory Rate (breaths/min)")
    weight: Optional[float] = Field(None, ge=0, le=500, description="Weight (kg)")
    height: Optional[float] = Field(None, ge=0, le=300, description="Height (cm)")
    bmi: Optional[float] = Field(None, ge=0, le=100, description="Body Mass Index (kg/m²)")
    device_source: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class HealthMetricsCreate(HealthMetricsBase):
    pass


class HealthMetricsUpdate(HealthMetricsBase):
    pass


class HealthMetricsResponse(HealthMetricsBase):
    id: PydanticObjectId
    patient_id: PydanticObjectId
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
