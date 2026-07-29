"""
Independent tools for MedicalReportAnalysisAgent.
Each tool is a pure function — independently testable, no side effects.

Tools:
  1. OCRProcessor           — extract text from file bytes (in ocr.py)
  2. ReportParser           — detect type, clean text (in parser.py)
  3. LabValueExtractor      — extract structured lab values (LLM)
  4. ReferenceRangeChecker  — compare values to clinical ranges (rule-based)
  5. AbnormalityDetector    — flag out-of-range values (rule-based)
  6. TrendComparator        — compare with previous reports (rule-based)
  7. MedicalReportRetriever — ChromaDB RAG (in rag.py)
  8. SummaryGenerator       — patient-friendly summary (LLM)
  9. ConfidenceCalculator   — compute confidence score (rule-based)
"""

import json
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.report_analysis.schemas import (
    ExtractedLabValue,
    AbnormalFinding,
    TrendResult,
)
from app.agents.report_analysis.prompts import (
    LAB_VALUE_EXTRACTION_PROMPT,
    MEDICAL_EXPLANATION_PROMPT,
    LIFESTYLE_RECOMMENDATIONS_PROMPT,
)
from app.agents.report_analysis.parser import extract_numeric_values_regex, truncate_for_llm
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("report_analysis.tools")

# ------------------------------------------------------------------ #
#  Reference Range Engine — WHO / NIH / ADA / AHA / Mayo Clinic      #
# ------------------------------------------------------------------ #
# Structure: test_name_lower → {unit, source, ranges: [(category, min, max)]}
# None = no bound on that side

_REFERENCE_RANGES: dict[str, dict] = {
    # CBC
    "hemoglobin": {
        "unit": "g/dL", "source": "WHO / NIH",
        "male_ranges": [
            ("critical",      None,   7.0),
            ("low",           7.0,   13.5),
            ("normal",       13.5,   17.5),
            ("high",         17.5,    None),
        ],
        "female_ranges": [
            ("critical",      None,   7.0),
            ("low",           7.0,   12.0),
            ("normal",       12.0,   15.5),
            ("high",         15.5,    None),
        ],
        "default_ranges": [
            ("critical",      None,   7.0),
            ("low",           7.0,   12.0),
            ("normal",       12.0,   17.5),
            ("high",         17.5,    None),
        ],
    },
    "wbc": {
        "unit": "10³/µL", "source": "NIH / MedlinePlus",
        "default_ranges": [
            ("critical",      None,   2.0),
            ("low",           2.0,    4.5),
            ("normal",        4.5,   11.0),
            ("high",         11.0,   30.0),
            ("critical",     30.0,    None),
        ],
    },
    "platelets": {
        "unit": "10³/µL", "source": "NIH / Mayo Clinic",
        "default_ranges": [
            ("critical",      None,   20.0),
            ("low",          20.0,  150.0),
            ("normal",      150.0,  400.0),
            ("high",        400.0,    None),
        ],
    },
    "rbc": {
        "unit": "10⁶/µL", "source": "NIH",
        "male_ranges": [
            ("low",   None,  4.5),
            ("normal", 4.5,  5.9),
            ("high",  5.9,   None),
        ],
        "female_ranges": [
            ("low",   None,  4.0),
            ("normal", 4.0,  5.2),
            ("high",  5.2,   None),
        ],
        "default_ranges": [
            ("low",   None,  4.0),
            ("normal", 4.0,  5.9),
            ("high",  5.9,   None),
        ],
    },
    "hematocrit": {
        "unit": "%", "source": "NIH",
        "male_ranges": [
            ("low",   None, 41.0),
            ("normal", 41.0, 53.0),
            ("high",  53.0,  None),
        ],
        "female_ranges": [
            ("low",   None, 36.0),
            ("normal", 36.0, 46.0),
            ("high",  46.0,  None),
        ],
        "default_ranges": [
            ("low",   None, 36.0),
            ("normal", 36.0, 53.0),
            ("high",  53.0,  None),
        ],
    },
    "mcv": {
        "unit": "fL", "source": "NIH",
        "default_ranges": [
            ("low",   None, 80.0),
            ("normal", 80.0, 100.0),
            ("high",  100.0, None),
        ],
    },
    # LFT
    "alt": {
        "unit": "U/L", "source": "NIH / MedlinePlus",
        "default_ranges": [
            ("normal",  0.0,  56.0),
            ("high",   56.0, 200.0),
            ("critical", 200.0, None),
        ],
    },
    "ast": {
        "unit": "U/L", "source": "NIH / MedlinePlus",
        "default_ranges": [
            ("normal",  0.0,  40.0),
            ("high",   40.0, 200.0),
            ("critical", 200.0, None),
        ],
    },
    "bilirubin": {
        "unit": "mg/dL", "source": "NIH / Mayo Clinic",
        "default_ranges": [
            ("normal",  0.0,  1.2),
            ("high",    1.2,  3.0),
            ("critical", 3.0, None),
        ],
    },
    "albumin": {
        "unit": "g/dL", "source": "NIH",
        "default_ranges": [
            ("low",   None,  3.5),
            ("normal", 3.5,  5.0),
            ("high",  5.0,   None),
        ],
    },
    "alp": {
        "unit": "U/L", "source": "NIH",
        "default_ranges": [
            ("normal",  44.0, 147.0),
            ("low",     None,  44.0),
            ("high",   147.0,  None),
        ],
    },
    # KFT
    "creatinine": {
        "unit": "mg/dL", "source": "NIH / MedlinePlus",
        "male_ranges": [
            ("low",   None,  0.7),
            ("normal", 0.7,  1.3),
            ("high",  1.3,   3.0),
            ("critical", 3.0, None),
        ],
        "female_ranges": [
            ("low",   None,  0.6),
            ("normal", 0.6,  1.1),
            ("high",  1.1,   3.0),
            ("critical", 3.0, None),
        ],
        "default_ranges": [
            ("low",   None,  0.6),
            ("normal", 0.6,  1.3),
            ("high",  1.3,   3.0),
            ("critical", 3.0, None),
        ],
    },
    "urea": {
        "unit": "mg/dL", "source": "NIH",
        "default_ranges": [
            ("low",   None,  7.0),
            ("normal", 7.0,  20.0),
            ("high",  20.0,  50.0),
            ("critical", 50.0, None),
        ],
    },
    "uric acid": {
        "unit": "mg/dL", "source": "NIH",
        "male_ranges": [
            ("low",   None,  3.4),
            ("normal", 3.4,  7.0),
            ("high",  7.0,   None),
        ],
        "female_ranges": [
            ("low",   None,  2.4),
            ("normal", 2.4,  6.0),
            ("high",  6.0,   None),
        ],
        "default_ranges": [
            ("low",   None,  2.4),
            ("normal", 2.4,  7.0),
            ("high",  7.0,   None),
        ],
    },
    # Lipid Profile
    "total cholesterol": {
        "unit": "mg/dL", "source": "AHA / NIH",
        "default_ranges": [
            ("normal",  None, 200.0),
            ("borderline_high", 200.0, 240.0),
            ("high",   240.0,  None),
        ],
    },
    "ldl": {
        "unit": "mg/dL", "source": "AHA / NIH",
        "default_ranges": [
            ("normal",  None, 100.0),
            ("borderline_high", 100.0, 160.0),
            ("high",   160.0, 190.0),
            ("critical", 190.0, None),
        ],
    },
    "hdl": {
        "unit": "mg/dL", "source": "AHA / NIH",
        "male_ranges": [
            ("low",   None,  40.0),
            ("normal", 40.0,  None),
        ],
        "female_ranges": [
            ("low",   None,  50.0),
            ("normal", 50.0,  None),
        ],
        "default_ranges": [
            ("low",   None,  40.0),
            ("normal", 40.0,  None),
        ],
    },
    "triglycerides": {
        "unit": "mg/dL", "source": "AHA / NIH",
        "default_ranges": [
            ("normal",  None, 150.0),
            ("borderline_high", 150.0, 200.0),
            ("high",   200.0, 500.0),
            ("critical", 500.0, None),
        ],
    },
    # Blood Sugar
    "glucose": {
        "unit": "mg/dL", "source": "ADA / NIH",
        "default_ranges": [
            ("critical",  None,  54.0),
            ("low",       54.0,  70.0),
            ("normal",    70.0, 100.0),
            ("borderline_high", 100.0, 126.0),
            ("high",     126.0, 200.0),
            ("critical", 200.0,  None),
        ],
    },
    "hba1c": {
        "unit": "%", "source": "ADA / NIH",
        "default_ranges": [
            ("normal",  None,  5.7),
            ("borderline_high", 5.7, 6.5),
            ("high",    6.5,   None),
        ],
    },
    # Thyroid
    "tsh": {
        "unit": "mIU/L", "source": "NIH / MedlinePlus",
        "default_ranges": [
            ("low",   None,  0.4),
            ("normal", 0.4,  4.0),
            ("high",  4.0,   10.0),
            ("critical", 10.0, None),
        ],
    },
    "free t4": {
        "unit": "ng/dL", "source": "NIH",
        "default_ranges": [
            ("low",   None,  0.8),
            ("normal", 0.8,  1.8),
            ("high",  1.8,   None),
        ],
    },
    "free t3": {
        "unit": "pg/mL", "source": "NIH",
        "default_ranges": [
            ("low",   None,  2.3),
            ("normal", 2.3,  4.2),
            ("high",  4.2,   None),
        ],
    },
    # Vitamins
    "vitamin d": {
        "unit": "ng/mL", "source": "NIH / MedlinePlus",
        "default_ranges": [
            ("critical",  None, 10.0),
            ("low",       10.0, 20.0),
            ("borderline_low", 20.0, 30.0),
            ("normal",    30.0, 100.0),
            ("critical", 100.0,  None),
        ],
    },
    "vitamin b12": {
        "unit": "pg/mL", "source": "NIH / MedlinePlus",
        "default_ranges": [
            ("critical",  None, 150.0),
            ("low",      150.0, 200.0),
            ("borderline_low", 200.0, 300.0),
            ("normal",   300.0, 900.0),
            ("high",     900.0,  None),
        ],
    },
}

# Aliases for common alternate names
_TEST_ALIASES: dict[str, str] = {
    "hb": "hemoglobin", "haemoglobin": "hemoglobin", "hgb": "hemoglobin",
    "white blood cells": "wbc", "white blood cell count": "wbc",
    "red blood cells": "rbc", "red blood cell count": "rbc",
    "plt": "platelets", "platelet count": "platelets",
    "hct": "hematocrit", "packed cell volume": "hematocrit", "pcv": "hematocrit",
    "sgpt": "alt", "alanine aminotransferase": "alt",
    "sgot": "ast", "aspartate aminotransferase": "ast",
    "total bilirubin": "bilirubin",
    "serum creatinine": "creatinine",
    "blood urea": "urea", "bun": "urea",
    "fasting glucose": "glucose", "fasting blood sugar": "glucose",
    "blood glucose": "glucose", "fbs": "glucose",
    "cholesterol": "total cholesterol",
    "ldl cholesterol": "ldl", "hdl cholesterol": "hdl",
    "tg": "triglycerides", "trigs": "triglycerides",
    "glycated hemoglobin": "hba1c", "a1c": "hba1c",
    "thyroid stimulating hormone": "tsh",
    "ft4": "free t4", "ft3": "free t3",
    "25-oh vitamin d": "vitamin d", "25-hydroxyvitamin d": "vitamin d",
    "cobalamin": "vitamin b12", "b12": "vitamin b12",
}


def _normalize_test_name(name: str) -> str:
    """Normalize test name to canonical form for range lookup."""
    lower = name.lower().strip()
    return _TEST_ALIASES.get(lower, lower)


def _get_ranges(config: dict, gender: Optional[str] = None) -> list:
    if gender and gender.lower() == "male" and "male_ranges" in config:
        return config["male_ranges"]
    if gender and gender.lower() == "female" and "female_ranges" in config:
        return config["female_ranges"]
    return config.get("default_ranges", [])


def _categorize_value(config: dict, value: float, gender: Optional[str] = None) -> tuple[str, str]:
    """Return (category, range_string) for a value."""
    ranges = _get_ranges(config, gender)
    unit = config.get("unit", "")
    for category, low, high in ranges:
        if low is None and high is not None and value < high:
            return category, f"<{high} {unit}"
        if high is None and low is not None and value >= low:
            return category, f"≥{low} {unit}"
        if low is not None and high is not None and low <= value < high:
            return category, f"{low}–{high} {unit}"
    return "unknown", "see reference"


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
#  Tool 3: LabValueExtractor                                          #
# ------------------------------------------------------------------ #

async def extract_lab_values(
    text: str,
    report_type: str,
) -> list[ExtractedLabValue]:
    """
    Extract structured lab values from report text using LLM.
    Falls back to regex extraction if LLM fails.
    """
    logger.info("Extracting lab values | report_type=%s | text_len=%d", report_type, len(text))
    truncated = truncate_for_llm(text, max_chars=4000)

    try:
        llm = _get_llm(temperature=0.0)
        prompt = LAB_VALUE_EXTRACTION_PROMPT.format(text=truncated)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = _safe_json_parse(response.content, [])

        values = []
        for item in raw:
            if not isinstance(item, dict) or "test_name" not in item:
                continue
            try:
                values.append(ExtractedLabValue(
                    test_name=item["test_name"],
                    value=float(item["value"]),
                    unit=item.get("unit", ""),
                    raw_text=item.get("raw_text"),
                    panel=item.get("panel", report_type),
                ))
            except (ValueError, KeyError):
                continue

        logger.info("LLM extracted %d lab values", len(values))
        return values

    except Exception as exc:
        logger.error("LLM lab extraction failed: %s — falling back to regex", exc)
        # Regex fallback
        regex_results = extract_numeric_values_regex(text)
        return [
            ExtractedLabValue(
                test_name=r["test_name"],
                value=r["value"],
                unit=r["unit"],
                raw_text=r["raw_text"],
                panel=report_type,
            )
            for r in regex_results[:20]  # cap at 20
        ]


# ------------------------------------------------------------------ #
#  Tool 4: ReferenceRangeChecker                                      #
# ------------------------------------------------------------------ #

def check_reference_ranges(
    lab_values: list[ExtractedLabValue],
    gender: Optional[str] = None,
) -> dict[str, tuple[str, str]]:
    """
    Compare lab values against clinical reference ranges.
    Returns dict: test_name → (category, range_string).
    Rule-based — no LLM, deterministic.
    """
    results = {}
    for val in lab_values:
        canonical = _normalize_test_name(val.test_name)
        config = _REFERENCE_RANGES.get(canonical)
        if not config:
            results[val.test_name] = ("unknown", "no reference available")
            continue
        category, range_str = _categorize_value(config, val.value, gender)
        results[val.test_name] = (category, range_str)
        logger.debug("Range check: %s=%.2f → %s (%s)", val.test_name, val.value, category, range_str)
    return results


# ------------------------------------------------------------------ #
#  Tool 5: AbnormalityDetector                                        #
# ------------------------------------------------------------------ #

def detect_abnormalities(
    lab_values: list[ExtractedLabValue],
    range_results: dict[str, tuple[str, str]],
) -> tuple[list[AbnormalFinding], list[ExtractedLabValue]]:
    """
    Split lab values into abnormal findings and normal findings.
    Returns (abnormal_findings, normal_values).
    Rule-based — no LLM.
    """
    abnormal: list[AbnormalFinding] = []
    normal: list[ExtractedLabValue] = []

    for val in lab_values:
        category, range_str = range_results.get(val.test_name, ("unknown", ""))

        if category in ("normal", "unknown"):
            normal.append(val)
            continue

        canonical = _normalize_test_name(val.test_name)
        config = _REFERENCE_RANGES.get(canonical, {})
        source = config.get("source", "")

        # Compute deviation from nearest normal boundary
        deviation = None
        ranges = config.get("default_ranges", [])
        for cat, low, high in ranges:
            if cat == "normal":
                if low is not None and val.value < low and low != 0:
                    deviation = round((low - val.value) / low * 100, 1)
                elif high is not None and val.value >= high and high != 0:
                    deviation = round((val.value - high) / high * 100, 1)
                break

        status_map = {
            "low": "low", "borderline_low": "borderline_low",
            "borderline_high": "borderline_high", "high": "high", "critical": "critical",
        }
        status = status_map.get(category, "high")

        abnormal.append(AbnormalFinding(
            test_name=val.test_name,
            value=val.value,
            unit=val.unit,
            status=status,
            normal_range=range_str,
            deviation_percent=deviation,
            source=source,
        ))
        logger.info("ABNORMAL: %s=%.2f %s (%s)", val.test_name, val.value, val.unit, status)

    return abnormal, normal


# ------------------------------------------------------------------ #
#  Tool 6: TrendComparator                                            #
# ------------------------------------------------------------------ #

def compare_trends(
    current_values: list[ExtractedLabValue],
    previous_reports: list[dict],
) -> list[TrendResult]:
    """
    Compare current lab values with previous report values.
    Rule-based — no LLM.
    """
    if not previous_reports:
        return []

    # Build lookup from most recent previous report
    prev_lookup: dict[str, float] = {}
    for report in previous_reports[:1]:  # use most recent
        for item in report.get("lab_values", []):
            name = _normalize_test_name(item.get("test_name", ""))
            if name and item.get("value") is not None:
                prev_lookup[name] = float(item["value"])

    trends = []
    for val in current_values:
        canonical = _normalize_test_name(val.test_name)
        prev_val = prev_lookup.get(canonical)
        if prev_val is None:
            continue

        change_pct = ((val.value - prev_val) / prev_val * 100) if prev_val != 0 else 0.0
        threshold = 5.0  # % change to be considered a trend

        # Determine if higher or lower is "better" for this test
        config = _REFERENCE_RANGES.get(canonical, {})
        ranges = config.get("default_ranges", [])
        normal_low = next((low for cat, low, high in ranges if cat == "normal" and low is not None), None)
        normal_high = next((high for cat, low, high in ranges if cat == "normal" and high is not None), None)

        if abs(change_pct) < threshold:
            direction = "stable"
        elif normal_low is not None and normal_high is not None:
            # Moving toward normal range = improving
            prev_in_normal = normal_low <= prev_val < normal_high
            curr_in_normal = normal_low <= val.value < normal_high
            if not prev_in_normal and curr_in_normal:
                direction = "improving"
            elif prev_in_normal and not curr_in_normal:
                direction = "worsening"
            else:
                # Both outside normal — check if moving toward range
                prev_dist = min(abs(prev_val - normal_low), abs(prev_val - normal_high))
                curr_dist = min(abs(val.value - normal_low), abs(val.value - normal_high))
                direction = "improving" if curr_dist < prev_dist else "worsening"
        else:
            direction = "stable"

        trends.append(TrendResult(
            test_name=val.test_name,
            direction=direction,
            previous_value=prev_val,
            current_value=val.value,
            change_percent=round(change_pct, 1),
            interpretation=_trend_interpretation(val.test_name, direction, change_pct),
        ))

    return trends


def _trend_interpretation(test_name: str, direction: str, change_pct: float) -> str:
    label = test_name.title()
    if direction == "stable":
        return f"{label} has remained stable compared to the previous report."
    elif direction == "improving":
        return f"{label} shows improvement ({abs(change_pct):.1f}% change toward normal range)."
    elif direction == "worsening":
        return f"{label} shows a worsening trend ({abs(change_pct):.1f}% change away from normal range)."
    return f"{label}: {direction}."


# ------------------------------------------------------------------ #
#  Tool 8: SummaryGenerator                                           #
# ------------------------------------------------------------------ #

async def generate_lifestyle_recommendations(
    report_type: str,
    abnormal_findings: list[AbnormalFinding],
    patient_context: str,
    rag_context: str,
) -> list[str]:
    """Generate lifestyle recommendations using LLM."""
    if not abnormal_findings:
        return ["Maintain your current healthy lifestyle.", "Schedule regular check-ups with your doctor."]

    try:
        llm = _get_llm(temperature=0.3)
        abnorm_text = "; ".join(
            f"{a.test_name} ({a.status}): {a.value} {a.unit}" for a in abnormal_findings
        )
        prompt = LIFESTYLE_RECOMMENDATIONS_PROMPT.format(
            report_type=report_type,
            abnormal_findings=abnorm_text,
            patient_context=patient_context,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = _safe_json_parse(response.content, [])
        if isinstance(raw, list):
            return [str(r) for r in raw[:5]]
        return [str(raw)]
    except Exception as exc:
        logger.error("Lifestyle recommendations failed: %s", exc)
        return ["Consult your healthcare provider for personalized lifestyle advice."]


# ------------------------------------------------------------------ #
#  Tool 9: ConfidenceCalculator                                       #
# ------------------------------------------------------------------ #

def calculate_report_confidence(
    lab_values_count: int,
    abnormal_count: int,
    rag_docs_count: int,
    ocr_confidence: float,
    text_length: int,
) -> float:
    """
    Compute confidence score [0.0, 1.0] for the report analysis.
    Rule-based — deterministic.
    """
    score = 0.0
    # OCR quality
    score += ocr_confidence * 0.30
    # Lab values extracted
    score += min(lab_values_count * 0.05, 0.30)
    # RAG support
    score += min(rag_docs_count * 0.05, 0.20)
    # Text length (longer = more complete report)
    if text_length > 500:
        score += 0.10
    elif text_length > 100:
        score += 0.05
    return round(min(score, 1.0), 2)


def estimate_risk_level(abnormal_findings: list[AbnormalFinding]) -> str:
    """Estimate overall risk level from abnormal findings."""
    if any(a.status == "critical" for a in abnormal_findings):
        return "critical"
    high_count = sum(1 for a in abnormal_findings if a.status == "high")
    if high_count >= 3:
        return "high"
    if high_count >= 1 or any(a.status == "borderline_high" for a in abnormal_findings):
        return "moderate"
    return "low"
