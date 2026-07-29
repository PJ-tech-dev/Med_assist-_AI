import json
import os
import uuid
from typing import Optional, List, Dict, Any
from beanie import PydanticObjectId
from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pymongo import DESCENDING

from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.medical_report import MedicalReport, ReportAnalysisResult
from app.agents.report_analysis.ocr import default_ocr_processor
from app.agents.report_analysis.parser import detect_report_type, clean_report_text
from app.agents.report_analysis.agent import MedicalReportAnalysisAgent
from app.agents.base import initial_state
from app.utils.logger import get_logger

router = APIRouter(prefix="/reports", tags=["reports"])
logger = get_logger("api.reports")

_report_agent = MedicalReportAnalysisAgent()

_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "text/plain",
}
_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ------------------------------------------------------------------ #
#  POST /reports/upload                                               #
# ------------------------------------------------------------------ #

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_report(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a medical report file. Runs OCR and stores raw text."""
    mime = file.content_type or "application/octet-stream"
    if mime not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime}. Allowed: PDF, PNG, JPEG, TIFF, TXT.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 20 MB limit.",
        )

    # OCR extraction
    if mime == "text/plain":
        raw_text = file_bytes.decode("utf-8", errors="replace")
        ocr_confidence = 1.0
        engine = "plaintext"
    else:
        ocr_result = default_ocr_processor.extract(file_bytes, mime)
        raw_text = ocr_result.text
        ocr_confidence = ocr_result.confidence
        engine = ocr_result.engine

    clean_text = clean_report_text(raw_text)
    report_type = detect_report_type(clean_text) if clean_text else "UNKNOWN"

    logger.info(
        "Report uploaded | user=%s | file=%s | type=%s | ocr_engine=%s | chars=%d",
        current_user.id, file.filename, report_type, engine, len(clean_text),
    )

    # Save the file permanently to disk
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    file_path = os.path.join(uploads_dir, f"{uuid.uuid4()}{file_ext}")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    report = MedicalReport(
        patient_id=PydanticObjectId(patient_id),
        user_id=current_user.id,
        filename=file.filename or "unknown",
        file_size_bytes=len(file_bytes),
        mime_type=mime,
        file_path=file_path,
        report_type=report_type,
        raw_text=clean_text,
        ocr_confidence=ocr_confidence,
    )
    await report.insert()

    # Automatically trigger analysis after upload
    extracted_values = []
    summary_text = "No extractable text found in the report (OCR failed or empty file)."
    
    if report.raw_text:
        try:
            state = initial_state(
                session_id=f"report-{report.id}",
                user_id=str(current_user.id),
                user_message=f"Analyze this {report.report_type} medical report.",
            )
            state["metadata"] = {"report_text": report.raw_text, "ocr_confidence": report.ocr_confidence or 0.8}
            result_state = await _report_agent.safe_execute(state)
            
            if result_state.get("agent_outputs"):
                output = result_state["agent_outputs"][0]
                structured = output.get("metadata", {}).get("structured_result", {})
                
                # Format lab values for frontend
                lab_results = structured.get("lab_values", [])
                for lv in lab_results:
                    extracted_values.append({
                        "name": lv.get("test_name", "Unknown"),
                        "value": str(lv.get("value", "")),
                        "range": lv.get("normal_range", ""),
                        "status": lv.get("status", "normal")
                    })
                
                summary_text = output.get("response", "")
                
                analysis = ReportAnalysisResult(
                    report_id=report.id,
                    structured_results=structured,
                    summary=structured.get("summary", {}).get("clinical_summary", ""),
                    patient_friendly_summary=summary_text,
                    abnormalities_count=output.get("metadata", {}).get("abnormal_count", 0),
                    confidence=output.get("confidence", 0.0),
                    risk_level=output.get("metadata", {}).get("risk_level", "low"),
                )
                await analysis.insert()
        except Exception as e:
            logger.error(f"Automatic analysis failed during upload: {e}")
            summary_text = f"Analysis failed: {str(e)}"
    else:
        # Create a blank analysis if OCR failed
        analysis = ReportAnalysisResult(
            report_id=report.id,
            patient_friendly_summary=summary_text,
            summary=summary_text,
        )
        await analysis.insert()

    return {
        "id": str(report.id),
        "filename": report.filename,
        "report_type": report.report_type,
        "ocr_confidence": report.ocr_confidence,
        "ocr_engine": engine,
        "text_length": len(clean_text),
        "upload_time": report.upload_time.isoformat(),
        "extracted_values": extracted_values,
        "summary": summary_text,
        "status": "Analyzed" if report.raw_text else "OCR Failed",
        "message": "Report uploaded and analyzed successfully.",
    }


@router.post("/create_from_llm", status_code=status.HTTP_201_CREATED)
async def create_report_from_llm(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    filename: str = Form(...),
    raw_text: str = Form(...),
    summary: str = Form(...),
    report_type: str = Form("Medical Report"),
    extracted_values: str = Form("[]"),
    current_user: User = Depends(get_current_user),
):
    """Save a report that was parsed by Puter LLM on the frontend and store its file."""
    logger.info(
        "Report LLM upload | user=%s | file=%s | type=%s | chars=%d",
        current_user.id, filename, report_type, len(raw_text),
    )

    file_bytes = await file.read()
    mime = file.content_type or "application/pdf"

    # Save the file permanently to disk
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    file_path = os.path.join(uploads_dir, f"{uuid.uuid4()}{file_ext}")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    report = MedicalReport(
        patient_id=PydanticObjectId(patient_id),
        user_id=current_user.id,
        filename=filename or "unknown",
        file_size_bytes=len(file_bytes),
        mime_type=mime,
        file_path=file_path,
        report_type=report_type,
        raw_text=raw_text,
        ocr_confidence=1.0,
    )
    await report.insert()

    parsed_values = json.loads(extracted_values)
    structured = {"lab_values": []}
    for val in parsed_values:
        structured["lab_values"].append({
            "test_name": val.get("name", ""),
            "value": val.get("value", ""),
            "normal_range": val.get("range", ""),
            "status": val.get("status", "normal")
        })

    analysis = ReportAnalysisResult(
        report_id=report.id,
        structured_results=structured,
        summary=summary,
        patient_friendly_summary=summary,
        abnormalities_count=0,
        confidence=1.0,
        risk_level="low",
    )
    await analysis.insert()

    # Save to MedicalHistory
    from app.models.medical_history import MedicalHistory
    from datetime import date
    try:
        new_history = MedicalHistory(
            patient_id=PydanticObjectId(patient_id),
            diagnosis=f"Medical Report Analysis: {report_type}",
            visit_date=date.today(),
            notes=summary,
        )
        await new_history.insert()
        logger.info("Saved report analysis to MedicalHistory for user %s", patient_id)
    except Exception as e:
        logger.error("Failed to save report analysis to MedicalHistory: %s", e)

    return {
        "id": str(report.id),
        "filename": report.filename,
        "report_type": report.report_type,
        "upload_time": report.upload_time.isoformat(),
        "extracted_values": parsed_values,
        "summary": summary,
        "status": "Analyzed",
        "message": "Report saved successfully from LLM.",
    }


# ------------------------------------------------------------------ #
#  GET /reports                                                        #
# ------------------------------------------------------------------ #

@router.get("")
async def list_reports(
    patient_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """List all reports for the current user, optionally filtered by patient."""
    query_conds = [
        MedicalReport.user_id == current_user.id,
        MedicalReport.is_deleted == False,
    ]
    if patient_id:
        query_conds.append(MedicalReport.patient_id == PydanticObjectId(patient_id))
        
    reports = await MedicalReport.find(*query_conds).sort(
        [("upload_time", DESCENDING)]
    ).to_list()

    result_items = []
    for r in reports:
        # Fetch the latest analysis for this report
        analysis = await ReportAnalysisResult.find(
            ReportAnalysisResult.report_id == r.id
        ).sort([("created_at", DESCENDING)]).first_or_none()
        
        extracted_values = []
        if analysis and analysis.structured_results:
            lab_results = analysis.structured_results.get("lab_values", [])
            for lv in lab_results:
                extracted_values.append({
                    "name": lv.get("test_name", "Unknown"),
                    "value": str(lv.get("value", "")),
                    "range": lv.get("normal_range", ""),
                    "status": lv.get("status", "normal")
                })
                
        summary_text = analysis.patient_friendly_summary if analysis else "No analysis available."
        status_text = "Analyzed" if analysis and analysis.abnormalities_count is not None else "Pending"
        if not r.raw_text:
            status_text = "OCR Failed"

        result_items.append({
            "id": str(r.id),
            "filename": r.filename,
            "report_type": r.report_type,
            "patient_id": str(r.patient_id),
            "upload_time": r.upload_time.isoformat(),
            "ocr_confidence": r.ocr_confidence,
            "extracted_values": extracted_values,
            "summary": summary_text,
            "status": status_text,
        })

    return {
        "total": len(reports),
        "items": result_items,
    }


# ------------------------------------------------------------------ #
#  GET /reports/{id}                                                   #
# ------------------------------------------------------------------ #

@router.get("/{report_id}")
async def get_report(
    report_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    """Get a single report with its latest analysis result."""
    report = await _get_owned_report(report_id, current_user.id)

    # Fetch latest analysis
    analysis = await ReportAnalysisResult.find(
        ReportAnalysisResult.report_id == report_id
    ).sort([("created_at", DESCENDING)]).first_or_none()

    return {
        "id": str(report.id),
        "filename": report.filename,
        "report_type": report.report_type,
        "patient_id": str(report.patient_id),
        "upload_time": report.upload_time.isoformat(),
        "ocr_confidence": report.ocr_confidence,
        "raw_text_preview": (report.raw_text or "")[:500],
        "analysis": {
            "summary": analysis.summary if analysis else None,
            "patient_friendly_summary": analysis.patient_friendly_summary if analysis else None,
            "abnormalities_count": analysis.abnormalities_count if analysis else 0,
            "confidence": analysis.confidence if analysis else 0.0,
            "risk_level": analysis.risk_level if analysis else None,
            "structured_results": analysis.structured_results if analysis else None,
        } if analysis else None,
    }


# ------------------------------------------------------------------ #
#  DELETE /reports/{id}                                               #
# ------------------------------------------------------------------ #

@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a report."""
    report = await _get_owned_report(report_id, current_user.id)
    report.is_deleted = True
    await report.save()


# ------------------------------------------------------------------ #
#  POST /reports/{id}/analyze                                         #
# ------------------------------------------------------------------ #

@router.post("/{report_id}/analyze")
async def analyze_report(
    report_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    """Run the MedicalReportAnalysisAgent on an uploaded report."""
    report = await _get_owned_report(report_id, current_user.id)

    if not report.raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Report has no extracted text. Re-upload with a readable file.",
        )

    # Build agent state with report text injected into metadata
    state = initial_state(
        session_id=f"report-{report_id}",
        user_id=str(current_user.id),
        user_message=f"Analyze this {report.report_type} medical report.",
    )
    state["metadata"] = {"report_text": report.raw_text, "ocr_confidence": report.ocr_confidence or 0.8}

    logger.info("Analyzing report | report_id=%s | type=%s", report_id, report.report_type)
    result_state = await _report_agent.safe_execute(state)

    if not result_state["agent_outputs"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed. Please try again.",
        )

    output = result_state["agent_outputs"][0]
    structured = output.get("metadata", {}).get("structured_result", {})

    # Persist analysis result
    analysis = ReportAnalysisResult(
        report_id=report_id,
        structured_results=structured,
        summary=structured.get("summary", {}).get("clinical_summary", ""),
        patient_friendly_summary=output.get("response", ""),
        abnormalities_count=output.get("metadata", {}).get("abnormal_count", 0),
        confidence=output.get("confidence", 0.0),
        risk_level=output.get("metadata", {}).get("risk_level", "low"),
    )
    await analysis.insert()

    return {
        "report_id": str(report_id),
        "analysis_id": str(analysis.id),
        "report_type": structured.get("report_type", report.report_type),
        "risk_level": analysis.risk_level,
        "confidence": analysis.confidence,
        "abnormalities_count": analysis.abnormalities_count,
        "patient_friendly_summary": analysis.patient_friendly_summary,
        "structured_results": structured,
    }


# ------------------------------------------------------------------ #
#  Helper                                                             #
# ------------------------------------------------------------------ #

async def _get_owned_report(
    report_id: PydanticObjectId, user_id: PydanticObjectId
) -> MedicalReport:
    report = await MedicalReport.find_one(
        MedicalReport.id == report_id,
        MedicalReport.user_id == user_id,
        MedicalReport.is_deleted == False,
    )
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report

# ------------------------------------------------------------------ #
#  POST /reports/analyze-all                                          #
# ------------------------------------------------------------------ #

@router.post("/analyze-all")
async def analyze_all_reports(
    patient_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Analyze all reports for the user/patient and provide a holistic AI suggestion."""
    query_conds = [
        MedicalReport.user_id == current_user.id,
        MedicalReport.is_deleted == False,
    ]
    if patient_id:
        query_conds.append(MedicalReport.patient_id == PydanticObjectId(patient_id))
        
    reports = await MedicalReport.find(*query_conds).sort(
        [("upload_time", DESCENDING)]
    ).to_list()
    
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found to analyze.",
        )
        
    # Gather raw text or analysis summaries
    report_texts = []
    for r in reports:
        analysis = await ReportAnalysisResult.find_one(ReportAnalysisResult.report_id == r.id)
        if analysis and analysis.patient_friendly_summary:
            report_texts.append(f"Report [{r.filename}] Analysis: {analysis.patient_friendly_summary}")
        elif r.raw_text:
            report_texts.append(f"Report [{r.filename}] Raw Text: {r.raw_text[:1000]}")
        else:
            report_texts.append(f"Report [{r.filename}]: No text could be extracted (OCR failed or empty file).")
            
    if not report_texts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reports have no extractable data or analyses.",
        )
        
    combined_context = "\n\n".join(report_texts)
    
    try:
        from app.core.llm import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = get_llm(temperature=0.3)
        if not llm:
            raise Exception("LLM not configured.")
            
        system_prompt = (
            "You are an expert AI Medical Assistant specializing in Indian clinical standards (e.g., ICMR guidelines, Indian reference ranges). "
            "The user has provided data from multiple medical reports. "
            "Synthesize this information into a holistic, patient-friendly health summary and actionable AI suggestion. "
            "Contextualize the findings against standard Indian clinical practices and terminology where relevant. "
            "Group your insights into 'Overall Health Summary', 'Key Trends/Abnormalities', and 'Holistic Recommendations'. "
            "Format beautifully in Markdown. Never prescribe medication; always recommend consulting a doctor for serious issues."
        )
        
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Here is the aggregated report data:\n\n{combined_context}")
        ])
        
        return {
            "status": "success",
            "suggestion": response.content.strip()
        }
    except Exception as e:
        logger.error(f"Error in holistic analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate holistic AI suggestion."
        )