import json
from datetime import datetime, timezone
from typing import Optional
from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.models.chat_session import ChatSession, AgentExecutionLog
from app.models.patient_profile import PatientProfile
from app.models.medical_history import MedicalHistory
from app.agents.base import ConversationTurn, AgentOutput
from app.utils.logger import get_logger

logger = get_logger("chat_service")


class ChatService:

    async def get_or_create_session(
        self,
        user_id: PydanticObjectId,
        session_id: Optional[str],
        patient_profile_id: Optional[PydanticObjectId],
    ) -> ChatSession:
        """Load existing session or create a new one."""
        if session_id:
            try:
                sid = PydanticObjectId(session_id)
                session = await ChatSession.find_one(
                    ChatSession.id == sid,
                    ChatSession.user_id == user_id,
                    ChatSession.is_active == True,
                )
                if session:
                    return session
            except Exception:
                pass
            logger.warning("Session %s not found, creating new one", session_id)

        session = ChatSession(
            user_id=user_id,
            patient_profile_id=patient_profile_id,
            conversation_history="[]",
        )
        await session.insert()
        logger.info("New session created: %s", session.id)
        return session

    async def load_patient_context(
        self,
        user_id: PydanticObjectId,
        patient_profile_id: Optional[PydanticObjectId],
    ) -> tuple[Optional[dict], list[dict]]:
        """Load patient profile and medical history for agent context."""
        if not patient_profile_id:
            return None, []

        profile = await PatientProfile.find_one(
            PatientProfile.id == patient_profile_id,
            PatientProfile.user_id == user_id,
            PatientProfile.is_deleted == False,
        )
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        profile_dict = {
            "id": str(profile.id),
            "full_name": profile.full_name,
            "date_of_birth": str(profile.date_of_birth),
            "gender": profile.gender,
            "blood_group": profile.blood_group,
            "allergies": profile.allergies,
            "chronic_diseases": profile.chronic_diseases,
        }

        # Load medical histories
        histories = await MedicalHistory.find(
            MedicalHistory.patient_id == profile.id,
            MedicalHistory.is_deleted == False
        ).to_list()

        history_list = [
            {
                "diagnosis": h.diagnosis,
                "visit_date": str(h.visit_date),
                "doctor_name": h.doctor_name,
                "hospital_name": h.hospital_name,
            }
            for h in histories
        ]
        return profile_dict, history_list

    def get_conversation_history(self, session: ChatSession) -> list[ConversationTurn]:
        try:
            return json.loads(session.conversation_history)
        except (json.JSONDecodeError, TypeError):
            return []

    async def save_turn(
        self,
        session: ChatSession,
        user_message: str,
        assistant_response: str,
        agent_outputs: list[AgentOutput],
        detected_intents: list[str],
        selected_agents: list[str],
    ) -> None:
        """Append conversation turn and persist agent execution logs."""
        now = datetime.now(timezone.utc).isoformat()
        history = self.get_conversation_history(session)
        history.append(ConversationTurn(role="user", content=user_message, timestamp=now))
        history.append(ConversationTurn(role="assistant", content=assistant_response, timestamp=now))

        session.conversation_history = json.dumps(history)
        session.last_detected_intents = json.dumps(detected_intents)
        session.last_selected_agents = json.dumps(selected_agents)
        await session.save()

        # Persist per-agent logs
        for out in agent_outputs:
            log = AgentExecutionLog(
                session_id=session.id,
                agent_name=out["agent_name"],
                status="error" if out.get("error") else "success",
                execution_time_ms=out.get("execution_time_ms", 0.0),
                input_snapshot=json.dumps({"message": user_message}),
                output_snapshot=json.dumps({"response": out.get("response", "")}),
                error_message=out.get("error"),
            )
            await log.insert()

        logger.info(
            "Turn saved | session=%s | agents=%s", session.id, selected_agents
        )


chat_service = ChatService()