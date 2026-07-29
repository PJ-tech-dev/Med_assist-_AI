"""
SymptomAnalysisAgent — Production implementation.

Pipeline:
  1. Extract symptoms from user message (LLM)
  2. Normalize medical terms (rule-based + LLM)
  3. Build patient context string from AgentState
  4. Classify severity (rule-based fast path + LLM)
  5. Retrieve conditions + RAG context (ChromaDB + LLM)
  6. Generate follow-up questions (rule-based, memory-aware)
  7. Compute confidence score
  8. Generate final natural language response (LLM)
  9. Return structured AgentOutput

Safety guarantees:
  - Never diagnoses diseases
  - Never prescribes medications
  - Always recommends professional consultation
  - Emergency detected → immediate safety guidance
"""

import json
import time
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentState, AgentOutput
from app.agents.symptom.schemas import (
    ExtractedSymptom,
    PossibleCondition,
    SymptomAnalysisResult,
)
from app.agents.symptom.tools import (
    extract_symptoms,
    normalize_symptoms,
    classify_severity,
    retrieve_conditions,
    generate_followup_questions,
    compute_confidence,
)
from app.agents.symptom.prompts import FINAL_RESPONSE_PROMPT
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("agent.symptom_analysis")

_EMERGENCY_RESPONSE = (
    "⚠️ URGENT: Based on the symptoms you've described, this may be a medical emergency. "
    "Please call emergency services (112 / 911) immediately or go to the nearest emergency room. "
    "Do not wait. If you are alone, call for help now.\n\n"
    "While waiting for help:\n"
    "• Stay calm and sit or lie down\n"
    "• Do not eat or drink anything\n"
    "• Keep your phone with you\n\n"
    "This is not a substitute for emergency medical care."
)


class SymptomAnalysisAgent(BaseAgent):
    """
    Production-ready symptom analysis agent.
    Replaces the Module 3 placeholder.
    """

    name = "SymptomAnalysisAgent"
    description = "Analyses symptoms, retrieves medical knowledge, and provides structured health guidance."
    supported_intents = ["symptom_analysis", "general_health_query"]
    tools: list = []

    async def execute(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        logger.info(
            "SymptomAnalysisAgent START | session=%s | message_len=%d",
            state["session_id"], len(state["user_message"]),
        )

        try:
            result = await self._run_pipeline(state)
        except Exception as exc:
            logger.error("Pipeline failed: %s", exc)
            result = SymptomAnalysisResult(
                requires_followup=True,
                followup_questions=["Could you describe your symptoms in more detail?"],
                recommendations=["Please consult a healthcare professional."],
                confidence=0.0,
            )

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Build natural language response
        if result.is_emergency:
            response_text = _EMERGENCY_RESPONSE
        else:
            response_text = await self._generate_response(result, state)

        logger.info(
            "SymptomAnalysisAgent END | session=%s | severity=%s | confidence=%.2f | "
            "symptoms=%d | conditions=%d | emergency=%s | elapsed_ms=%.1f",
            state["session_id"],
            result.severity,
            result.confidence,
            len(result.symptoms),
            len(result.possible_conditions),
            result.is_emergency,
            elapsed_ms,
        )

        state["agent_outputs"].append(
            self.build_output(
                response=response_text,
                confidence=result.confidence,
                metadata={
                    "structured_result": result.model_dump(),
                    "severity": result.severity,
                    "is_emergency": result.is_emergency,
                    "symptoms_count": len(result.symptoms),
                    "conditions_count": len(result.possible_conditions),
                    "rag_sources": result.sources,
                },
                execution_time_ms=elapsed_ms,
            )
        )
        return state

    async def _run_pipeline(self, state: AgentState) -> SymptomAnalysisResult:
        """Execute the full analysis pipeline step by step."""

        # Step 1 & 2: Extract + normalize symptoms
        symptoms = await extract_symptoms(state["user_message"])
        symptoms = normalize_symptoms(symptoms)

        # Step 3: Build context strings
        patient_ctx = self._build_patient_context(state)
        history_ctx = self._build_history_context(state)
        conv_history = self._build_conversation_context(state)

        # Step 4: Classify severity
        severity = await classify_severity(symptoms, patient_ctx, history_ctx)
        is_emergency = severity == "emergency"

        # Step 5: Retrieve conditions (skip if emergency — speed matters)
        if is_emergency:
            conditions_data: dict = {
                "possible_conditions": [],
                "requires_followup": False,
                "followup_questions": [],
                "recommendations": ["Call emergency services immediately."],
                "sources": [],
                "rag_docs_count": 0,
            }
        else:
            conditions_data = await retrieve_conditions(
                symptoms, patient_ctx, history_ctx, conv_history
            )

        # Step 6: Generate follow-up questions (memory-aware)
        existing_questions = conditions_data.get("followup_questions", [])
        if conditions_data.get("requires_followup") and not is_emergency:
            followup_qs = generate_followup_questions(
                symptoms, existing_questions, conv_history
            )
            # Merge LLM-generated and rule-based questions, deduplicate
            all_questions = list(dict.fromkeys(existing_questions + followup_qs))[:3]
        else:
            all_questions = existing_questions[:3]

        # Step 7: Compute confidence
        confidence = compute_confidence(
            symptoms,
            conditions_data.get("possible_conditions", []),
            conditions_data.get("rag_docs_count", 0),
        )

        # Step 8: Build structured result
        possible_conditions = [
            PossibleCondition(**c)
            for c in conditions_data.get("possible_conditions", [])
            if isinstance(c, dict) and "name" in c
        ]

        return SymptomAnalysisResult(
            symptoms=symptoms,
            possible_conditions=possible_conditions,
            severity=severity,  # type: ignore[arg-type]
            confidence=confidence,
            requires_followup=conditions_data.get("requires_followup", False),
            followup_questions=all_questions,
            recommendations=conditions_data.get("recommendations", []),
            sources=conditions_data.get("sources", []),
            is_emergency=is_emergency,
        )

    async def _generate_response(self, result: SymptomAnalysisResult, state: AgentState) -> str:
        """Generate a natural language response from the structured result using LLM."""
        try:
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.4)
            if not llm:
                return self._fallback_response(result)

            history = state.get("conversation_history", [])
            history_text = "\n".join(f"{h.get('role', 'user')}: {h.get('content', '')}" for h in history[-4:]) or "No prior context."

            prompt = FINAL_RESPONSE_PROMPT.format(
                user_message=state.get("user_message", ""),
                conversation_history=history_text,
                symptoms=", ".join(s.normalized for s in result.symptoms) or "none explicitly mentioned",
                conditions=", ".join(
                    f"{c.name} ({c.likelihood} likelihood)" for c in result.possible_conditions
                ) or "none identified",
                severity=result.severity,
                recommendations="\n".join(f"• {r}" for r in result.recommendations) or "rest and monitor",
                requires_followup=result.requires_followup,
                followup_questions="\n".join(f"• {q}" for q in result.followup_questions) or "none",
            )
            response = await llm.ainvoke(prompt)
            response_str = str(response.content).strip()
            if not result.is_emergency:
                response_str += "\n\n🛒 **PharmEasy & Nearby Medical Shop Order**: Would you like to order & pay for recommended medicines via **PharmEasy** (https://pharmeasy.in/) or your nearest local medical shop?"
            return response_str
        except Exception as exc:
            logger.error("Response generation failed: %s", exc)
            return self._fallback_response(result)

    def _fallback_response(self, result: SymptomAnalysisResult) -> str:
        """Rule-based fallback response when LLM is unavailable."""
        parts = ["Based on the information provided:\n"]

        if result.symptoms:
            symptom_list = ", ".join(s.normalized for s in result.symptoms)
            parts.append(f"Symptoms identified: {symptom_list}\n")

        if result.possible_conditions:
            parts.append("Possible conditions include:")
            for c in result.possible_conditions:
                parts.append(f"  • {c.name} ({c.likelihood} likelihood) — {c.reasoning}")

        parts.append(f"\nSeverity assessment: {result.severity.capitalize()}")

        if result.recommendations:
            parts.append("\nRecommendations:")
            for r in result.recommendations:
                parts.append(f"  • {r}")

        if result.followup_questions:
            parts.append("\nTo better assist you, please answer:")
            for q in result.followup_questions:
                parts.append(f"  • {q}")

        if not result.is_emergency:
            parts.append(
                "\n🛒 **PharmEasy & Nearby Medical Shop Order**: Would you like to order & pay for recommended medicines via **PharmEasy** (https://pharmeasy.in/) or your nearest local medical shop?"
            )

        parts.append(
            "\n⚕️ Please consult a qualified healthcare professional for proper diagnosis and treatment."
        )
        return "\n".join(parts)

    def _build_patient_context(self, state: AgentState) -> str:
        profile = state.get("patient_profile")
        if not profile:
            return "No patient profile available."
        parts = [
            f"Age group: {profile.get('date_of_birth', 'unknown')}",
            f"Gender: {profile.get('gender', 'unknown')}",
            f"Blood group: {profile.get('blood_group', 'unknown')}",
        ]
        if profile.get("allergies"):
            parts.append(f"Known allergies: {profile['allergies']}")
        if profile.get("chronic_diseases"):
            parts.append(f"Chronic conditions: {profile['chronic_diseases']}")
        return " | ".join(parts)

    def _build_history_context(self, state: AgentState) -> str:
        history = state.get("medical_history") or []
        if not history:
            return "No medical history available."
        recent = history[-3:]  # last 3 records
        return "; ".join(
            f"{h.get('diagnosis', 'unknown')} ({h.get('visit_date', 'unknown')})"
            for h in recent
        )

    def _build_conversation_context(self, state: AgentState) -> str:
        turns = state.get("conversation_history") or []
        if not turns:
            return ""
        # Last 6 turns (3 exchanges)
        recent = turns[-6:]
        return "\n".join(f"{t['role'].upper()}: {t['content']}" for t in recent)
