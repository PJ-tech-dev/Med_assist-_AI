import pytest
from datetime import date, timedelta
from pydantic import ValidationError

from app.schemas.patient import PatientProfileCreate, PatientProfileUpdate
from app.schemas.medical_history import MedicalHistoryCreate
from app.schemas.medication import MedicationCreate


# ------------------------------------------------------------------ #
#  PatientProfileCreate Validation                                     #
# ------------------------------------------------------------------ #

def _valid_patient(**overrides) -> dict:
    base = {
        "full_name": "John Doe",
        "date_of_birth": date(1990, 1, 1),
        "gender": "male",
        "blood_group": "O+",
        "phone_number": "+911234567890",
    }
    return {**base, **overrides}


def test_patient_create_valid():
    p = PatientProfileCreate(**_valid_patient())
    assert p.gender == "male"
    assert p.blood_group == "O+"


def test_patient_create_invalid_gender():
    with pytest.raises(ValidationError, match="gender"):
        PatientProfileCreate(**_valid_patient(gender="alien"))


def test_patient_create_invalid_blood_group():
    with pytest.raises(ValidationError, match="blood_group"):
        PatientProfileCreate(**_valid_patient(blood_group="Z+"))


def test_patient_create_future_dob():
    with pytest.raises(ValidationError, match="date_of_birth"):
        PatientProfileCreate(**_valid_patient(date_of_birth=date.today() + timedelta(days=1)))


def test_patient_create_invalid_phone():
    with pytest.raises(ValidationError, match="phone"):
        PatientProfileCreate(**_valid_patient(phone_number="abc"))


def test_patient_create_negative_height():
    with pytest.raises(ValidationError):
        PatientProfileCreate(**_valid_patient(height_cm=-10.0))


# ------------------------------------------------------------------ #
#  MedicalHistoryCreate Validation                                     #
# ------------------------------------------------------------------ #

def test_medical_history_valid():
    h = MedicalHistoryCreate(diagnosis="Flu", visit_date=date.today())
    assert h.diagnosis == "Flu"


def test_medical_history_future_date():
    with pytest.raises(ValidationError, match="future"):
        MedicalHistoryCreate(diagnosis="Flu", visit_date=date.today() + timedelta(days=1))


def test_medical_history_empty_diagnosis():
    with pytest.raises(ValidationError, match="empty"):
        MedicalHistoryCreate(diagnosis="   ", visit_date=date.today())


# ------------------------------------------------------------------ #
#  MedicationCreate Validation                                         #
# ------------------------------------------------------------------ #

def test_medication_valid():
    m = MedicationCreate(
        medicine_name="Paracetamol",
        dosage="500mg",
        frequency="twice daily",
        start_date=date.today(),
    )
    assert m.medicine_name == "Paracetamol"


def test_medication_end_before_start():
    with pytest.raises(ValidationError, match="end_date"):
        MedicationCreate(
            medicine_name="Paracetamol",
            dosage="500mg",
            frequency="twice daily",
            start_date=date.today(),
            end_date=date.today() - timedelta(days=1),
        )


def test_medication_empty_name():
    with pytest.raises(ValidationError, match="empty"):
        MedicationCreate(
            medicine_name="  ",
            dosage="500mg",
            frequency="twice daily",
            start_date=date.today(),
        )
