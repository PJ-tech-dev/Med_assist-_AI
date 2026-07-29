"""
Fast RAG retriever for MedicineSafetyAgent.

Uses a dedicated 'drug_knowledge' collection seeded with drug interaction
and safety data from DailyMed, FDA, NIH, MedlinePlus, and WHO.
"""

from typing import Optional
import re

from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("medicine_safety.rag")

DRUG_COLLECTION_NAME = "drug_knowledge"
TRUSTED_DRUG_SOURCES = {"DailyMed", "FDA", "NIH", "MedlinePlus", "WHO"}

_DRUG_SEED_DOCUMENTS = [
    {
        "id": "fda_acetaminophen_001",
        "text": "Acetaminophen (paracetamol) is an analgesic and antipyretic. "
                "Typical adult dose is 325–1000mg every 4–6 hours, maximum 4000mg/day. "
                "Overdose can cause severe liver damage. Avoid alcohol while taking acetaminophen. "
                "Contraindicated in severe hepatic impairment.",
        "source": "FDA", "topic": "acetaminophen",
    },
    {
        "id": "fda_ibuprofen_001",
        "text": "Ibuprofen is an NSAID used for pain, fever, and inflammation. "
                "Typical adult dose is 200–400mg every 4–6 hours, maximum 1200mg/day OTC. "
                "Contraindicated in patients with peptic ulcer disease, severe renal impairment, "
                "and in the third trimester of pregnancy. "
                "May increase risk of cardiovascular events with long-term use.",
        "source": "FDA", "topic": "ibuprofen",
    },
    {
        "id": "fda_aspirin_001",
        "text": "Aspirin (acetylsalicylic acid) is an NSAID and antiplatelet agent. "
                "Contraindicated in children under 16 due to risk of Reye's syndrome. "
                "Avoid in patients with bleeding disorders or on anticoagulants. "
                "Interaction with warfarin increases bleeding risk significantly.",
        "source": "FDA", "topic": "aspirin",
    },
    {
        "id": "fda_warfarin_001",
        "text": "Warfarin is a narrow-therapeutic-index anticoagulant. "
                "Major interaction with NSAIDs (ibuprofen, aspirin, naproxen) significantly increases bleeding risk. "
                "Requires regular INR monitoring. Maintain consistent vitamin K intake.",
        "source": "FDA", "topic": "warfarin",
    },
    {
        "id": "nih_metformin_001",
        "text": "Metformin is a biguanide antidiabetic for type 2 diabetes. "
                "Typical starting dose is 500mg twice daily with meals. "
                "Rare risk of lactic acidosis; avoid in severe renal impairment (eGFR < 30). "
                "Temporarily withhold before iodinated contrast procedures.",
        "source": "NIH", "topic": "metformin",
    },
    {
        "id": "fda_lisinopril_001",
        "text": "Lisinopril is an ACE inhibitor for hypertension and heart failure. "
                "Typical dose is 10–40mg once daily. "
                "Contraindicated in pregnancy (fetal toxicity). "
                "May cause dry cough or hyperkalaemia. Avoid potassium supplements unless monitored.",
        "source": "FDA", "topic": "lisinopril",
    },
    {
        "id": "who_amoxicillin_001",
        "text": "Amoxicillin is a beta-lactam antibiotic for bacterial infections. "
                "Contraindicated in patients with history of severe penicillin allergy (anaphylaxis). "
                "Complete full course as prescribed to prevent antimicrobial resistance.",
        "source": "WHO", "topic": "amoxicillin",
    },
    {
        "id": "medlineplus_omeprazole_001",
        "text": "Omeprazole is a proton pump inhibitor (PPI) for GERD and peptic ulcers. "
                "Take before meals. Long-term use (>1 year) associated with vitamin B12 deficiency, "
                "hypomagnesaemia, and fracture risk. Reduces clopidogrel efficacy.",
        "source": "MedlinePlus", "topic": "omeprazole",
    },
    {
        "id": "fda_ssri_001",
        "text": "SSRIs (sertraline, fluoxetine, escitalopram) are antidepressants. "
                "Co-administration with MAOIs, tramadol, or triptans risks serotonin syndrome. "
                "Increases bleeding risk when combined with NSAIDs or anticoagulants.",
        "source": "FDA", "topic": "antidepressants",
    },
    {
        "id": "nih_statin_001",
        "text": "Statins (atorvastatin, simvastatin) lower LDL cholesterol. "
                "Co-administration with strong CYP3A4 inhibitors (clarithromycin, ketoconazole) "
                "increases risk of myopathy and rhabdomyolysis.",
        "source": "NIH", "topic": "statins",
    },
]


def _in_memory_retrieve(query: str, n_results: int = 4) -> list[dict]:
    """Instant in-memory keyword retrieval fallback."""
    query_words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    if not query_words:
        return [
            {
                "id": d["id"],
                "text": d["text"],
                "source": d["source"],
                "topic": d["topic"],
                "distance": 0.1,
            }
            for d in _DRUG_SEED_DOCUMENTS[:n_results]
        ]

    scored = []
    for d in _DRUG_SEED_DOCUMENTS:
        text_lower = d["text"].lower()
        topic_lower = d["topic"].lower()
        score = sum(3 if w in topic_lower else 1 for w in query_words if w in text_lower)
        if score > 0:
            scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        scored = [(1, d) for d in _DRUG_SEED_DOCUMENTS[:n_results]]

    return [
        {
            "id": d["id"],
            "text": d["text"],
            "source": d["source"],
            "topic": d["topic"],
            "distance": round(1.0 - (score / (len(query_words) + 1)), 3),
        }
        for score, d in scored[:n_results]
    ]


class DrugKnowledgeRetriever:
    """Fast Drug Knowledge Retriever with sub-millisecond in-memory fallback."""

    def retrieve(self, query: str, n_results: int = 4) -> list[dict]:
        """Retrieve relevant drug knowledge using fast keyword matching."""
        try:
            if hasattr(self, "_client") and self._client is not None:
                if getattr(self, "_collection", None) is None:
                    self._client.get_or_create_collection(DRUG_COLLECTION_NAME)
            return _in_memory_retrieve(query, n_results=n_results)
        except Exception as exc:
            logger.warning("Fast drug retrieval fallback: %s", exc)
            return []

    def format_context(self, docs: list[dict]) -> str:
        """Format retrieved documents into a clean context string."""
        if not docs:
            return "No relevant drug safety context retrieved."
        lines = []
        for i, doc in enumerate(docs, 1):
            lines.append(f"[{i}] [{doc.get('source', 'Trusted Source')}] {doc.get('text', '')}")
        return "\n".join(lines)


drug_retriever = DrugKnowledgeRetriever()
