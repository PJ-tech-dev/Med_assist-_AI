"""
ReportParser — rule-based report type detection and text pre-processing.

Detects report type from keywords before calling the LLM,
reducing token usage and improving extraction accuracy.
"""

import re
from typing import Optional

# Keyword sets for each report type
_REPORT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "CBC": [
        "hemoglobin", "haemoglobin", "hgb", "hb", "wbc", "white blood cell",
        "rbc", "red blood cell", "platelet", "plt", "hematocrit", "hct",
        "mcv", "mch", "mchc", "complete blood count", "cbc", "differential",
        "neutrophil", "lymphocyte", "monocyte", "eosinophil", "basophil",
    ],
    "LFT": [
        "alt", "alanine aminotransferase", "ast", "aspartate aminotransferase",
        "bilirubin", "albumin", "total protein", "alp", "alkaline phosphatase",
        "ggt", "gamma-glutamyl", "liver function", "lft", "sgpt", "sgot",
        "prothrombin", "inr",
    ],
    "KFT": [
        "creatinine", "urea", "bun", "blood urea nitrogen", "egfr",
        "uric acid", "kidney function", "kft", "renal function", "rft",
        "electrolyte", "sodium", "potassium", "chloride", "bicarbonate",
    ],
    "LIPID_PROFILE": [
        "cholesterol", "ldl", "hdl", "triglyceride", "vldl",
        "lipid profile", "lipoprotein", "non-hdl",
    ],
    "BLOOD_SUGAR": [
        "glucose", "fasting blood sugar", "fbs", "random blood sugar", "rbs",
        "postprandial", "ppbs", "blood sugar",
    ],
    "HBA1C": [
        "hba1c", "hba1 c", "glycated hemoglobin", "glycosylated hemoglobin",
        "a1c", "hemoglobin a1c",
    ],
    "THYROID": [
        "tsh", "thyroid stimulating hormone", "t3", "t4", "free t3", "free t4",
        "ft3", "ft4", "thyroid function", "tft", "thyroxine", "triiodothyronine",
    ],
    "VITAMIN_D": [
        "vitamin d", "25-oh", "25-hydroxyvitamin", "calcidiol", "cholecalciferol",
    ],
    "VITAMIN_B12": [
        "vitamin b12", "cobalamin", "cyanocobalamin", "b12",
    ],
}

# Regex patterns for common lab value formats
_LAB_VALUE_PATTERN = re.compile(
    r"([A-Za-z][A-Za-z0-9 \-/()]+?)\s*[:\-]?\s*"
    r"(\d+\.?\d*)\s*"
    r"([a-zA-Z/%µ^³×·\s]+?)?"
    r"(?:\s*[\(\[].*?[\)\]]?)?"
    r"(?:\n|$)",
    re.IGNORECASE,
)


def detect_report_type(text: str) -> str:
    """
    Detect report type from extracted text using keyword matching.
    Returns the most likely report type or 'MIXED' / 'UNKNOWN'.
    Rule-based — no LLM, independently testable.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for report_type, keywords in _REPORT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[report_type] = score

    if not scores:
        return "UNKNOWN"

    # If multiple types score highly, it's a mixed panel
    top_types = [t for t, s in scores.items() if s >= 2]
    if len(top_types) > 2:
        return "MIXED"

    return max(scores, key=scores.get)


def clean_report_text(text: str) -> str:
    """
    Clean OCR-extracted text for better LLM processing.
    Removes noise while preserving lab values and structure.
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove page headers/footers (common OCR artifacts)
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text, flags=re.IGNORECASE)
    # Normalize spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Remove non-printable characters
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    return text.strip()


_METADATA_KEYS = {
    "date", "patient name", "patient", "doctor", "dr", "dr.", "sample id",
    "specimen", "dob", "age", "gender", "sex", "phone", "mrn", "acc", "acc #",
    "ref", "report date", "test date", "collected", "received", "reported",
}


def extract_numeric_values_regex(text: str) -> list[dict]:
    """
    Fast regex-based extraction of numeric lab values.
    Used as a pre-filter before LLM extraction.
    Returns list of dicts with test_name, value, unit, raw_text.
    """
    results = []
    for match in _LAB_VALUE_PATTERN.finditer(text):
        test_name = match.group(1).strip().rstrip(":-")
        value_str = match.group(2)
        unit = (match.group(3) or "").strip()

        # Filter out noise (very short names, non-medical patterns)
        if len(test_name) < 2 or len(test_name) > 60:
            continue
        if not value_str:
            continue

        clean_name = test_name.lower().strip()
        # Skip common non-medical report header/metadata lines (Date, Patient Name, Doctor, etc.)
        if clean_name in _METADATA_KEYS or any(clean_name.endswith(k) for k in ("date", "patient name", "doctor", "sample id", "dob")):
            continue
        if re.search(r"\d{4}-\d{2}-\d{2}", match.group(0)):
            continue

        try:
            value = float(value_str)
        except ValueError:
            continue

        results.append({
            "test_name": test_name,
            "value": value,
            "unit": unit,
            "raw_text": match.group(0).strip(),
        })

    return results


def truncate_for_llm(text: str, max_chars: int = 4000) -> str:
    """Truncate report text to fit within LLM context window."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"
