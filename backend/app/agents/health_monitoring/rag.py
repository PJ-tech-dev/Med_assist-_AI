"""
HealthKnowledgeRetriever — ChromaDB RAG for clinical reference ranges.

Sources: WHO, American Heart Association (AHA), NIH, MedlinePlus.
Collection: health_monitoring_knowledge
"""

import logging
from typing import Optional

try:
    import chromadb
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

from app.core.settings import settings

logger = logging.getLogger("health_monitoring.rag")

# ------------------------------------------------------------------ #
#  Seed documents — clinical reference ranges from trusted sources   #
# ------------------------------------------------------------------ #
_SEED_DOCUMENTS = [
    {
        "id": "aha_bp_classification",
        "text": (
            "Blood Pressure Classification (American Heart Association, 2017): "
            "Normal: systolic <120 mmHg AND diastolic <80 mmHg. "
            "Elevated: systolic 120–129 mmHg AND diastolic <80 mmHg. "
            "High Blood Pressure Stage 1: systolic 130–139 mmHg OR diastolic 80–89 mmHg. "
            "High Blood Pressure Stage 2: systolic ≥140 mmHg OR diastolic ≥90 mmHg. "
            "Hypertensive Crisis: systolic >180 mmHg AND/OR diastolic >120 mmHg — seek emergency care. "
            "Low blood pressure (hypotension): systolic <90 mmHg or diastolic <60 mmHg."
        ),
        "source": "American Heart Association",
        "category": "blood_pressure",
    },
    {
        "id": "who_heart_rate",
        "text": (
            "Heart Rate Reference Ranges (WHO / NIH): "
            "Normal resting heart rate for adults: 60–100 beats per minute (bpm). "
            "Bradycardia (slow): <60 bpm — may be normal in athletes; consult physician if symptomatic. "
            "Tachycardia (fast): >100 bpm at rest — may indicate fever, dehydration, anxiety, or cardiac issues. "
            "Severe tachycardia: >150 bpm — seek immediate medical attention. "
            "Athletes may have resting heart rates of 40–60 bpm, which is normal."
        ),
        "source": "WHO / NIH",
        "category": "heart_rate",
    },
    {
        "id": "ada_blood_glucose",
        "text": (
            "Blood Glucose Reference Ranges (American Diabetes Association / NIH): "
            "Fasting blood glucose: Normal <100 mg/dL; Prediabetes 100–125 mg/dL; Diabetes ≥126 mg/dL. "
            "2-hour postprandial: Normal <140 mg/dL; Prediabetes 140–199 mg/dL; Diabetes ≥200 mg/dL. "
            "Random blood glucose: Diabetes suspected if ≥200 mg/dL with symptoms. "
            "Hypoglycemia: <70 mg/dL — requires immediate treatment. "
            "Severe hypoglycemia: <54 mg/dL — emergency. "
            "Target for diabetic patients (ADA): fasting 80–130 mg/dL; postprandial <180 mg/dL."
        ),
        "source": "American Diabetes Association / NIH",
        "category": "blood_glucose",
    },
    {
        "id": "who_spo2",
        "text": (
            "Oxygen Saturation (SpO2) Reference Ranges (WHO / NIH): "
            "Normal SpO2: 95–100%. "
            "Mild hypoxemia: 91–94% — monitor closely, consider supplemental oxygen. "
            "Moderate hypoxemia: 86–90% — supplemental oxygen required. "
            "Severe hypoxemia: ≤85% — emergency, immediate medical attention required. "
            "For COPD patients, acceptable SpO2 may be 88–92%. "
            "SpO2 below 90% is generally considered a medical emergency."
        ),
        "source": "WHO / NIH",
        "category": "spo2",
    },
    {
        "id": "who_body_temperature",
        "text": (
            "Body Temperature Reference Ranges (WHO / MedlinePlus): "
            "Normal oral temperature: 36.1–37.2°C (97–99°F). "
            "Low-grade fever: 37.3–38.0°C (99.1–100.4°F). "
            "Fever: ≥38.0°C (100.4°F) — indicates infection or inflammation. "
            "High fever: ≥39.5°C (103.1°F) — requires medical evaluation. "
            "Hyperpyrexia: ≥41.0°C (105.8°F) — medical emergency. "
            "Hypothermia: <35.0°C (95°F) — medical emergency. "
            "Rectal temperature is ~0.5°C higher than oral; axillary is ~0.5°C lower."
        ),
        "source": "WHO / MedlinePlus",
        "category": "body_temperature",
    },
    {
        "id": "who_bmi_classification",
        "text": (
            "BMI Classification (WHO): "
            "Underweight: BMI <18.5 kg/m². "
            "Normal weight: BMI 18.5–24.9 kg/m². "
            "Overweight: BMI 25.0–29.9 kg/m². "
            "Obesity Class I: BMI 30.0–34.9 kg/m². "
            "Obesity Class II: BMI 35.0–39.9 kg/m². "
            "Obesity Class III (severe): BMI ≥40.0 kg/m². "
            "For Asian populations, WHO recommends lower cut-offs: overweight ≥23 kg/m², obese ≥27.5 kg/m²."
        ),
        "source": "WHO",
        "category": "bmi",
    },
    {
        "id": "nih_respiratory_rate",
        "text": (
            "Respiratory Rate Reference Ranges (NIH / MedlinePlus): "
            "Normal adult respiratory rate: 12–20 breaths per minute. "
            "Bradypnea (slow): <12 breaths/min — may indicate CNS depression or metabolic alkalosis. "
            "Tachypnea (fast): >20 breaths/min — may indicate fever, anxiety, respiratory distress, or sepsis. "
            "Severe tachypnea: >30 breaths/min — requires urgent medical evaluation. "
            "Respiratory rate is a sensitive early indicator of clinical deterioration."
        ),
        "source": "NIH / MedlinePlus",
        "category": "respiratory_rate",
    },
    {
        "id": "aha_bp_age_adjusted",
        "text": (
            "Age-Adjusted Blood Pressure Considerations (AHA / NIH): "
            "Elderly patients (≥65 years): Target systolic BP <130 mmHg per AHA 2017 guidelines. "
            "Children and adolescents: BP is age, sex, and height percentile-based. "
            "Isolated systolic hypertension (systolic ≥140, diastolic <90) is common in elderly. "
            "White coat hypertension: elevated in clinical settings, normal at home — ambulatory monitoring recommended. "
            "Orthostatic hypotension: drop of ≥20 mmHg systolic or ≥10 mmHg diastolic within 3 minutes of standing."
        ),
        "source": "AHA / NIH",
        "category": "blood_pressure",
    },
    {
        "id": "nih_glucose_age",
        "text": (
            "Blood Glucose Considerations by Age and Condition (NIH / ADA): "
            "Elderly patients: less strict targets acceptable — fasting 80–180 mg/dL. "
            "Pregnant women (gestational diabetes): fasting <95 mg/dL; 1-hour postprandial <140 mg/dL. "
            "Children with Type 1 diabetes: fasting 80–130 mg/dL; bedtime 90–150 mg/dL. "
            "HbA1c target for most adults with diabetes: <7.0% (ADA). "
            "Continuous glucose monitoring target: 70–180 mg/dL for >70% of time."
        ),
        "source": "NIH / ADA",
        "category": "blood_glucose",
    },
    {
        "id": "medlineplus_vitals_monitoring",
        "text": (
            "Vital Signs Monitoring Guidelines (MedlinePlus / NIH): "
            "Vital signs include temperature, pulse, respiration rate, and blood pressure. "
            "They are the most basic measures of body function. "
            "Monitoring trends over time is more informative than single readings. "
            "Consistent elevation or decline in any vital sign warrants medical evaluation. "
            "Home monitoring devices should be validated and calibrated regularly. "
            "Readings should be taken at consistent times (e.g., morning, before meals) for trend accuracy. "
            "Patients with chronic conditions (hypertension, diabetes, heart disease) should monitor more frequently."
        ),
        "source": "MedlinePlus / NIH",
        "category": "general",
    },
    {
        "id": "aha_heart_rate_zones",
        "text": (
            "Heart Rate Zones and Clinical Significance (AHA): "
            "Maximum heart rate (estimated): 220 minus age. "
            "Target heart rate during moderate exercise: 50–70% of maximum. "
            "Target heart rate during vigorous exercise: 70–85% of maximum. "
            "Resting heart rate trend: decreasing resting HR over weeks indicates improving cardiovascular fitness. "
            "Increasing resting HR trend: may indicate overtraining, illness, or cardiac stress. "
            "Heart rate variability (HRV): higher HRV generally indicates better cardiovascular health."
        ),
        "source": "American Heart Association",
        "category": "heart_rate",
    },
    {
        "id": "who_weight_management",
        "text": (
            "Weight and BMI Health Implications (WHO / NIH): "
            "Unintentional weight loss >5% in 6–12 months is clinically significant. "
            "Rapid weight gain (>2 kg in 1 week) may indicate fluid retention — consult physician. "
            "BMI alone does not account for muscle mass, bone density, or fat distribution. "
            "Waist circumference is an additional risk indicator: men >102 cm, women >88 cm indicates high risk. "
            "Weight management through diet and exercise reduces risk of type 2 diabetes, hypertension, and CVD."
        ),
        "source": "WHO / NIH",
        "category": "weight_bmi",
    },
]


class HealthKnowledgeRetriever:
    """
    ChromaDB-backed retriever for clinical reference ranges.
    Falls back to in-memory ChromaDB if server is unavailable.
    """

    COLLECTION_NAME = "health_monitoring_knowledge"

    def __init__(self) -> None:
        self._client: Optional[object] = None
        self._collection: Optional[object] = None
        self._initialized = False

    def _init(self) -> None:
        if self._initialized:
            return
        try:
            if _CHROMA_AVAILABLE:
                client = chromadb.HttpClient(
                    host=settings.chroma_host,
                    port=settings.chroma_port,
                )
                client.heartbeat()
                self._client = client
                logger.info("HealthKnowledgeRetriever: connected to ChromaDB server")
            else:
                raise RuntimeError("chromadb not installed")
        except Exception:
            logger.warning("ChromaDB server unavailable — using in-memory fallback")
            self._client = chromadb.Client()

        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._seed_if_empty()
        self._initialized = True

    def _seed_if_empty(self) -> None:
        if self._collection.count() > 0:
            return
        logger.info("Seeding health_monitoring_knowledge collection (%d docs)", len(_SEED_DOCUMENTS))
        self._collection.add(
            ids=[d["id"] for d in _SEED_DOCUMENTS],
            documents=[d["text"] for d in _SEED_DOCUMENTS],
            metadatas=[
                {"source": d["source"], "category": d["category"]}
                for d in _SEED_DOCUMENTS
            ],
        )

    def retrieve(self, query: str, n_results: int = 4) -> list[dict]:
        self._init()
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, len(_SEED_DOCUMENTS)),
            )
            docs = []
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                docs.append({
                    "text": doc,
                    "source": meta.get("source", "Unknown"),
                    "category": meta.get("category", "general"),
                })
            return docs
        except Exception as exc:
            logger.error("RAG retrieval failed: %s", exc)
            return []

    def format_context(self, docs: list[dict]) -> str:
        if not docs:
            return "No reference data available."
        parts = []
        for d in docs:
            parts.append(f"[{d['source']}] {d['text']}")
        return "\n\n".join(parts)


# Singleton
health_retriever = HealthKnowledgeRetriever()
