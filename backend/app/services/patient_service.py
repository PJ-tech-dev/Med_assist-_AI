from typing import Optional
from beanie import PydanticObjectId
from beanie.operators import RegEx, Or
from fastapi import HTTPException, status

from app.models.patient_profile import PatientProfile
from app.models.medical_history import MedicalHistory
from app.models.medication import Medication
from app.models.health_metrics import HealthMetrics
from app.schemas.patient import PatientProfileCreate, PatientProfileUpdate
from app.schemas.medical_history import MedicalHistoryCreate, MedicalHistoryUpdate
from app.schemas.medication import MedicationCreate, MedicationUpdate
from app.schemas.health_metrics import HealthMetricsCreate


class PatientService:
    """Service layer for all patient-related database operations using Beanie ODM."""

    # ------------------------------------------------------------------ #
    #  Patient Profile                                                     #
    # ------------------------------------------------------------------ #

    async def create_profile(
        self, user_id: PydanticObjectId, payload: PatientProfileCreate
    ) -> PatientProfile:
        profile = PatientProfile(user_id=user_id, **payload.model_dump())
        await profile.insert()
        return profile

    async def get_profile(
        self, profile_id: PydanticObjectId, user_id: PydanticObjectId
    ) -> PatientProfile:
        profile = await PatientProfile.find_one(
            PatientProfile.id == profile_id,
            PatientProfile.user_id == user_id,
            PatientProfile.is_deleted == False,
        )
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
        return profile

    async def list_profiles(
        self,
        user_id: PydanticObjectId,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        gender: Optional[str] = None,
        blood_group: Optional[str] = None,
    ) -> tuple[int, list[PatientProfile]]:
        
        query_conditions = [
            PatientProfile.user_id == user_id,
            PatientProfile.is_deleted == False
        ]
        
        if search:
            search_cond = Or(
                RegEx(PatientProfile.full_name, f".*{search}.*", "i"),
                RegEx(PatientProfile.chronic_diseases, f".*{search}.*", "i"),
                RegEx(PatientProfile.allergies, f".*{search}.*", "i")
            )
            query_conditions.append(search_cond)
            
        if gender:
            query_conditions.append(PatientProfile.gender == gender.lower())
        if blood_group:
            query_conditions.append(PatientProfile.blood_group == blood_group.upper())

        query = PatientProfile.find(*query_conditions)
        
        total = await query.count()
        result = await query.skip((page - 1) * page_size).limit(page_size).to_list()
        
        return total, result

    async def update_profile(
        self,
        profile_id: PydanticObjectId,
        user_id: PydanticObjectId,
        payload: PatientProfileUpdate,
    ) -> PatientProfile:
        profile = await self.get_profile(profile_id, user_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)
        await profile.save()
        return profile

    async def delete_profile(
        self, profile_id: PydanticObjectId, user_id: PydanticObjectId
    ) -> None:
        profile = await self.get_profile(profile_id, user_id)
        profile.is_deleted = True
        await profile.save()

    # ------------------------------------------------------------------ #
    #  Medical History                                                     #
    # ------------------------------------------------------------------ #

    async def _get_profile_or_404(
        self, patient_id: PydanticObjectId, user_id: PydanticObjectId
    ) -> PatientProfile:
        """Verify the patient belongs to the requesting user."""
        return await self.get_profile(patient_id, user_id)

    async def add_medical_history(
        self,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        payload: MedicalHistoryCreate,
    ) -> MedicalHistory:
        await self._get_profile_or_404(patient_id, user_id)
        record = MedicalHistory(patient_id=patient_id, **payload.model_dump())
        await record.insert()
        return record

    async def list_medical_history(
        self,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[int, list[MedicalHistory]]:
        await self._get_profile_or_404(patient_id, user_id)
        query = MedicalHistory.find(
            MedicalHistory.patient_id == patient_id,
            MedicalHistory.is_deleted == False
        )
        total = await query.count()
        result = await query.skip((page - 1) * page_size).limit(page_size).to_list()
        return total, result

    async def update_medical_history(
        self,
        record_id: PydanticObjectId,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        payload: MedicalHistoryUpdate,
    ) -> MedicalHistory:
        await self._get_profile_or_404(patient_id, user_id)
        record = await MedicalHistory.find_one(
            MedicalHistory.id == record_id,
            MedicalHistory.patient_id == patient_id,
            MedicalHistory.is_deleted == False
        )
        if not record:
            raise HTTPException(status_code=404, detail="Medical history record not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        await record.save()
        return record

    async def delete_medical_history(
        self, record_id: PydanticObjectId, patient_id: PydanticObjectId, user_id: PydanticObjectId
    ) -> None:
        await self._get_profile_or_404(patient_id, user_id)
        record = await MedicalHistory.find_one(
            MedicalHistory.id == record_id,
            MedicalHistory.patient_id == patient_id,
            MedicalHistory.is_deleted == False
        )
        if not record:
            raise HTTPException(status_code=404, detail="Medical history record not found")
        record.is_deleted = True
        await record.save()

    # ------------------------------------------------------------------ #
    #  Medications                                                         #
    # ------------------------------------------------------------------ #

    async def add_medication(
        self,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        payload: MedicationCreate,
    ) -> Medication:
        await self._get_profile_or_404(patient_id, user_id)
        med = Medication(patient_id=patient_id, **payload.model_dump())
        await med.insert()
        return med

    async def list_medications(
        self,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        active_only: bool = False,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[int, list[Medication]]:
        await self._get_profile_or_404(patient_id, user_id)
        query_conds = [
            Medication.patient_id == patient_id,
            Medication.is_deleted == False
        ]
        if active_only:
            query_conds.append(Medication.is_active == True)
            
        query = Medication.find(*query_conds)
        total = await query.count()
        result = await query.skip((page - 1) * page_size).limit(page_size).to_list()
        return total, result

    async def update_medication(
        self,
        med_id: PydanticObjectId,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        payload: MedicationUpdate,
    ) -> Medication:
        await self._get_profile_or_404(patient_id, user_id)
        med = await Medication.find_one(
            Medication.id == med_id,
            Medication.patient_id == patient_id,
            Medication.is_deleted == False
        )
        if not med:
            raise HTTPException(status_code=404, detail="Medication not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(med, field, value)
        await med.save()
        return med

    async def delete_medication(
        self, med_id: PydanticObjectId, patient_id: PydanticObjectId, user_id: PydanticObjectId
    ) -> None:
        await self._get_profile_or_404(patient_id, user_id)
        med = await Medication.find_one(
            Medication.id == med_id,
            Medication.patient_id == patient_id,
            Medication.is_deleted == False
        )
        if not med:
            raise HTTPException(status_code=404, detail="Medication not found")
        med.is_deleted = True
        await med.save()

    # ------------------------------------------------------------------ #
    #  Health Metrics (Vitals)                                             #
    # ------------------------------------------------------------------ #

    async def add_vitals(
        self,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        payload: HealthMetricsCreate,
    ) -> HealthMetrics:
        await self._get_profile_or_404(patient_id, user_id)
        metric = HealthMetrics(patient_id=patient_id, **payload.model_dump())
        await metric.insert()
        return metric

    async def list_vitals(
        self,
        patient_id: PydanticObjectId,
        user_id: PydanticObjectId,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, list[HealthMetrics]]:
        await self._get_profile_or_404(patient_id, user_id)
        query = HealthMetrics.find(HealthMetrics.patient_id == patient_id).sort(-HealthMetrics.recorded_at)
        total = await query.count()
        result = await query.skip((page - 1) * page_size).limit(page_size).to_list()
        return total, result


patient_service = PatientService()