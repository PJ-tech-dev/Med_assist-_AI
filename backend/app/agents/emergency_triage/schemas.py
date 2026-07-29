"""
Pydantic schemas for EmergencyTriageAgent structured output.
These are used both for LLM output parsing and API response serialisation.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class TriageProtocol(BaseModel):
    condition: str
    immediate_actions: list[str] = Field(default_factory=list)
    what_not_to_do: list[str] = Field(default_factory=list)


class EmergencyTriageResult(BaseModel):
    """
    Structured output returned by EmergencyTriageAgent.
    This is serialised into AgentOutput.metadata["structured_result"].
    """
    is_emergency: bool = True
    trigger_sos_mode: bool = True
    recommended_dial: str = "108 / 911"
    severity: Literal["critical", "high", "moderate", "low"] = "high"
    emergency_type: str = "Unknown"  # e.g., "Cardiac", "Trauma", "Respiratory"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    dispatch_recommendation: str = "Call emergency services (108 / 911) immediately."
    triage_protocol: Optional[TriageProtocol] = None
    disclaimer: str = (
        "⚠️ CRITICAL ALERT: This is an AI system and NOT a substitute for professional medical help. "
        "If you are experiencing a life-threatening emergency, call your local emergency number (e.g. 108, 911) immediately."
    )
