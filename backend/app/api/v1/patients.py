from typing import Optional
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.patient import (
    PatientProfileCreate,
    PatientProfileUpdate,
    PatientProfileResponse,
    PaginatedPatients,
)
from app.schemas.medical_history import (
    MedicalHistoryCreate,
    MedicalHistoryUpdate,
    MedicalHistoryResponse,
)
from app.schemas.medication import MedicationCreate, MedicationUpdate, MedicationResponse
from app.schemas.health_metrics import HealthMetricsCreate, HealthMetricsResponse
from app.services.patient_service import patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


# ------------------------------------------------------------------ #
#  Patient Profile Endpoints                                           #
# ------------------------------------------------------------------ #

@router.post("", response_model=PatientProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientProfileCreate,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.create_profile(current_user.id, payload)


@router.get("", response_model=PaginatedPatients)
async def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    blood_group: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    total, items = await patient_service.list_profiles(
        current_user.id, page, page_size, search, gender, blood_group
    )
    return PaginatedPatients(total=total, page=page, page_size=page_size, items=items)


@router.get("/{patient_id}", response_model=PatientProfileResponse)
async def get_patient(
    patient_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.get_profile(patient_id, current_user.id)


@router.patch("/{patient_id}", response_model=PatientProfileResponse)
async def update_patient(
    patient_id: PydanticObjectId,
    payload: PatientProfileUpdate,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.update_profile(patient_id, current_user.id, payload)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    await patient_service.delete_profile(patient_id, current_user.id)


# ------------------------------------------------------------------ #
#  Medical History Endpoints                                           #
# ------------------------------------------------------------------ #

@router.post(
    "/{patient_id}/history",
    response_model=MedicalHistoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_history(
    patient_id: PydanticObjectId,
    payload: MedicalHistoryCreate,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.add_medical_history(patient_id, current_user.id, payload)


@router.get("/{patient_id}/history", response_model=dict)
async def list_history(
    patient_id: PydanticObjectId,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    total, items = await patient_service.list_medical_history(
        patient_id, current_user.id, page, page_size
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [MedicalHistoryResponse.model_validate(i) for i in items],
    }


@router.patch("/{patient_id}/history/{record_id}", response_model=MedicalHistoryResponse)
async def update_history(
    patient_id: PydanticObjectId,
    record_id: PydanticObjectId,
    payload: MedicalHistoryUpdate,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.update_medical_history(
        record_id, patient_id, current_user.id, payload
    )


@router.delete("/{patient_id}/history/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(
    patient_id: PydanticObjectId,
    record_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    await patient_service.delete_medical_history(record_id, patient_id, current_user.id)


# ------------------------------------------------------------------ #
#  Medication Endpoints                                                #
# ------------------------------------------------------------------ #

@router.post(
    "/{patient_id}/medications",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_medication(
    patient_id: PydanticObjectId,
    payload: MedicationCreate,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.add_medication(patient_id, current_user.id, payload)


@router.get("/{patient_id}/medications", response_model=dict)
async def list_medications(
    patient_id: PydanticObjectId,
    active_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    total, items = await patient_service.list_medications(
        patient_id, current_user.id, active_only, page, page_size
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [MedicationResponse.model_validate(i) for i in items],
    }


@router.patch("/{patient_id}/medications/{med_id}", response_model=MedicationResponse)
async def update_medication(
    patient_id: PydanticObjectId,
    med_id: PydanticObjectId,
    payload: MedicationUpdate,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.update_medication(
        med_id, patient_id, current_user.id, payload
    )


@router.delete("/{patient_id}/medications/{med_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    patient_id: PydanticObjectId,
    med_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    await patient_service.delete_medication(med_id, patient_id, current_user.id)


# ------------------------------------------------------------------ #
#  Health Metrics (Vitals) Endpoints                                   #
# ------------------------------------------------------------------ #

@router.post(
    "/{patient_id}/vitals",
    response_model=HealthMetricsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_vitals(
    patient_id: PydanticObjectId,
    payload: HealthMetricsCreate,
    current_user: User = Depends(get_current_user),
):
    return await patient_service.add_vitals(patient_id, current_user.id, payload)


@router.get("/{patient_id}/vitals", response_model=dict)
async def list_vitals(
    patient_id: PydanticObjectId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    total, items = await patient_service.list_vitals(
        patient_id, current_user.id, page, page_size
    )
    return {"total": total, "page": page, "page_size": page_size, "items": items}