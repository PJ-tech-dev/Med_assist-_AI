"""
MedicalReportAnalysisAgent — Production implementation.

Pipeline:
  1. Extract text from report (OCR or raw text from state metadata)
  2. Detect report type (rule-based parser)
  3. Extract lab values (LLM + regex fallback)
  4. Check reference ranges (rule-based)
  5. Detect abnormalities (rule-based)
  6. Compare trends with previous reports (rule-based)
  7. Retrieve medical knowledge from ChromaDB (RAG)
  8. Generate lifestyle recommendations (LLM)
  9. Generate patient-friendly summary (LLM)
  10. Compute confidence score (rule-based)
  11. Build AgentOutput

Safety guarantees:
  - Never diagnoses conditions
  - Never prescribes medications
  - Always recommends professional consultation for abnormal values
  - Critical values always surfaced first
"""

import time
from typing import Optional
from datetime import date
from beanie import PydanticObjectId

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentState
from app.agents.report_analysis.schemas import (
    MedicalReportAnalysisResult,
    MedicalReportSummary,
)
from app.agents.report_analysis.tools import (
    extract_lab_values,
    check_reference_ranges,
    detect_abnormalities,
    compare_trends,
    generate_lifestyle_recommendations,
    calculate_report_confidence,
    estimate_risk_level,
)
from app.agents.report_analysis.parser import detect_report_type, clean_report_text
from app.agents.report_analysis.rag import report_retriever
from app.agents.report_analysis.prompts import PATIENT_FRIENDLY_SUMMARY_PROMPT
from app.models.medical_history import MedicalHistory
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("agent.report_analysis")

_CRITICAL_PREFIX = (
    "🚨 CRITICAL FINDINGS ALERT: One or more of your lab values are at a critical level. "
    "Please seek immediate medical attention.\n\n"
)


class MedicalReportAnalysisAgent(BaseAgent):
    """Production-ready medical report analysis agent. Replaces Module 3 placeholder."""

    name = "MedicalReportAnalysisAgent"
    description = "Analyzes medical reports, extracts lab values, detects abnormalities, and generates patient-friendly summaries."
    supported_intents = ["report_analysis"]
    tools: list = []

    async def execute(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        logger.info(
            "MedicalReportAnalysisAgent START | session=%s | message_len=%d",
            state["session_id"], len(state["user_message"]),
        )

        try:
            result = await self._run_pipeline(state)
        except Exception as exc:
            logger.error("Report analysis pipeline failed: %s", exc)
            result = MedicalReportAnalysisResult(
                recommendations=["Please consult a healthcare professional for report interpretation."],
                confidence=0.0,
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        response_text = await self._generate_response(result)

        if result.risk_level == "critical":
            response_text = _CRITICAL_PREFIX + response_text

        logger.info(
            "MedicalReportAnalysisAgent END | session=%s | report_type=%s | "
            "lab_values=%d | abnormal=%d | risk=%s | confidence=%.2f | elapsed_ms=%.1f",
            state["session_id"],
            result.report_type,
            len(result.lab_values),
            len(result.abnormal_findings),
            result.risk_level,
            result.confidence,
            elapsed_ms,
        )

        state["agent_outputs"].append(
            self.build_output(
                response=response_text,
                confidence=result.confidence,
                metadata={
                    "structured_result": result.model_dump(),
                    "report_type": result.report_type,
                    "lab_values_count": len(result.lab_values),
                    "abnormal_count": len(result.abnormal_findings),
                    "risk_level": result.risk_level,
                    "requires_followup": result.requires_followup,
                },
                execution_time_ms=elapsed_ms,
            )
        )
        
        # Save the report findings to the medical history database so it appears for the MedicalHistoryAgent
        try:
            user_id_str = state.get("user_id")
            if user_id_str and result.report_type:
                new_history = MedicalHistory(
                    patient_id=PydanticObjectId(user_id_str),
                    diagnosis=f"Medical Report Analysis: {result.report_type}",
                    visit_date=date.today(),
                    notes=response_text,
                )
                await new_history.insert()
                logger.info("Saved report analysis to MedicalHistory for user %s", user_id_str)
        except Exception as e:
            logger.error("Failed to save report analysis to MedicalHistory: %s", e)

        return state

    async def _run_pipeline(self, state: AgentState) -> MedicalReportAnalysisResult:
        # Step 1: Get report text — from metadata (uploaded file) or user message
        raw_text = state.get("metadata", {}).get("report_text") or state["user_message"]
        clean_text = clean_report_text(raw_text)

        # Step 2: Detect report type
        report_type = detect_report_type(clean_text)
        logger.info("Detected report type: %s", report_type)

        # Step 3: Extract lab values
        gender = self._get_gender(state)
        lab_values = await extract_lab_values(clean_text, report_type)

        # Step 4: Reference range check
        range_results = check_reference_ranges(lab_values, gender=gender)

        # Step 5: Detect abnormalities
        abnormal_findings, normal_findings = detect_abnormalities(lab_values, range_results)

        # Step 6: Trend comparison
        previous_reports = state.get("metadata", {}).get("previous_reports", [])
        trend_results = compare_trends(lab_values, previous_reports)

        # Step 7: RAG retrieval
        query = f"{report_type} {' '.join(v.test_name for v in lab_values[:5])}"
        rag_docs = report_retriever.retrieve(query, n_results=4)
        rag_context = report_retriever.format_context(rag_docs)
        sources = list({d["source"] for d in rag_docs})

        # Step 8: Lifestyle recommendations
        patient_ctx = self._build_patient_context(state)
        lifestyle_recs = await generate_lifestyle_recommendations(
            report_type, abnormal_findings, patient_ctx, rag_context
        )

        # Step 9: Risk level + confidence
        risk_level = estimate_risk_level(abnormal_findings)
        ocr_conf = state.get("metadata", {}).get("ocr_confidence", 0.8)
        confidence = calculate_report_confidence(
            lab_values_count=len(lab_values),
            abnormal_count=len(abnormal_findings),
            rag_docs_count=len(rag_docs),
            ocr_confidence=ocr_conf,
            text_length=len(clean_text),
        )

        # Step 10: Build summary
        key_findings = [
            f"{a.test_name}: {a.value} {a.unit} ({a.status.upper()}) — normal: {a.normal_range}"
            for a in abnormal_findings[:5]
        ]
        followup_recs = self._build_followup_recommendations(abnormal_findings, risk_level)

        summary = MedicalReportSummary(
            report_type=report_type,
            patient_friendly="",  # filled by LLM below
            clinical_summary=self._build_clinical_summary(report_type, abnormal_findings, normal_findings),
            key_findings=key_findings,
            lifestyle_recommendations=lifestyle_recs,
            followup_recommendations=followup_recs,
        )

        return MedicalReportAnalysisResult(
            report_type=report_type,
            lab_values=lab_values,
            abnormal_findings=abnormal_findings,
            normal_findings=normal_findings,
            trend_results=trend_results,
            summary=summary,
            risk_level=risk_level,
            confidence=confidence,
            sources=sources,
            requires_followup=len(abnormal_findings) > 0 or risk_level in ("high", "critical"),
        )

    async def _generate_response(self, result: MedicalReportAnalysisResult) -> str:
        try:
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.3)
            if not llm:
                return self._fallback_response(result)
            abnorm_text = "; ".join(
                f"{a.test_name} ({a.status}): {a.value} {a.unit}" for a in result.abnormal_findings
            ) or "none"
            clinical_notes = "\n".join(f"• {f}" for f in result.summary.key_findings) or "All values within normal range."

            prompt = PATIENT_FRIENDLY_SUMMARY_PROMPT.format(
                report_type=result.report_type,
                abnormal_findings=abnorm_text,
                normal_count=len(result.normal_findings),
                risk_level=result.risk_level,
                clinical_notes=clinical_notes,
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as exc:
            logger.error("Response generation failed: %s", exc)
            return self._fallback_response(result)

    def _fallback_response(self, result: MedicalReportAnalysisResult) -> str:
        parts = [f"📋 Medical Report Analysis — {result.report_type}\n"]

        if result.abnormal_findings:
            parts.append("⚠️ Abnormal Values:")
            for a in result.abnormal_findings:
                parts.append(
                    f"  • {a.test_name}: {a.value} {a.unit} ({a.status.upper()}) "
                    f"— Normal: {a.normal_range}"
                )

        if result.normal_findings:
            parts.append(f"\n✅ {len(result.normal_findings)} value(s) within normal range.")

        if result.trend_results:
            parts.append("\n📈 Trends:")
            for t in result.trend_results:
                parts.append(f"  • {t.test_name}: {t.direction}")

        parts.append(f"\nRisk Level: {result.risk_level.upper()}")

        if result.summary.followup_recommendations:
            parts.append("\nRecommendations:")
            for r in result.summary.followup_recommendations:
                parts.append(f"  {r}")

        parts.append(
            "\n⚕️ This analysis is informational only. "
            "Always consult a qualified healthcare professional for medical interpretation."
        )
        return "\n".join(parts)

    def _build_clinical_summary(
        self,
        report_type: str,
        abnormal: list,
        normal: list,
    ) -> str:
        total = len(abnormal) + len(normal)
        if total == 0:
            return f"{report_type} report received. No lab values could be extracted."
        critical = [a for a in abnormal if a.status == "critical"]
        high = [a for a in abnormal if a.status == "high"]
        summary = f"{report_type} report: {total} values analyzed. "
        if critical:
            summary += f"{len(critical)} critical value(s). "
        if high:
            summary += f"{len(high)} high value(s). "
        summary += f"{len(normal)} within normal range."
        return summary

    def _build_followup_recommendations(self, abnormal: list, risk_level: str) -> list[str]:
        recs = []
        critical = [a for a in abnormal if a.status == "critical"]
        if critical:
            recs.append("🚨 Seek immediate medical attention for critical lab values.")
        if risk_level in ("high", "critical"):
            recs.append("Schedule an urgent appointment with your healthcare provider.")
        elif risk_level == "moderate":
            recs.append("Schedule a follow-up appointment with your doctor to discuss these results.")
        if abnormal:
            recs.append("Do not self-medicate based on these results — consult your doctor.")
        recs.append(
            "⚕️ This analysis is informational only. "
            "Always consult a qualified healthcare professional."
        )
        return recs

    def _get_gender(self, state: AgentState) -> Optional[str]:
        profile = state.get("patient_profile") or {}
        return profile.get("gender")

    def _build_patient_context(self, state: AgentState) -> str:
        profile = state.get("patient_profile")
        if not profile:
            return "No patient profile available."
        parts = [f"Gender: {profile.get('gender', 'unknown')}"]
        if profile.get("date_of_birth"):
            parts.append(f"DOB: {profile['date_of_birth']}")
        if profile.get("chronic_diseases"):
            parts.append(f"Conditions: {profile['chronic_diseases']}")
        return " | ".join(parts)
