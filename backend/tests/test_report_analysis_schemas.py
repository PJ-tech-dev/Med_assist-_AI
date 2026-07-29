"""
Schema tests for Module 7 — MedicalReportAnalysisAgent.
Covers all Pydantic v2 models, field defaults, validators, and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.agents.report_analysis.schemas import (
    ExtractedLabValue,
    ReferenceRange,
    AbnormalFinding,
    TrendResult,
    MedicalReportSummary,
    MedicalReportAnalysisResult,
)


# ------------------------------------------------------------------ #
#  ExtractedLabValue                                                   #
# ------------------------------------------------------------------ #

def test_extracted_lab_value_required_fields():
    v = ExtractedLabValue(test_name="Hemoglobin", value=13.5, unit="g/dL")
    assert v.test_name == "Hemoglobin"
    assert v.value == 13.5
    assert v.unit == "g/dL"
    assert v.raw_text is None
    assert v.panel is None


def test_extracted_lab_value_optional_fields():
    v = ExtractedLabValue(
        test_name="WBC", value=6.5, unit="10³/µL",
        raw_text="WBC: 6.5", panel="CBC",
    )
    assert v.raw_text == "WBC: 6.5"
    assert v.panel == "CBC"


def test_extracted_lab_value_missing_required_raises():
    with pytest.raises(ValidationError):
        ExtractedLabValue(value=13.5, unit="g/dL")  # test_name missing


# ------------------------------------------------------------------ #
#  ReferenceRange                                                      #
# ------------------------------------------------------------------ #

def test_reference_range_defaults():
    r = ReferenceRange(test_name="ALT", unit="U/L", source="NIH")
    assert r.normal_min is None
    assert r.normal_max is None
    assert r.age_adjusted is False
    assert r.gender_adjusted is False


def test_reference_range_full():
    r = ReferenceRange(
        test_name="Hemoglobin", normal_min=12.0, normal_max=17.5,
        unit="g/dL", source="WHO / NIH", gender_adjusted=True,
    )
    assert r.normal_min == 12.0
    assert r.normal_max == 17.5
    assert r.gender_adjusted is True


# ------------------------------------------------------------------ #
#  AbnormalFinding                                                     #
# ------------------------------------------------------------------ #

def test_abnormal_finding_valid_statuses():
    for status in ("low", "borderline_low", "normal", "borderline_high", "high", "critical"):
        f = AbnormalFinding(
            test_name="Glucose", value=55.0, unit="mg/dL",
            status=status, normal_range="70–100 mg/dL",
        )
        assert f.status == status


def test_abnormal_finding_invalid_status_raises():
    with pytest.raises(ValidationError):
        AbnormalFinding(
            test_name="Glucose", value=55.0, unit="mg/dL",
            status="very_high", normal_range="70–100 mg/dL",
        )


def test_abnormal_finding_optional_fields_default_none():
    f = AbnormalFinding(
        test_name="TSH", value=8.5, unit="mIU/L",
        status="high", normal_range="0.4–4.0 mIU/L",
    )
    assert f.deviation_percent is None
    assert f.clinical_significance is None
    assert f.source is None


# ------------------------------------------------------------------ #
#  TrendResult                                                         #
# ------------------------------------------------------------------ #

def test_trend_result_valid_directions():
    for direction in ("improving", "stable", "worsening", "insufficient_data"):
        t = TrendResult(test_name="Creatinine", direction=direction)
        assert t.direction == direction


def test_trend_result_invalid_direction_raises():
    with pytest.raises(ValidationError):
        TrendResult(test_name="Creatinine", direction="unknown_direction")


def test_trend_result_defaults():
    t = TrendResult(test_name="HbA1c", direction="stable")
    assert t.previous_value is None
    assert t.current_value is None
    assert t.change_percent is None
    assert t.interpretation == ""


# ------------------------------------------------------------------ #
#  MedicalReportAnalysisResult                                        #
# ------------------------------------------------------------------ #

def test_result_defaults():
    r = MedicalReportAnalysisResult()
    assert r.report_type == "unknown"
    assert r.lab_values == []
    assert r.abnormal_findings == []
    assert r.normal_findings == []
    assert r.trend_results == []
    assert r.risk_level == "low"
    assert r.confidence == 0.0
    assert r.sources == []
    assert r.requires_followup is False
    assert "informational purposes" in r.disclaimer


def test_result_confidence_bounds():
    with pytest.raises(ValidationError):
        MedicalReportAnalysisResult(confidence=1.5)
    with pytest.raises(ValidationError):
        MedicalReportAnalysisResult(confidence=-0.1)


def test_result_valid_risk_levels():
    for level in ("low", "moderate", "high", "critical"):
        r = MedicalReportAnalysisResult(risk_level=level)
        assert r.risk_level == level


def test_result_invalid_risk_level_raises():
    with pytest.raises(ValidationError):
        MedicalReportAnalysisResult(risk_level="extreme")


def test_result_summary_default_factory():
    r = MedicalReportAnalysisResult()
    assert r.summary.report_type == "unknown"
    assert r.summary.patient_friendly == ""
    assert r.summary.clinical_summary == ""
    assert r.summary.key_findings == []
    assert r.summary.lifestyle_recommendations == []
    assert r.summary.followup_recommendations == []


def test_result_full_population():
    lab = ExtractedLabValue(test_name="Hemoglobin", value=10.2, unit="g/dL", panel="CBC")
    finding = AbnormalFinding(
        test_name="Hemoglobin", value=10.2, unit="g/dL",
        status="low", normal_range="12.0–15.5 g/dL",
        deviation_percent=17.4, source="WHO / NIH",
    )
    trend = TrendResult(
        test_name="Hemoglobin", direction="worsening",
        previous_value=11.5, current_value=10.2, change_percent=-11.3,
    )
    summary = MedicalReportSummary(
        report_type="CBC",
        patient_friendly="Your hemoglobin is low.",
        clinical_summary="CBC: 1 value analyzed. 1 low value.",
        key_findings=["Hemoglobin: 10.2 g/dL (LOW)"],
        lifestyle_recommendations=["Eat iron-rich foods."],
        followup_recommendations=["Consult your doctor."],
    )
    r = MedicalReportAnalysisResult(
        report_type="CBC",
        lab_values=[lab],
        abnormal_findings=[finding],
        trend_results=[trend],
        summary=summary,
        risk_level="moderate",
        confidence=0.82,
        sources=["WHO / NIH"],
        requires_followup=True,
    )
    assert r.report_type == "CBC"
    assert len(r.lab_values) == 1
    assert len(r.abnormal_findings) == 1
    assert r.abnormal_findings[0].deviation_percent == 17.4
    assert r.trend_results[0].direction == "worsening"
    assert r.confidence == 0.82
    assert r.requires_followup is True
    assert r.summary.key_findings == ["Hemoglobin: 10.2 g/dL (LOW)"]
