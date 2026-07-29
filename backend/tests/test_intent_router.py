import pytest
from app.agents.intent_router import detect_intents, resolve_agents


# ------------------------------------------------------------------ #
#  detect_intents                                                      #
# ------------------------------------------------------------------ #

def test_symptom_intent():
    intents = detect_intents("I have a fever and headache")
    assert "symptom_analysis" in intents


def test_emergency_intent_is_exclusive():
    intents = detect_intents("I have chest pain and can't breathe")
    assert intents == ["emergency_triage"]


def test_medicine_safety_intent():
    intents = detect_intents("Is it safe to take ibuprofen with paracetamol?")
    assert "medicine_safety" in intents


def test_report_analysis_intent():
    intents = detect_intents("Can you analyse my blood test report?")
    assert "report_analysis" in intents


def test_health_monitoring_intent():
    intents = detect_intents("My blood pressure is 140/90, is that normal?")
    assert "health_monitoring" in intents


def test_patient_history_intent():
    intents = detect_intents("Show me my medical history and past conditions")
    assert "patient_history" in intents


def test_general_health_fallback():
    intents = detect_intents("hello there")
    assert "general_health_query" in intents


def test_multiple_intents():
    intents = detect_intents("I have a headache and want to check my medication dosage")
    assert "symptom_analysis" in intents
    assert "medicine_safety" in intents


def test_emergency_overrides_others():
    # Even if other keywords present, emergency must be sole intent
    intents = detect_intents("I have chest pain and want to check my medication")
    assert intents == ["emergency_triage"]


# ------------------------------------------------------------------ #
#  resolve_agents                                                      #
# ------------------------------------------------------------------ #

def test_resolve_agents_symptom():
    agents = resolve_agents(["symptom_analysis"])
    assert "SymptomAnalysisAgent" in agents


def test_resolve_agents_emergency():
    agents = resolve_agents(["emergency_triage"])
    assert "EmergencyTriageAgent" in agents


def test_resolve_agents_deduplication():
    # general_health_query also maps to SymptomAnalysisAgent
    agents = resolve_agents(["symptom_analysis", "general_health_query"])
    assert agents.count("SymptomAnalysisAgent") == 1


def test_resolve_agents_multiple_intents():
    agents = resolve_agents(["symptom_analysis", "medicine_safety"])
    assert "SymptomAnalysisAgent" in agents
    assert "MedicineSafetyAgent" in agents
