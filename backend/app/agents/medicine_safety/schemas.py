"""
Pydantic v2 schemas for MedicineSafetyAgent structured output.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ExtractedMedication(BaseModel):
    raw: str                            # original text from user
    generic_name: str                   # normalized generic name
    brand_name: Optional[str] = None    # brand name if identified
    dosage_mentioned: Optional[str] = None   # e.g. "500mg"
    frequency_mentioned: Optional[str] = None  # e.g. "twice daily"
    route: Optional[str] = None         # oral, topical, IV, etc.


class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity: Literal["minor", "moderate", "major", "contraindicated"]
    description: str
    mechanism: Optional[str] = None
    source: Optional[str] = None


class AllergyAlert(BaseModel):
    medication: str
    allergen: str                       # matched allergen from patient profile
    reaction_type: Optional[str] = None # e.g. "anaphylaxis", "rash"
    severity: Literal["low", "moderate", "high", "critical"] = "high"


class Contraindication(BaseModel):
    medication: str
    condition: str                      # matched chronic disease / history
    reason: str
    severity: Literal["relative", "absolute"] = "relative"
    source: Optional[str] = None


class DuplicateWarning(BaseModel):
    medication: str
    existing_medication: str            # from patient's current medications
    note: str


class DosageValidation(BaseModel):
    medication: str
    mentioned_dosage: str
    typical_range: str                  # informational only
    is_within_range: Optional[bool] = None
    note: str


class MedicineSafetyResult(BaseModel):
    """
    Full structured output of MedicineSafetyAgent.
    Serialised into AgentOutput.metadata["structured_result"].
    """
    medications: list[ExtractedMedication] = Field(default_factory=list)
    interactions: list[DrugInteraction] = Field(default_factory=list)
    contraindications: list[Contraindication] = Field(default_factory=list)
    allergy_alerts: list[AllergyAlert] = Field(default_factory=list)
    duplicate_warnings: list[DuplicateWarning] = Field(default_factory=list)
    dosage_validation: list[DosageValidation] = Field(default_factory=list)
    severity: Literal["safe", "caution", "warning", "danger"] = "safe"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    recommendations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    requires_immediate_attention: bool = False
    disclaimer: str = (
        "This information is for educational purposes only. "
        "Always consult a qualified pharmacist or physician before making "
        "any changes to your medications."
    )
