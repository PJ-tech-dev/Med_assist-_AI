"""
Pydantic v2 schemas for MedicalReportAnalysisAgent structured output.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ExtractedLabValue(BaseModel):
    """A single lab value extracted from the report."""
    test_name: str                          # e.g. "Hemoglobin"
    value: float
    unit: str                               # e.g. "g/dL"
    raw_text: Optional[str] = None          # original text fragment
    panel: Optional[str] = None             # e.g. "CBC", "LFT"


class ReferenceRange(BaseModel):
    """Clinical reference range for a lab test."""
    test_name: str
    normal_min: Optional[float] = None
    normal_max: Optional[float] = None
    unit: str
    source: str                             # WHO / NIH / MedlinePlus
    age_adjusted: bool = False
    gender_adjusted: bool = False


class AbnormalFinding(BaseModel):
    """A lab value that falls outside the normal range."""
    test_name: str
    value: float
    unit: str
    status: Literal["low", "borderline_low", "normal", "borderline_high", "high", "critical"]
    normal_range: str                       # human-readable e.g. "12.0–17.5 g/dL"
    deviation_percent: Optional[float] = None
    clinical_significance: Optional[str] = None
    source: Optional[str] = None


class TrendResult(BaseModel):
    """Trend comparison for a single test across multiple reports."""
    test_name: str
    direction: Literal["improving", "stable", "worsening", "insufficient_data"]
    previous_value: Optional[float] = None
    current_value: Optional[float] = None
    change_percent: Optional[float] = None
    interpretation: str = ""


class MedicalReportSummary(BaseModel):
    """Patient-friendly and clinical summaries."""
    report_type: str
    patient_friendly: str
    clinical_summary: str
    key_findings: list[str] = Field(default_factory=list)
    lifestyle_recommendations: list[str] = Field(default_factory=list)
    followup_recommendations: list[str] = Field(default_factory=list)


class MedicalReportAnalysisResult(BaseModel):
    """
    Full structured output of MedicalReportAnalysisAgent.
    Serialised into AgentOutput.metadata['structured_result'].
    """
    report_type: str = "unknown"
    lab_values: list[ExtractedLabValue] = Field(default_factory=list)
    abnormal_findings: list[AbnormalFinding] = Field(default_factory=list)
    normal_findings: list[ExtractedLabValue] = Field(default_factory=list)
    trend_results: list[TrendResult] = Field(default_factory=list)
    summary: MedicalReportSummary = Field(
        default_factory=lambda: MedicalReportSummary(
            report_type="unknown",
            patient_friendly="",
            clinical_summary="",
        )
    )
    risk_level: Literal["low", "moderate", "high", "critical"] = "low"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    sources: list[str] = Field(default_factory=list)
    requires_followup: bool = False
    disclaimer: str = (
        "This analysis is for informational purposes only. "
        "Always consult a qualified healthcare professional for medical interpretation."
    )
