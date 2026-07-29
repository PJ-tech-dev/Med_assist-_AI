"""
Tests for EmergencyTriageAgent.
Covers schemas, tools with mocked LLMs, and agent execution.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.emergency_triage.schemas import EmergencyTriageResult, TriageProtocol
from app.agents.emergency_triage.tools import classify_emergency, retrieve_triage_protocol
from app.agents.emergency_triage.agent import EmergencyTriageAgent
from app.agents.base import initial_state, AgentState


# ------------------------------------------------------------------ #
#  1. Schema Validation Tests                                          #
# ------------------------------------------------------------------ #

def test_triage_protocol_schema():
    p = TriageProtocol(condition="Cardiac Arrest", immediate_actions=["Start CPR"], what_not_to_do=["Don't move"])
    assert p.condition == "Cardiac Arrest"
    assert len(p.immediate_actions) == 1
    assert p.what_not_to_do == ["Don't move"]


def test_triage_result_schema_defaults():
    r = EmergencyTriageResult()
    assert r.is_emergency is True
    assert r.severity == "high"
    assert r.emergency_type == "Unknown"
    assert r.confidence == 0.0
    assert r.triage_protocol is None
    assert "CRITICAL ALERT" in r.disclaimer


def test_triage_result_invalid_severity():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        EmergencyTriageResult(severity="mild")  # 'mild' is not allowed


def test_triage_result_confidence_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        EmergencyTriageResult(confidence=1.5)
    with pytest.raises(ValidationError):
        EmergencyTriageResult(confidence=-0.1)


# ------------------------------------------------------------------ #
#  2. Mocked Tools Tests                                               #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
@patch("app.agents.emergency_triage.tools._get_llm")
async def test_classify_emergency_success(mock_get_llm):
    """Test successful classification via mocked LLM."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = json.dumps({
        "is_emergency": True,
        "severity": "critical",
        "emergency_type": "Cardiac Arrest",
        "dispatch_recommendation": "Call 911 immediately and start CPR."
    })
    mock_get_llm.return_value = mock_llm

    result = await classify_emergency("I think someone is having a heart attack, no pulse!")
    
    assert result["is_emergency"] is True
    assert result["severity"] == "critical"
    assert result["emergency_type"] == "Cardiac Arrest"
    assert "Call 911" in result["dispatch_recommendation"]


@pytest.mark.asyncio
@patch("app.agents.emergency_triage.tools._get_llm")
async def test_classify_emergency_fallback_on_invalid_json(mock_get_llm):
    """Test fallback when LLM returns invalid JSON."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = "Not a JSON object"
    mock_get_llm.return_value = mock_llm

    result = await classify_emergency("Help me")
    
    # Should use fallback values
    assert result["is_emergency"] is True
    assert result["severity"] == "high"
    assert result["emergency_type"] == "Unknown"
    assert "Call emergency services" in result["dispatch_recommendation"]


@pytest.mark.asyncio
@patch("app.agents.emergency_triage.tools._get_llm")
async def test_retrieve_triage_protocol_success(mock_get_llm):
    """Test successful protocol retrieval via mocked LLM."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = json.dumps({
        "immediate_actions": ["Apply pressure", "Elevate wound"],
        "what_not_to_do": ["Do not remove tourniquet"]
    })
    mock_get_llm.return_value = mock_llm

    protocol = await retrieve_triage_protocol("Severe Bleeding", "critical", "I cut my arm badly")
    
    assert protocol.condition == "Severe Bleeding"
    assert "Apply pressure" in protocol.immediate_actions
    assert "Do not remove tourniquet" in protocol.what_not_to_do


# ------------------------------------------------------------------ #
#  3. Agent Integration Tests                                          #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
@patch("app.agents.emergency_triage.agent.classify_emergency")
@patch("app.agents.emergency_triage.agent.retrieve_triage_protocol")
async def test_emergency_triage_agent_success(mock_retrieve, mock_classify):
    """Test full agent execution pipeline."""
    mock_classify.return_value = {
        "is_emergency": True,
        "severity": "critical",
        "emergency_type": "Stroke",
        "dispatch_recommendation": "Call 911."
    }
    mock_retrieve.return_value = TriageProtocol(
        condition="Stroke",
        immediate_actions=["Note the time", "Keep patient calm"],
        what_not_to_do=["Do not give food or water"]
    )
    
    agent = EmergencyTriageAgent()
    state = initial_state(session_id="test-session", user_id="test-user", user_message="My dad's face is drooping.")
    
    new_state = await agent.execute(state)
    
    assert len(new_state["agent_outputs"]) == 1
    output = new_state["agent_outputs"][0]
    
    assert output["agent_name"] == "EmergencyTriageAgent"
    assert output["confidence"] == 0.9
    
    # Check response text
    assert "URGENT MEDICAL ALERT" in output["response"]
    assert "Call 911" in output["response"]
    assert "Note the time" in output["response"]
    assert "Do not give food or water" in output["response"]
    assert "CRITICAL ALERT" in output["response"]
    
    # Check structured metadata
    meta = output["metadata"]["structured_result"]
    assert meta["severity"] == "critical"
    assert meta["emergency_type"] == "Stroke"
    assert meta["triage_protocol"]["condition"] == "Stroke"


@pytest.mark.asyncio
@patch("app.agents.emergency_triage.agent.classify_emergency")
async def test_emergency_triage_agent_handles_exceptions(mock_classify):
    """Test agent fallback when internal pipeline fails."""
    mock_classify.side_effect = Exception("LLM Timeout")
    
    agent = EmergencyTriageAgent()
    state = initial_state(session_id="test-session", user_id="test-user", user_message="Help")
    
    new_state = await agent.execute(state)
    
    output = new_state["agent_outputs"][0]
    assert "error occurred" in output["response"]
    assert "call emergency services (112 / 911) immediately" in output["response"]
    assert output["metadata"]["structured_result"]["is_emergency"] is True
    assert output["metadata"]["structured_result"]["error"] == "LLM Timeout"
