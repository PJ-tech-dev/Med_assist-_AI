from typing import List
from beanie import PydanticObjectId

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.health_metrics import HealthMetricsCreate, HealthMetricsResponse
from app.services.health_metrics_service import health_metrics_service

router = APIRouter(prefix="/patients", tags=["health-metrics"])

@router.post(
    "/{patient_id}/health-metrics",
    response_model=HealthMetricsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_health_metrics(
    patient_id: PydanticObjectId,
    payload: HealthMetricsCreate,
    current_user: User = Depends(get_current_user),
):
    """Log live vital telemetry (e.g. from SmartWatch)."""
    return await health_metrics_service.create_metrics(patient_id, current_user.id, payload)


@router.get(
    "/{patient_id}/health-metrics",
    response_model=List[HealthMetricsResponse],
)
async def list_health_metrics(
    patient_id: PydanticObjectId,
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    """Retrieve recent vital telemetry for analytics."""
    return await health_metrics_service.get_recent_metrics(patient_id, current_user.id, limit)
