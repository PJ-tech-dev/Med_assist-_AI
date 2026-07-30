"""
FastAPI router for Automated WhatsApp Emergency Alerts.
"""

from typing import Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.services.whatsapp_service import send_automated_whatsapp_alert
from app.core.dependencies import get_current_user
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.whatsapp")

router = APIRouter(prefix="/emergency", tags=["emergency_whatsapp"])


class WhatsAppAlertRequest(BaseModel):
    phone: str = Field(..., json_schema_extra={"example": "+919876543210"})
    contact_name: Optional[str] = "Emergency Contact"
    emergency_type: str = Field(..., json_schema_extra={"example": "Heart Attack / High BPM (138 BPM)"})
    details: str = Field(..., json_schema_extra={"example": "Patient reported acute cardiac distress."})
    location: Optional[str] = "37.7749, -122.4194"


class WhatsAppAlertResponse(BaseModel):
    status: str
    provider: str
    recipient: str
    emergency_type: str
    message: str


@router.post("/whatsapp-alert", response_model=WhatsAppAlertResponse, status_code=status.HTTP_200_OK)
async def dispatch_whatsapp_alert(
    payload: WhatsAppAlertRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Automated WhatsApp Emergency Alert Endpoint.
    Automatically called by AI Agent / SmartWatch telemetry to send real-time WhatsApp emergency message.
    """
    logger.info("Emergency WhatsApp request | user=%s", current_user.id)
    
    result = await send_automated_whatsapp_alert(
        phone=payload.phone,
        contact_name=payload.contact_name or "Emergency Contact",
        emergency_type=payload.emergency_type,
        details=payload.details,
        location=payload.location or "37.7749, -122.4194"
    )

    return WhatsAppAlertResponse(
        status=result.get("status", "dispatched"),
        provider=result.get("provider", "automated"),
        recipient=payload.phone,
        emergency_type=payload.emergency_type,
        message=result.get("message", "Automated WhatsApp alert sent successfully.")
    )


class AmbulanceDispatchRequest(BaseModel):
    location: str = Field(..., json_schema_extra={"example": "37.7749, -122.4194"})
    patient_id: Optional[str] = None
    reason: str = Field(..., json_schema_extra={"example": "Automated SOS dispatch due to unresponsive high BPM"})

@router.post("/ambulance", status_code=status.HTTP_200_OK)
async def dispatch_ambulance(
    payload: AmbulanceDispatchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Automated Ambulance Dispatch Simulation Endpoint.
    """
    logger.warning("Ambulance simulation requested | user=%s", current_user.id)
    return {
        "status": "dispatched",
        "service": "Emergency Medical Services",
        "location": payload.location,
        "eta_minutes": 8,
        "message": "Ambulance has been successfully dispatched to your location."
    }
