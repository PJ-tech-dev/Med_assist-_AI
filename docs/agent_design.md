# MedAssist AI — Agent Design

## BaseAgent Contract

Every agent must inherit `BaseAgent` and satisfy this interface:

```python
class BaseAgent(ABC):
    name: str                        # unique snake_case identifier
    description: str                 # human-readable purpose
    supported_intents: list[str]     # intents this agent handles
    tools: list[Any]                 # LangChain tools

    async def execute(state: AgentState) -> AgentState
```

### Rules every agent must follow
1. Append **exactly one** `AgentOutput` to `state["agent_outputs"]`
2. Must **not** modify any state key other than `agent_outputs`
3. Must be **stateless** — all context comes from `AgentState`
4. Must call `self.build_output(...)` to construct the output
5. Always call via `safe_execute()` — never `execute()` directly

---

## AgentState — Shared Graph State

```
AgentState
├── session_id          str         — chat session UUID
├── user_id             str         — authenticated user UUID
├── user_message        str         — raw user input
├── conversation_history list       — prior turns [{role, content, timestamp}]
├── patient_profile     dict|None   — loaded from PostgreSQL
├── medical_history     list[dict]  — loaded from PostgreSQL
├── retrieved_context   list[str]   — RAG chunks from ChromaDB (Module 9)
├── detected_intents    list[str]   — set by IntentRouter
├── selected_agents     list[str]   — set by IntentRouter
├── agent_outputs       list        — appended by each agent
├── final_response      str         — set by merge_outputs node
└── metadata            dict        — timing, routing info, debug data
```

---

## The Six Agents

### 1. SymptomAnalysisAgent ✅ Production (Module 4)
- **Intent:** `symptom_analysis`, `general_health_query`
- **Purpose:** Analyse user-reported symptoms, suggest possible conditions
- **Status:** Full production implementation
- **Package:** `app/agents/symptom/`
- **Pipeline:**
  1. `extract_symptoms` — LLM extracts structured symptoms from free text
  2. `normalize_symptoms` — rule-based + LLM medical term normalization
  3. `classify_severity` — rule-based fast path + LLM (mild/moderate/severe/emergency)
  4. `retrieve_conditions` — ChromaDB RAG + LLM reasoning
  5. `generate_followup_questions` — rule-based, memory-aware, capped at 3
  6. `compute_confidence` — deterministic scoring [0.0, 1.0]
  7. `_generate_response` — final natural language response via LLM
- **Tools:** `SymptomExtractorTool`, `MedicalEntityNormalizer`, `SeverityClassifier`, `ConditionRetriever`, `FollowUpQuestionGenerator`
- **RAG Sources:** WHO, CDC, NIH, MedlinePlus
- **Safety:** Never diagnoses, never prescribes, always recommends professional consultation
- **Memory:** Uses `conversation_history` to avoid repeating follow-up questions
- **Output Schema:** `SymptomAnalysisResult` (Pydantic v2)

### 2. MedicalHistoryAgent *(placeholder — Module 6)*
- **Intent:** `patient_history`
- **Purpose:** Retrieve and summarise patient's past diagnoses and conditions
- **Full implementation:** Module 6
- **Tools planned:** patient history retriever, timeline builder

### 3. MedicineSafetyAgent ✅ Production (Module 5)
- **Intent:** `medicine_safety`
- **Purpose:** Check drug safety, interactions, allergies, contraindications
- **Status:** Full production implementation
- **Package:** `app/agents/medicine_safety/`
- **Pipeline:**
  1. `extract_medications` — LLM extracts structured drug names from free text
  2. `normalize_drug_name` — rule-based brand → generic mapping (40+ drugs)
  3. `check_interactions` — RAG + LLM drug-drug interaction detection
  4. `check_allergies` — rule-based allergy + cross-reactivity check
  5. `check_contraindications` — rule-based fast path + LLM for complex cases
  6. `check_duplicates` — exact + same-class duplicate detection
  7. `validate_dosages` — informational range check (RAG + LLM)
  8. `compute_overall_severity` — deterministic: safe/caution/warning/danger
  9. `build_recommendations` — prioritised safety recommendations
  10. `_generate_response` — natural language response via LLM
- **Tools:** `DrugNameExtractor`, `DrugNormalizer`, `InteractionChecker`, `AllergyChecker`, `ContraindicationChecker`, `DuplicateMedicationChecker`, `DosageValidator`, `DrugKnowledgeRetriever`
- **RAG Sources:** DailyMed, FDA, NIH, MedlinePlus, WHO (12 seed documents)
- **Safety:** Never prescribes, never recommends dosages, always recommends pharmacist/physician
- **Memory:** Uses `patient_profile` allergies, chronic diseases, and `metadata.current_medications`
- **Output Schema:** `MedicineSafetyResult` (Pydantic v2)

### 3. MedicineSafetyAgent
- **Intent:** `medicine_safety`
- **Purpose:** Check drug interactions, dosage safety, contraindications
- **Full implementation:** Module 6
- **Tools planned:** drug interaction checker, dosage validator, ChromaDB retriever

### 4. EmergencyTriageAgent
- **Intent:** `emergency_triage`
- **Purpose:** Detect life-threatening situations, provide immediate guidance
- **Execution:** Always runs **alone, sequentially** — never in parallel
- **Full implementation:** Module 7
- **Tools planned:** emergency classifier, triage protocol retriever

### 5. HealthMonitoringAgent
- **Intent:** `health_monitoring`
- **Purpose:** Analyse vitals trends, flag abnormal readings
- **Full implementation:** Module 8
- **Tools planned:** vitals analyser, trend detector, reference range checker

### 6. MedicalReportAnalysisAgent
- **Intent:** `report_analysis`
- **Purpose:** Parse and explain lab results, imaging reports
- **Full implementation:** Module 9
- **Tools planned:** report parser, ChromaDB retriever, reference range tool

---

## Intent → Agent Mapping

| Intent | Agent(s) |
|--------|---------|
| `emergency_triage` | EmergencyTriageAgent (exclusive) |
| `symptom_analysis` | SymptomAnalysisAgent |
| `medicine_safety` | MedicineSafetyAgent |
| `report_analysis` | MedicalReportAnalysisAgent |
| `health_monitoring` | HealthMonitoringAgent |
| `patient_history` | MedicalHistoryAgent |
| `general_health_query` | SymptomAnalysisAgent (fallback) |

---

## Execution Strategy

```
Single agent or Emergency → Sequential
Multiple non-emergency    → Parallel (asyncio.gather)
```

Parallel execution uses a **state snapshot** per agent to avoid race conditions on shared mutable state. Outputs are merged after all tasks complete.

---

## Adding a New Agent (Checklist)

1. Create class in `app/agents/implementations.py` inheriting `BaseAgent`
2. Set `name`, `description`, `supported_intents`, `tools`
3. Implement `async def execute(state) -> AgentState`
4. Register instance in `_AGENT_REGISTRY` in `orchestrator.py`
5. Add intent → agent mapping in `INTENT_AGENT_MAP` in `intent_router.py`
6. Add intent patterns to `_INTENT_RULES` in `intent_router.py`
7. Write unit tests in `tests/`
