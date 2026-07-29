"""
LangGraph Orchestrator — coordinates all MedAssist AI agents.

Graph topology:
  START
    └─► route_intent          (detect intents, select agents)
          └─► execute_agents  (run selected agents sequentially or in parallel)
                └─► merge_outputs  (combine agent responses into final_response)
  END

The orchestrator contains NO healthcare logic.
All domain logic lives inside individual agents.
"""

import asyncio
from typing import Any

from langgraph.graph import StateGraph, END

from app.agents.base import AgentState
from app.agents.intent_router import detect_intents, resolve_agents
from app.agents.implementations import (
    SymptomAnalysisAgent,
    MedicalHistoryAgent,
    MedicineSafetyAgent,
    EmergencyTriageAgent,
    HealthMonitoringAgent,
    MedicalReportAnalysisAgent,
    PharmacyOrderAgent,
)
from app.utils.logger import get_logger

logger = get_logger("orchestrator")

# ------------------------------------------------------------------ #
#  Agent Registry                                                      #
# ------------------------------------------------------------------ #

_AGENT_REGISTRY: dict[str, Any] = {
    agent.name: agent
    for agent in [
        SymptomAnalysisAgent(),
        MedicalHistoryAgent(),
        MedicineSafetyAgent(),
        EmergencyTriageAgent(),
        HealthMonitoringAgent(),
        MedicalReportAnalysisAgent(),
        PharmacyOrderAgent(),
    ]
}


# ------------------------------------------------------------------ #
#  Graph Nodes                                                         #
# ------------------------------------------------------------------ #

async def node_route_intent(state: AgentState) -> AgentState:
    """Detect intents and resolve which agents to run."""
    intents = detect_intents(state["user_message"])
    agents = resolve_agents(intents)

    state["detected_intents"] = intents
    state["selected_agents"] = agents
    state["metadata"]["intent_routing"] = {
        "intents": intents,
        "agents": agents,
    }
    logger.info(
        "session=%s | intents=%s | agents=%s",
        state["session_id"], intents, agents,
    )
    return state


async def node_execute_agents(state: AgentState) -> AgentState:
    """
    Execute selected agents.
    - Emergency triage: runs alone, sequentially (safety-critical).
    - All others: run concurrently via asyncio.gather for performance.
    """
    selected = state["selected_agents"]
    if not selected:
        logger.warning("session=%s | no agents selected", state["session_id"])
        return state

    agents = [_AGENT_REGISTRY[name] for name in selected if name in _AGENT_REGISTRY]
    unknown = [name for name in selected if name not in _AGENT_REGISTRY]
    if unknown:
        logger.warning("Unknown agents requested: %s", unknown)

    is_emergency = "EmergencyTriageAgent" in selected

    if is_emergency or len(agents) == 1:
        # Sequential — preserves order and is safer for emergencies
        for agent in agents:
            state = await agent.safe_execute(state)
    else:
        # Parallel — each agent gets a snapshot of state; outputs are merged after
        tasks = [agent.safe_execute(dict(state)) for agent in agents]  # type: ignore[arg-type]
        results: list[AgentState] = await asyncio.gather(*tasks)
        for result in results:
            state["agent_outputs"].extend(result["agent_outputs"])

    logger.info(
        "session=%s | executed %d agent(s)", state["session_id"], len(agents)
    )
    return state


async def node_merge_outputs(state: AgentState) -> AgentState:
    """
    Synthesize all agent outputs (and user prompt) into a single cohesive response
    using the Master LLM. Acts as a conversational AI for general chitchat.

    CRITICAL: Emergency triage responses bypass LLM synthesis entirely —
    the structured SOS response is passed directly to preserve urgency formatting,
    emergency protocol steps, and SOS mode activation markers.

    Logs per-agent execution time and errors.
    """
    outputs = state["agent_outputs"]
    total_ms = 0.0
    context_parts: list[str] = []

    # ── Emergency bypass: do NOT rewrite emergency triage output ──
    is_emergency = "EmergencyTriageAgent" in state.get("selected_agents", [])
    if is_emergency:
        for out in outputs:
            total_ms += out.get("execution_time_ms", 0.0)
            if out.get("agent_name") == "EmergencyTriageAgent":
                if out.get("error"):
                    logger.error(
                        "session=%s | EmergencyTriageAgent error=%s",
                        state["session_id"], out["error"],
                    )
                    # Use error fallback text if present, else generic
                    state["final_response"] = out.get("response") or (
                        "⚠️ URGENT: An error occurred, but your symptoms may indicate a "
                        "life-threatening emergency. Please call emergency services (108 / 911) immediately."
                    )
                else:
                    state["final_response"] = out.get("response", "")
                break
        else:
            # EmergencyTriageAgent output not found — use safe fallback
            state["final_response"] = (
                "🚨 EMERGENCY ALERT: Your message indicates a potential medical emergency. "
                "Please call emergency services (108 / 911) immediately."
            )
        state["metadata"]["total_agent_execution_ms"] = total_ms
        logger.warning(
            "session=%s | emergency bypass | response_len=%d | total_ms=%.1f",
            state["session_id"], len(state["final_response"]), total_ms,
        )
        return state

    # ── Normal path: collect outputs and synthesize with Master LLM ──
    for out in outputs:
        total_ms += out.get("execution_time_ms", 0.0)
        if out.get("error"):
            logger.error(
                "session=%s | agent=%s | error=%s",
                state["session_id"], out["agent_name"], out["error"],
            )
            continue
        if out.get("response"):
            context_parts.append(f"[{out['agent_name']} Data]:\n{out['response']}")

    context_str = "\n\n".join(context_parts)

    # ── Master LLM Synthesis ──
    from app.core.llm import get_llm
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = get_llm(temperature=0.7)  # A bit of creativity for chat

    if llm:
        system_prompt = (
            "You are MedAssist AI, a highly intelligent, empathetic, and professional healthcare assistant. "
            "You behave like ChatGPT—you can hold normal conversations, greet the user, and answer general questions. "
            "When the user asks a medical question, various specialized sub-agents are triggered in the background to gather data. "
            "Your job is to read the user's message and the raw data from the sub-agents (if any), and synthesize a single, "
            "fluent, and cohesive response. "
            "IMPORTANT RULES:\n"
            "1. NEVER expose the names of the internal sub-agents (e.g., 'SymptomAnalysisAgent Data') to the user.\n"
            "2. Seamlessly weave the medical insights into your natural response. Do not output raw markdown tags unnecessarily.\n"
            "3. If there is no agent data, simply reply naturally to the user's message (e.g., greet them back)."
        )

        human_msg = f"User Message:\n{state['user_message']}\n\n"
        if context_str:
            human_msg += f"Background Agent Data (Synthesize this into your response):\n{context_str}"

        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_msg)
            ])
            state["final_response"] = response.content.strip()
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            state["final_response"] = context_str if context_str else "I am MedAssist AI. How can I help you?"
    else:
        # Fallback if no LLM configured
        state["final_response"] = context_str if context_str else "I am MedAssist AI. How can I help you?"

    state["metadata"]["total_agent_execution_ms"] = total_ms

    logger.info(
        "session=%s | synthesized response | total_ms=%.1f",
        state["session_id"], total_ms,
    )
    return state


# ------------------------------------------------------------------ #
#  Graph Construction                                                  #
# ------------------------------------------------------------------ #

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("route_intent", node_route_intent)
    graph.add_node("execute_agents", node_execute_agents)
    graph.add_node("merge_outputs", node_merge_outputs)

    graph.set_entry_point("route_intent")
    graph.add_edge("route_intent", "execute_agents")
    graph.add_edge("execute_agents", "merge_outputs")
    graph.add_edge("merge_outputs", END)

    return graph


# Compile once at import time — reused across all requests
_compiled_graph = build_graph().compile()


async def run_orchestrator(state: AgentState) -> AgentState:
    """
    Public entry point. Accepts an initialised AgentState,
    runs the full LangGraph pipeline, and returns the final state.
    """
    logger.info("Orchestrator START | session=%s", state["session_id"])
    result: AgentState = await _compiled_graph.ainvoke(state)  # type: ignore[assignment]
    logger.info(
        "Orchestrator END | session=%s | response_len=%d",
        state["session_id"], len(result.get("final_response", "")),
    )
    return result
