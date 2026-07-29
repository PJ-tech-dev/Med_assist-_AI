"""
LLM prompt templates for MedicalReportAnalysisAgent.
"""

REPORT_TYPE_DETECTION_PROMPT = """You are a medical report classifier.

Given the following extracted text from a medical report, identify the report type.

Choose ONE from: CBC, LFT, KFT, LIPID_PROFILE, BLOOD_SUGAR, HBA1C, THYROID, VITAMIN_D, VITAMIN_B12, MIXED, UNKNOWN

Text:
{text}

Return ONLY the report type string, nothing else.
"""

LAB_VALUE_EXTRACTION_PROMPT = """You are a medical data extraction assistant.

Extract all lab test values from the following medical report text.
Return a JSON array. Each item must have:
  - "test_name": standardized test name (e.g. "Hemoglobin", "WBC", "ALT")
  - "value": numeric value (float)
  - "unit": measurement unit (e.g. "g/dL", "10^3/uL", "U/L")
  - "raw_text": the original text fragment
  - "panel": the panel this test belongs to (e.g. "CBC", "LFT", "KFT")

Rules:
- Normalize test names to standard medical terminology.
- If a value has a range like "12.5 (Normal: 12-16)", extract value=12.5.
- Return [] if no lab values are found.
- Return ONLY valid JSON, no explanation.

Report text:
{text}
"""

MEDICAL_EXPLANATION_PROMPT = """You are a medical knowledge assistant.

Explain the following lab test result in clinical terms.

Test: {test_name}
Value: {value} {unit}
Status: {status}
Normal range: {normal_range}
Reference context:
{rag_context}

Provide a 1-2 sentence clinical explanation of what this result means.
Do not diagnose. Do not prescribe. Return plain text only.
"""

PATIENT_FRIENDLY_SUMMARY_PROMPT = """You are MedAssist AI, a patient-friendly medical assistant.

Generate a clear, empathetic summary of the following medical report analysis for the patient.

Report type: {report_type}
Abnormal findings: {abnormal_findings}
Normal findings count: {normal_count}
Risk level: {risk_level}
Key clinical notes:
{clinical_notes}

Guidelines:
- Use simple, non-technical language
- Be reassuring but honest about abnormal values
- Explain what each abnormal value means in plain terms
- List specific follow-up actions
- Never diagnose conditions
- Never prescribe medications
- End with a disclaimer that this is informational only

Patient summary:"""

LIFESTYLE_RECOMMENDATIONS_PROMPT = """You are a health and wellness advisor.

Based on the following medical report findings, provide practical lifestyle recommendations.

Report type: {report_type}
Abnormal findings: {abnormal_findings}
Patient context: {patient_context}

Provide 3-5 specific, actionable lifestyle recommendations.
Focus on diet, exercise, sleep, and stress management.
Do not prescribe medications. Do not diagnose.
Return as a JSON array of strings.
"""

CONFIDENCE_ESTIMATION_PROMPT = """You are a medical AI quality assessor.

Estimate the confidence level (0.0 to 1.0) of the following medical report analysis.

Factors to consider:
- Text clarity: {text_clarity}
- Values extracted: {values_count}
- Reference matches: {reference_matches}
- OCR quality: {ocr_quality}

Return ONLY a float between 0.0 and 1.0, nothing else.
"""
