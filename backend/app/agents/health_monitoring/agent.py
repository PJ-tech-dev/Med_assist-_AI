"""
HealthMonitoringAgent — Production implementation.

Pipeline:
  1. Extract vitals from user message (LLM)
  2. Load historical readings from AgentState metadata
  3. Retrieve clinical reference ranges from ChromaDB (RAG)
  4. Check reference ranges (rule-based, age/gender-adjusted)
  5. Detect abnormalities (rule-based)
  6. Analyze trends — daily/weekly/monthly (rule-based)
  7. Calculate health score 0–100 (rule-based)
  8. Estimate risk level (rule-based)
  9. Build recommendations (memory-aware, deduped)
  10. Generate LLM response with score explanation
  11. Log all metrics

Safety guarantees:
  - Never diagnoses conditions
  - Never prescribes medications or dosages
  - Always recommends professional consultation for abnormal values
  - Critical values always surfaced first
"""

import time
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentState
from app.agents.health_monitoring.schemas import HealthMonitoringResult, HealthScore
from app.agents.health_monitoring.tools import (
    extract_vitals,
    check_reference_ranges,
    detect_abnormalities,
    analyze_trends,
    calculate_health_score,
    estimate_risk_level,
    compute_monitoring_confidence,
    build_monitoring_recommendations,
)
from app.agents.health_monitoring.rag import health_retriever
from app.agents.health_monitoring.prompts import (
    HEALTH_SCORE_EXPLANATION_PROMPT,
    MONITORING_RESPONSE_PROMPT,
)
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("agent.health_monitoring")

_CRITICAL_PREFIX = (
    "🚨 CRITICAL HEALTH ALERT: One or more of your vital signs are at a critical level. "
    "Please seek immediate medical attention.\n\n"
)


class HealthMonitoringAgent(BaseAgent):
    """Production-ready health monitoring agent. Replaces Module 3 placeholder."""

    name = "HealthMonitoringAgent"
    description = "Analyzes vital signs, detects abnormalities, tracks trends, and generates health scores."
    supported_intents = ["health_monitoring"]
    tools: list = []

    async def execute(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        logger.info(
            "HealthMonitoringAgent START | session=%s | message_len=%d",
            state["session_id"], len(state["user_message"]),
        )

        try:
            result = await self._run_pipeline(state)
        except Exception as exc:
            logger.error("Health monitoring pipeline failed: %s", exc)
            result = HealthMonitoringResult(
                recommendations=["Please consult a healthcare professional for vital sign assessment."],
                confidence=0.0,
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        response_text = await self._generate_response(result)

        if result.risk_level == "critical":
            response_text = _CRITICAL_PREFIX + response_text

        logger.info(
            "HealthMonitoringAgent END | session=%s | score=%.1f | risk=%s | "
            "vitals=%d | abnormalities=%d | trends=%d | elapsed_ms=%.1f",
            state["session_id"],
            result.health_score.score,
            result.risk_level,
            len(result.current_vitals),
            len(result.abnormalities),
            len(result.trend_analysis),
            elapsed_ms,
        )

        state["agent_outputs"].append(
            self.build_output(
                response=response_text,
                confidence=result.confidence,
                metadata={
                    "structured_result": result.model_dump(),
                    "health_score": result.health_score.score,
                    "classification": result.health_score.classification,
                    "risk_level": result.risk_level,
                    "vitals_count": len(result.current_vitals),
                    "abnormalities_count": len(result.abnormalities),
                    "trends_count": len(result.trend_analysis),
                },
                execution_time_ms=elapsed_ms,
            )
        )
        return state

    async def _run_pipeline(self, state: AgentState) -> HealthMonitoringResult:
        # Step 1: Extract vitals from message
        vitals = await extract_vitals(state["user_message"])

        # Step 2: Load patient context
        age, gender = self._get_patient_demographics(state)
        history = self._get_health_history(state)
        previous_recs = self._get_previous_recommendations(state)

        # Step 3: RAG retrieval
        query = " ".join(v.metric for v in vitals) or "vital signs reference ranges"
        rag_docs = health_retriever.retrieve(query, n_results=4)
        sources = list({d["source"] for d in rag_docs})

        # Step 4: Reference range check
        check_reference_ranges(vitals, age=age, gender=gender)

        # Step 5: Detect abnormalities
        abnormalities = detect_abnormalities(vitals)

        # Step 6: Trend analysis
        window = self._determine_window(history)
        trends = analyze_trends(history, window=window)

        # Step 7: Health score
        health_score = calculate_health_score(vitals)

        # Step 8: Risk level
        risk_level = estimate_risk_level(abnormalities, health_score, trends)

        # Step 9: Recommendations (memory-aware)
        recommendations = build_monitoring_recommendations(
            abnormalities, trends, risk_level, health_score, previous_recs
        )

        # Step 10: Confidence
        confidence = compute_monitoring_confidence(
            vitals_count=len(vitals),
            rag_docs_count=len(rag_docs),
            history_records=len(history),
        )

        # Step 11: LLM score explanation
        health_score.explanation = await self._explain_score(health_score, abnormalities)

        return HealthMonitoringResult(
            current_vitals=vitals,
            abnormalities=abnormalities,
            trend_analysis=trends,
            health_score=health_score,
            risk_level=risk_level,
            recommendations=recommendations,
            confidence=confidence,
            sources=sources,
            requires_followup=len(abnormalities) > 0 or risk_level in ("high", "critical"),
        )

    async def _explain_score(
        self, health_score: HealthScore, abnormalities: list
    ) -> str:
        try:
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.3)
            if not llm:
                return f"Your health score is {health_score.score}/100 ({health_score.classification})."
            components_text = "\n".join(
                f"  {k.replace('_', ' ').title()}: {v}/100"
                for k, v in health_score.components.items()
            )
            abnorm_text = "; ".join(
                f"{a.metric} ({a.status})" for a in abnormalities
            ) or "none"
            prompt = HEALTH_SCORE_EXPLANATION_PROMPT.format(
                score=health_score.score,
                classification=health_score.classification,
                components=components_text,
                abnormalities=abnorm_text,
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        except Exception as exc:
            logger.error("Score explanation failed: %s", exc)
            return (
                f"Your health score is {health_score.score}/100 ({health_score.classification}). "
                "This is based on the vital signs you provided."
            )

    async def _generate_response(self, result: HealthMonitoringResult) -> str:
        try:
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.3)
            if not llm:
                return f"Overall Health Score: {result.health_score.score}/100."
            vitals_text = "; ".join(
                f"{v.metric.replace('_', ' ')}: {v.value} {v.unit}"
                for v in result.current_vitals
            ) or "not provided"
            abnorm_text = "; ".join(
                f"{a.metric} ({a.status})" for a in result.abnormalities
            ) or "none"
            trend_text = "; ".join(
                f"{t.metric}: {t.direction}" for t in result.trend_analysis
            ) or "no trend data"
            recs_text = "\n".join(f"• {r}" for r in result.recommendations)

            prompt = MONITORING_RESPONSE_PROMPT.format(
                current_vitals=vitals_text,
                abnormalities=abnorm_text,
                health_score=result.health_score.score,
                classification=result.health_score.classification,
                risk_level=result.risk_level,
                trend_summary=trend_text,
                recommendations=recs_text,
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as exc:
            logger.error("Response generation failed: %s", exc)
            return self._fallback_response(result)

    def _fallback_response(self, result: HealthMonitoringResult) -> str:
        parts = ["Here is your health monitoring summary:\n"]

        if result.current_vitals:
            parts.append("📊 Current Vitals:")
            for v in result.current_vitals:
                parts.append(f"  • {v.metric.replace('_', ' ').title()}: {v.value} {v.unit}")

        if result.abnormalities:
            parts.append("\n⚠️ Abnormal Values:")
            for a in result.abnormalities:
                parts.append(
                    f"  • {a.metric.replace('_', ' ').title()}: {a.value} {a.unit} "
                    f"({a.status.upper()}) — normal range: {a.reference_range}"
                )

        if result.trend_analysis:
            parts.append("\n📈 Trends:")
            for t in result.trend_analysis:
                parts.append(f"  • {t.metric.replace('_', ' ').title()}: {t.direction}")

        parts.append(
            f"\n🏥 Health Score: {result.health_score.score}/100 "
            f"({result.health_score.classification.upper()})"
        )
        parts.append(f"Risk Level: {result.risk_level.upper()}")

        if result.recommendations:
            parts.append("\nRecommendations:")
            for r in result.recommendations:
                parts.append(f"  {r}")

        parts.append(
            "\n⚕️ This analysis is informational only. "
            "Always consult a qualified healthcare professional for medical decisions."
        )
        return "\n".join(parts)

    def _get_patient_demographics(self, state: AgentState) -> tuple[Optional[int], Optional[str]]:
        profile = state.get("patient_profile") or {}
        gender = profile.get("gender")
        dob = profile.get("date_of_birth")
        age = None
        if dob:
            try:
                from datetime import date
                birth = date.fromisoformat(str(dob))
                today = date.today()
                age = today.year - birth.year - (
                    (today.month, today.day) < (birth.month, birth.day)
                )
            except Exception:
                pass
        return age, gender

    def _get_health_history(self, state: AgentState) -> list[dict]:
        """
        Load historical health metrics from AgentState metadata.
        Populated by ChatService when patient context is loaded.
        """
        return state.get("metadata", {}).get("health_metrics_history", [])

    def _get_previous_recommendations(self, state: AgentState) -> list[str]:
        """Extract previous health recommendations from conversation history."""
        recs = []
        for turn in (state.get("conversation_history") or []):
            if turn.get("role") == "assistant":
                content = turn.get("content", "")
                for line in content.split("\n"):
                    line = line.strip().lstrip("•").strip()
                    if len(line) > 20:
                        recs.append(line)
        return recs

    def _determine_window(self, history: list[dict]) -> str:
        """Choose trend window based on available history depth."""
        if len(history) >= 20:
            return "monthly"
        if len(history) >= 7:
            return "weekly"
        return "daily"
