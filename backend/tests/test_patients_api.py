import pytest
from datetime import date
from httpx import AsyncClient


PATIENT_PAYLOAD = {
    "full_name": "Jane Doe",
    "date_of_birth": "1992-05-15",
    "gender": "female",
    "blood_group": "A+",
    "phone_number": "+911234567890",
    "allergies": "Penicillin",
    "chronic_diseases": "Diabetes",
}


@pytest.mark.asyncio
async def test_create_patient(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Jane Doe"
    assert data["blood_group"] == "A+"
    return data["id"]


@pytest.mark.asyncio
async def test_list_patients(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/patients", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_get_patient(client: AsyncClient, auth_headers: dict):
    # Create first
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=auth_headers)
    patient_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/patients/{patient_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == patient_id


@pytest.mark.asyncio
async def test_update_patient(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=auth_headers)
    patient_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/patients/{patient_id}",
        json={"full_name": "Jane Updated"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Jane Updated"


@pytest.mark.asyncio
async def test_delete_patient(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=auth_headers)
    patient_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/patients/{patient_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Confirm soft-deleted — should 404
    resp = await client.get(f"/api/v1/patients/{patient_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_medical_history(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=auth_headers)
    patient_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/patients/{patient_id}/history",
        json={"diagnosis": "Hypertension", "visit_date": "2024-01-10", "doctor_name": "Dr. Smith"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["diagnosis"] == "Hypertension"


@pytest.mark.asyncio
async def test_add_medication(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=auth_headers)
    patient_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/patients/{patient_id}/medications",
        json={
            "medicine_name": "Metformin",
            "dosage": "500mg",
            "frequency": "twice daily",
            "start_date": "2024-01-01",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["medicine_name"] == "Metformin"


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    resp = await client.get("/api/v1/patients")
    assert resp.status_code == 403
