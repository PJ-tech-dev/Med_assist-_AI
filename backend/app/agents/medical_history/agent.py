"""
MedicalHistoryAgent — Production implementation.

Analyzes a patient's medical history (past diagnoses, conditions, 
allergies, procedures, family history) using AI to provide a cohesive summary 
and context to the user.
"""

import time
import json
from typing import Any

from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentState
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("agent.medical_history")

HISTORY_ANALYSIS_PROMPT = """You are a clinical AI assistant for the MedAssist AI platform.
The user is asking about their medical history or past conditions. 

Here is the structured context from the patient's medical database profile:
---
PATIENT PROFILE:
{patient_profile}

PAST MEDICAL HISTORY RECORDS:
{medical_history}
---

User's message:
"{user_message}"

Instructions:
1. Analyze the provided medical history and answer the user's question accurately based ONLY on the provided context.
2. If the user asks for a general summary, provide a cohesive, patient-friendly summary of their past conditions, allergies, and significant medical events.
3. If the provided medical history is empty or there are no relevant records, politely inform the user that no medical history records were found in the database.
4. Do NOT hallucinate diagnoses or conditions that are not present in the provided context.
5. Keep the response clinical, professional, and easy to understand (under 150 words).
"""

class MedicalHistoryAgent(BaseAgent):
    """Retrieves and summarises patient medical history using AI."""
    
    name = "MedicalHistoryAgent"
    description = "Retrieves and summarises patient medical history using AI analysis."
    supported_intents = ["patient_history"]
    tools: list = []

    async def execute(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        logger.info(
            "MedicalHistoryAgent START | session=%s",
            state["session_id"]
        )

        try:
            # Extract context
            profile_raw = state.get("patient_profile") or {}
            history_raw = state.get("medical_history") or []
            
            # Format nicely for the prompt
            profile_str = json.dumps(profile_raw, indent=2) if profile_raw else "No basic profile found."
            history_str = json.dumps(history_raw, indent=2) if history_raw else "No past medical history records found."
            
            # Generate AI analysis
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.3)
            
            prompt = HISTORY_ANALYSIS_PROMPT.format(
                patient_profile=profile_str,
                medical_history=history_str,
                user_message=state.get("user_message", "Summarize my medical history.")
            )
            
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            response_text = str(response.content).strip()

        except Exception as exc:
            logger.error("MedicalHistoryAgent failed: %s", exc)
            response_text = "I encountered an error while analyzing your medical history. Please try again later."
            history_raw = []

        elapsed_ms = (time.perf_counter() - start) * 1000

        state["agent_outputs"].append(
            self.build_output(
                response=response_text,
                confidence=0.9,
                metadata={
                    "history_records_analyzed": len(history_raw)
                },
                execution_time_ms=elapsed_ms,
            )
        )
        return state
