"""
MedicalReportRetriever — ChromaDB RAG for lab test reference knowledge.

Sources: WHO, NIH, MedlinePlus, CDC, Mayo Clinic.
Collection: medical_report_knowledge
"""

import logging
from typing import Optional

try:
    import chromadb
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

from app.core.settings import settings

logger = logging.getLogger("report_analysis.rag")

_SEED_DOCUMENTS = [
    {
        "id": "cbc_hemoglobin",
        "text": (
            "Hemoglobin (Hb) Reference Ranges (WHO / NIH): "
            "Adult males: 13.5–17.5 g/dL. Adult females: 12.0–15.5 g/dL. "
            "Children (6–12 years): 11.5–15.5 g/dL. "
            "Anemia defined as Hb <13.0 g/dL in males, <12.0 g/dL in females (WHO). "
            "Severe anemia: <8.0 g/dL — requires urgent evaluation. "
            "Polycythemia: Hb >17.5 g/dL in males, >15.5 g/dL in females."
        ),
        "source": "WHO / NIH",
        "panel": "CBC",
    },
    {
        "id": "cbc_wbc",
        "text": (
            "White Blood Cell (WBC) Count Reference Ranges (NIH / MedlinePlus): "
            "Normal adult range: 4.5–11.0 × 10³/µL. "
            "Leukopenia: <4.0 × 10³/µL — may indicate viral infection, bone marrow suppression. "
            "Leukocytosis: >11.0 × 10³/µL — may indicate bacterial infection, inflammation, stress. "
            "Critical high: >30.0 × 10³/µL — requires immediate evaluation. "
            "Neutrophils: 50–70% of WBC. Lymphocytes: 20–40%. Monocytes: 2–8%."
        ),
        "source": "NIH / MedlinePlus",
        "panel": "CBC",
    },
    {
        "id": "cbc_platelets",
        "text": (
            "Platelet Count Reference Ranges (NIH / Mayo Clinic): "
            "Normal range: 150–400 × 10³/µL. "
            "Thrombocytopenia: <150 × 10³/µL — increased bleeding risk. "
            "Severe thrombocytopenia: <50 × 10³/µL — significant bleeding risk. "
            "Critical: <20 × 10³/µL — spontaneous bleeding risk, emergency. "
            "Thrombocytosis: >400 × 10³/µL — may indicate inflammation, iron deficiency, or myeloproliferative disorder."
        ),
        "source": "NIH / Mayo Clinic",
        "panel": "CBC",
    },
    {
        "id": "cbc_rbc_hematocrit",
        "text": (
            "RBC and Hematocrit Reference Ranges (NIH): "
            "RBC — Males: 4.5–5.9 × 10⁶/µL; Females: 4.0–5.2 × 10⁶/µL. "
            "Hematocrit — Males: 41–53%; Females: 36–46%. "
            "MCV (Mean Corpuscular Volume): 80–100 fL. "
            "MCH: 27–33 pg. MCHC: 32–36 g/dL. "
            "Low MCV suggests iron deficiency or thalassemia. High MCV suggests B12/folate deficiency."
        ),
        "source": "NIH",
        "panel": "CBC",
    },
    {
        "id": "lft_alt_ast",
        "text": (
            "Liver Function Tests — ALT and AST (NIH / MedlinePlus): "
            "ALT (Alanine Aminotransferase): Normal 7–56 U/L. "
            "AST (Aspartate Aminotransferase): Normal 10–40 U/L. "
            "Mild elevation (1–3× ULN): may indicate fatty liver, medication effect. "
            "Moderate elevation (3–10× ULN): hepatitis, alcohol-related liver disease. "
            "Severe elevation (>10× ULN): acute hepatitis, ischemic hepatitis, drug toxicity. "
            "AST:ALT ratio >2 suggests alcoholic liver disease."
        ),
        "source": "NIH / MedlinePlus",
        "panel": "LFT",
    },
    {
        "id": "lft_bilirubin_albumin",
        "text": (
            "Liver Function Tests — Bilirubin and Albumin (NIH / Mayo Clinic): "
            "Total Bilirubin: Normal 0.2–1.2 mg/dL. "
            "Direct Bilirubin: Normal 0.0–0.3 mg/dL. "
            "Jaundice appears when total bilirubin >2.5 mg/dL. "
            "Albumin: Normal 3.5–5.0 g/dL. Low albumin indicates chronic liver disease or malnutrition. "
            "Total Protein: Normal 6.0–8.3 g/dL. "
            "ALP (Alkaline Phosphatase): Normal 44–147 U/L; elevated in cholestasis, bone disease."
        ),
        "source": "NIH / Mayo Clinic",
        "panel": "LFT",
    },
    {
        "id": "kft_creatinine_urea",
        "text": (
            "Kidney Function Tests — Creatinine and Urea (NIH / MedlinePlus): "
            "Serum Creatinine — Males: 0.7–1.3 mg/dL; Females: 0.6–1.1 mg/dL. "
            "Blood Urea Nitrogen (BUN): Normal 7–20 mg/dL. "
            "eGFR (estimated GFR): Normal ≥60 mL/min/1.73m². "
            "CKD Stage 3: eGFR 30–59. Stage 4: eGFR 15–29. Stage 5 (failure): eGFR <15. "
            "BUN:Creatinine ratio >20 suggests pre-renal azotemia (dehydration). "
            "Uric Acid: Males 3.4–7.0 mg/dL; Females 2.4–6.0 mg/dL."
        ),
        "source": "NIH / MedlinePlus",
        "panel": "KFT",
    },
    {
        "id": "lipid_profile",
        "text": (
            "Lipid Profile Reference Ranges (AHA / NIH / CDC): "
            "Total Cholesterol: Desirable <200 mg/dL; Borderline 200–239; High ≥240 mg/dL. "
            "LDL Cholesterol: Optimal <100 mg/dL; Near optimal 100–129; Borderline 130–159; High 160–189; Very high ≥190. "
            "HDL Cholesterol: Low (risk) <40 mg/dL in men, <50 in women; Protective ≥60 mg/dL. "
            "Triglycerides: Normal <150 mg/dL; Borderline 150–199; High 200–499; Very high ≥500 mg/dL. "
            "Non-HDL Cholesterol: Optimal <130 mg/dL."
        ),
        "source": "AHA / NIH / CDC",
        "panel": "LIPID_PROFILE",
    },
    {
        "id": "blood_glucose_hba1c",
        "text": (
            "Blood Glucose and HbA1c Reference Ranges (ADA / NIH): "
            "Fasting Glucose: Normal <100 mg/dL; Prediabetes 100–125; Diabetes ≥126 mg/dL. "
            "Random Glucose: Diabetes suspected if ≥200 mg/dL with symptoms. "
            "HbA1c: Normal <5.7%; Prediabetes 5.7–6.4%; Diabetes ≥6.5%. "
            "Target HbA1c for diabetics (ADA): <7.0%. "
            "Hypoglycemia: <70 mg/dL. Severe: <54 mg/dL — emergency."
        ),
        "source": "ADA / NIH",
        "panel": "BLOOD_SUGAR",
    },
    {
        "id": "thyroid_tsh_t3_t4",
        "text": (
            "Thyroid Function Tests (NIH / MedlinePlus / Mayo Clinic): "
            "TSH (Thyroid Stimulating Hormone): Normal 0.4–4.0 mIU/L. "
            "Low TSH (<0.4): hyperthyroidism (overactive thyroid). "
            "High TSH (>4.0): hypothyroidism (underactive thyroid). "
            "Free T4: Normal 0.8–1.8 ng/dL. Free T3: Normal 2.3–4.2 pg/mL. "
            "Subclinical hypothyroidism: TSH 4–10 with normal T4. "
            "Subclinical hyperthyroidism: TSH <0.4 with normal T3/T4."
        ),
        "source": "NIH / MedlinePlus / Mayo Clinic",
        "panel": "THYROID",
    },
    {
        "id": "vitamin_d_b12",
        "text": (
            "Vitamin D and B12 Reference Ranges (NIH / MedlinePlus): "
            "Vitamin D (25-OH): Deficient <20 ng/mL; Insufficient 20–29 ng/mL; Sufficient 30–100 ng/mL; Toxic >100 ng/mL. "
            "Vitamin B12: Normal 200–900 pg/mL. "
            "B12 deficiency: <200 pg/mL — causes megaloblastic anemia, neuropathy. "
            "Borderline B12: 200–300 pg/mL — may require supplementation. "
            "Folate: Normal 2.7–17.0 ng/mL. Low folate causes megaloblastic anemia."
        ),
        "source": "NIH / MedlinePlus",
        "panel": "VITAMINS",
    },
    {
        "id": "cbc_interpretation",
        "text": (
            "CBC Interpretation Guidelines (Mayo Clinic / NIH): "
            "A complete blood count evaluates overall health and detects disorders like anemia, infection, and leukemia. "
            "Anemia pattern: low Hb + low RBC + low Hematocrit. "
            "Iron deficiency anemia: low MCV, low MCH, low ferritin. "
            "B12/folate deficiency: high MCV (macrocytic anemia). "
            "Infection pattern: elevated WBC with neutrophilia. "
            "Viral infection: lymphocytosis. Bacterial infection: neutrophilia. "
            "Thrombocytopenia with low WBC and Hb: bone marrow suppression."
        ),
        "source": "Mayo Clinic / NIH",
        "panel": "CBC",
    },
]


class MedicalReportRetriever:
    """
    ChromaDB-backed retriever for lab test reference knowledge.
    Falls back to in-memory ChromaDB if server is unavailable.
    """

    COLLECTION_NAME = "medical_report_knowledge"

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
                logger.info("MedicalReportRetriever: connected to ChromaDB server")
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
        logger.info("Seeding medical_report_knowledge collection (%d docs)", len(_SEED_DOCUMENTS))
        self._collection.add(
            ids=[d["id"] for d in _SEED_DOCUMENTS],
            documents=[d["text"] for d in _SEED_DOCUMENTS],
            metadatas=[
                {"source": d["source"], "panel": d["panel"]}
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
                    "panel": meta.get("panel", "general"),
                })
            return docs
        except Exception as exc:
            logger.error("RAG retrieval failed: %s", exc)
            return []

    def format_context(self, docs: list[dict]) -> str:
        if not docs:
            return "No reference data available."
        return "\n\n".join(f"[{d['source']}] {d['text']}" for d in docs)


# Singleton
report_retriever = MedicalReportRetriever()
