import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from app.agents.base import AgentState, initial_state, AgentOutput
from app.agents.orchestrator import (
    node_route_intent,
    node_execute_agents,
    node_merge_outputs,
    run_orchestrator,
)


def _make_state(**overrides) -> AgentState:
    state = initial_state(
        session_id="test-session-001",
        user_id="test-user-001",
        user_message=overrides.pop("user_message", "I have a headache"),
    )
    state.update(overrides)
    return state


# ------------------------------------------------------------------ #
#  node_route_intent                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_route_intent_symptom():
    state = _make_state(user_message="I have a fever and headache")
    result = await node_route_intent(state)
    assert "symptom_analysis" in result["detected_intents"]
    assert "SymptomAnalysisAgent" in result["selected_agents"]


@pytest.mark.asyncio
async def test_route_intent_emergency_exclusive():
    state = _make_state(user_message="I have chest pain and can't breathe")
    result = await node_route_intent(state)
    assert result["detected_intents"] == ["emergency_triage"]
    assert result["selected_agents"] == ["EmergencyTriageAgent"]


@pytest.mark.asyncio
async def test_route_intent_metadata_populated():
    state = _make_state(user_message="check my blood pressure")
    result = await node_route_intent(state)
    assert "intent_routing" in result["metadata"]
    assert "intents" in result["metadata"]["intent_routing"]
    assert "agents" in result["metadata"]["intent_routing"]


# ------------------------------------------------------------------ #
#  node_execute_agents                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_execute_agents_no_agents_selected():
    state = _make_state()
    state["selected_agents"] = []
    result = await node_execute_agents(state)
    assert result["agent_outputs"] == []


@pytest.mark.asyncio
async def test_execute_agents_single_agent():
    state = _make_state(user_message="I have a cough")
    state["selected_agents"] = ["SymptomAnalysisAgent"]
    result = await node_execute_agents(state)
    assert len(result["agent_outputs"]) == 1
    assert result["agent_outputs"][0]["agent_name"] == "SymptomAnalysisAgent"


@pytest.mark.asyncio
async def test_execute_agents_parallel_multiple():
    state = _make_state(user_message="I have a headache and want to check my medication")
    state["selected_agents"] = ["SymptomAnalysisAgent", "MedicineSafetyAgent"]
    result = await node_execute_agents(state)
    agent_names = [o["agent_name"] for o in result["agent_outputs"]]
    assert "SymptomAnalysisAgent" in agent_names
    assert "MedicineSafetyAgent" in agent_names


@pytest.mark.asyncio
async def test_execute_agents_emergency_sequential():
    state = _make_state(user_message="chest pain emergency")
    state["selected_agents"] = ["EmergencyTriageAgent"]
    result = await node_execute_agents(state)
    assert len(result["agent_outputs"]) == 1
    assert result["agent_outputs"][0]["agent_name"] == "EmergencyTriageAgent"


@pytest.mark.asyncio
async def test_execute_agents_unknown_agent_skipped():
    state = _make_state()
    state["selected_agents"] = ["NonExistentAgent"]
    result = await node_execute_agents(state)
    assert result["agent_outputs"] == []


# ------------------------------------------------------------------ #
#  node_merge_outputs                                                  #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_merge_outputs_empty():
    state = _make_state()
    state["agent_outputs"] = []
    result = await node_merge_outputs(state)
    assert "couldn't process" in result["final_response"].lower()


@pytest.mark.asyncio
async def test_merge_outputs_single():
    state = _make_state()
    state["agent_outputs"] = [
        AgentOutput(
            agent_name="SymptomAnalysisAgent",
            response="You may have a cold.",
            confidence=0.9,
            metadata={},
            execution_time_ms=50.0,
            error=None,
        )
    ]
    result = await node_merge_outputs(state)
    assert result["final_response"] == "You may have a cold."


@pytest.mark.asyncio
async def test_merge_outputs_multiple_joined():
    state = _make_state()
    state["agent_outputs"] = [
        AgentOutput(agent_name="A", response="Response A", confidence=1.0,
                    metadata={}, execution_time_ms=10.0, error=None),
        AgentOutput(agent_name="B", response="Response B", confidence=1.0,
                    metadata={}, execution_time_ms=20.0, error=None),
    ]
    result = await node_merge_outputs(state)
    assert "Response A" in result["final_response"]
    assert "Response B" in result["final_response"]


@pytest.mark.asyncio
async def test_merge_outputs_error_skipped():
    state = _make_state()
    state["agent_outputs"] = [
        AgentOutput(agent_name="A", response="", confidence=0.0,
                    metadata={}, execution_time_ms=5.0, error="Something failed"),
        AgentOutput(agent_name="B", response="Valid response", confidence=1.0,
                    metadata={}, execution_time_ms=10.0, error=None),
    ]
    result = await node_merge_outputs(state)
    assert result["final_response"] == "Valid response"


@pytest.mark.asyncio
async def test_merge_outputs_total_ms_tracked():
    state = _make_state()
    state["agent_outputs"] = [
        AgentOutput(agent_name="A", response="R", confidence=1.0,
                    metadata={}, execution_time_ms=100.0, error=None),
    ]
    result = await node_merge_outputs(state)
    assert result["metadata"]["total_agent_execution_ms"] == 100.0


# ------------------------------------------------------------------ #
#  Full orchestrator pipeline                                          #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_orchestrator_full_pipeline():
    state = initial_state(
        session_id="full-test-session",
        user_id="full-test-user",
        user_message="I have a fever",
    )
    result = await run_orchestrator(state)
    assert result["final_response"] != ""
    assert len(result["detected_intents"]) > 0
    assert len(result["selected_agents"]) > 0
    assert len(result["agent_outputs"]) > 0


@pytest.mark.asyncio
async def test_run_orchestrator_emergency():
    state = initial_state(
        session_id="emergency-session",
        user_id="emergency-user",
        user_message="I am having a heart attack",
    )
    result = await run_orchestrator(state)
    assert result["detected_intents"] == ["emergency_triage"]
    assert "EmergencyTriageAgent" in result["selected_agents"]
    assert "emergency" in result["final_response"].lower() or "PLACEHOLDER" in result["final_response"]
