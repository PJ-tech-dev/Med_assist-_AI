from typing import Sequence
from beanie import PydanticObjectId
from fastapi import HTTPException, status
from pymongo import DESCENDING

from app.models.health_metrics import HealthMetrics
from app.models.patient_profile import PatientProfile
from app.schemas.health_metrics import HealthMetricsCreate


class HealthMetricsService:
    async def create_metrics(
        self, patient_id: PydanticObjectId, user_id: PydanticObjectId, payload: HealthMetricsCreate
    ) -> HealthMetrics:
        # Verify ownership
        patient = await PatientProfile.find_one(
            PatientProfile.id == patient_id,
            PatientProfile.user_id == user_id,
            PatientProfile.is_deleted == False,
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found."
            )

        metric = HealthMetrics(
            patient_id=patient_id,
            **payload.model_dump(exclude_unset=True)
        )
        await metric.insert()
        return metric

    async def get_recent_metrics(
        self, patient_id: PydanticObjectId, user_id: PydanticObjectId, limit: int = 50
    ) -> Sequence[HealthMetrics]:
        # Verify ownership
        patient = await PatientProfile.find_one(
            PatientProfile.id == patient_id,
            PatientProfile.user_id == user_id,
            PatientProfile.is_deleted == False,
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found."
            )

        result = await HealthMetrics.find(
            HealthMetrics.patient_id == patient_id
        ).sort([("recorded_at", DESCENDING)]).limit(limit).to_list()
        return result


health_metrics_service = HealthMetricsService()
