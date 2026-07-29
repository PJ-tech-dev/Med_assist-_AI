# MedAssist AI — Workflow Documentation

## LangGraph Graph Topology

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                         ▼
              ┌──────────────────────┐
              │    route_intent      │
              │                      │
              │  • detect_intents()  │
              │  • resolve_agents()  │
              │  • populate:         │
              │    detected_intents  │
              │    selected_agents   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   execute_agents     │
              │                      │
              │  Emergency?          │
              │  ┌─────────────────┐ │
              │  │  Sequential     │ │
              │  │  EmergencyAgent │ │
              │  └─────────────────┘ │
              │                      │
              │  Others?             │
              │  ┌─────────────────┐ │
              │  │  Parallel       │ │
              │  │  asyncio.gather │ │
              │  │  Agent A ──┐    │ │
              │  │  Agent B ──┤    │ │
              │  │  Agent C ──┘    │ │
              │  └─────────────────┘ │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │    merge_outputs     │
              │                      │
              │  • Skip errored outs │
              │  • Join responses    │
              │  • Set final_response│
              │  • Track total_ms    │
              └──────────┬───────────┘
                         │
                         ▼
                    ┌─────────┐
                    │   END   │
                    └─────────┘
```

---

## Full Chat Request Workflow

```
Step 1 — Authentication
  POST /api/v1/chat
  Authorization: Bearer <jwt>
        │
        ▼ (FastAPI dependency)
  decode JWT → load User from PostgreSQL

Step 2 — Session Management
  session_id provided? → load existing ChatSession
  session_id missing?  → create new ChatSession
        │
        ▼
  Load conversation_history from session

Step 3 — Patient Context Loading
  patient_profile_id provided?
    YES → load PatientProfile + MedicalHistories (eager load)
    NO  → patient_profile = None, medical_history = []

Step 4 — State Initialisation
  initial_state(
    session_id, user_id, user_message,
    conversation_history, patient_profile, medical_history
  )

Step 5 — LangGraph Orchestration
  run_orchestrator(state)
    ├── route_intent node
    ├── execute_agents node
    └── merge_outputs node

Step 6 — Persistence
  Append user + assistant turns to conversation_history
  Save AgentExecutionLog rows for each agent

Step 7 — Response
  Return ChatResponse {
    session_id, final_response,
    detected_intents, selected_agents,
    agent_outputs, total_execution_ms
  }
```

---

## Intent Detection Workflow

```
User message
     │
     ▼
Pattern matching against _INTENT_RULES (priority-ordered)
     │
     ├── emergency_triage matched?
     │     YES → return ["emergency_triage"] immediately
     │
     ├── Other intents matched?
     │     YES → deduplicate, preserve priority order
     │
     └── Nothing matched?
           → fallback to ["general_health_query"]
```

---

## Agent Execution Modes

### Sequential (Emergency or Single Agent)
```
state → EmergencyTriageAgent.safe_execute(state) → updated state
```

### Parallel (Multiple Non-Emergency Agents)
```
state_snapshot_A → AgentA.safe_execute() ─┐
state_snapshot_B → AgentB.safe_execute() ─┤ asyncio.gather
state_snapshot_C → AgentC.safe_execute() ─┘
                                           │
                              merge all agent_outputs into state
```

---

## Integration Points for Future Modules

| Module | Integration Point |
|--------|------------------|
| 4 — SymptomAnalysisAgent | ✅ Complete — Full LLM chain + ChromaDB RAG |
| 5 — MedicineSafetyAgent | ✅ Complete — Full LLM chain + ChromaDB RAG + rule-based checks |
| 6 — MedicalHistoryAgent | Replace placeholder with history summarisation chain |
| 7 — EmergencyTriageAgent | Replace placeholder with triage classification chain |
| 8 — HealthMonitoringAgent | Replace placeholder with vitals analysis chain |
| 9 — MedicalReportAnalysisAgent | Replace placeholder with report parsing chain |
| 9 — ChromaDB RAG | Populate `state["retrieved_context"]` in a new `retrieve_context` node before `execute_agents` |
| 10 — React Frontend | Consume `POST /api/v1/chat` and `GET /api/v1/chat/sessions` |

---

## Error Handling Strategy

| Scenario | Behaviour |
|----------|-----------|
| Agent raises exception | `safe_execute` catches it, appends error AgentOutput, continues |
| All agents fail | `merge_outputs` returns a generic error message |
| Unknown agent name | Logged as warning, skipped silently |
| Invalid JWT | 401 before orchestrator is ever called |
| Patient not found | 404 before orchestrator is ever called |
| Empty message | 422 Pydantic validation error |
