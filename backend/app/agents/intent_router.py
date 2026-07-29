"""
Intent Router — keyword + pattern based multi-intent detection.

Detects one or more intents from a user message without calling an LLM.
Each intent maps to one or more agents in the orchestrator.

Supported intents:
  symptom_analysis    → SymptomAnalysisAgent
  medicine_safety     → MedicineSafetyAgent
  report_analysis     → MedicalReportAnalysisAgent
  health_monitoring   → HealthMonitoringAgent
  emergency_triage    → EmergencyTriageAgent
  patient_history     → MedicalHistoryAgent
  order_history       → PharmacyOrderAgent
  general_health_query→ SymptomAnalysisAgent (fallback)
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger("intent_router")


@dataclass
class IntentRule:
    intent: str
    patterns: list[str]
    priority: int = 0          # higher = evaluated first
    _compiled: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def matches(self, text: str) -> bool:
        return any(rx.search(text) for rx in self._compiled)


# Intent rules ordered by priority (highest first)
_INTENT_RULES: list[IntentRule] = [
    IntentRule(
        intent="emergency_triage",
        priority=100,
        patterns=[
            r"\bchest\s+pain\b", r"\bcan'?t\s+breath", r"\bshortness\s+of\s+breath\b",
            r"\bheart\s+attack\b", r"\bstroke\b", r"\bemergency\b", r"\bunconsciou",
            r"\bseizure\b", r"\bsevere\s+bleed", r"\bsuicid",
        ],
    ),
    IntentRule(
        intent="symptom_analysis",
        priority=80,
        patterns=[
            r"\bsymptom", r"\bfever\b", r"\bcough\b", r"\bheadache\b", r"\bpain\b",
            r"\bnausea\b", r"\bvomit", r"\bdizziness\b", r"\bfatigue\b", r"\bitch",
            r"\brash\b", r"\bswelling\b", r"\bi\s+(have|feel|am)\b", r"\bhurts?\b",
            r"\bsore\b", r"\bache\b",
        ],
    ),
    IntentRule(
        intent="medicine_safety",
        priority=70,
        patterns=[
            r"\bmedic(ine|ation|al)?\b", r"\bdrug\b", r"\bdose\b", r"\bdosage\b",
            r"\bprescri", r"\bside\s+effect", r"\binteraction\b", r"\bparacetamol\b",
            r"\bibuprofen\b", r"\bantibiotic\b", r"\btablet\b", r"\bcapsule\b",
            r"\bcan\s+i\s+take\b", r"\bsafe\s+to\s+take\b",
        ],
    ),
    IntentRule(
        intent="report_analysis",
        priority=70,
        patterns=[
            r"\breport\b", r"\blab\s+result", r"\bblood\s+test\b", r"\bx.?ray\b",
            r"\bscan\b", r"\bmri\b", r"\bct\s+scan\b", r"\bultrasound\b",
            r"\btest\s+result", r"\bdiagnos", r"\bpatholog",
            r"\bcbc\b", r"\blft\b", r"\bkft\b", r"\blipid\b",
            r"\bthyroid\s+report\b", r"\bcholesterol\s+report\b",
            r"\bupload\s+report\b", r"\bblood\s+report\b",
            r"\breport\s+analysis\b", r"\bscan\s+report\b",
        ],
    ),
    IntentRule(
        intent="health_monitoring",
        priority=60,
        patterns=[
            r"\bblood\s+pressure\b", r"\bbp\b", r"\bsugar\b", r"\bglucose\b",
            r"\bweight\b", r"\bbmi\b", r"\bheart\s+rate\b", r"\bpulse\b",
            r"\bmonitor", r"\btrack", r"\bvital", r"\bcholesterol\b",
            r"\bsleep\b", r"\bexercise\b",
        ],
    ),
    IntentRule(
        intent="patient_history",
        priority=50,
        patterns=[
            r"\bhistory\b", r"\bpast\s+(illness|condition|surgery|treatment)\b",
            r"\bprevious\b", r"\bchronic\b", r"\ballerg", r"\brecord\b",
            r"\bmy\s+(condition|illness|disease)\b",
        ],
    ),
    IntentRule(
        intent="order_history",
        priority=45,
        patterns=[
            r"\border\b", r"\bmy\s+orders?\b", r"\bpast\s+orders?\b",
            r"\bpurchase\b", r"\bdelivery\b", r"\btrack\s+order\b",
            r"\bmedicine\s+order\b", r"\bpharmacy\s+order\b",
        ],
    ),
    IntentRule(
        intent="general_health_query",
        priority=10,
        patterns=[
            r"\bhealth\b", r"\bwellness\b", r"\bdiet\b", r"\bnutrition\b",
            r"\bvitamin\b", r"\bsupplement\b", r"\blifestyle\b", r"\badvice\b",
            r"\btip\b", r"\bhow\s+to\b", r"\bwhat\s+is\b", r"\bwhat\s+are\b",
        ],
    ),
]

# Sort once at import time
_INTENT_RULES.sort(key=lambda r: r.priority, reverse=True)

# Maps intent → agent names (used by orchestrator)
INTENT_AGENT_MAP: dict[str, list[str]] = {
    "emergency_triage":    ["EmergencyTriageAgent"],
    "symptom_analysis":    ["SymptomAnalysisAgent"],
    "medicine_safety":     ["MedicineSafetyAgent"],
    "report_analysis":     ["MedicalReportAnalysisAgent"],
    "health_monitoring":   ["HealthMonitoringAgent"],
    "patient_history":     ["MedicalHistoryAgent"],
    "general_health_query": ["SymptomAnalysisAgent"],
    "chit_chat":           [],
}

# Emergency always runs alone — no other agents
_EMERGENCY_INTENT = "emergency_triage"


def detect_intents(message: str) -> list[str]:
    """
    Return a deduplicated, priority-ordered list of intents for a message.
    If emergency_triage is detected, it is returned as the sole intent.
    Falls back to general_health_query if nothing matches.
    """
    matched = [rule.intent for rule in _INTENT_RULES if rule.matches(message)]

    if _EMERGENCY_INTENT in matched:
        logger.warning("Emergency intent detected | message_preview='%s'", message[:80])
        return [_EMERGENCY_INTENT]

    # Deduplicate while preserving order
    seen: set[str] = set()
    intents: list[str] = []
    for intent in matched:
        if intent not in seen:
            seen.add(intent)
            intents.append(intent)

    if not intents:
        intents = ["chit_chat"]

    logger.info("Detected intents: %s", intents)
    return intents


def resolve_agents(intents: list[str]) -> list[str]:
    """
    Map intents → unique ordered list of agent names to execute.
    """
    seen: set[str] = set()
    agents: list[str] = []
    for intent in intents:
        for agent in INTENT_AGENT_MAP.get(intent, []):
            if agent not in seen:
                seen.add(agent)
                agents.append(agent)
    logger.info("Resolved agents: %s", agents)
    return agents
