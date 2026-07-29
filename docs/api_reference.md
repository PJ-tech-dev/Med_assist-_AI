# MedAssist AI — API Reference

**Base URL:** `http://localhost:8000/api/v1`
**Auth:** All protected endpoints require `Authorization: Bearer <access_token>`

---

## Auth Endpoints

### POST `/auth/register`
Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "full_name": "John Doe",
  "password": "SecurePass123!"
}
```
**Response `201`:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true
}
```

---

### POST `/auth/login`
Login and receive JWT tokens.

**Request:**
```json
{ "email": "user@example.com", "password": "SecurePass123!" }
```
**Response `200`:**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

---

### POST `/auth/refresh`
Refresh access token.

**Request:**
```json
{ "refresh_token": "<jwt>" }
```
**Response `200`:** Same as login response.

---

## Patient Profile Endpoints
> All endpoints require JWT auth.

### POST `/patients`
Create a patient profile.

**Request:**
```json
{
  "full_name": "Jane Doe",
  "date_of_birth": "1992-05-15",
  "gender": "female",
  "blood_group": "A+",
  "phone_number": "+911234567890",
  "height_cm": 165.0,
  "weight_kg": 60.0,
  "address": "123 Main St, Chennai",
  "emergency_contact_name": "John Doe",
  "emergency_contact_phone": "+910987654321",
  "emergency_contact_relation": "Spouse",
  "allergies": "Penicillin, Dust",
  "chronic_diseases": "Diabetes Type 2"
}
```
**Response `201`:** Full `PatientProfileResponse` object.

---

### GET `/patients`
List all patient profiles with pagination, search, and filtering.

**Query Params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 10 | Items per page (max 100) |
| `search` | string | - | Search by name, allergies, chronic diseases |
| `gender` | string | - | Filter by gender |
| `blood_group` | string | - | Filter by blood group |

**Response `200`:**
```json
{
  "total": 5,
  "page": 1,
  "page_size": 10,
  "items": [ { "...PatientProfileResponse" } ]
}
```

---

### GET `/patients/{patient_id}`
Get a single patient profile.

**Response `200`:** `PatientProfileResponse`
**Response `404`:** Patient not found.

---

### PATCH `/patients/{patient_id}`
Partially update a patient profile.

**Request:** Any subset of `PatientProfileCreate` fields.
**Response `200`:** Updated `PatientProfileResponse`.

---

### DELETE `/patients/{patient_id}`
Soft-delete a patient profile.

**Response `204`:** No content.

---

## Medical History Endpoints

### POST `/patients/{patient_id}/history`
Add a medical history record.

**Request:**
```json
{
  "diagnosis": "Hypertension",
  "visit_date": "2024-01-10",
  "doctor_name": "Dr. Smith",
  "hospital_name": "City Hospital",
  "notes": "Blood pressure 140/90"
}
```
**Response `201`:** `MedicalHistoryResponse`

---

### GET `/patients/{patient_id}/history`
List medical history with pagination.

**Query Params:** `page`, `page_size`
**Response `200`:**
```json
{
  "total": 3,
  "page": 1,
  "page_size": 10,
  "items": [ { "...MedicalHistoryResponse" } ]
}
```

---

### PATCH `/patients/{patient_id}/history/{record_id}`
Update a medical history record.

**Response `200`:** Updated `MedicalHistoryResponse`.

---

### DELETE `/patients/{patient_id}/history/{record_id}`
Soft-delete a medical history record.

**Response `204`:** No content.

---

## Medication Endpoints

### POST `/patients/{patient_id}/medications`
Add a medication.

**Request:**
```json
{
  "medicine_name": "Metformin",
  "dosage": "500mg",
  "frequency": "twice daily",
  "start_date": "2024-01-01",
  "end_date": "2024-06-01",
  "is_active": true,
  "prescribing_doctor": "Dr. Patel"
}
```
**Response `201`:** `MedicationResponse`

---

### GET `/patients/{patient_id}/medications`
List medications with pagination and active filter.

**Query Params:** `page`, `page_size`, `active_only` (bool)
**Response `200`:** Paginated `MedicationResponse` list.

---

### PATCH `/patients/{patient_id}/medications/{med_id}`
Update a medication.

**Response `200`:** Updated `MedicationResponse`.

---

### DELETE `/patients/{patient_id}/medications/{med_id}`
Soft-delete a medication.

**Response `204`:** No content.

---

## Chat Endpoints
> All endpoints require JWT auth.

### POST `/chat`
Send a message to the AI orchestrator.

**Request:**
```json
{
  "message": "Is it safe to take ibuprofen with warfarin?",
  "session_id": "uuid-optional",
  "patient_profile_id": "uuid-optional"
}
```
**Response `200`:**
```json
{
  "session_id": "uuid",
  "final_response": "Based on the information provided...",
  "detected_intents": ["medicine_safety"],
  "selected_agents": ["MedicineSafetyAgent"],
  "agent_outputs": [
    {
      "agent_name": "MedicineSafetyAgent",
      "response": "...",
      "confidence": 0.72,
      "execution_time_ms": 1840.5,
      "error": null
    }
  ],
  "total_execution_ms": 2100.3
}
```

**MedicineSafetyAgent structured_result (in metadata):**
```json
{
  "medications": [{"raw": "ibuprofen", "generic_name": "ibuprofen", "dosage_mentioned": null}],
  "interactions": [{"drug_a": "ibuprofen", "drug_b": "warfarin", "severity": "major", "description": "Increased bleeding risk"}],
  "contraindications": [],
  "allergy_alerts": [],
  "duplicate_warnings": [],
  "dosage_validation": [],
  "severity": "warning",
  "confidence": 0.72,
  "recommendations": ["Consult your pharmacist before taking these together."],
  "sources": ["NIH", "FDA"],
  "requires_immediate_attention": false,
  "disclaimer": "This information is for educational purposes only..."
}
```

**SymptomAnalysisAgent structured_result (in metadata):**
```json
{
  "symptoms": [{"raw": "headache", "normalized": "headache", "duration": "2 days"}],
  "possible_conditions": [{"name": "Tension Headache", "likelihood": "high", "reasoning": "..."}],
  "severity": "mild",
  "confidence": 0.65,
  "requires_followup": true,
  "followup_questions": ["What is your current temperature?"],
  "recommendations": ["Rest", "Stay hydrated"],
  "sources": ["WHO", "CDC"],
  "is_emergency": false,
  "disclaimer": "..."
}
```

---

### GET `/chat/sessions`
List all active chat sessions.

**Response `200`:** Array of `SessionResponse` objects.

---

### DELETE `/chat/sessions/{session_id}`
Soft-close a chat session.

**Response `204`:** No content.

---

## Error Responses

| Status | Meaning |
|--------|---------|
| `400` | Validation error / bad request |
| `401` | Missing or invalid JWT |
| `403` | Forbidden |
| `404` | Resource not found |
| `422` | Pydantic validation error |
