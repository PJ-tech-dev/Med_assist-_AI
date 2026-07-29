# MedAssist AI — System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│              React SPA  ←→  Nginx Reverse Proxy                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTPS
┌──────────────────────────────▼──────────────────────────────────┐
│                       API GATEWAY LAYER                         │
│                FastAPI  (uvicorn ASGI server)                   │
│                                                                 │
│   /api/v1/auth      /api/v1/patients      /api/v1/chat          │
│   JWT Middleware    CRUD Endpoints        Orchestrator Entry    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                   ORCHESTRATION LAYER                           │
│                  LangGraph StateGraph                           │
│                                                                 │
│   ┌─────────────┐   ┌──────────────────┐   ┌───────────────┐   │
│   │route_intent │──▶│ execute_agents   │──▶│ merge_outputs │   │
│   │             │   │                  │   │               │   │
│   │IntentRouter │   │ Sequential /     │   │ Combine all   │   │
│   │(pattern     │   │ Parallel agent   │   │ agent outputs │   │
│   │ matching)   │   │ execution        │   │ into one resp │   │
│   └─────────────┘   └──────────────────┘   └───────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      AGENT LAYER                                │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │SymptomAnalysis   │  │ MedicalHistory   │                    │
│  │Agent             │  │ Agent            │                    │
│  └──────────────────┘  └──────────────────┘                    │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │MedicineSafety    │  │ EmergencyTriage  │                    │
│  │Agent             │  │ Agent            │                    │
│  └──────────────────┘  └──────────────────┘                    │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │HealthMonitoring  │  │ MedicalReport    │                    │
│  │Agent             │  │ AnalysisAgent    │                    │
│  └──────────────────┘  └──────────────────┘                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    DATA & AI SERVICES LAYER                     │
│                                                                 │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│   │  PostgreSQL  │   │   ChromaDB   │   │   OpenAI API     │   │
│   │              │   │              │   │   (GPT-4o)       │   │
│   │  users       │   │  RAG vector  │   │                  │   │
│   │  patients    │   │  store for   │   │  LLM backbone    │   │
│   │  history     │   │  medical     │   │  for all agents  │   │
│   │  sessions    │   │  knowledge   │   │                  │   │
│   │  logs        │   │              │   │                  │   │
│   └──────────────┘   └──────────────┘   └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Request Lifecycle

```
User sends message
       │
       ▼
JWT Authentication (FastAPI dependency)
       │
       ▼
Load / Create ChatSession (PostgreSQL)
       │
       ▼
Load PatientProfile + MedicalHistory (PostgreSQL)
       │
       ▼
Build AgentState (initial_state factory)
       │
       ▼
LangGraph Orchestrator
  ├── Node 1: route_intent
  │     └── IntentRouter → detected_intents, selected_agents
  ├── Node 2: execute_agents
  │     ├── Emergency? → Sequential execution
  │     └── Others?    → Parallel execution (asyncio.gather)
  └── Node 3: merge_outputs
        └── Combine responses → final_response
       │
       ▼
Save conversation turn + AgentExecutionLog (PostgreSQL)
       │
       ▼
Return ChatResponse to client
```

---

## Technology Decisions

| Concern | Choice | Reason |
|---------|--------|--------|
| API Framework | FastAPI | Async-native, auto OpenAPI docs, Pydantic v2 |
| Orchestration | LangGraph | Stateful graph, supports conditional routing |
| Database | PostgreSQL + SQLAlchemy async | ACID, UUID support, async driver |
| Vector Store | ChromaDB | Lightweight, self-hosted, LangChain native |
| Auth | JWT (HS256) | Stateless, scalable |
| LLM | OpenAI GPT-4o | Best-in-class medical reasoning |
| Containerisation | Docker Compose | Reproducible dev + prod environments |

---

## Security Architecture

- All patient endpoints require valid JWT
- Users can only access their own patient records (ownership check in service layer)
- Passwords hashed with bcrypt (cost factor 12)
- Refresh tokens are typed (`"type": "refresh"`) to prevent token reuse attacks
- CORS configured (tighten `allow_origins` in production)
- No PII logged — only UUIDs and message lengths in logs
