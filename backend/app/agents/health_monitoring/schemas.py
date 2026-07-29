"""
Pydantic v2 schemas for HealthMonitoringAgent structured output.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class VitalReading(BaseModel):
    """A single extracted vital sign value."""
    metric: str                          # e.g. "systolic_bp", "heart_rate"
    value: float
    unit: str                            # e.g. "mmHg", "bpm", "mg/dL"
    raw_text: Optional[str] = None       # original text fragment


class ReferenceRange(BaseModel):
    """Clinical reference range for a vital metric."""
    metric: str
    normal_min: Optional[float] = None
    normal_max: Optional[float] = None
    unit: str
    category: str                        # e.g. "normal", "elevated", "high", "critical"
    source: str                          # WHO / AHA / NIH / MedlinePlus
    age_adjusted: bool = False
    gender_adjusted: bool = False


class AbnormalityFlag(BaseModel):
    """A detected abnormal vital sign."""
    metric: str
    value: float
    unit: str
    status: Literal["low", "borderline_low", "normal", "borderline_high", "high", "critical"]
    deviation_percent: Optional[float] = None   # % above/below normal range
    reference_range: Optional[str] = None       # human-readable range string
    source: Optional[str] = None


class TrendPoint(BaseModel):
    """A single data point in a trend series."""
    recorded_at: str                     # ISO datetime string
    value: float


class MetricTrend(BaseModel):
    """Trend analysis for a single vital metric."""
    metric: str
    direction: Literal["improving", "stable", "declining", "insufficient_data"]
    window: Literal["daily", "weekly", "monthly"]
    data_points: int
    latest_value: Optional[float] = None
    earliest_value: Optional[float] = None
    change_percent: Optional[float] = None
    series: list[TrendPoint] = Field(default_factory=list)
    interpretation: str = ""


class HealthScore(BaseModel):
    """Composite health score from 0–100."""
    score: float = Field(ge=0.0, le=100.0)
    classification: Literal["excellent", "good", "fair", "poor", "critical"]
    components: dict[str, float] = Field(default_factory=dict)  # metric → sub-score
    explanation: str = ""


class HealthMonitoringResult(BaseModel):
    """
    Full structured output of HealthMonitoringAgent.
    Serialised into AgentOutput.metadata["structured_result"].
    """
    current_vitals: list[VitalReading] = Field(default_factory=list)
    abnormalities: list[AbnormalityFlag] = Field(default_factory=list)
    trend_analysis: list[MetricTrend] = Field(default_factory=list)
    health_score: HealthScore = Field(
        default_factory=lambda: HealthScore(
            score=0.0, classification="fair", explanation="Insufficient data"
        )
    )
    risk_level: Literal["low", "moderate", "high", "critical"] = "low"
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    sources: list[str] = Field(default_factory=list)
    requires_followup: bool = False
    disclaimer: str = (
        "This analysis is for informational purposes only. "
        "Always consult a qualified healthcare professional for medical advice."
    )
