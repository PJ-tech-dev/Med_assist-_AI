"""
Pydantic schemas for SymptomAnalysisAgent structured output.
These are used both for LLM output parsing and API response serialisation.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ExtractedSymptom(BaseModel):
    raw: str                          # original text from user
    normalized: str                   # standardised medical term
    duration: Optional[str] = None    # e.g. "3 days"
    severity_hint: Optional[str] = None  # e.g. "mild", "severe"
    body_part: Optional[str] = None


class PossibleCondition(BaseModel):
    name: str
    likelihood: Literal["low", "moderate", "high"]
    reasoning: str                    # one-sentence explanation
    source: Optional[str] = None      # e.g. "WHO", "CDC", "NIH"


class SymptomAnalysisResult(BaseModel):
    """
    Structured output returned by SymptomAnalysisAgent.
    This is serialised into AgentOutput.metadata["structured_result"].
    """
    symptoms: list[ExtractedSymptom] = Field(default_factory=list)
    possible_conditions: list[PossibleCondition] = Field(default_factory=list)
    severity: Literal["mild", "moderate", "severe", "emergency"] = "mild"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    requires_followup: bool = False
    followup_questions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    is_emergency: bool = False
    disclaimer: str = (
        "This information is for educational purposes only and does not constitute "
        "medical advice. Please consult a qualified healthcare professional."
    )
