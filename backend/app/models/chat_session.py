from typing import Optional, List
from beanie import Document, PydanticObjectId, Indexed
from app.models.base import TimestampMixin

class ChatSession(Document, TimestampMixin):
    user_id: Indexed(PydanticObjectId)
    patient_profile_id: Optional[Indexed(PydanticObjectId)] = None

    conversation_history: str = "[]"
    last_detected_intents: Optional[str] = None
    last_selected_agents: Optional[str] = None
    is_active: bool = True

    class Settings:
        name = "chat_sessions"

class AgentExecutionLog(Document, TimestampMixin):
    session_id: Indexed(PydanticObjectId)
    agent_name: str
    status: str  # success | error
    execution_time_ms: float = 0.0

    input_snapshot: Optional[str] = None
    output_snapshot: Optional[str] = None
    error_message: Optional[str] = None

    class Settings:
        name = "agent_execution_logs"