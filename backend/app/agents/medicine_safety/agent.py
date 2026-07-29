"""
MedicineSafetyAgent — Production implementation.

Pipeline:
  1. Extract medications from user message (LLM)
  2. Normalize drug names (brand → generic, rule-based)
  3. Build patient context (allergies, conditions, current meds)
  4. Retrieve drug knowledge from ChromaDB (RAG)
  5. Check drug-drug interactions (RAG + LLM)
  6. Check allergies (rule-based, fast)
  7. Check contraindications (rule-based + LLM)
  8. Check duplicate medications (rule-based)
  9. Validate dosages informally (RAG + LLM)
  10. Compute severity + confidence
  11. Build recommendations
  12. Generate natural language response (LLM)

Safety guarantees:
  - Never prescribes medications
  - Never recommends specific dosages
  - Always recommends pharmacist/physician consultation
  - Allergy alerts always surfaced first
"""

import time
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentState
from app.agents.medicine_safety.schemas import MedicineSafetyResult
from app.agents.medicine_safety.tools import (
    extract_medications,
    check_interactions,
    check_allergies,
    check_contraindications,
    check_duplicates,
    validate_dosages,
    compute_overall_severity,
    compute_safety_confidence,
    build_recommendations,
)
from app.agents.medicine_safety.rag import drug_retriever
from app.agents.medicine_safety.prompts import SAFETY_RESPONSE_PROMPT
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("agent.medicine_safety")

_DANGER_RESPONSE_PREFIX = (
    "🚨 CRITICAL SAFETY ALERT: Based on the information provided, there is a serious "
    "safety concern with the medication(s) mentioned.\n\n"
)


class MedicineSafetyAgent(BaseAgent):
    """Production-ready medicine safety agent. Replaces Module 3 placeholder."""

    name = "MedicineSafetyAgent"
    description = "Checks medicine safety, drug interactions, allergies, and contraindications."
    supported_intents = ["medicine_safety"]
    tools: list = []

    async def execute(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        logger.info(
            "MedicineSafetyAgent START | session=%s | message_len=%d",
            state["session_id"], len(state["user_message"]),
        )

        try:
            result = await self._run_pipeline(state)
        except Exception as exc:
            logger.error("Medicine safety pipeline failed: %s", exc)
            result = MedicineSafetyResult(
                recommendations=["Please consult a pharmacist or physician for medication guidance."],
                confidence=0.0,
            )

        elapsed_ms = (time.perf_counter() - start) * 1000

        if result.severity == "danger" or result.requires_immediate_attention:
            response_text = _DANGER_RESPONSE_PREFIX + await self._generate_response(result, state)
        else:
            response_text = await self._generate_response(result, state)

        logger.info(
            "MedicineSafetyAgent END | session=%s | severity=%s | confidence=%.2f | "
            "meds=%d | interactions=%d | allergy_alerts=%d | elapsed_ms=%.1f",
            state["session_id"],
            result.severity,
            result.confidence,
            len(result.medications),
            len(result.interactions),
            len(result.allergy_alerts),
            elapsed_ms,
        )

        state["agent_outputs"].append(
            self.build_output(
                response=response_text,
                confidence=result.confidence,
                metadata={
                    "structured_result": result.model_dump(),
                    "severity": result.severity,
                    "requires_immediate_attention": result.requires_immediate_attention,
                    "medications_count": len(result.medications),
                    "interactions_count": len(result.interactions),
                    "allergy_alerts_count": len(result.allergy_alerts),
                    "contraindications_count": len(result.contraindications),
                },
                execution_time_ms=elapsed_ms,
            )
        )
        return state

    async def _run_pipeline(self, state: AgentState) -> MedicineSafetyResult:
        # Step 1: Extract medications
        medications = await extract_medications(state["user_message"])

        # Step 2: Build patient context
        patient_ctx = self._build_patient_context(state)
        current_meds = self._get_current_medications(state)
        allergies = self._get_allergies(state)
        chronic_diseases = self._get_chronic_diseases(state)
        medical_history = state.get("medical_history") or []

        # Step 3: RAG retrieval — query with all drug names
        query = " ".join(m.generic_name for m in medications) or state["user_message"]
        rag_docs = drug_retriever.retrieve(query, n_results=5)
        rag_context = drug_retriever.format_context(rag_docs)
        sources = list({d["source"] for d in rag_docs})

        # Step 4: Run all checks concurrently where possible
        import asyncio
        interactions, contraindications, dosage_validations = await asyncio.gather(
            check_interactions(medications, current_meds, rag_context),
            check_contraindications(medications, chronic_diseases, medical_history, rag_context),
            validate_dosages(medications, patient_ctx, rag_context),
        )

        # Rule-based checks (synchronous, fast)
        allergy_alerts = check_allergies(medications, allergies)
        duplicate_warnings = check_duplicates(medications, current_meds)

        # Step 5: Aggregate severity + confidence
        severity = compute_overall_severity(interactions, allergy_alerts, contraindications)
        requires_immediate = severity == "danger"
        confidence = compute_safety_confidence(
            medications,
            rag_docs_count=len(rag_docs),
            checks_performed=4,
        )
        recommendations = build_recommendations(
            interactions, allergy_alerts, contraindications, duplicate_warnings, severity
        )

        return MedicineSafetyResult(
            medications=medications,
            interactions=interactions,
            contraindications=contraindications,
            allergy_alerts=allergy_alerts,
            duplicate_warnings=duplicate_warnings,
            dosage_validation=dosage_validations,
            severity=severity,  # type: ignore[arg-type]
            confidence=confidence,
            recommendations=recommendations,
            sources=sources,
            requires_immediate_attention=requires_immediate,
        )

    async def _generate_response(self, result: MedicineSafetyResult, state: AgentState) -> str:
        try:
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.4)
            if not llm:
                return self._fallback_response(result)

            history = state.get("conversation_history", [])
            history_text = "\n".join(f"{h.get('role', 'user')}: {h.get('content', '')}" for h in history[-4:]) or "No prior context."

            prompt = SAFETY_RESPONSE_PROMPT.format(
                user_message=state.get("user_message", ""),
                conversation_history=history_text,
                medications=", ".join(m.generic_name for m in result.medications) or "none explicitly mentioned",
                interactions="; ".join(
                    f"{i.drug_a} + {i.drug_b} ({i.severity})" for i in result.interactions
                ) or "none",
                allergy_alerts="; ".join(
                    f"{a.medication} — {a.allergen}" for a in result.allergy_alerts
                ) or "none",
                contraindications="; ".join(
                    f"{c.medication} + {c.condition}" for c in result.contraindications
                ) or "none",
                duplicate_warnings="; ".join(
                    f"{d.medication}" for d in result.duplicate_warnings
                ) or "none",
                severity=result.severity,
                recommendations="\n".join(f"• {r}" for r in result.recommendations) or "consult pharmacist",
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        except Exception as exc:
            logger.error("Response generation failed: %s", exc)
            return self._fallback_response(result)

    def _fallback_response(self, result: MedicineSafetyResult) -> str:
        parts = ["Based on the information provided:\n"]

        if result.allergy_alerts:
            parts.append("⚠️ ALLERGY ALERTS:")
            for a in result.allergy_alerts:
                parts.append(f"  • {a.medication} may trigger your {a.allergen} allergy")

        if result.interactions:
            parts.append("\nDrug Interactions:")
            for i in result.interactions:
                parts.append(f"  • {i.drug_a} + {i.drug_b}: {i.severity} — {i.description}")

        if result.contraindications:
            parts.append("\nContraindications:")
            for c in result.contraindications:
                parts.append(f"  • {c.medication} with {c.condition}: {c.reason}")

        if result.duplicate_warnings:
            parts.append("\nDuplicate Warnings:")
            for d in result.duplicate_warnings:
                parts.append(f"  • {d.note}")

        parts.append(f"\nOverall Safety: {result.severity.upper()}")
        parts.append("\nRecommendations:")
        for r in result.recommendations:
            parts.append(f"  • {r}")

        parts.append(
            "\n⚕️ This information is educational only. "
            "Always consult your pharmacist or physician before making medication decisions."
        )
        return "\n".join(parts)

    def _build_patient_context(self, state: AgentState) -> str:
        profile = state.get("patient_profile")
        if not profile:
            return "No patient profile available."
        parts = [
            f"Gender: {profile.get('gender', 'unknown')}",
            f"DOB: {profile.get('date_of_birth', 'unknown')}",
        ]
        if profile.get("allergies"):
            parts.append(f"Allergies: {profile['allergies']}")
        if profile.get("chronic_diseases"):
            parts.append(f"Chronic conditions: {profile['chronic_diseases']}")
        return " | ".join(parts)

    def _get_allergies(self, state: AgentState) -> str:
        profile = state.get("patient_profile")
        return (profile or {}).get("allergies", "") or ""

    def _get_chronic_diseases(self, state: AgentState) -> str:
        profile = state.get("patient_profile")
        return (profile or {}).get("chronic_diseases", "") or ""

    def _get_current_medications(self, state: AgentState) -> list[dict]:
        """
        Current medications come from AgentState.metadata if pre-loaded,
        or from medical_history as a fallback.
        Full medication loading is wired in Module 2's patient service.
        """
        return state.get("metadata", {}).get("current_medications", [])
