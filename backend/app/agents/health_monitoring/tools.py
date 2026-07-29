"""
Independent tools for HealthMonitoringAgent.
Each tool is a pure function — independently testable, no side effects.

Tools:
  1. VitalsExtractor          — extract vital readings from free text (LLM)
  2. ReferenceRangeChecker    — compare vitals against clinical ranges (rule-based)
  3. TrendAnalyzer            — detect improving/stable/declining trends (rule-based)
  4. AbnormalityDetector      — flag out-of-range values with severity (rule-based)
  5. HealthScoreCalculator    — compute 0–100 composite health score (rule-based)
  6. RiskLevelEstimator       — estimate overall risk level (rule-based)
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.health_monitoring.schemas import (
    VitalReading,
    ReferenceRange,
    AbnormalityFlag,
    MetricTrend,
    TrendPoint,
    HealthScore,
)
from app.agents.health_monitoring.prompts import (
    VITALS_EXTRACTION_PROMPT,
    TREND_INTERPRETATION_PROMPT,
)
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("health_monitoring.tools")

# ------------------------------------------------------------------ #
#  Clinical reference ranges — rule-based, sourced from WHO/AHA/NIH  #
# ------------------------------------------------------------------ #

# Structure: metric → {category: (min, max), ...}
# None means no lower/upper bound for that category
_REFERENCE_RANGES: dict[str, dict] = {
    "systolic_bp": {
        "unit": "mmHg",
        "source": "AHA",
        "ranges": [
            ("low",           None,  90.0),
            ("normal",        90.0, 120.0),
            ("elevated",     120.0, 130.0),
            ("high",         130.0, 180.0),
            ("critical",     180.0,  None),
        ],
    },
    "diastolic_bp": {
        "unit": "mmHg",
        "source": "AHA",
        "ranges": [
            ("low",           None,  60.0),
            ("normal",        60.0,  80.0),
            ("high",          80.0, 120.0),
            ("critical",     120.0,  None),
        ],
    },
    "heart_rate": {
        "unit": "bpm",
        "source": "WHO / NIH",
        "ranges": [
            ("low",           None,  50.0),
            ("borderline_low", 50.0, 60.0),
            ("normal",        60.0, 100.0),
            ("high",         100.0, 150.0),
            ("critical",     150.0,  None),
        ],
    },
    "blood_glucose": {
        "unit": "mg/dL",
        "source": "ADA / NIH",
        "ranges": [
            ("critical",      None,  54.0),
            ("low",           54.0,  70.0),
            ("normal",        70.0, 100.0),
            ("elevated",     100.0, 126.0),
            ("high",         126.0, 200.0),
            ("critical",     200.0,  None),
        ],
    },
    "spo2": {
        "unit": "%",
        "source": "WHO / NIH",
        "ranges": [
            ("critical",      None,  86.0),
            ("low",           86.0,  91.0),
            ("borderline_low", 91.0, 95.0),
            ("normal",        95.0, 100.0),
        ],
    },
    "body_temperature": {
        "unit": "°C",
        "source": "WHO / MedlinePlus",
        "ranges": [
            ("critical",      None,  35.0),
            ("low",           35.0,  36.1),
            ("normal",        36.1,  37.3),
            ("elevated",      37.3,  38.0),
            ("high",          38.0,  39.5),
            ("critical",      39.5,  None),
        ],
    },
    "respiratory_rate": {
        "unit": "breaths/min",
        "source": "NIH / MedlinePlus",
        "ranges": [
            ("low",           None,  12.0),
            ("normal",        12.0,  20.0),
            ("high",          20.0,  30.0),
            ("critical",      30.0,  None),
        ],
    },
    "bmi": {
        "unit": "kg/m²",
        "source": "WHO",
        "ranges": [
            ("low",           None,  18.5),
            ("normal",        18.5,  25.0),
            ("elevated",      25.0,  30.0),
            ("high",          30.0,  40.0),
            ("critical",      40.0,  None),
        ],
    },
}

# Health score weights per metric (must sum to 1.0)
_SCORE_WEIGHTS: dict[str, float] = {
    "systolic_bp":      0.20,
    "diastolic_bp":     0.15,
    "heart_rate":       0.15,
    "blood_glucose":    0.20,
    "spo2":             0.15,
    "body_temperature": 0.05,
    "respiratory_rate": 0.05,
    "bmi":              0.05,
}

# Category → sub-score (0–100)
_CATEGORY_SCORES: dict[str, float] = {
    "normal":         100.0,
    "borderline_low":  75.0,
    "borderline_high": 75.0,
    "elevated":        65.0,
    "low":             50.0,
    "high":            40.0,
    "critical":        10.0,
}

# Score classification thresholds
_SCORE_CLASSIFICATIONS = [
    (85.0, "excellent"),
    (70.0, "good"),
    (50.0, "fair"),
    (30.0, "poor"),
    (0.0,  "critical"),
]

# Risk level thresholds
_RISK_THRESHOLDS = [
    (85.0, "low"),
    (65.0, "moderate"),
    (40.0, "high"),
    (0.0,  "critical"),
]


def _get_llm(temperature: float = 0.1):
    from app.core.llm import get_llm
    return get_llm(temperature=temperature)


def _safe_json_parse(text: str, fallback) -> any:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed. Raw: %s", text[:200])
        return fallback


# ------------------------------------------------------------------ #
#  Tool 1: VitalsExtractor                                            #
# ------------------------------------------------------------------ #

async def extract_vitals(message: str) -> list[VitalReading]:
    """
    Extract vital sign readings from free-text user message using LLM.
    Returns structured VitalReading list.
    """
    logger.info("Extracting vitals from message (len=%d)", len(message))
    try:
        llm = _get_llm()
        prompt = VITALS_EXTRACTION_PROMPT.format(message=message)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = _safe_json_parse(response.content, [])

        readings = []
        for item in raw:
            if not isinstance(item, dict) or "metric" not in item:
                continue
            try:
                readings.append(VitalReading(
                    metric=item["metric"],
                    value=float(item["value"]),
                    unit=item.get("unit", ""),
                    raw_text=item.get("raw_text"),
                ))
            except (ValueError, KeyError):
                continue
        logger.info("Extracted %d vital readings", len(readings))
        return readings
    except Exception as exc:
        logger.error("Vitals extraction failed: %s", exc)
        return []


# ------------------------------------------------------------------ #
#  Tool 2: ReferenceRangeChecker                                      #
# ------------------------------------------------------------------ #

def get_metric_category(metric: str, value: float) -> tuple[str, str]:
    """
    Return (category, range_string) for a metric value.
    Rule-based — no LLM, deterministic.
    """
    config = _REFERENCE_RANGES.get(metric)
    if not config:
        return "unknown", "no reference available"

    unit = config["unit"]
    for category, low, high in config["ranges"]:
        if low is None and high is not None and value < high:
            return category, f"<{high} {unit}"
        if high is None and low is not None and value >= low:
            return category, f"≥{low} {unit}"
        if low is not None and high is not None and low <= value < high:
            return category, f"{low}–{high} {unit}"

    return "unknown", "out of defined range"


def check_reference_ranges(
    vitals: list[VitalReading],
    age: Optional[int] = None,
    gender: Optional[str] = None,
) -> list[ReferenceRange]:
    """
    Compare vital readings against clinical reference ranges.
    Returns ReferenceRange objects with category and source.
    Age/gender adjustments applied where applicable.
    """
    results = []
    for vital in vitals:
        config = _REFERENCE_RANGES.get(vital.metric)
        if not config:
            continue

        category, _ = get_metric_category(vital.metric, vital.value)

        # Age adjustment: elderly BP target is stricter
        age_adjusted = False
        if vital.metric == "systolic_bp" and age and age >= 65:
            age_adjusted = True

        results.append(ReferenceRange(
            metric=vital.metric,
            normal_min=_get_normal_min(vital.metric),
            normal_max=_get_normal_max(vital.metric),
            unit=config["unit"],
            category=category,
            source=config["source"],
            age_adjusted=age_adjusted,
            gender_adjusted=False,
        ))
    return results


def _get_normal_min(metric: str) -> Optional[float]:
    config = _REFERENCE_RANGES.get(metric)
    if not config:
        return None
    for category, low, high in config["ranges"]:
        if category == "normal" and low is not None:
            return low
    return None


def _get_normal_max(metric: str) -> Optional[float]:
    config = _REFERENCE_RANGES.get(metric)
    if not config:
        return None
    for category, low, high in config["ranges"]:
        if category == "normal" and high is not None:
            return high
    return None


# ------------------------------------------------------------------ #
#  Tool 3: TrendAnalyzer                                              #
# ------------------------------------------------------------------ #

def analyze_trends(
    history: list[dict],
    window: str = "weekly",
) -> list[MetricTrend]:
    """
    Detect improving/stable/declining trends from historical readings.
    history: list of dicts with keys matching HealthMetrics columns + 'recorded_at'.
    window: 'daily' | 'weekly' | 'monthly'
    Rule-based — no LLM.
    """
    if not history:
        return []

    # Group values per metric
    metric_series: dict[str, list[tuple[str, float]]] = {}
    for record in history:
        recorded_at = record.get("recorded_at", "")
        if isinstance(recorded_at, datetime):
            recorded_at = recorded_at.isoformat()

        for metric in _REFERENCE_RANGES:
            val = record.get(metric)
            if val is not None:
                metric_series.setdefault(metric, []).append((recorded_at, float(val)))

    trends = []
    for metric, series in metric_series.items():
        if len(series) < 2:
            trends.append(MetricTrend(
                metric=metric,
                direction="insufficient_data",
                window=window,
                data_points=len(series),
                latest_value=series[-1][1] if series else None,
                interpretation="Not enough data points for trend analysis.",
            ))
            continue

        # Sort by time
        series.sort(key=lambda x: x[0])
        values = [v for _, v in series]
        earliest = values[0]
        latest = values[-1]

        change_pct = ((latest - earliest) / earliest * 100) if earliest != 0 else 0.0

        # For SpO2: higher is better; for BP/glucose/BMI: lower is better
        higher_is_better = metric in ("spo2",)
        lower_is_better = metric in (
            "systolic_bp", "diastolic_bp", "blood_glucose", "bmi", "body_temperature"
        )

        threshold = 3.0  # % change to be considered a trend

        if abs(change_pct) < threshold:
            direction = "stable"
        elif higher_is_better:
            direction = "improving" if change_pct > 0 else "declining"
        elif lower_is_better:
            direction = "improving" if change_pct < 0 else "declining"
        else:
            # heart_rate, respiratory_rate — stable is best
            direction = "stable" if abs(change_pct) < threshold else (
                "declining" if change_pct > 0 else "improving"
            )

        config = _REFERENCE_RANGES.get(metric, {})
        unit = config.get("unit", "")
        normal_min = _get_normal_min(metric)
        normal_max = _get_normal_max(metric)
        ref_str = (
            f"{normal_min}–{normal_max} {unit}"
            if normal_min is not None and normal_max is not None
            else "see reference"
        )

        trends.append(MetricTrend(
            metric=metric,
            direction=direction,
            window=window,
            data_points=len(series),
            latest_value=latest,
            earliest_value=earliest,
            change_percent=round(change_pct, 1),
            series=[TrendPoint(recorded_at=ts, value=v) for ts, v in series],
            interpretation=_build_trend_interpretation(metric, direction, change_pct, unit),
        ))

    return trends


def _build_trend_interpretation(
    metric: str, direction: str, change_pct: float, unit: str
) -> str:
    label = metric.replace("_", " ").title()
    if direction == "stable":
        return f"{label} has remained stable over the selected period."
    elif direction == "improving":
        return f"{label} shows an improving trend ({abs(change_pct):.1f}% change)."
    elif direction == "declining":
        return f"{label} shows a declining trend ({abs(change_pct):.1f}% change) — monitor closely."
    return f"{label} trend: {direction}."


# ------------------------------------------------------------------ #
#  Tool 4: AbnormalityDetector                                        #
# ------------------------------------------------------------------ #

def detect_abnormalities(vitals: list[VitalReading]) -> list[AbnormalityFlag]:
    """
    Flag vital readings that fall outside normal ranges.
    Rule-based — no LLM, deterministic.
    """
    flags: list[AbnormalityFlag] = []

    for vital in vitals:
        category, range_str = get_metric_category(vital.metric, vital.value)
        if category in ("normal", "unknown"):
            continue

        config = _REFERENCE_RANGES.get(vital.metric, {})
        unit = config.get("unit", vital.unit)
        source = config.get("source", "")

        # Compute deviation from nearest normal boundary
        normal_min = _get_normal_min(vital.metric)
        normal_max = _get_normal_max(vital.metric)
        deviation = None
        if normal_min is not None and vital.value < normal_min and normal_min != 0:
            deviation = round((normal_min - vital.value) / normal_min * 100, 1)
        elif normal_max is not None and vital.value > normal_max and normal_max != 0:
            deviation = round((vital.value - normal_max) / normal_max * 100, 1)

        # Map category to AbnormalityFlag status
        status_map = {
            "low": "low",
            "borderline_low": "borderline_low",
            "elevated": "borderline_high",
            "high": "high",
            "critical": "critical",
        }
        status = status_map.get(category, "high")

        flags.append(AbnormalityFlag(
            metric=vital.metric,
            value=vital.value,
            unit=unit,
            status=status,
            deviation_percent=deviation,
            reference_range=range_str,
            source=source,
        ))
        logger.info("ABNORMALITY: %s=%.1f %s (%s)", vital.metric, vital.value, unit, status)

    return flags


# ------------------------------------------------------------------ #
#  Tool 5: HealthScoreCalculator                                      #
# ------------------------------------------------------------------ #

def calculate_health_score(vitals: list[VitalReading]) -> HealthScore:
    """
    Compute a composite health score from 0–100.
    Each metric contributes a weighted sub-score based on its category.
    Rule-based — no LLM.
    """
    if not vitals:
        return HealthScore(
            score=0.0,
            classification="fair",
            explanation="No vital signs provided for scoring.",
        )

    components: dict[str, float] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for vital in vitals:
        weight = _SCORE_WEIGHTS.get(vital.metric)
        if weight is None:
            continue
        category, _ = get_metric_category(vital.metric, vital.value)
        sub_score = _CATEGORY_SCORES.get(category, 50.0)
        components[vital.metric] = round(sub_score, 1)
        weighted_sum += sub_score * weight
        total_weight += weight

    if total_weight == 0:
        score = 0.0
    else:
        score = round(weighted_sum / total_weight, 1)

    classification = "fair"
    for threshold, label in _SCORE_CLASSIFICATIONS:
        if score >= threshold:
            classification = label
            break

    return HealthScore(
        score=score,
        classification=classification,
        components=components,
        explanation="",  # filled by LLM in agent
    )


# ------------------------------------------------------------------ #
#  Tool 6: RiskLevelEstimator                                         #
# ------------------------------------------------------------------ #

def estimate_risk_level(
    abnormalities: list[AbnormalityFlag],
    health_score: HealthScore,
    trends: list[MetricTrend],
) -> str:
    """
    Estimate overall risk level: low | moderate | high | critical.
    Rule-based — deterministic.
    """
    # Critical abnormality → always critical risk
    if any(a.status == "critical" for a in abnormalities):
        return "critical"

    # Multiple high abnormalities → high risk
    high_count = sum(1 for a in abnormalities if a.status == "high")
    if high_count >= 2:
        return "high"

    # Declining trend on critical metric → escalate
    critical_metrics = {"systolic_bp", "diastolic_bp", "spo2", "blood_glucose"}
    declining_critical = any(
        t.metric in critical_metrics and t.direction == "declining"
        for t in trends
    )
    if declining_critical and high_count >= 1:
        return "high"

    # Use health score as primary signal
    for threshold, level in _RISK_THRESHOLDS:
        if health_score.score >= threshold:
            return level

    return "critical"


# ------------------------------------------------------------------ #
#  Confidence Calculator                                              #
# ------------------------------------------------------------------ #

def compute_monitoring_confidence(
    vitals_count: int,
    rag_docs_count: int,
    history_records: int,
) -> float:
    """Compute confidence score [0.0, 1.0]."""
    score = 0.0
    score += min(vitals_count * 0.12, 0.40)
    score += min(rag_docs_count * 0.06, 0.30)
    score += min(history_records * 0.03, 0.30)
    return round(min(score, 1.0), 2)


# ------------------------------------------------------------------ #
#  Recommendations Builder                                            #
# ------------------------------------------------------------------ #

def build_monitoring_recommendations(
    abnormalities: list[AbnormalityFlag],
    trends: list[MetricTrend],
    risk_level: str,
    health_score: HealthScore,
    previous_recommendations: list[str],
) -> list[str]:
    """
    Build a prioritised, deduplicated list of health recommendations.
    Avoids repeating recommendations already given in conversation history.
    """
    recs: list[str] = []
    prev_set = {r.lower().strip() for r in previous_recommendations}

    def _add(rec: str) -> None:
        if rec.lower().strip() not in prev_set:
            recs.append(rec)

    # Critical flags first
    critical = [a for a in abnormalities if a.status == "critical"]
    for a in critical:
        _add(f"🚨 {a.metric.replace('_', ' ').title()} is at a critical level ({a.value} {a.unit}). "
             "Seek immediate medical attention.")

    # High flags
    high = [a for a in abnormalities if a.status == "high"]
    for a in high:
        _add(f"⚠️ {a.metric.replace('_', ' ').title()} is elevated ({a.value} {a.unit}). "
             "Consult your healthcare provider.")

    # Declining trends on key metrics
    for t in trends:
        if t.direction == "declining" and t.metric in (
            "spo2", "systolic_bp", "diastolic_bp", "blood_glucose"
        ):
            _add(f"📉 {t.metric.replace('_', ' ').title()} shows a declining trend. "
                 "Schedule a check-up with your doctor.")

    # Risk-level recommendations
    if risk_level == "critical":
        _add("🚨 Your current vital signs indicate a critical health situation. "
             "Please seek emergency medical care immediately.")
    elif risk_level == "high":
        _add("Please schedule an urgent appointment with your healthcare provider.")
    elif risk_level == "moderate":
        _add("Consider scheduling a routine check-up with your healthcare provider.")

    # General
    _add("Continue monitoring your vital signs regularly and keep a log for your doctor.")
    _add(
        "⚕️ This analysis is informational only. "
        "Always consult a qualified healthcare professional for medical decisions."
    )

    return recs
