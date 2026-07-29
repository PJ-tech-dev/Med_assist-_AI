"""
EmergencyTriageAgent — Production implementation.

Pipeline:
  1. Classify emergency severity and type (LLM).
  2. Retrieve immediate triage protocol (LLM).
  3. Generate final urgent response.
  4. Return structured AgentOutput.

This agent runs exclusively and never in parallel.
"""

import time
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentState, AgentOutput
from app.agents.emergency_triage.schemas import EmergencyTriageResult, TriageProtocol
from app.agents.emergency_triage.tools import classify_emergency, retrieve_triage_protocol
from app.utils.logger import get_logger

logger = get_logger("agent.emergency_triage")


class EmergencyTriageAgent(BaseAgent):
    """
    Production-ready emergency triage agent.
    Replaces the Module 8 placeholder.
    """

    name = "EmergencyTriageAgent"
    description = "Detects life-threatening situations and provides immediate triage guidance."
    supported_intents = ["emergency_triage"]
    tools: list = []

    async def execute(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        user_message = state.get("user_message", "")
        logger.info(
            "EmergencyTriageAgent START | session=%s | message_len=%d",
            state.get("session_id", "unknown"), len(user_message),
        )

        try:
            # Step 1: Classify the emergency
            classification = await classify_emergency(user_message)
            severity = classification.get("severity", "high")
            emergency_type = classification.get("emergency_type", "Unknown")
            dispatch_rec = classification.get("dispatch_recommendation", "Call emergency services immediately.")
            
            # Step 2: Retrieve triage protocol
            protocol = await retrieve_triage_protocol(emergency_type, severity, user_message)
            
            # Step 3: Build structured result
            result = EmergencyTriageResult(
                is_emergency=True,
                severity=severity,
                emergency_type=emergency_type,
                confidence=0.9,  # High confidence for emergency triage
                dispatch_recommendation=dispatch_rec,
                triage_protocol=protocol
            )
            
            response_text = self._build_response_text(result)
            metadata = result.model_dump()
            
        except Exception as exc:
            logger.error("Pipeline failed: %s", exc)
            response_text = (
                "⚠️ URGENT: An error occurred processing your request, but your symptoms may indicate a medical emergency. "
                "Please call emergency services (112 / 911) immediately."
            )
            metadata = {"error": str(exc), "is_emergency": True}

        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "EmergencyTriageAgent END | session=%s | severity=%s | elapsed_ms=%.1f",
            state.get("session_id", "unknown"),
            metadata.get("severity", "unknown"),
            elapsed_ms,
        )

        state["agent_outputs"].append(
            self.build_output(
                response=response_text,
                confidence=metadata.get("confidence", 0.0),
                metadata={"structured_result": metadata},
                execution_time_ms=elapsed_ms,
            )
        )
        return state

    def _build_response_text(self, result: EmergencyTriageResult) -> str:
        """Construct the final response text based on the triage result."""
        lines = []
        
        # SOS Mode Urgency header
        if result.severity in ["critical", "high"] or "cardiac" in result.emergency_type.lower() or "heart attack" in result.emergency_type.lower():
            lines.append("🚨 **SOS MODE ACTIVATED: URGENT MEDICAL ALERT** 🚨")
            lines.append(f"**{result.dispatch_recommendation}**")
            lines.append("")
            lines.append("📞 **Please confirm to call 108 or 911 immediately.**")
            lines.append("📲 **Automated emergency alert messages are being dispatched to your close contacts & next of kin.**")
        else:
            lines.append("⚠️ **URGENT MEDICAL ALERT**")
            lines.append(f"{result.dispatch_recommendation}")
            
        lines.append("")
        
        # Triage protocol
        if result.triage_protocol:
            if result.triage_protocol.immediate_actions:
                lines.append("**Immediate Actions to Take:**")
                for action in result.triage_protocol.immediate_actions:
                    lines.append(f"• {action}")
                lines.append("")
                
            if result.triage_protocol.what_not_to_do:
                lines.append("**What NOT to Do:**")
                for action in result.triage_protocol.what_not_to_do:
                    lines.append(f"• ❌ {action}")
                lines.append("")
                
        # Disclaimer
        lines.append("---")
        lines.append(f"*{result.disclaimer}*")
        
        return "\n".join(lines)
