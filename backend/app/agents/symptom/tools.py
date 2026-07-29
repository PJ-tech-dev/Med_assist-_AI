"""
Independent tools for SymptomAnalysisAgent.

Each tool is a pure function — no side effects, independently testable.

Tools:
  1. SymptomExtractorTool       — parse symptoms from free text via LLM
  2. MedicalEntityNormalizer    — map lay terms to medical terminology
  3. SeverityClassifier         — classify overall severity via LLM
  4. ConditionRetriever         — retrieve conditions from RAG + LLM reasoning
  5. FollowUpQuestionGenerator  — generate context-aware follow-up questions
"""

import json
import re
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.symptom.schemas import (
    ExtractedSymptom,
    PossibleCondition,
    SymptomAnalysisResult,
)
from app.agents.symptom.prompts import (
    SYMPTOM_EXTRACTION_PROMPT,
    SEVERITY_CLASSIFICATION_PROMPT,
    CONDITION_ANALYSIS_PROMPT,
)
from app.agents.symptom.rag import medical_retriever
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("symptom.tools")

# Lay term → normalized medical term mapping (extends LLM normalization)
_TERM_MAP: dict[str, str] = {
    "tummy ache": "abdominal pain",
    "stomach ache": "abdominal pain",
    "belly pain": "abdominal pain",
    "runny nose": "rhinorrhea",
    "stuffy nose": "nasal congestion",
    "sore throat": "pharyngitis",
    "throwing up": "vomiting",
    "throwing-up": "vomiting",
    "feel sick": "nausea",
    "feeling sick": "nausea",
    "high temperature": "fever",
    "temperature": "fever",
    "can't breathe": "dyspnea",
    "shortness of breath": "dyspnea",
    "chest tightness": "chest tightness",
    "heart racing": "palpitations",
    "heart pounding": "palpitations",
    "dizzy": "dizziness",
    "lightheaded": "lightheadedness",
    "tired": "fatigue",
    "exhausted": "fatigue",
    "itchy": "pruritus",
    "itching": "pruritus",
    "swollen": "edema",
    "back pain": "dorsalgia",
    "joint pain": "arthralgia",
    "muscle pain": "myalgia",
    "muscle ache": "myalgia",
}


def _get_llm(temperature: float = 0.1):
    from app.core.llm import get_llm
    return get_llm(temperature=temperature)


def _safe_json_parse(text: str, fallback: Any) -> Any:
    """Extract and parse JSON from LLM response, with fallback."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed, using fallback. Raw: %s", text[:200])
        return fallback


# ------------------------------------------------------------------ #
#  Tool 1: SymptomExtractorTool                                       #
# ------------------------------------------------------------------ #

async def extract_symptoms(message: str) -> list[ExtractedSymptom]:
    """
    Extract and structure symptoms from a free-text user message.
    Uses LLM for extraction, then applies rule-based normalization.
    """
    logger.info("Extracting symptoms from message (len=%d)", len(message))
    try:
        llm = _get_llm()
        prompt = SYMPTOM_EXTRACTION_PROMPT.format(message=message)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = _safe_json_parse(response.content, [])

        symptoms = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            raw_text = item.get("raw", "")
            normalized = item.get("normalized", raw_text)
            # Apply rule-based normalization on top of LLM output
            normalized = normalize_term(normalized or raw_text)
            symptoms.append(
                ExtractedSymptom(
                    raw=raw_text,
                    normalized=normalized,
                    duration=item.get("duration"),
                    severity_hint=item.get("severity_hint"),
                    body_part=item.get("body_part"),
                )
            )
        logger.info("Extracted %d symptoms", len(symptoms))
        return symptoms
    except Exception as exc:
        logger.error("Symptom extraction failed: %s", exc)
        return []


# ------------------------------------------------------------------ #
#  Tool 2: MedicalEntityNormalizer                                    #
# ------------------------------------------------------------------ #

def normalize_term(term: str) -> str:
    """
    Normalize a lay medical term to its standard medical equivalent.
    Uses rule-based lookup first, falls back to the original term.
    Independently testable — no LLM call.
    """
    lower = term.lower().strip()
    return _TERM_MAP.get(lower, term)


def normalize_symptoms(symptoms: list[ExtractedSymptom]) -> list[ExtractedSymptom]:
    """Apply normalization to a list of extracted symptoms."""
    for s in symptoms:
        s.normalized = normalize_term(s.normalized or s.raw)
    return symptoms


# ------------------------------------------------------------------ #
#  Tool 3: SeverityClassifier                                         #
# ------------------------------------------------------------------ #

async def classify_severity(
    symptoms: list[ExtractedSymptom],
    patient_context: str,
    history_context: str,
) -> str:
    """
    Classify overall severity as: mild | moderate | severe | emergency.
    Uses LLM with patient context for accurate classification.
    """
    symptom_text = ", ".join(s.normalized for s in symptoms) if symptoms else "unknown"
    logger.info("Classifying severity for symptoms: %s", symptom_text)

    # Rule-based emergency check first (fast path, no LLM needed)
    emergency_terms = {
        "chest pain", "dyspnea", "loss of consciousness", "seizure",
        "severe bleeding", "stroke", "heart attack", "anaphylaxis",
    }
    if any(term in symptom_text.lower() for term in emergency_terms):
        logger.warning("Emergency detected via rule-based check")
        return "emergency"

    try:
        llm = _get_llm(temperature=0.0)
        prompt = SEVERITY_CLASSIFICATION_PROMPT.format(
            symptoms=symptom_text,
            patient_context=patient_context,
            history_context=history_context,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        severity = response.content.strip().lower()
        if severity not in {"mild", "moderate", "severe", "emergency"}:
            logger.warning("Unexpected severity value '%s', defaulting to moderate", severity)
            severity = "moderate"
        logger.info("Severity classified: %s", severity)
        return severity
    except Exception as exc:
        logger.error("Severity classification failed: %s", exc)
        return "moderate"  # safe default


# ------------------------------------------------------------------ #
#  Tool 4: ConditionRetriever                                         #
# ------------------------------------------------------------------ #

async def retrieve_conditions(
    symptoms: list[ExtractedSymptom],
    patient_context: str,
    history_context: str,
    conversation_history: str,
) -> dict:
    """
    Retrieve relevant medical knowledge from ChromaDB and use LLM
    to reason about possible conditions.
    Returns dict with possible_conditions, requires_followup,
    followup_questions, recommendations, sources.
    """
    symptom_text = ", ".join(s.normalized for s in symptoms) if symptoms else "unknown"

    # RAG retrieval
    rag_docs = medical_retriever.retrieve(symptom_text, n_results=4)
    rag_context = medical_retriever.format_context(rag_docs)
    sources = list({doc["source"] for doc in rag_docs})
    logger.info("RAG retrieved %d docs | sources=%s", len(rag_docs), sources)

    try:
        llm = _get_llm(temperature=0.2)
        prompt = CONDITION_ANALYSIS_PROMPT.format(
            symptoms=symptom_text,
            patient_context=patient_context,
            history_context=history_context,
            rag_context=rag_context,
            conversation_history=conversation_history,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        result = _safe_json_parse(response.content, {})

        # Merge RAG sources with LLM-identified sources
        llm_sources = result.get("sources", [])
        all_sources = list(set(sources + llm_sources))

        return {
            "possible_conditions": result.get("possible_conditions", []),
            "requires_followup": result.get("requires_followup", False),
            "followup_questions": result.get("followup_questions", []),
            "recommendations": result.get("recommendations", []),
            "sources": all_sources,
            "rag_docs_count": len(rag_docs),
        }
    except Exception as exc:
        logger.error("Condition retrieval failed: %s", exc)
        return {
            "possible_conditions": [],
            "requires_followup": True,
            "followup_questions": ["Could you describe your symptoms in more detail?"],
            "recommendations": ["Please consult a healthcare professional for proper evaluation."],
            "sources": [],
            "rag_docs_count": 0,
        }


# ------------------------------------------------------------------ #
#  Tool 5: FollowUpQuestionGenerator                                  #
# ------------------------------------------------------------------ #

def generate_followup_questions(
    symptoms: list[ExtractedSymptom],
    existing_questions: list[str],
    conversation_history: str,
) -> list[str]:
    """
    Generate context-aware follow-up questions.
    Avoids repeating questions already asked in conversation history.
    Independently testable — no LLM call (rule-based).
    """
    questions: list[str] = []
    symptom_names = {s.normalized.lower() for s in symptoms}

    # Symptom-specific follow-up rules
    if "fever" in symptom_names and not _already_asked("temperature", existing_questions, conversation_history):
        questions.append("What is your current temperature reading?")

    if "headache" in symptom_names and not _already_asked("headache location", existing_questions, conversation_history):
        questions.append("Where exactly is the headache located, and is it throbbing or constant?")

    if "abdominal pain" in symptom_names and not _already_asked("bowel", existing_questions, conversation_history):
        questions.append("Have you had any changes in bowel movements or appetite?")

    if "cough" in symptom_names and not _already_asked("mucus", existing_questions, conversation_history):
        questions.append("Is the cough dry or producing mucus? If mucus, what colour?")

    if "fatigue" in symptom_names and not _already_asked("sleep", existing_questions, conversation_history):
        questions.append("How long have you been feeling fatigued, and has your sleep been affected?")

    # Generic follow-ups if no symptoms have specific questions
    if not questions:
        if not _already_asked("how long", existing_questions, conversation_history):
            questions.append("How long have you been experiencing these symptoms?")
        if not _already_asked("medication", existing_questions, conversation_history):
            questions.append("Are you currently taking any medications?")

    # Check if duration is missing for any symptom
    missing_duration = [s for s in symptoms if not s.duration]
    if missing_duration and not _already_asked("started", existing_questions, conversation_history):
        names = ", ".join(s.normalized for s in missing_duration[:2])
        questions.append(f"When did the {names} start?")

    return questions[:3]  # cap at 3 follow-up questions


def _already_asked(keyword: str, existing: list[str], history: str) -> bool:
    """Check if a similar question was already asked."""
    keyword_lower = keyword.lower()
    for q in existing:
        if keyword_lower in q.lower():
            return True
    return keyword_lower in history.lower()


# ------------------------------------------------------------------ #
#  Confidence Scorer                                                   #
# ------------------------------------------------------------------ #

def compute_confidence(
    symptoms: list[ExtractedSymptom],
    conditions: list[dict],
    rag_docs_count: int,
) -> float:
    """
    Compute a confidence score [0.0, 1.0] based on:
    - Number of symptoms extracted
    - Number of conditions identified
    - RAG retrieval success
    """
    score = 0.0
    if symptoms:
        score += min(len(symptoms) * 0.15, 0.45)   # up to 0.45 for symptoms
    if conditions:
        score += min(len(conditions) * 0.1, 0.30)  # up to 0.30 for conditions
    if rag_docs_count > 0:
        score += min(rag_docs_count * 0.05, 0.25)  # up to 0.25 for RAG
    return round(min(score, 1.0), 2)
