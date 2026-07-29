"""
Parser and OCR tests for Module 7 — MedicalReportAnalysisAgent.
Covers detect_report_type, clean_report_text, extract_numeric_values_regex,
OCRResult, and DefaultOCRProcessor (with mocked heavy dependencies).
"""

import io
import pytest
from unittest.mock import MagicMock, patch

from app.agents.report_analysis.parser import (
    detect_report_type,
    clean_report_text,
    extract_numeric_values_regex,
    truncate_for_llm,
)
from app.agents.report_analysis.ocr import OCRResult, DefaultOCRProcessor


# ------------------------------------------------------------------ #
#  detect_report_type                                                  #
# ------------------------------------------------------------------ #

def test_detect_cbc():
    text = "Hemoglobin: 13.5 g/dL\nWBC: 6.5\nPlatelet: 250"
    assert detect_report_type(text) == "CBC"


def test_detect_lft():
    text = "ALT: 35 U/L\nAST: 28 U/L\nBilirubin: 0.8 mg/dL\nAlbumin: 4.2"
    assert detect_report_type(text) == "LFT"


def test_detect_thyroid():
    text = "TSH: 4.5 mIU/L\nFree T3: 3.2 pg/mL\nFree T4: 1.1 ng/dL"
    assert detect_report_type(text) == "THYROID"


def test_detect_unknown():
    assert detect_report_type("Patient name: John. Age: 45.") == "UNKNOWN"


def test_detect_mixed_panel():
    # CBC + LFT + KFT keywords — should return MIXED
    text = (
        "Hemoglobin: 13.5\nWBC: 6.5\nPlatelet: 250\n"          # CBC (3)
        "ALT: 35\nAST: 28\nBilirubin: 0.8\nAlbumin: 4.2\n"     # LFT (4)
        "Creatinine: 1.0\nUrea: 28\nBUN: 14\nEGFR: 90\n"       # KFT (4)
    )
    assert detect_report_type(text) == "MIXED"


# ------------------------------------------------------------------ #
#  clean_report_text                                                   #
# ------------------------------------------------------------------ #

def test_clean_normalizes_crlf():
    assert "\r" not in clean_report_text("line1\r\nline2\r\nline3")


def test_clean_collapses_blank_lines():
    result = clean_report_text("a\n\n\n\n\nb")
    assert "\n\n\n" not in result


def test_clean_removes_page_markers():
    result = clean_report_text("Report\nPage 1 of 3\nHemoglobin: 13.5")
    assert "Page 1 of 3" not in result


def test_clean_collapses_spaces():
    result = clean_report_text("Hemoglobin    13.5   g/dL")
    assert "  " not in result


def test_clean_strips_non_printable():
    result = clean_report_text("Hemoglobin\x00\x01: 13.5")
    assert "\x00" not in result
    assert "\x01" not in result


# ------------------------------------------------------------------ #
#  extract_numeric_values_regex                                        #
# ------------------------------------------------------------------ #

def test_extract_finds_lab_values():
    text = "Hemoglobin: 13.5 g/dL\nWBC: 6.5 10³/µL\n"
    results = extract_numeric_values_regex(text)
    names = [r["test_name"] for r in results]
    assert any("Hemoglobin" in n for n in names)


def test_extract_returns_float_values():
    text = "Creatinine: 1.2 mg/dL\n"
    results = extract_numeric_values_regex(text)
    assert results
    assert isinstance(results[0]["value"], float)


def test_extract_empty_text_returns_empty_list():
    assert extract_numeric_values_regex("") == []


def test_extract_filters_short_names():
    # Single-char names should be filtered out
    text = "A: 5.0\n"
    results = extract_numeric_values_regex(text)
    assert all(len(r["test_name"]) >= 2 for r in results)


# ------------------------------------------------------------------ #
#  truncate_for_llm                                                    #
# ------------------------------------------------------------------ #

def test_truncate_short_text_unchanged():
    text = "short text"
    assert truncate_for_llm(text, max_chars=100) == text


def test_truncate_long_text_appends_marker():
    text = "x" * 5000
    result = truncate_for_llm(text, max_chars=4000)
    assert result.endswith("[truncated]")
    assert len(result) < 5000


# ------------------------------------------------------------------ #
#  OCRResult                                                           #
# ------------------------------------------------------------------ #

def test_ocr_result_is_empty_short_text():
    assert OCRResult("short", 0.9).is_empty() is True


def test_ocr_result_not_empty_long_text():
    assert OCRResult("Hemoglobin: 13.5 g/dL — within normal range", 0.95).is_empty() is False


def test_ocr_result_text_stripped():
    r = OCRResult("  hello world  ", 0.8)
    assert r.text == "hello world"


# ------------------------------------------------------------------ #
#  DefaultOCRProcessor — PDF (mocked pypdf)                           #
# ------------------------------------------------------------------ #

def test_ocr_pdf_text_layer_extracted():
    """pypdf available and returns sufficient text → confidence 0.95, engine pypdf."""
    processor = DefaultOCRProcessor()

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Hemoglobin: 13.5 g/dL\n" * 5  # >50 chars

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("app.agents.report_analysis.ocr._PYPDF_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.pypdf", create=True) as mock_pypdf:
        mock_pypdf.PdfReader.return_value = mock_reader
        result = processor.extract(b"%PDF-fake", "application/pdf")

    assert result.engine == "pypdf"
    assert result.confidence == 0.95
    assert result.pages == 1
    assert not result.is_empty()


def test_ocr_pdf_no_pypdf_returns_empty():
    """pypdf unavailable → graceful empty result."""
    processor = DefaultOCRProcessor()
    with patch("app.agents.report_analysis.ocr._PYPDF_AVAILABLE", False):
        result = processor.extract(b"%PDF-fake", "application/pdf")
    assert result.engine == "none"
    assert result.confidence == 0.0
    assert result.is_empty()


# ------------------------------------------------------------------ #
#  DefaultOCRProcessor — image (mocked pytesseract)                   #
# ------------------------------------------------------------------ #

def test_ocr_image_tesseract_extracted():
    """Tesseract available → confidence 0.80, engine tesseract."""
    processor = DefaultOCRProcessor()

    mock_image = MagicMock()
    long_text = "WBC: 6.5 10³/µL — within normal range for adults"

    with patch("app.agents.report_analysis.ocr._TESSERACT_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.Image", create=True) as mock_pil, \
         patch("app.agents.report_analysis.ocr.pytesseract", create=True) as mock_tess:
        mock_pil.open.return_value = mock_image
        mock_tess.image_to_string.return_value = long_text
        result = processor.extract(b"\x89PNG", "image/png")

    assert result.engine == "tesseract"
    assert result.confidence == 0.80
    assert not result.is_empty()


def test_ocr_image_no_tesseract_returns_empty():
    """Tesseract unavailable → graceful empty result."""
    processor = DefaultOCRProcessor()
    with patch("app.agents.report_analysis.ocr._TESSERACT_AVAILABLE", False):
        result = processor.extract(b"\x89PNG", "image/png")
    assert result.engine == "none"
    assert result.is_empty()


# ------------------------------------------------------------------ #
#  detect_report_type — additional panels                              #
# ------------------------------------------------------------------ #

def test_detect_kft():
    """KFT keywords (creatinine, urea, bun, egfr) → KFT."""
    text = (
        "Creatinine: 1.0 mg/dL\n"
        "Urea: 28 mg/dL\n"
        "BUN: 14 mg/dL\n"
        "EGFR: 90 mL/min/1.73m2\n"
    )
    assert detect_report_type(text) == "KFT"


def test_detect_lipid_profile():
    """Lipid panel keywords (cholesterol, ldl, hdl, triglyceride) → LIPID_PROFILE."""
    text = (
        "Total Cholesterol: 190 mg/dL\n"
        "LDL: 100 mg/dL\n"
        "HDL: 55 mg/dL\n"
        "Triglycerides: 150 mg/dL\n"
    )
    assert detect_report_type(text) == "LIPID_PROFILE"


def test_detect_blood_sugar():
    """Blood sugar keywords (glucose, fasting blood sugar, fbs) → BLOOD_SUGAR."""
    text = "Fasting Blood Sugar: 95 mg/dL\nRandom Blood Sugar: 120 mg/dL"
    assert detect_report_type(text) == "BLOOD_SUGAR"


def test_detect_hba1c():
    """HbA1c keywords (hba1c, glycated hemoglobin, a1c) → HBA1C."""
    text = "HbA1c: 5.4%\nGlycated Hemoglobin: 5.4%\nA1c: 5.4%"
    assert detect_report_type(text) == "HBA1C"


def test_detect_vitamin_d():
    """Vitamin D keywords (vitamin d, 25-oh, calcidiol) → VITAMIN_D."""
    text = "25-OH Vitamin D: 32 ng/mL\nCalcidiol: 32 ng/mL"
    assert detect_report_type(text) == "VITAMIN_D"


def test_detect_vitamin_b12():
    """Vitamin B12 keywords (vitamin b12, cobalamin, b12) → VITAMIN_B12."""
    text = "Vitamin B12: 450 pg/mL\nCobalamin: 450 pg/mL"
    assert detect_report_type(text) == "VITAMIN_B12"


# ------------------------------------------------------------------ #
#  detect_report_type — malformed / edge cases                         #
# ------------------------------------------------------------------ #

def test_detect_garbage_text_returns_unknown():
    """Completely non-medical garbage text → UNKNOWN."""
    text = "!@#$%^&*()_+{}[]|\\:;\"'<>,.?/~`"
    assert detect_report_type(text) == "UNKNOWN"


# ------------------------------------------------------------------ #
#  clean_report_text — edge cases                                      #
# ------------------------------------------------------------------ #

def test_clean_empty_string():
    """Empty string input returns empty string."""
    assert clean_report_text("") == ""


# ------------------------------------------------------------------ #
#  extract_numeric_values_regex — bracketed reference ranges           #
# ------------------------------------------------------------------ #

def test_extract_values_with_reference_brackets():
    """Values with bracketed reference ranges [Ref: min–max] are still extracted."""
    text = "Glucose: 95 mg/dL [Ref: 70-100]\nVitamin B12: 450 pg/mL [Ref: 200-900]"
    results = extract_numeric_values_regex(text)
    names = [r["test_name"] for r in results]
    assert any("Glucose" in n for n in names)
    assert any("Vitamin B12" in n for n in names)


# ------------------------------------------------------------------ #
#  BaseOCRProcessor — abstract instantiation                           #
# ------------------------------------------------------------------ #

def test_base_ocr_processor_cannot_instantiate():
    """BaseOCRProcessor is abstract and cannot be instantiated directly."""
    from app.agents.report_analysis.ocr import BaseOCRProcessor
    with pytest.raises(TypeError):
        BaseOCRProcessor()


# ------------------------------------------------------------------ #
#  DefaultOCRProcessor — scanned PDF fallback (pdf2image)              #
# ------------------------------------------------------------------ #

def test_ocr_pdf_text_layer_empty_fallback_to_image():
    """
    When pypdf returns insufficient text (< 50 chars),
    DefaultOCRProcessor falls back to pdf2image + tesseract.
    """
    processor = DefaultOCRProcessor()

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "short"  # < 50 chars → triggers fallback

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    mock_pdf_image = MagicMock()
    fallback_text = "WBC: 6.5 10³/µL — extracted from scanned PDF"

    # Use create=True for conditionally-imported modules
    with patch("app.agents.report_analysis.ocr._PYPDF_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr._TESSERACT_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.pypdf", create=True) as mock_pypdf, \
         patch("app.agents.report_analysis.ocr.pytesseract", create=True) as mock_tess, \
         patch("app.agents.report_analysis.ocr.Image", create=True) as mock_pil, \
         patch("app.agents.report_analysis.ocr.pdf2image", create=True) as mock_pdf2image:
        mock_pypdf.PdfReader.return_value = mock_reader
        mock_pdf2image.convert_from_bytes.return_value = [mock_pdf_image]
        mock_tess.image_to_string.return_value = fallback_text
        mock_pil.open.return_value = mock_pdf_image

        result = processor.extract(b"%PDF-scanned", "application/pdf")

    assert result.engine == "tesseract_pdf"
    assert result.confidence == 0.75
    assert not result.is_empty()


# ------------------------------------------------------------------ #
#  DefaultOCRProcessor — JPEG & TIFF image formats                     #
# ------------------------------------------------------------------ #

def test_ocr_image_jpeg_extracted():
    """JPEG image MIME type → tesseract engine, confidence 0.80."""
    processor = DefaultOCRProcessor()

    mock_image = MagicMock()
    long_text = "WBC: 6.5 10³/µL — JPEG extracted"

    with patch("app.agents.report_analysis.ocr._TESSERACT_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.Image", create=True) as mock_pil, \
         patch("app.agents.report_analysis.ocr.pytesseract", create=True) as mock_tess:
        mock_pil.open.return_value = mock_image
        mock_tess.image_to_string.return_value = long_text
        result = processor.extract(b"\xFF\xD8\xFF\xE0", "image/jpeg")

    assert result.engine == "tesseract"
    assert result.confidence == 0.80
    assert not result.is_empty()


def test_ocr_image_tiff_extracted():
    """TIFF image MIME type → tesseract engine, confidence 0.80."""
    processor = DefaultOCRProcessor()

    mock_image = MagicMock()
    long_text = "WBC: 6.5 10³/µL — TIFF extracted"

    with patch("app.agents.report_analysis.ocr._TESSERACT_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.Image", create=True) as mock_pil, \
         patch("app.agents.report_analysis.ocr.pytesseract", create=True) as mock_tess:
        mock_pil.open.return_value = mock_image
        mock_tess.image_to_string.return_value = long_text
        result = processor.extract(b"II*\x00", "image/tiff")

    assert result.engine == "tesseract"
    assert result.confidence == 0.80
    assert not result.is_empty()


# ------------------------------------------------------------------ #
#  DefaultOCRProcessor — empty / corrupted input                       #
# ------------------------------------------------------------------ #

def test_ocr_empty_bytes_returns_empty():
    """Empty bytes input produces an empty OCR result gracefully."""
    processor = DefaultOCRProcessor()
    result = processor.extract(b"", "application/pdf")
    assert result.is_empty()
    assert result.confidence == 0.0


def test_ocr_corrupted_pdf_returns_error_engine():
    """Corrupted PDF that raises an exception returns engine='error'."""
    processor = DefaultOCRProcessor()

    with patch("app.agents.report_analysis.ocr._PYPDF_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.pypdf", create=True) as mock_pypdf:
        mock_pypdf.PdfReader.side_effect = Exception("Corrupted PDF")
        result = processor.extract(b"%%EOF-corrupted", "application/pdf")

    assert result.engine == "error"
    assert result.is_empty()
    assert result.confidence == 0.0


# ------------------------------------------------------------------ #
#  NEW TESTS — batch 2: detect_report_type edge cases                 #
# ------------------------------------------------------------------ #

def test_detect_single_keyword_match():
    """A single keyword match is sufficient to identify the panel."""
    text = "Just a random text mentioning hemoglobin somewhere in here"
    assert detect_report_type(text) == "CBC"


def test_detect_two_panels_not_mixed():
    """Exactly 2 panels with score >= 2 each — should pick the higher scored one, not MIXED."""
    # CBC: hemoglobin(1), wbc(1), platelet(1) → 3
    # LFT:  alt(1), ast(1) → 2
    text = (
        "Hemoglobin: 13.5\nWBC: 6.5\nPlatelet: 250\n"
        "ALT: 35\nAST: 28\n"
    )
    assert detect_report_type(text) == "CBC"


def test_detect_numeric_only_text():
    """Purely numeric or symbolic text with no keywords → UNKNOWN."""
    text = "12345 67890 111213 141516"
    assert detect_report_type(text) == "UNKNOWN"


# ------------------------------------------------------------------ #
#  NEW TESTS — batch 2: clean_report_text edge cases                  #
# ------------------------------------------------------------------ #

def test_clean_only_whitespace():
    """Whitespace-only input → empty string after strip."""
    assert clean_report_text("   \t\n  \n  ") == ""


def test_clean_strips_non_ascii():
    """Non-ASCII printable characters (µ, ³) are replaced with space (step 5 runs after step 4, so double spaces can appear)."""
    result = clean_report_text("Hemoglobin\u00b3: 13.5 \u00b5g/dL")
    # The superscript 3 and micro sign are non-ASCII → replaced with space
    # Note: space collapsing (step 4) runs BEFORE non-printable removal (step 5),
    # so the newly introduced spaces from ³/µ are NOT collapsed.
    assert "\u00b3" not in result
    assert "\u00b5" not in result
    assert "Hemoglobin" in result
    assert "13.5" in result


# ------------------------------------------------------------------ #
#  NEW TESTS — batch 2: extract_numeric_values_regex edge cases       #
# ------------------------------------------------------------------ #

def test_extract_values_without_units():
    """Values without explicit units are still extracted."""
    text = "Hemoglobin: 13.5\nWBC: 6.5\nPlatelet: 250\n"
    results = extract_numeric_values_regex(text)
    assert len(results) >= 1
    assert any(abs(r["value"] - 13.5) < 0.001 for r in results)


def test_extract_small_decimal_values():
    """Very small decimal values (e.g. TSH=0.05) are preserved as floats."""
    text = "TSH: 0.05 mIU/L\nFree T3: 3.2 pg/mL\n"
    results = extract_numeric_values_regex(text)
    # find the TSH result
    tsh = [r for r in results if "TSH" in r["test_name"]]
    assert len(tsh) == 1
    assert abs(tsh[0]["value"] - 0.05) < 0.001


def test_extract_no_matches():
    """Text with no lab-value-like patterns → empty list."""
    text = "Patient Name: John Doe\nDate: 2024-01-15\nDoctor: Smith"
    assert extract_numeric_values_regex(text) == []


# ------------------------------------------------------------------ #
#  NEW TESTS — batch 2: truncate_for_llm edge cases                   #
# ------------------------------------------------------------------ #

def test_truncate_empty_string():
    """Empty string → unchanged empty string."""
    assert truncate_for_llm("") == ""


def test_truncate_exact_limit():
    """String of exactly max_chars length → unchanged (no truncation marker)."""
    text = "x" * 4000
    result = truncate_for_llm(text, max_chars=4000)
    assert result == text
    assert "[truncated]" not in result


# ------------------------------------------------------------------ #
#  NEW TESTS — batch 2: OCRResult edge cases                          #
# ------------------------------------------------------------------ #

def test_ocr_result_stores_fields():
    """OCRResult constructor stores all fields correctly."""
    r = OCRResult("   Test text with values   ", 0.85, pages=3, engine="tesseract")
    assert r.text == "Test text with values"  # stripped
    assert r.confidence == 0.85
    assert r.pages == 3
    assert r.engine == "tesseract"


def test_ocr_result_edge_lengths():
    """9 chars → is_empty, 10 chars → not is_empty."""
    r1 = OCRResult("123456789", 0.5)          # 9 chars
    r2 = OCRResult("1234567890", 0.5)         # 10 chars
    assert r1.is_empty() is True
    assert r2.is_empty() is False


# ------------------------------------------------------------------ #
#  NEW TESTS — batch 2: BaseOCRProcessor clean_text                   #
# ------------------------------------------------------------------ #

def test_base_ocr_clean_text():
    """BaseOCRProcessor.clean_text collapses multiple newlines/spaces and strips."""
    from app.agents.report_analysis.ocr import BaseOCRProcessor

    class DummyProcessor(BaseOCRProcessor):
        def extract(self, file_bytes: bytes, mime_type: str) -> OCRResult:
            return OCRResult("", 0.0)

    processor = DummyProcessor()
    raw = "  Hemoglobin:   13.5   g/dL\n\n\n\nWBC:   6.5  \n  "
    cleaned = processor.clean_text(raw)
    assert "\n\n\n" not in cleaned
    assert "  " not in cleaned
    assert cleaned == cleaned.strip()
    assert "Hemoglobin" in cleaned
    assert "WBC" in cleaned


# ------------------------------------------------------------------ #
#  NEW TESTS — batch 2: DefaultOCRProcessor failure / fallback paths  #
# ------------------------------------------------------------------ #

def test_ocr_image_tesseract_failure():
    """When Tesseract exists but raises internally — _ocr_pil_image catches and returns ''.
    The result has engine='tesseract' with confidence 0.80, but text is empty."""
    processor = DefaultOCRProcessor()

    mock_image = MagicMock()

    with patch("app.agents.report_analysis.ocr._TESSERACT_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.Image", create=True) as mock_pil, \
         patch("app.agents.report_analysis.ocr.pytesseract", create=True) as mock_tess:
        mock_pil.open.return_value = mock_image
        mock_tess.image_to_string.side_effect = Exception("Tesseract crashed")
        result = processor.extract(b"\x89PNG", "image/png")

    # _ocr_pil_image catches the exception internally and returns ""
    # so _extract_image produces a tesseract result with empty text
    assert result.engine == "tesseract"
    assert result.is_empty()
    assert result.confidence == 0.80


def test_ocr_unsupported_mime_fallback():
    """Unsupported MIME type falls back to PDF extraction (pypdf)."""
    processor = DefaultOCRProcessor()

    # Text must be > 50 chars to pass the _extract_pdf length check
    long_text = "Hemoglobin: 13.5 g/dL\nWBC: 6.5 10³/µL\nPlatelet: 250\nCreatinine: 1.0 mg/dL\n"
    mock_page = MagicMock()
    mock_page.extract_text.return_value = long_text
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("app.agents.report_analysis.ocr._PYPDF_AVAILABLE", True), \
         patch("app.agents.report_analysis.ocr.pypdf", create=True) as mock_pypdf:
        mock_pypdf.PdfReader.return_value = mock_reader
        # Pass an unknown MIME type, e.g. application/octet-stream
        result = processor.extract(b"%PDF-fallback", "application/octet-stream")

    assert result.engine == "pypdf"
    assert not result.is_empty()
    assert result.confidence == 0.95
