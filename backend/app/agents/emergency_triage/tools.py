"""
Independent tools for EmergencyTriageAgent.
"""

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.emergency_triage.schemas import TriageProtocol
from app.agents.emergency_triage.prompts import (
    EMERGENCY_CLASSIFICATION_PROMPT,
    TRIAGE_PROTOCOL_PROMPT,
)
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("emergency_triage.tools")


def _get_llm(temperature: float = 0.0):
    from app.core.llm import get_llm
    return get_llm(temperature=temperature)


def _safe_json_parse(text: str, fallback: Any) -> Any:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed, using fallback. Raw: %s", text[:200])
        return fallback


async def classify_emergency(message: str) -> dict[str, Any]:
    """
    Classify the emergency severity and type based on the user's message.
    """
    logger.info("Classifying emergency for message (len=%d)", len(message))

    msg_lower = message.lower()
    is_cardiac_rule = any(k in msg_lower for k in ["heart attack", "cardiac", "chest pain", "cannot breathe", "can't breathe", "unconscious", "stroke"])

    fallback = {
        "is_emergency": True,
        "severity": "critical" if is_cardiac_rule else "high",
        "emergency_type": "Cardiac Event (Heart Attack)" if is_cardiac_rule else "Unknown",
        "dispatch_recommendation": "Call emergency services (108 / 911) immediately.",
        "trigger_sos_mode": True,
        "recommended_dial": "108 / 911"
    }

    try:
        llm = _get_llm(temperature=0.0)
        sys_msg = SystemMessage(content=EMERGENCY_CLASSIFICATION_PROMPT.format(message=message))
        response = await llm.ainvoke([sys_msg])
        
        parsed = _safe_json_parse(response.content, fallback=fallback)
        if is_cardiac_rule and isinstance(parsed, dict):
            parsed["is_emergency"] = True
            parsed["trigger_sos_mode"] = True
            parsed["recommended_dial"] = "108 / 911"
        return parsed
    except Exception as e:
        logger.error("LLM call failed in classify_emergency: %s", e)
        return fallback


async def retrieve_triage_protocol(emergency_type: str, severity: str, message: str) -> TriageProtocol:
    """
    Retrieve immediate actions and what not to do based on the emergency.
    """
    logger.info("Retrieving triage protocol for %s (severity: %s)", emergency_type, severity)
    fallback_protocol = TriageProtocol(
        condition=emergency_type,
        immediate_actions=["Call emergency services immediately.", "Stay calm and wait for help."],
        what_not_to_do=["Do not move the patient unless absolutely necessary."]
    )

    try:
        llm = _get_llm(temperature=0.1)
        sys_msg = SystemMessage(content=TRIAGE_PROTOCOL_PROMPT.format(
            emergency_type=emergency_type,
            severity=severity,
            message=message
        ))
        response = await llm.ainvoke([sys_msg])
        
        parsed = _safe_json_parse(response.content, fallback={})
        if not parsed:
            return fallback_protocol

        return TriageProtocol(
            condition=emergency_type,
            immediate_actions=parsed.get("immediate_actions", fallback_protocol.immediate_actions),
            what_not_to_do=parsed.get("what_not_to_do", fallback_protocol.what_not_to_do)
        )
    except Exception as e:
        logger.error("LLM call failed in retrieve_triage_protocol: %s", e)
        return fallback_protocol
