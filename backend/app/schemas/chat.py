from beanie import PydanticObjectId
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator, ConfigDict


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None          # None = start new session
    patient_profile_id: Optional[PydanticObjectId] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be empty")
        return v.strip()


class AgentOutputSchema(BaseModel):
    agent_name: str
    response: str
    confidence: float
    execution_time_ms: float
    error: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    final_response: str
    detected_intents: list[str]
    selected_agents: list[str]
    agent_outputs: list[AgentOutputSchema]
    total_execution_ms: float


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    user_id: PydanticObjectId
    patient_profile_id: Optional[PydanticObjectId] = None
    is_active: bool = True
    conversation_history: Optional[str] = "[]"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
