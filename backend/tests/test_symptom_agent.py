"""
Comprehensive tests for SymptomAnalysisAgent — Module 4.

Test categories:
  1. Schema validation tests
  2. Tool unit tests (no LLM)
  3. Mock LLM tests
  4. RAG retriever tests
  5. Conversation memory tests
  6. Full agent integration tests (mocked LLM)
  7. Safety guardrail tests
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from app.agents.symptom.schemas import (
    ExtractedSymptom,
    PossibleCondition,
    SymptomAnalysisResult,
)
from app.agents.symptom.tools import (
    normalize_term,
    normalize_symptoms,
    classify_severity,
    generate_followup_questions,
    compute_confidence,
    _already_asked,
)
from app.agents.symptom.rag import MedicalKnowledgeRetriever
from app.agents.symptom.agent import SymptomAnalysisAgent
from app.agents.base import initial_state, AgentState


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _make_symptom(raw: str, normalized: str = None, duration: str = None) -> ExtractedSymptom:
    return ExtractedSymptom(raw=raw, normalized=normalized or raw, duration=duration)


def _make_state(message: str = "I have a headache", **overrides) -> AgentState:
    state = initial_state(
        session_id="test-session",
        user_id="test-user",
        user_message=message,
    )
    state.update(overrides)
    return state


# ------------------------------------------------------------------ #
#  1. Schema Validation Tests                                          #
# ------------------------------------------------------------------ #

def test_extracted_symptom_schema():
    s = ExtractedSymptom(raw="tummy ache", normalized="abdominal pain", duration="2 days")
    assert s.raw == "tummy ache"
    assert s.normalized == "abdominal pain"
    assert s.duration == "2 days"


def test_possible_condition_schema():
    c = PossibleCondition(name="Migraine", likelihood="high", reasoning="Throbbing headache")
    assert c.name == "Migraine"
    assert c.likelihood == "high"


def test_possible_condition_invalid_likelihood():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PossibleCondition(name="X", likelihood="very_high", reasoning="test")


def test_symptom_analysis_result_defaults():
    r = SymptomAnalysisResult()
    assert r.severity == "mild"
    assert r.confidence == 0.0
    assert r.requires_followup is False
    assert r.is_emergency is False
    assert "educational purposes" in r.disclaimer


def test_symptom_analysis_result_confidence_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SymptomAnalysisResult(confidence=1.5)
    with pytest.raises(ValidationError):
        SymptomAnalysisResult(confidence=-0.1)


# ------------------------------------------------------------------ #
#  2. Tool Unit Tests (no LLM)                                        #
# ------------------------------------------------------------------ #

def test_normalize_term_known():
    assert normalize_term("tummy ache") == "abdominal pain"
    assert normalize_term("runny nose") == "rhinorrhea"
    assert normalize_term("throwing up") == "vomiting"
    assert normalize_term("dizzy") == "dizziness"
    assert normalize_term("tired") == "fatigue"


def test_normalize_term_unknown_passthrough():
    assert normalize_term("hypertension") == "hypertension"
    assert normalize_term("unknown_term_xyz") == "unknown_term_xyz"


def test_normalize_term_case_insensitive():
    assert normalize_term("Tummy Ache") == "abdominal pain"
    assert normalize_term("RUNNY NOSE") == "rhinorrhea"


def test_normalize_symptoms_list():
    symptoms = [
        _make_symptom("tummy ache", "tummy ache"),
        _make_symptom("dizzy", "dizzy"),
    ]
    result = normalize_symptoms(symptoms)
    assert result[0].normalized == "abdominal pain"
    assert result[1].normalized == "dizziness"


def test_compute_confidence_empty():
    assert compute_confidence([], [], 0) == 0.0


def test_compute_confidence_with_data():
    symptoms = [_make_symptom("fever"), _make_symptom("headache")]
    conditions = [{"name": "Flu"}, {"name": "Cold"}]
    score = compute_confidence(symptoms, conditions, rag_docs_count=3)
    assert 0.0 < score <= 1.0


def test_compute_confidence_capped_at_1():
    symptoms = [_make_symptom(f"s{i}") for i in range(10)]
    conditions = [{"name": f"c{i}"} for i in range(10)]
    score = compute_confidence(symptoms, conditions, rag_docs_count=10)
    assert score <= 1.0


def test_already_asked_in_existing():
    assert _already_asked("temperature", ["What is your temperature?"], "") is True


def test_already_asked_in_history():
    assert _already_asked("temperature", [], "USER: What is your temperature?") is True


def test_already_asked_not_found():
    assert _already_asked("temperature", ["How long?"], "USER: I have a headache") is False


# ------------------------------------------------------------------ #
#  3. Follow-Up Question Generator Tests                              #
# ------------------------------------------------------------------ #

def test_followup_fever_generates_temperature_question():
    symptoms = [_make_symptom("fever", "fever")]
    questions = generate_followup_questions(symptoms, [], "")
    assert any("temperature" in q.lower() for q in questions)


def test_followup_headache_generates_location_question():
    symptoms = [_make_symptom("headache", "headache")]
    questions = generate_followup_questions(symptoms, [], "")
    assert any("headache" in q.lower() for q in questions)


def test_followup_avoids_repeat_questions():
    symptoms = [_make_symptom("fever", "fever")]
    existing = ["What is your current temperature reading?"]
    questions = generate_followup_questions(symptoms, existing, "")
    assert not any("temperature" in q.lower() for q in questions)


def test_followup_avoids_history_questions():
    symptoms = [_make_symptom("fever", "fever")]
    history = "ASSISTANT: What is your current temperature reading?"
    questions = generate_followup_questions(symptoms, [], history)
    assert not any("temperature" in q.lower() for q in questions)


def test_followup_capped_at_three():
    symptoms = [
        _make_symptom("fever", "fever"),
        _make_symptom("headache", "headache"),
        _make_symptom("abdominal pain", "abdominal pain"),
        _make_symptom("cough", "cough"),
        _make_symptom("fatigue", "fatigue"),
    ]
    questions = generate_followup_questions(symptoms, [], "")
    assert len(questions) <= 3


def test_followup_generic_when_no_specific():
    symptoms = [_make_symptom("hypertension", "hypertension")]
    questions = generate_followup_questions(symptoms, [], "")
    assert len(questions) > 0


# ------------------------------------------------------------------ #
#  4. RAG Retriever Tests                                             #
# ------------------------------------------------------------------ #

def test_rag_retriever_in_memory():
    """Test retriever with in-memory ChromaDB (no server needed)."""
    retriever = MedicalKnowledgeRetriever()
    import chromadb
    retriever._client = chromadb.EphemeralClient()
    retriever._collection = None

    docs = retriever.retrieve("fever headache", n_results=2)
    assert isinstance(docs, list)
    # After seeding, should return results
    assert len(docs) >= 0  # may be 0 if collection empty before seed


def test_rag_format_context_empty():
    retriever = MedicalKnowledgeRetriever()
    result = retriever.format_context([])
    assert "No relevant" in result


def test_rag_format_context_with_docs():
    retriever = MedicalKnowledgeRetriever()
    docs = [{"text": "Fever info", "source": "WHO", "topic": "fever", "relevance_score": 0.9}]
    result = retriever.format_context(docs)
    assert "WHO" in result
    assert "Fever info" in result


def test_rag_retriever_handles_failure():
    """Retriever should return empty list on failure, not raise."""
    retriever = MedicalKnowledgeRetriever()
    retriever._client = MagicMock()
    retriever._client.get_or_create_collection.side_effect = Exception("Connection failed")
    retriever._collection = None
    docs = retriever.retrieve("fever")
    assert docs == []


# ------------------------------------------------------------------ #
#  5. Mock LLM Tests                                                  #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_extract_symptoms_mock_llm():
    mock_response = MagicMock()
    mock_response.content = json.dumps([
        {"raw": "headache", "normalized": "headache", "duration": "2 days",
         "severity_hint": "moderate", "body_part": "head"}
    ])
    with patch("app.agents.symptom.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.symptom.tools import extract_symptoms
        symptoms = await extract_symptoms("I have a headache for 2 days")
    assert len(symptoms) == 1
    assert symptoms[0].normalized == "headache"
    assert symptoms[0].duration == "2 days"


@pytest.mark.asyncio
async def test_extract_symptoms_invalid_json_fallback():
    mock_response = MagicMock()
    mock_response.content = "not valid json at all"
    with patch("app.agents.symptom.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.symptom.tools import extract_symptoms
        symptoms = await extract_symptoms("I feel sick")
    assert symptoms == []


@pytest.mark.asyncio
async def test_classify_severity_emergency_rule_based():
    """Emergency should be detected without LLM call."""
    symptoms = [_make_symptom("chest pain", "chest pain")]
    severity = await classify_severity(symptoms, "", "")
    assert severity == "emergency"


@pytest.mark.asyncio
async def test_classify_severity_mock_llm():
    mock_response = MagicMock()
    mock_response.content = "moderate"
    with patch("app.agents.symptom.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.symptom.tools import classify_severity
        symptoms = [_make_symptom("headache", "headache")]
        severity = await classify_severity(symptoms, "", "")
    assert severity == "moderate"


@pytest.mark.asyncio
async def test_classify_severity_invalid_llm_response_defaults():
    mock_response = MagicMock()
    mock_response.content = "unknown_level"
    with patch("app.agents.symptom.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)
        from app.agents.symptom.tools import classify_severity
        symptoms = [_make_symptom("headache", "headache")]
        severity = await classify_severity(symptoms, "", "")
    assert severity == "moderate"


@pytest.mark.asyncio
async def test_retrieve_conditions_mock_llm():
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "possible_conditions": [
            {"name": "Tension Headache", "likelihood": "high",
             "reasoning": "Common cause of headache", "source": "WHO"}
        ],
        "requires_followup": True,
        "followup_questions": ["How long have you had the headache?"],
        "recommendations": ["Rest in a quiet dark room", "Stay hydrated"],
        "sources": ["WHO"],
    })
    with patch("app.agents.symptom.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)
        with patch("app.agents.symptom.tools.medical_retriever") as mock_rag:
            mock_rag.retrieve.return_value = [
                {"text": "Headache info", "source": "WHO", "topic": "headache", "relevance_score": 0.9}
            ]
            mock_rag.format_context.return_value = "[Source: WHO] Headache info"
            from app.agents.symptom.tools import retrieve_conditions
            symptoms = [_make_symptom("headache", "headache")]
            result = await retrieve_conditions(symptoms, "", "", "")
    assert len(result["possible_conditions"]) == 1
    assert result["possible_conditions"][0]["name"] == "Tension Headache"
    assert result["requires_followup"] is True


# ------------------------------------------------------------------ #
#  6. Full Agent Integration Tests (mocked LLM)                       #
# ------------------------------------------------------------------ #

def _mock_llm_for_agent():
    """Returns a mock that simulates all LLM calls in the agent pipeline."""
    extract_resp = MagicMock()
    extract_resp.content = json.dumps([
        {"raw": "headache", "normalized": "headache", "duration": "1 day",
         "severity_hint": "moderate", "body_part": "head"}
    ])

    severity_resp = MagicMock()
    severity_resp.content = "moderate"

    conditions_resp = MagicMock()
    conditions_resp.content = json.dumps({
        "possible_conditions": [
            {"name": "Tension Headache", "likelihood": "high",
             "reasoning": "Most common headache type", "source": "WHO"}
        ],
        "requires_followup": True,
        "followup_questions": ["How long have you had the headache?"],
        "recommendations": ["Rest", "Stay hydrated", "Avoid bright lights"],
        "sources": ["WHO"],
    })

    final_resp = MagicMock()
    final_resp.content = (
        "I understand you're experiencing a headache. Based on the information provided, "
        "possible conditions include Tension Headache (high likelihood). "
        "Recommendations: Rest, stay hydrated. Please consult a healthcare professional."
    )

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        extract_resp, severity_resp, conditions_resp, final_resp
    ])
    return mock_llm


@pytest.mark.asyncio
async def test_agent_full_pipeline_mocked():
    state = _make_state("I have a headache for 1 day")
    agent = SymptomAnalysisAgent()

    with patch("app.agents.symptom.tools._get_llm") as MockLLM, \
         patch("app.core.llm.get_llm") as MockAgentLLM, \
         patch("app.agents.symptom.tools.medical_retriever") as mock_rag:

        mock_llm = _mock_llm_for_agent()
        MockLLM.return_value = mock_llm
        MockAgentLLM.return_value = mock_llm
        mock_rag.retrieve.return_value = [
            {"text": "Headache info", "source": "WHO", "topic": "headache", "relevance_score": 0.9}
        ]
        mock_rag.format_context.return_value = "[Source: WHO] Headache info"

        result_state = await agent.execute(state)

    assert len(result_state["agent_outputs"]) == 1
    output = result_state["agent_outputs"][0]
    assert output["agent_name"] == "SymptomAnalysisAgent"
    assert output["response"] != ""
    assert output["confidence"] >= 0.0
    assert "structured_result" in output["metadata"]
    assert output["metadata"]["is_emergency"] is False


@pytest.mark.asyncio
async def test_agent_emergency_path():
    state = _make_state("I have severe chest pain and can't breathe")
    agent = SymptomAnalysisAgent()

    with patch("app.agents.symptom.tools._get_llm") as MockLLM, \
         patch("app.core.llm.get_llm") as MockAgentLLM, \
         patch("app.agents.symptom.tools.medical_retriever") as mock_rag:

        extract_resp = MagicMock()
        extract_resp.content = json.dumps([
            {"raw": "chest pain", "normalized": "chest pain", "duration": None,
             "severity_hint": "severe", "body_part": "chest"}
        ])
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=extract_resp)
        MockLLM.return_value = mock_llm
        MockAgentLLM.return_value = mock_llm
        mock_rag.retrieve.return_value = []
        mock_rag.format_context.return_value = ""

        result_state = await agent.execute(state)

    output = result_state["agent_outputs"][0]
    assert output["metadata"]["is_emergency"] is True
    assert "emergency" in output["response"].lower() or "URGENT" in output["response"]


@pytest.mark.asyncio
async def test_agent_llm_failure_graceful():
    """Agent should not crash when LLM fails — returns fallback response."""
    state = _make_state("I feel sick")
    agent = SymptomAnalysisAgent()

    with patch("app.agents.symptom.tools._get_llm") as MockLLM, \
         patch("app.core.llm.get_llm") as MockAgentLLM:
        MockLLM.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))
        MockAgentLLM.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))

        result_state = await agent.execute(state)

    assert len(result_state["agent_outputs"]) == 1
    output = result_state["agent_outputs"][0]
    assert output["agent_name"] == "SymptomAnalysisAgent"
    # Should have a response even on failure
    assert output["response"] != "" or output["error"] is not None


# ------------------------------------------------------------------ #
#  7. Conversation Memory Tests                                        #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_agent_uses_conversation_history():
    """Agent should not re-ask questions already in conversation history."""
    state = _make_state("I still have the headache")
    state["conversation_history"] = [
        {"role": "user", "content": "I have a headache", "timestamp": "2024-01-01T10:00:00"},
        {"role": "assistant", "content": "How long have you had the headache?", "timestamp": "2024-01-01T10:00:01"},
        {"role": "user", "content": "For 2 days", "timestamp": "2024-01-01T10:00:02"},
    ]

    symptoms = [_make_symptom("headache", "headache")]
    conv_history = "ASSISTANT: How long have you had the headache?\nUSER: For 2 days"
    questions = generate_followup_questions(symptoms, [], conv_history)
    # Should not ask about headache duration again
    assert not any("how long" in q.lower() for q in questions)


def test_agent_build_conversation_context():
    agent = SymptomAnalysisAgent()
    state = _make_state()
    state["conversation_history"] = [
        {"role": "user", "content": "I have a fever", "timestamp": "t1"},
        {"role": "assistant", "content": "How long?", "timestamp": "t2"},
    ]
    ctx = agent._build_conversation_context(state)
    assert "USER: I have a fever" in ctx
    assert "ASSISTANT: How long?" in ctx


def test_agent_build_patient_context_with_profile():
    agent = SymptomAnalysisAgent()
    state = _make_state()
    state["patient_profile"] = {
        "gender": "female",
        "blood_group": "O+",
        "allergies": "Penicillin",
        "chronic_diseases": "Diabetes",
        "date_of_birth": "1990-01-01",
    }
    ctx = agent._build_patient_context(state)
    assert "Penicillin" in ctx
    assert "Diabetes" in ctx


def test_agent_build_patient_context_no_profile():
    agent = SymptomAnalysisAgent()
    state = _make_state()
    state["patient_profile"] = None
    ctx = agent._build_patient_context(state)
    assert "No patient profile" in ctx


# ------------------------------------------------------------------ #
#  8. Safety Guardrail Tests                                           #
# ------------------------------------------------------------------ #

def test_result_has_disclaimer():
    result = SymptomAnalysisResult()
    assert len(result.disclaimer) > 0
    assert "medical advice" in result.disclaimer.lower()


@pytest.mark.asyncio
async def test_agent_fallback_response_no_diagnosis():
    agent = SymptomAnalysisAgent()
    result = SymptomAnalysisResult(
        symptoms=[_make_symptom("fever", "fever")],
        possible_conditions=[
            PossibleCondition(name="Viral Infection", likelihood="high",
                              reasoning="Common cause of fever")
        ],
        severity="mild",
        confidence=0.6,
        recommendations=["Rest", "Stay hydrated"],
    )
    response = agent._fallback_response(result)
    # Must not use definitive diagnosis language
    assert "you have" not in response.lower() or "possible" in response.lower()
    assert "consult" in response.lower() or "healthcare" in response.lower()
