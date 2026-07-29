"""
Comprehensive tests for MedicineSafetyAgent — Module 5.

Test categories:
  1. Schema validation (5 tests)
  2. DrugNormalizer unit tests (8 tests)
  3. AllergyChecker unit tests (7 tests)
  4. DuplicateMedicationChecker unit tests (5 tests)
  5. Severity aggregator unit tests (5 tests)
  6. RAG retriever tests (4 tests)
  7. Mock LLM — DrugNameExtractor (4 tests)
  8. Mock LLM — InteractionChecker (4 tests)
  9. Mock LLM — ContraindicationChecker (3 tests)
  10. Full agent integration tests (5 tests)
  11. Conversation memory tests (3 tests)
  12. Safety guardrail tests (3 tests)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.medicine_safety.schemas import (
    ExtractedMedication,
    DrugInteraction,
    AllergyAlert,
    Contraindication,
    DuplicateWarning,
    DosageValidation,
    MedicineSafetyResult,
)
from app.agents.medicine_safety.tools import (
    normalize_drug_name,
    get_drug_class,
    check_allergies,
    check_duplicates,
    compute_overall_severity,
    compute_safety_confidence,
    build_recommendations,
)
from app.agents.medicine_safety.rag import DrugKnowledgeRetriever
from app.agents.medicine_safety.agent import MedicineSafetyAgent
from app.agents.base import initial_state, AgentState


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _med(generic: str, brand: str = None, dosage: str = None) -> ExtractedMedication:
    return ExtractedMedication(raw=brand or generic, generic_name=generic,
                               brand_name=brand, dosage_mentioned=dosage)


def _make_state(message: str = "Is ibuprofen safe to take?", **overrides) -> AgentState:
    state = initial_state(
        session_id="test-med-session",
        user_id="test-user",
        user_message=message,
    )
    state.update(overrides)
    return state


def _state_with_profile(allergies: str = "", chronic: str = "") -> AgentState:
    state = _make_state()
    state["patient_profile"] = {
        "gender": "male", "date_of_birth": "1980-01-01",
        "allergies": allergies, "chronic_diseases": chronic,
    }
    return state


# ------------------------------------------------------------------ #
#  1. Schema Validation Tests                                          #
# ------------------------------------------------------------------ #

def test_extracted_medication_schema():
    m = ExtractedMedication(raw="Tylenol", generic_name="acetaminophen",
                            brand_name="Tylenol", dosage_mentioned="500mg")
    assert m.generic_name == "acetaminophen"
    assert m.dosage_mentioned == "500mg"


def test_drug_interaction_severity_validation():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DrugInteraction(drug_a="a", drug_b="b", severity="extreme", description="test")


def test_allergy_alert_defaults():
    a = AllergyAlert(medication="amoxicillin", allergen="penicillin")
    assert a.severity == "high"


def test_medicine_safety_result_defaults():
    r = MedicineSafetyResult()
    assert r.severity == "safe"
    assert r.confidence == 0.0
    assert r.requires_immediate_attention is False
    assert "educational" in r.disclaimer.lower()


def test_medicine_safety_result_confidence_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MedicineSafetyResult(confidence=1.5)


# ------------------------------------------------------------------ #
#  2. DrugNormalizer Unit Tests                                        #
# ------------------------------------------------------------------ #

def test_normalize_brand_to_generic_tylenol():
    assert normalize_drug_name("Tylenol") == "acetaminophen"


def test_normalize_brand_to_generic_advil():
    assert normalize_drug_name("Advil") == "ibuprofen"


def test_normalize_brand_to_generic_coumadin():
    assert normalize_drug_name("Coumadin") == "warfarin"


def test_normalize_brand_to_generic_glucophage():
    assert normalize_drug_name("Glucophage") == "metformin"


def test_normalize_brand_to_generic_lipitor():
    assert normalize_drug_name("Lipitor") == "atorvastatin"


def test_normalize_unknown_passthrough():
    assert normalize_drug_name("unknowndrug") == "unknowndrug"


def test_normalize_case_insensitive():
    assert normalize_drug_name("TYLENOL") == "acetaminophen"
    assert normalize_drug_name("advil") == "ibuprofen"


def test_get_drug_class_nsaid():
    assert get_drug_class("ibuprofen") == "nsaid"
    assert get_drug_class("naproxen") == "nsaid"
    assert get_drug_class("aspirin") == "nsaid"


def test_get_drug_class_statin():
    assert get_drug_class("atorvastatin") == "statin"
    assert get_drug_class("rosuvastatin") == "statin"


def test_get_drug_class_unknown():
    assert get_drug_class("unknowndrug") is None


# ------------------------------------------------------------------ #
#  3. AllergyChecker Unit Tests                                        #
# ------------------------------------------------------------------ #

def test_allergy_direct_match():
    meds = [_med("amoxicillin")]
    alerts = check_allergies(meds, "amoxicillin")
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"


def test_allergy_cross_reactivity_penicillin():
    meds = [_med("amoxicillin")]
    alerts = check_allergies(meds, "penicillin")
    assert len(alerts) >= 1
    assert any(a.reaction_type == "possible cross-reactivity" or
               a.reaction_type == "known allergy" for a in alerts)


def test_allergy_cross_reactivity_sulfa():
    meds = [_med("trimethoprim-sulfamethoxazole")]
    alerts = check_allergies(meds, "sulfa")
    assert len(alerts) >= 1


def test_allergy_no_match():
    meds = [_med("metformin")]
    alerts = check_allergies(meds, "penicillin")
    assert len(alerts) == 0


def test_allergy_empty_profile():
    meds = [_med("ibuprofen")]
    alerts = check_allergies(meds, "")
    assert alerts == []


def test_allergy_multiple_allergens():
    meds = [_med("amoxicillin"), _med("ibuprofen")]
    alerts = check_allergies(meds, "penicillin, aspirin")
    # amoxicillin cross-reacts with penicillin; ibuprofen cross-reacts with aspirin
    assert len(alerts) >= 1


def test_allergy_critical_severity_on_direct_match():
    meds = [_med("warfarin")]
    alerts = check_allergies(meds, "warfarin")
    assert alerts[0].severity == "critical"


# ------------------------------------------------------------------ #
#  4. DuplicateMedicationChecker Unit Tests                           #
# ------------------------------------------------------------------ #

def test_duplicate_exact_match():
    meds = [_med("metformin")]
    current = [{"medicine_name": "metformin"}]
    warnings = check_duplicates(meds, current)
    assert len(warnings) == 1
    assert "already" in warnings[0].note.lower()


def test_duplicate_same_class_nsaid():
    meds = [_med("ibuprofen")]
    current = [{"medicine_name": "naproxen"}]
    warnings = check_duplicates(meds, current)
    assert len(warnings) == 1
    assert "nsaid" in warnings[0].note.lower()


def test_duplicate_same_class_statin():
    meds = [_med("atorvastatin")]
    current = [{"medicine_name": "rosuvastatin"}]
    warnings = check_duplicates(meds, current)
    assert len(warnings) == 1


def test_no_duplicate_different_class():
    meds = [_med("metformin")]
    current = [{"medicine_name": "lisinopril"}]
    warnings = check_duplicates(meds, current)
    assert len(warnings) == 0


def test_duplicate_empty_current_meds():
    meds = [_med("ibuprofen")]
    warnings = check_duplicates(meds, [])
    assert warnings == []


# ------------------------------------------------------------------ #
#  5. Severity Aggregator Unit Tests                                  #
# ------------------------------------------------------------------ #

def test_severity_safe_no_issues():
    assert compute_overall_severity([], [], []) == "safe"


def test_severity_danger_critical_allergy():
    alerts = [AllergyAlert(medication="amoxicillin", allergen="penicillin", severity="critical")]
    assert compute_overall_severity([], alerts, []) == "danger"


def test_severity_danger_contraindicated_interaction():
    interactions = [DrugInteraction(drug_a="a", drug_b="b",
                                    severity="contraindicated", description="test")]
    assert compute_overall_severity(interactions, [], []) == "danger"


def test_severity_warning_major_interaction():
    interactions = [DrugInteraction(drug_a="a", drug_b="b",
                                    severity="major", description="test")]
    assert compute_overall_severity(interactions, [], []) == "warning"


def test_severity_caution_minor_interaction():
    interactions = [DrugInteraction(drug_a="a", drug_b="b",
                                    severity="minor", description="test")]
    assert compute_overall_severity(interactions, [], []) == "caution"


# ------------------------------------------------------------------ #
#  6. RAG Retriever Tests                                             #
# ------------------------------------------------------------------ #

def test_drug_rag_in_memory():
    import chromadb
    retriever = DrugKnowledgeRetriever()
    retriever._client = chromadb.EphemeralClient()
    retriever._collection = None
    docs = retriever.retrieve("ibuprofen interaction", n_results=2)
    assert isinstance(docs, list)


def test_drug_rag_format_context_empty():
    retriever = DrugKnowledgeRetriever()
    assert "No relevant" in retriever.format_context([])


def test_drug_rag_format_context_with_docs():
    retriever = DrugKnowledgeRetriever()
    docs = [{"text": "Ibuprofen info", "source": "FDA", "topic": "ibuprofen", "relevance_score": 0.9}]
    ctx = retriever.format_context(docs)
    assert "FDA" in ctx
    assert "Ibuprofen info" in ctx


def test_drug_rag_handles_failure():
    retriever = DrugKnowledgeRetriever()
    retriever._client = MagicMock()
    retriever._client.get_or_create_collection.side_effect = Exception("fail")
    retriever._collection = None
    docs = retriever.retrieve("ibuprofen")
    assert docs == []


# ------------------------------------------------------------------ #
#  7. Mock LLM — DrugNameExtractor                                    #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_extract_medications_mock_llm():
    mock_resp = MagicMock()
    mock_resp.content = json.dumps([
        {"raw": "Advil", "generic_name": "ibuprofen", "brand_name": "Advil",
         "dosage_mentioned": "400mg", "frequency_mentioned": "twice daily", "route": "oral"}
    ])
    with patch("app.agents.medicine_safety.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_resp)
        from app.agents.medicine_safety.tools import extract_medications
        meds = await extract_medications("I take Advil 400mg twice daily")
    assert len(meds) == 1
    assert meds[0].generic_name == "ibuprofen"
    assert meds[0].dosage_mentioned == "400mg"


@pytest.mark.asyncio
async def test_extract_medications_invalid_json_fallback():
    mock_resp = MagicMock()
    mock_resp.content = "not json"
    with patch("app.agents.medicine_safety.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_resp)
        from app.agents.medicine_safety.tools import extract_medications
        meds = await extract_medications("some message")
    assert meds == []


@pytest.mark.asyncio
async def test_extract_medications_llm_failure_returns_empty():
    with patch("app.agents.medicine_safety.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM down"))
        from app.agents.medicine_safety.tools import extract_medications
        meds = await extract_medications("I take ibuprofen")
    assert meds == []


@pytest.mark.asyncio
async def test_extract_medications_normalizes_brand():
    mock_resp = MagicMock()
    mock_resp.content = json.dumps([
        {"raw": "Tylenol", "generic_name": "Tylenol", "brand_name": "Tylenol",
         "dosage_mentioned": None, "frequency_mentioned": None, "route": None}
    ])
    with patch("app.agents.medicine_safety.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_resp)
        from app.agents.medicine_safety.tools import extract_medications
        meds = await extract_medications("I take Tylenol")
    # normalize_drug_name should convert Tylenol → acetaminophen
    assert meds[0].generic_name == "acetaminophen"


# ------------------------------------------------------------------ #
#  8. Mock LLM — InteractionChecker                                   #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_interaction_check_found():
    mock_resp = MagicMock()
    mock_resp.content = json.dumps([
        {"drug_a": "warfarin", "drug_b": "ibuprofen", "severity": "major",
         "description": "Increased bleeding risk", "mechanism": "NSAID inhibits platelet aggregation",
         "source": "NIH"}
    ])
    with patch("app.agents.medicine_safety.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_resp)
        from app.agents.medicine_safety.tools import check_interactions
        meds = [_med("ibuprofen")]
        current = [{"medicine_name": "warfarin"}]
        interactions = await check_interactions(meds, current, "context")
    assert len(interactions) == 1
    assert interactions[0].severity == "major"


@pytest.mark.asyncio
async def test_interaction_check_none_found():
    mock_resp = MagicMock()
    mock_resp.content = json.dumps([])
    with patch("app.agents.medicine_safety.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_resp)
        from app.agents.medicine_safety.tools import check_interactions
        meds = [_med("metformin")]
        interactions = await check_interactions(meds, [], "context")
    assert interactions == []


@pytest.mark.asyncio
async def test_interaction_check_single_drug_skips_llm():
    """Single drug — no interaction check needed."""
    from app.agents.medicine_safety.tools import check_interactions
    meds = [_med("metformin")]
    interactions = await check_interactions(meds, [], "context")
    assert interactions == []


@pytest.mark.asyncio
async def test_interaction_check_llm_failure_returns_empty():
    with patch("app.agents.medicine_safety.tools._get_llm") as MockLLM:
        MockLLM.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM down"))
        from app.agents.medicine_safety.tools import check_interactions
        meds = [_med("ibuprofen"), _med("warfarin")]
        interactions = await check_interactions(meds, [], "context")
    assert interactions == []


# ------------------------------------------------------------------ #
#  9. Mock LLM — ContraindicationChecker                              #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_contraindication_rule_based_peptic_ulcer():
    from app.agents.medicine_safety.tools import check_contraindications
    meds = [_med("ibuprofen")]
    contraindications = await check_contraindications(meds, "peptic ulcer", [], "")
    assert len(contraindications) >= 1
    assert any("peptic ulcer" in c.condition.lower() for c in contraindications)


@pytest.mark.asyncio
async def test_contraindication_rule_based_renal():
    from app.agents.medicine_safety.tools import check_contraindications
    meds = [_med("metformin")]
    contraindications = await check_contraindications(meds, "renal impairment", [], "")
    assert len(contraindications) >= 1


@pytest.mark.asyncio
async def test_contraindication_no_conditions():
    from app.agents.medicine_safety.tools import check_contraindications
    meds = [_med("metformin")]
    contraindications = await check_contraindications(meds, "", [], "")
    assert contraindications == []


# ------------------------------------------------------------------ #
#  10. Full Agent Integration Tests (mocked LLM)                      #
# ------------------------------------------------------------------ #

def _mock_pipeline_llm():
    extract_resp = MagicMock()
    extract_resp.content = json.dumps([
        {"raw": "ibuprofen", "generic_name": "ibuprofen", "brand_name": None,
         "dosage_mentioned": "400mg", "frequency_mentioned": "twice daily", "route": "oral"}
    ])
    interaction_resp = MagicMock()
    interaction_resp.content = json.dumps([])
    contraindication_resp = MagicMock()
    contraindication_resp.content = json.dumps([])
    dosage_resp = MagicMock()
    dosage_resp.content = json.dumps([
        {"medication": "ibuprofen", "mentioned_dosage": "400mg",
         "typical_range": "200-400mg every 4-6 hours", "is_within_range": True,
         "note": "Within typical OTC range"}
    ])
    final_resp = MagicMock()
    final_resp.content = (
        "Based on the information provided, ibuprofen appears safe at the mentioned dosage. "
        "Please consult your pharmacist for personalised advice."
    )
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        extract_resp, interaction_resp, contraindication_resp, dosage_resp, final_resp
    ])
    return mock_llm


@pytest.mark.asyncio
async def test_agent_full_pipeline_safe():
    state = _make_state("Is ibuprofen 400mg safe to take?")
    agent = MedicineSafetyAgent()

    with patch("app.agents.medicine_safety.tools._get_llm") as MockTools, \
         patch("app.core.llm.get_llm") as MockAgent, \
         patch("app.agents.medicine_safety.tools.drug_retriever") as mock_rag:

        mock_llm = _mock_pipeline_llm()
        MockTools.return_value = mock_llm
        MockAgent.return_value = mock_llm
        mock_rag.retrieve.return_value = [
            {"text": "Ibuprofen info", "source": "FDA", "topic": "ibuprofen", "relevance_score": 0.9}
        ]
        mock_rag.format_context.return_value = "[Source: FDA] Ibuprofen info"

        result_state = await agent.execute(state)

    assert len(result_state["agent_outputs"]) == 1
    output = result_state["agent_outputs"][0]
    assert output["agent_name"] == "MedicineSafetyAgent"
    assert output["response"] != ""
    assert output["confidence"] >= 0.0
    assert "structured_result" in output["metadata"]


@pytest.mark.asyncio
async def test_agent_allergy_alert_detected():
    state = _make_state("Can I take amoxicillin?")
    state["patient_profile"] = {
        "allergies": "penicillin", "chronic_diseases": "",
        "gender": "female", "date_of_birth": "1990-01-01",
    }
    agent = MedicineSafetyAgent()

    extract_resp = MagicMock()
    extract_resp.content = json.dumps([
        {"raw": "amoxicillin", "generic_name": "amoxicillin", "brand_name": None,
         "dosage_mentioned": None, "frequency_mentioned": None, "route": None}
    ])
    interaction_resp = MagicMock()
    interaction_resp.content = json.dumps([])
    contraindication_resp = MagicMock()
    contraindication_resp.content = json.dumps([])
    dosage_resp = MagicMock()
    dosage_resp.content = json.dumps([])
    final_resp = MagicMock()
    final_resp.content = "ALLERGY ALERT: amoxicillin may trigger your penicillin allergy."

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        extract_resp, interaction_resp, contraindication_resp, dosage_resp, final_resp
    ])

    with patch("app.agents.medicine_safety.tools._get_llm") as MockTools, \
         patch("app.core.llm.get_llm") as MockAgent, \
         patch("app.agents.medicine_safety.tools.drug_retriever") as mock_rag:

        MockTools.return_value = mock_llm
        MockAgent.return_value = mock_llm
        mock_rag.retrieve.return_value = []
        mock_rag.format_context.return_value = ""

        result_state = await agent.execute(state)

    output = result_state["agent_outputs"][0]
    structured = output["metadata"]["structured_result"]
    assert len(structured["allergy_alerts"]) >= 1
    assert structured["severity"] in ("danger", "warning", "caution")


@pytest.mark.asyncio
async def test_agent_llm_failure_graceful():
    state = _make_state("Is aspirin safe?")
    agent = MedicineSafetyAgent()

    with patch("app.agents.medicine_safety.tools._get_llm") as MockTools, \
         patch("app.core.llm.get_llm") as MockAgent, \
         patch("app.agents.medicine_safety.tools.drug_retriever") as mock_rag:

        MockTools.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM down"))
        MockAgent.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM down"))
        mock_rag.retrieve.return_value = []
        mock_rag.format_context.return_value = ""

        result_state = await agent.execute(state)

    assert len(result_state["agent_outputs"]) == 1
    output = result_state["agent_outputs"][0]
    assert output["agent_name"] == "MedicineSafetyAgent"


@pytest.mark.asyncio
async def test_agent_danger_prefix_on_critical_allergy():
    """Response should be prefixed with CRITICAL SAFETY ALERT for danger severity."""
    state = _make_state("Can I take amoxicillin?")
    state["patient_profile"] = {
        "allergies": "amoxicillin", "chronic_diseases": "",
        "gender": "male", "date_of_birth": "1985-01-01",
    }
    agent = MedicineSafetyAgent()

    extract_resp = MagicMock()
    extract_resp.content = json.dumps([
        {"raw": "amoxicillin", "generic_name": "amoxicillin", "brand_name": None,
         "dosage_mentioned": None, "frequency_mentioned": None, "route": None}
    ])
    other_resp = MagicMock()
    other_resp.content = json.dumps([])
    final_resp = MagicMock()
    final_resp.content = "Do not take amoxicillin."

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        extract_resp, other_resp, other_resp, other_resp, final_resp
    ])

    with patch("app.agents.medicine_safety.tools._get_llm") as MockTools, \
         patch("app.core.llm.get_llm") as MockAgent, \
         patch("app.agents.medicine_safety.tools.drug_retriever") as mock_rag:

        MockTools.return_value = mock_llm
        MockAgent.return_value = mock_llm
        mock_rag.retrieve.return_value = []
        mock_rag.format_context.return_value = ""

        result_state = await agent.execute(state)

    output = result_state["agent_outputs"][0]
    assert "CRITICAL" in output["response"] or "ALLERGY" in output["response"]


@pytest.mark.asyncio
async def test_agent_no_medications_extracted():
    state = _make_state("What is the weather today?")
    agent = MedicineSafetyAgent()

    extract_resp = MagicMock()
    extract_resp.content = json.dumps([])
    other_resp = MagicMock()
    other_resp.content = json.dumps([])
    final_resp = MagicMock()
    final_resp.content = "No medications were identified in your message."

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        extract_resp, other_resp, other_resp, other_resp, final_resp
    ])

    with patch("app.agents.medicine_safety.tools._get_llm") as MockTools, \
         patch("app.core.llm.get_llm") as MockAgent, \
         patch("app.agents.medicine_safety.tools.drug_retriever") as mock_rag:

        MockTools.return_value = mock_llm
        MockAgent.return_value = mock_llm
        mock_rag.retrieve.return_value = []
        mock_rag.format_context.return_value = ""

        result_state = await agent.execute(state)

    output = result_state["agent_outputs"][0]
    assert output["metadata"]["structured_result"]["severity"] == "safe"


# ------------------------------------------------------------------ #
#  11. Conversation Memory Tests                                       #
# ------------------------------------------------------------------ #

def test_agent_build_patient_context_with_profile():
    agent = MedicineSafetyAgent()
    state = _state_with_profile(allergies="penicillin", chronic="diabetes")
    ctx = agent._build_patient_context(state)
    assert "penicillin" in ctx
    assert "diabetes" in ctx


def test_agent_build_patient_context_no_profile():
    agent = MedicineSafetyAgent()
    state = _make_state()
    state["patient_profile"] = None
    ctx = agent._build_patient_context(state)
    assert "No patient profile" in ctx


def test_agent_get_current_medications_from_metadata():
    agent = MedicineSafetyAgent()
    state = _make_state()
    state["metadata"]["current_medications"] = [{"medicine_name": "metformin"}]
    meds = agent._get_current_medications(state)
    assert len(meds) == 1
    assert meds[0]["medicine_name"] == "metformin"


# ------------------------------------------------------------------ #
#  12. Safety Guardrail Tests                                          #
# ------------------------------------------------------------------ #

def test_result_has_disclaimer():
    result = MedicineSafetyResult()
    assert "pharmacist" in result.disclaimer.lower() or "physician" in result.disclaimer.lower()


def test_fallback_response_no_prescription():
    agent = MedicineSafetyAgent()
    result = MedicineSafetyResult(
        medications=[_med("ibuprofen")],
        severity="caution",
        recommendations=["Consult your pharmacist"],
    )
    response = agent._fallback_response(result)
    assert "prescribe" not in response.lower()
    assert "consult" in response.lower() or "pharmacist" in response.lower()


def test_recommendations_always_include_consultation():
    recs = build_recommendations([], [], [], [], "safe")
    assert any("pharmacist" in r.lower() or "physician" in r.lower() or
               "healthcare" in r.lower() for r in recs)
