"""
Fast Medical Knowledge RAG retriever for SymptomAnalysisAgent.

Retrieves relevant medical knowledge from trusted sources:
  WHO, CDC, NIH, MedlinePlus
"""

from typing import Optional
import re

from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("symptom.rag")

TRUSTED_SOURCES = {"WHO", "CDC", "NIH", "MedlinePlus"}

_SEED_DOCUMENTS = [
    {
        "id": "who_fever_001",
        "text": "Fever is a temporary increase in body temperature, often due to illness. "
                "A fever is usually a sign that the body is fighting an infection. "
                "Adults typically have a fever if their body temperature rises above 38°C (100.4°F). "
                "Most fevers caused by common viral infections resolve within a few days.",
        "source": "WHO", "topic": "fever",
    },
    {
        "id": "cdc_headache_001",
        "text": "Headaches are one of the most common pain conditions. "
                "Tension headaches are the most common type, causing mild to moderate pain. "
                "Migraine headaches cause moderate to severe throbbing pain, often on one side. "
                "Seek immediate care for sudden severe headache, headache with fever and stiff neck.",
        "source": "CDC", "topic": "headache",
    },
    {
        "id": "nih_cough_001",
        "text": "A cough is a reflex action to clear the airways of mucus and irritants. "
                "Acute coughs last less than 3 weeks and are usually caused by a cold or flu. "
                "Chronic coughs lasting more than 8 weeks may indicate asthma, GERD, or postnasal drip.",
        "source": "NIH", "topic": "cough",
    },
    {
        "id": "medlineplus_nausea_001",
        "text": "Nausea is an unpleasant sensation of needing to vomit. "
                "Common causes include viral gastroenteritis, food poisoning, motion sickness, "
                "pregnancy, and medications.",
        "source": "MedlinePlus", "topic": "nausea",
    },
    {
        "id": "who_fatigue_001",
        "text": "Fatigue is a feeling of tiredness or exhaustion that does not improve with rest. "
                "Common causes include poor sleep, stress, anaemia, thyroid disorders, and infections.",
        "source": "WHO", "topic": "fatigue",
    },
    {
        "id": "cdc_dizziness_001",
        "text": "Dizziness can feel like lightheadedness, unsteadiness, or vertigo. "
                "Causes include dehydration, inner ear issues, low blood pressure, and medication side effects.",
        "source": "CDC", "topic": "dizziness",
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
            for d in _SEED_DOCUMENTS[:n_results]
        ]

    scored = []
    for d in _SEED_DOCUMENTS:
        text_lower = d["text"].lower()
        topic_lower = d["topic"].lower()
        score = sum(3 if w in topic_lower else 1 for w in query_words if w in text_lower)
        if score > 0:
            scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        scored = [(1, d) for d in _SEED_DOCUMENTS[:n_results]]

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


class MedicalKnowledgeRetriever:
    """Fast Medical Knowledge Retriever with sub-millisecond retrieval."""

    def retrieve(self, query: str, n_results: int = 4) -> list[dict]:
        try:
            if hasattr(self, "_client") and self._client is not None:
                if getattr(self, "_collection", None) is None:
                    self._client.get_or_create_collection("medical_knowledge")
            return _in_memory_retrieve(query, n_results=n_results)
        except Exception as exc:
            logger.warning("Fast medical retrieval fallback: %s", exc)
            return []

    def format_context(self, docs: list[dict]) -> str:
        """Format retrieved documents into a clean context string."""
        if not docs:
            return "No relevant medical knowledge retrieved."
        lines = []
        for i, doc in enumerate(docs, 1):
            lines.append(f"[{i}] [{doc.get('source', 'Trusted Source')}] {doc.get('text', '')}")
        return "\n".join(lines)


medical_retriever = MedicalKnowledgeRetriever()
