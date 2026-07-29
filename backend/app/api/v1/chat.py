import time
from typing import Optional
from beanie import PydanticObjectId

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.chat_session import ChatSession
from app.schemas.chat import ChatRequest, ChatResponse, AgentOutputSchema, SessionResponse
from app.services.chat_service import chat_service
from app.agents.base import initial_state
from app.agents.orchestrator import run_orchestrator
from app.utils.logger import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger("api.chat")


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    wall_start = time.perf_counter()

    # 1. Load or create session
    session = await chat_service.get_or_create_session(
        current_user.id, payload.session_id, payload.patient_profile_id
    )

    # 2. Load patient context
    patient_profile, medical_history = await chat_service.load_patient_context(
        current_user.id, payload.patient_profile_id or session.patient_profile_id
    )

    # 3. Build initial state
    history = chat_service.get_conversation_history(session)
    state = initial_state(
        session_id=str(session.id),
        user_id=str(current_user.id),
        user_message=payload.message,
        conversation_history=history,
        patient_profile=patient_profile,
        medical_history=medical_history,
    )
    state["metadata"] = {"patient_profile_id": str(session.patient_profile_id)}

    # 4. Run orchestrator (intent → agents → merge)
    logger.info("Chat request | user=%s | session=%s", current_user.id, session.id)
    result = await run_orchestrator(state)

    # 5. Persist turn + logs
    await chat_service.save_turn(
        session=session,
        user_message=payload.message,
        assistant_response=result["final_response"],
        agent_outputs=result["agent_outputs"],
        detected_intents=result["detected_intents"],
        selected_agents=result["selected_agents"],
    )

    total_ms = (time.perf_counter() - wall_start) * 1000
    logger.info(
        "Chat complete | session=%s | total_ms=%.1f", session.id, total_ms
    )

    return ChatResponse(
        session_id=str(session.id),
        final_response=result["final_response"],
        detected_intents=result["detected_intents"],
        selected_agents=result["selected_agents"],
        agent_outputs=[
            AgentOutputSchema(
                agent_name=o["agent_name"] if isinstance(o, dict) else getattr(o, "agent_name", "Agent"),
                response=o.get("response", "") if isinstance(o, dict) else getattr(o, "response", ""),
                confidence=o.get("confidence", 0.0) if isinstance(o, dict) else getattr(o, "confidence", 0.0),
                execution_time_ms=o.get("execution_time_ms", 0.0) if isinstance(o, dict) else getattr(o, "execution_time_ms", 0.0),
                error=o.get("error") if isinstance(o, dict) else getattr(o, "error", None),
            )
            for o in result["agent_outputs"]
        ],
        total_execution_ms=total_ms,
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
):
    """Get all active chat sessions for the current user."""
    from pymongo import DESCENDING
    sessions = await ChatSession.find(
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True,
    ).sort([("updated_at", DESCENDING)]).to_list()
    return sessions


@router.delete("/sessions/{session_id}", status_code=204)
async def close_session(
    session_id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    """Close/deactivate a chat session."""
    session = await ChatSession.find_one(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    session.is_active = False
    await session.save()
    return None