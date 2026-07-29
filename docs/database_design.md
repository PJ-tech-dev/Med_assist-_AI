# MedAssist AI — Database Design

## Overview
All tables use:
- `UUID` as primary key (PostgreSQL native UUID)
- `created_at` / `updated_at` timestamps (timezone-aware)
- `is_deleted` boolean for soft deletes where applicable

---

## Table: `users`
> Module 1 — Auth foundation

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX |
| `full_name` | VARCHAR(255) | NOT NULL |
| `hashed_password` | VARCHAR(255) | NOT NULL |
| `is_active` | BOOLEAN | default TRUE |
| `is_verified` | BOOLEAN | default FALSE |
| `created_at` | TIMESTAMPTZ | server default NOW() |
| `updated_at` | TIMESTAMPTZ | server default NOW(), on update NOW() |

---

## Table: `patient_profiles`
> Module 2 — Patient Profile

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `user_id` | UUID | FK → users.id CASCADE, INDEX |
| `full_name` | VARCHAR(255) | NOT NULL |
| `date_of_birth` | DATE | NOT NULL |
| `gender` | VARCHAR(20) | NOT NULL — male/female/other |
| `blood_group` | VARCHAR(10) | nullable — A+/A-/B+/B-/AB+/AB-/O+/O- |
| `height_cm` | FLOAT | nullable |
| `weight_kg` | FLOAT | nullable |
| `phone_number` | VARCHAR(20) | nullable |
| `address` | TEXT | nullable |
| `emergency_contact_name` | VARCHAR(255) | nullable |
| `emergency_contact_phone` | VARCHAR(20) | nullable |
| `emergency_contact_relation` | VARCHAR(100) | nullable |
| `allergies` | TEXT | nullable, comma-separated |
| `chronic_diseases` | TEXT | nullable, comma-separated |
| `is_deleted` | BOOLEAN | default FALSE |
| `created_at` | TIMESTAMPTZ | server default NOW() |
| `updated_at` | TIMESTAMPTZ | server default NOW(), on update NOW() |

**Relationships:**
- `user_id` → `users.id` (many-to-one)
- One patient → many `medical_histories`
- One patient → many `medications`

---

## Table: `medical_histories`
> Module 2 — Medical History

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `patient_id` | UUID | FK → patient_profiles.id CASCADE, INDEX |
| `diagnosis` | VARCHAR(500) | NOT NULL |
| `visit_date` | DATE | NOT NULL |
| `doctor_name` | VARCHAR(255) | nullable |
| `hospital_name` | VARCHAR(255) | nullable |
| `notes` | TEXT | nullable |
| `attachments` | TEXT | nullable — JSON string of file paths (future S3) |
| `is_deleted` | BOOLEAN | default FALSE |
| `created_at` | TIMESTAMPTZ | server default NOW() |
| `updated_at` | TIMESTAMPTZ | server default NOW(), on update NOW() |

**Relationships:**
- `patient_id` → `patient_profiles.id` (many-to-one)

---

## Table: `medications`
> Module 2 — Medications

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default uuid4 |
| `patient_id` | UUID | FK → patient_profiles.id CASCADE, INDEX |
| `medicine_name` | VARCHAR(255) | NOT NULL |
| `dosage` | VARCHAR(100) | NOT NULL — e.g. "500mg" |
| `frequency` | VARCHAR(100) | NOT NULL — e.g. "twice daily" |
| `start_date` | DATE | NOT NULL |
| `end_date` | DATE | nullable |
| `is_active` | BOOLEAN | default TRUE |
| `prescribing_doctor` | VARCHAR(255) | nullable |
| `is_deleted` | BOOLEAN | default FALSE |
| `created_at` | TIMESTAMPTZ | server default NOW() |
| `updated_at` | TIMESTAMPTZ | server default NOW(), on update NOW() |

**Relationships:**
- `patient_id` → `patient_profiles.id` (many-to-one)

---

## Entity Relationship Diagram (Text)

```
users
  └── patient_profiles (user_id → users.id)
        ├── medical_histories (patient_id → patient_profiles.id)
        └── medications       (patient_id → patient_profiles.id)
```

---

## Soft Delete Strategy
Tables with `is_deleted`:
- `patient_profiles`
- `medical_histories`
- `medications`

All queries filter `WHERE is_deleted = FALSE` by default.
Hard deletes are never performed on these tables.
