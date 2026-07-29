"""
Independent tools for MedicineSafetyAgent.
Each tool is a pure function — independently testable, no side effects.

Tools:
  1. DrugNameExtractor          — extract medications from free text (LLM)
  2. DrugNormalizer             — brand → generic name mapping (rule-based)
  3. InteractionChecker         — drug-drug interaction detection (RAG + LLM)
  4. AllergyChecker             — cross-check against patient allergies (rule-based)
  5. ContraindicationChecker    — check against chronic diseases (RAG + LLM)
  6. DuplicateMedicationChecker — detect duplicates vs current medications (rule-based)
  7. DosageValidator            — informational dosage range check (RAG + LLM)
  8. DrugKnowledgeRetriever     — ChromaDB retrieval (in rag.py)
"""

import json
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.medicine_safety.schemas import (
    ExtractedMedication,
    DrugInteraction,
    AllergyAlert,
    Contraindication,
    DuplicateWarning,
    DosageValidation,
)
from app.agents.medicine_safety.prompts import (
    DRUG_EXTRACTION_PROMPT,
    INTERACTION_CHECK_PROMPT,
    CONTRAINDICATION_CHECK_PROMPT,
    DOSAGE_VALIDATION_PROMPT,
)
from app.agents.medicine_safety.rag import drug_retriever
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("medicine_safety.tools")

# ------------------------------------------------------------------ #
#  Brand → Generic name mapping (rule-based, 40+ common drugs)       #
# ------------------------------------------------------------------ #
_BRAND_TO_GENERIC: dict[str, str] = {
    # Analgesics / Antipyretics
    "tylenol": "acetaminophen", "panadol": "acetaminophen",
    "calpol": "acetaminophen", "paracetamol": "acetaminophen",
    "advil": "ibuprofen", "nurofen": "ibuprofen", "motrin": "ibuprofen",
    "aleve": "naproxen", "naprosyn": "naproxen",
    "bayer": "aspirin", "ecotrin": "aspirin",
    # Antibiotics
    "augmentin": "amoxicillin-clavulanate", "amoxil": "amoxicillin",
    "zithromax": "azithromycin", "z-pak": "azithromycin",
    "cipro": "ciprofloxacin", "flagyl": "metronidazole",
    "keflex": "cephalexin", "bactrim": "trimethoprim-sulfamethoxazole",
    # Cardiovascular
    "lipitor": "atorvastatin", "crestor": "rosuvastatin",
    "zocor": "simvastatin", "pravachol": "pravastatin",
    "coumadin": "warfarin", "xarelto": "rivaroxaban",
    "eliquis": "apixaban", "plavix": "clopidogrel",
    "lopressor": "metoprolol", "tenormin": "atenolol",
    "norvasc": "amlodipine", "zestril": "lisinopril",
    "vasotec": "enalapril", "altace": "ramipril",
    # Diabetes
    "glucophage": "metformin", "januvia": "sitagliptin",
    "jardiance": "empagliflozin", "ozempic": "semaglutide",
    "lantus": "insulin glargine", "humalog": "insulin lispro",
    # GI
    "prilosec": "omeprazole", "nexium": "esomeprazole",
    "prevacid": "lansoprazole", "zantac": "ranitidine",
    "pepcid": "famotidine",
    # Respiratory
    "ventolin": "albuterol", "proventil": "albuterol",
    "singulair": "montelukast", "flonase": "fluticasone",
    # Mental health
    "prozac": "fluoxetine", "zoloft": "sertraline",
    "lexapro": "escitalopram", "xanax": "alprazolam",
    "valium": "diazepam", "ambien": "zolpidem",
}

# Drug class groupings for duplicate detection
_DRUG_CLASSES: dict[str, list[str]] = {
    "nsaid": ["ibuprofen", "naproxen", "aspirin", "diclofenac", "celecoxib", "indomethacin"],
    "statin": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin"],
    "ace_inhibitor": ["lisinopril", "enalapril", "ramipril", "captopril", "perindopril"],
    "beta_blocker": ["metoprolol", "atenolol", "propranolol", "bisoprolol", "carvedilol"],
    "anticoagulant": ["warfarin", "rivaroxaban", "apixaban", "dabigatran", "heparin"],
    "ppi": ["omeprazole", "esomeprazole", "lansoprazole", "pantoprazole", "rabeprazole"],
    "ssri": ["fluoxetine", "sertraline", "escitalopram", "paroxetine", "citalopram"],
    "biguanide": ["metformin"],
}

# Allergy cross-reactivity map
_ALLERGY_CROSS_REACTIVITY: dict[str, list[str]] = {
    "penicillin": ["amoxicillin", "amoxicillin-clavulanate", "ampicillin", "piperacillin",
                   "nafcillin", "oxacillin", "dicloxacillin"],
    "sulfa": ["trimethoprim-sulfamethoxazole", "sulfamethoxazole", "sulfadiazine"],
    "aspirin": ["ibuprofen", "naproxen", "diclofenac", "celecoxib"],  # NSAID cross-reactivity
    "cephalosporin": ["cephalexin", "cefazolin", "ceftriaxone", "cefdinir"],
    "codeine": ["morphine", "oxycodone", "hydrocodone", "tramadol"],  # opioid class
}

# Condition → contraindicated drug classes
_CONDITION_CONTRAINDICATIONS: dict[str, list[str]] = {
    "peptic ulcer": ["ibuprofen", "naproxen", "aspirin", "diclofenac"],
    "renal impairment": ["metformin", "ibuprofen", "naproxen"],
    "liver disease": ["acetaminophen", "methotrexate", "statins"],
    "pregnancy": ["ibuprofen", "naproxen", "warfarin", "lisinopril", "enalapril", "ramipril"],
    "asthma": ["aspirin", "ibuprofen", "naproxen", "beta_blocker"],
    "heart failure": ["ibuprofen", "naproxen", "verapamil", "diltiazem"],
    "diabetes": [],  # handled separately
    "hypertension": [],  # NSAIDs reduce effectiveness — handled by LLM
    "bleeding disorder": ["aspirin", "ibuprofen", "naproxen", "warfarin"],
}


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
#  Tool 1: DrugNameExtractor                                          #
# ------------------------------------------------------------------ #

async def extract_medications(message: str) -> list[ExtractedMedication]:
    """Extract and structure medication names from free-text user message."""
    logger.info("Extracting medications from message (len=%d)", len(message))
    try:
        llm = _get_llm()
        prompt = DRUG_EXTRACTION_PROMPT.format(message=message)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = _safe_json_parse(response.content, [])

        medications = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            raw_name = item.get("raw", "")
            generic = normalize_drug_name(item.get("generic_name", raw_name))
            medications.append(
                ExtractedMedication(
                    raw=raw_name,
                    generic_name=generic,
                    brand_name=item.get("brand_name"),
                    dosage_mentioned=item.get("dosage_mentioned"),
                    frequency_mentioned=item.get("frequency_mentioned"),
                    route=item.get("route"),
                )
            )
        logger.info("Extracted %d medications", len(medications))
        return medications
    except Exception as exc:
        logger.error("Drug extraction failed: %s", exc)
        return []


# ------------------------------------------------------------------ #
#  Tool 2: DrugNormalizer                                             #
# ------------------------------------------------------------------ #

def normalize_drug_name(name: str) -> str:
    """
    Normalize brand name to generic name.
    Rule-based lookup — independently testable, no LLM.
    """
    return _BRAND_TO_GENERIC.get(name.lower().strip(), name.lower().strip())


def get_drug_class(drug: str) -> Optional[str]:
    """Return the drug class for a given generic drug name."""
    drug_lower = drug.lower().strip()
    for cls, members in _DRUG_CLASSES.items():
        if drug_lower in members:
            return cls
    return None


# ------------------------------------------------------------------ #
#  Tool 3: InteractionChecker                                         #
# ------------------------------------------------------------------ #

async def check_interactions(
    medications: list[ExtractedMedication],
    current_medications: list[dict],
    rag_context: str,
) -> list[DrugInteraction]:
    """
    Check drug-drug interactions using RAG context + LLM reasoning.
    Combines user-mentioned and patient's current medications.
    """
    all_drug_names = [m.generic_name for m in medications]
    current_names = [m.get("medicine_name", "").lower() for m in current_medications]
    all_names = list(set(all_drug_names + current_names))

    if len(all_names) < 2:
        logger.info("Less than 2 medications — no interactions to check")
        return []

    logger.info("Checking interactions for: %s", all_names)
    try:
        llm = _get_llm(temperature=0.0)
        prompt = INTERACTION_CHECK_PROMPT.format(
            medications=", ".join(all_drug_names),
            current_medications=", ".join(current_names) or "none",
            rag_context=rag_context,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = _safe_json_parse(response.content, [])

        interactions = []
        for item in raw:
            if not isinstance(item, dict) or "drug_a" not in item:
                continue
            interactions.append(
                DrugInteraction(
                    drug_a=item["drug_a"],
                    drug_b=item["drug_b"],
                    severity=item.get("severity", "moderate"),
                    description=item.get("description", ""),
                    mechanism=item.get("mechanism"),
                    source=item.get("source"),
                )
            )
        logger.info("Found %d interactions", len(interactions))
        return interactions
    except Exception as exc:
        logger.error("Interaction check failed: %s", exc)
        return []


# ------------------------------------------------------------------ #
#  Tool 4: AllergyChecker                                             #
# ------------------------------------------------------------------ #

def check_allergies(
    medications: list[ExtractedMedication],
    patient_allergies: str,
) -> list[AllergyAlert]:
    """
    Cross-check medications against patient allergies.
    Rule-based — no LLM, fast and deterministic.
    """
    if not patient_allergies:
        return []

    alerts: list[AllergyAlert] = []
    allergy_list = [a.strip().lower() for a in patient_allergies.split(",")]

    for med in medications:
        drug = med.generic_name.lower()

        for allergen in allergy_list:
            # Direct match
            if allergen in drug or drug in allergen:
                alerts.append(AllergyAlert(
                    medication=med.generic_name,
                    allergen=allergen,
                    severity="critical",
                    reaction_type="known allergy",
                ))
                logger.warning("ALLERGY ALERT: %s matches allergen %s", drug, allergen)
                continue

            # Cross-reactivity check
            cross_reactive = _ALLERGY_CROSS_REACTIVITY.get(allergen, [])
            if drug in cross_reactive:
                alerts.append(AllergyAlert(
                    medication=med.generic_name,
                    allergen=allergen,
                    severity="high",
                    reaction_type="possible cross-reactivity",
                ))
                logger.warning("CROSS-REACTIVITY: %s may cross-react with %s allergy", drug, allergen)

    return alerts


# ------------------------------------------------------------------ #
#  Tool 5: ContraindicationChecker                                    #
# ------------------------------------------------------------------ #

async def check_contraindications(
    medications: list[ExtractedMedication],
    chronic_diseases: str,
    medical_history: list[dict],
    rag_context: str,
) -> list[Contraindication]:
    """
    Check medications against patient's chronic diseases and history.
    Rule-based fast path + LLM for complex cases.
    """
    contraindications: list[Contraindication] = []
    conditions = []

    if chronic_diseases:
        conditions.extend([c.strip().lower() for c in chronic_diseases.split(",")])
    for h in medical_history:
        diag = h.get("diagnosis", "").lower()
        if diag:
            conditions.append(diag)

    # Rule-based fast path
    for med in medications:
        drug = med.generic_name.lower()
        drug_class = get_drug_class(drug)

        for condition in conditions:
            for cond_key, contraindicated_drugs in _CONDITION_CONTRAINDICATIONS.items():
                if cond_key in condition:
                    if drug in contraindicated_drugs or (drug_class and drug_class in contraindicated_drugs):
                        contraindications.append(Contraindication(
                            medication=med.generic_name,
                            condition=condition,
                            reason=f"{med.generic_name} is generally contraindicated in {cond_key}",
                            severity="relative",
                            source="NIH",
                        ))
                        logger.warning("CONTRAINDICATION: %s + %s", drug, condition)

    # LLM for complex cases not covered by rules
    if conditions and medications and rag_context:
        try:
            llm = _get_llm(temperature=0.0)
            prompt = CONTRAINDICATION_CHECK_PROMPT.format(
                medications=", ".join(m.generic_name for m in medications),
                chronic_diseases=chronic_diseases or "none",
                medical_history="; ".join(
                    h.get("diagnosis", "") for h in medical_history[:3]
                ) or "none",
                rag_context=rag_context,
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = _safe_json_parse(response.content, [])
            for item in raw:
                if not isinstance(item, dict) or "medication" not in item:
                    continue
                # Avoid duplicates from rule-based check
                existing = {(c.medication.lower(), c.condition.lower()) for c in contraindications}
                key = (item["medication"].lower(), item.get("condition", "").lower())
                if key not in existing:
                    contraindications.append(Contraindication(
                        medication=item["medication"],
                        condition=item.get("condition", ""),
                        reason=item.get("reason", ""),
                        severity=item.get("severity", "relative"),
                        source=item.get("source"),
                    ))
        except Exception as exc:
            logger.error("LLM contraindication check failed: %s", exc)

    return contraindications


# ------------------------------------------------------------------ #
#  Tool 6: DuplicateMedicationChecker                                 #
# ------------------------------------------------------------------ #

def check_duplicates(
    medications: list[ExtractedMedication],
    current_medications: list[dict],
) -> list[DuplicateWarning]:
    """
    Detect duplicate medications or same-class duplicates.
    Rule-based — no LLM, independently testable.
    """
    warnings: list[DuplicateWarning] = []
    current_generics = [
        normalize_drug_name(m.get("medicine_name", ""))
        for m in current_medications
    ]

    for med in medications:
        drug = med.generic_name.lower()
        drug_class = get_drug_class(drug)

        # Exact duplicate
        if drug in current_generics:
            warnings.append(DuplicateWarning(
                medication=med.generic_name,
                existing_medication=drug,
                note=f"You appear to already be taking {drug}. Taking it again may lead to overdose.",
            ))
            logger.warning("DUPLICATE: %s already in current medications", drug)
            continue

        # Same-class duplicate (e.g. two NSAIDs)
        if drug_class:
            for existing in current_generics:
                existing_class = get_drug_class(existing)
                if existing_class == drug_class and existing != drug:
                    warnings.append(DuplicateWarning(
                        medication=med.generic_name,
                        existing_medication=existing,
                        note=(
                            f"Both {med.generic_name} and {existing} belong to the "
                            f"{drug_class.upper()} class. Taking two drugs from the same class "
                            "is generally not recommended without medical supervision."
                        ),
                    ))
                    logger.warning("SAME-CLASS DUPLICATE: %s + %s (%s)", drug, existing, drug_class)

    return warnings


# ------------------------------------------------------------------ #
#  Tool 7: DosageValidator                                            #
# ------------------------------------------------------------------ #

async def validate_dosages(
    medications: list[ExtractedMedication],
    patient_context: str,
    rag_context: str,
) -> list[DosageValidation]:
    """
    Informational dosage range check using RAG context + LLM.
    Never recommends specific dosages — educational only.
    """
    meds_with_dosage = [m for m in medications if m.dosage_mentioned]
    if not meds_with_dosage:
        return []

    logger.info("Validating dosages for %d medications", len(meds_with_dosage))
    try:
        llm = _get_llm(temperature=0.0)
        meds_text = "; ".join(
            f"{m.generic_name} {m.dosage_mentioned}" for m in meds_with_dosage
        )
        prompt = DOSAGE_VALIDATION_PROMPT.format(
            medications_with_dosages=meds_text,
            patient_context=patient_context,
            rag_context=rag_context,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = _safe_json_parse(response.content, [])

        validations = []
        for item in raw:
            if not isinstance(item, dict) or "medication" not in item:
                continue
            validations.append(DosageValidation(
                medication=item["medication"],
                mentioned_dosage=item.get("mentioned_dosage", ""),
                typical_range=item.get("typical_range", "consult pharmacist"),
                is_within_range=item.get("is_within_range"),
                note=item.get("note", ""),
            ))
        return validations
    except Exception as exc:
        logger.error("Dosage validation failed: %s", exc)
        return []


# ------------------------------------------------------------------ #
#  Severity Aggregator                                                #
# ------------------------------------------------------------------ #

def compute_overall_severity(
    interactions: list[DrugInteraction],
    allergy_alerts: list[AllergyAlert],
    contraindications: list[Contraindication],
) -> str:
    """
    Compute overall safety severity: safe | caution | warning | danger.
    Rule-based — deterministic.
    """
    if any(a.severity == "critical" for a in allergy_alerts):
        return "danger"
    if any(i.severity == "contraindicated" for i in interactions):
        return "danger"
    if any(i.severity == "major" for i in interactions):
        return "warning"
    if any(c.severity == "absolute" for c in contraindications):
        return "warning"
    if interactions or contraindications or allergy_alerts:
        return "caution"
    return "safe"


def compute_safety_confidence(
    medications: list[ExtractedMedication],
    rag_docs_count: int,
    checks_performed: int,
) -> float:
    """Compute confidence score [0.0, 1.0]."""
    score = 0.0
    if medications:
        score += min(len(medications) * 0.2, 0.4)
    if rag_docs_count > 0:
        score += min(rag_docs_count * 0.08, 0.32)
    if checks_performed > 0:
        score += min(checks_performed * 0.07, 0.28)
    return round(min(score, 1.0), 2)


def build_recommendations(
    interactions: list[DrugInteraction],
    allergy_alerts: list[AllergyAlert],
    contraindications: list[Contraindication],
    duplicate_warnings: list[DuplicateWarning],
    severity: str,
) -> list[str]:
    """Build a prioritised list of safety recommendations."""
    recs: list[str] = []

    if allergy_alerts:
        recs.append(
            "⚠️ ALLERGY ALERT: Inform your doctor/pharmacist immediately about your allergy "
            "before taking the flagged medication(s)."
        )
    if any(i.severity in ("contraindicated", "major") for i in interactions):
        recs.append(
            "🚨 Serious drug interaction detected. Do not take these medications together "
            "without explicit medical supervision."
        )
    if contraindications:
        recs.append(
            "Discuss the flagged contraindications with your prescribing physician before starting treatment."
        )
    if duplicate_warnings:
        recs.append(
            "Possible duplicate medication detected. Review your current medication list with your pharmacist."
        )
    if severity in ("caution", "warning", "danger"):
        recs.append("Consult your pharmacist or physician before taking these medications together.")

    recs.append(
        "Always inform all your healthcare providers about every medication, supplement, "
        "and herbal product you are taking."
    )
    return recs
