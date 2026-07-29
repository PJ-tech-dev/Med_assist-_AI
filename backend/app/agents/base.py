"""
Base agent contract and shared state definition.

Every AI agent in MedAssist must:
  1. Inherit from BaseAgent
  2. Declare name, description, supported_intents
  3. Implement execute(state: AgentState) -> AgentState
"""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional
from typing_extensions import TypedDict


# ------------------------------------------------------------------ #
#  Shared Graph State                                                  #
# ------------------------------------------------------------------ #

class ConversationTurn(TypedDict):
    role: str          # "user" | "assistant"
    content: str
    timestamp: str


class AgentOutput(TypedDict):
    agent_name: str
    response: str
    confidence: float
    metadata: dict[str, Any]
    execution_time_ms: float
    error: Optional[str]


class AgentState(TypedDict):
    # Identity
    session_id: str
    user_id: str

    # Input
    user_message: str
    conversation_history: list[ConversationTurn]

    # Patient context (loaded before orchestration)
    patient_profile: Optional[dict[str, Any]]
    medical_history: list[dict[str, Any]]

    # RAG context (populated by retrieval step)
    retrieved_context: list[str]

    # Routing
    detected_intents: list[str]
    selected_agents: list[str]

    # Execution
    agent_outputs: list[AgentOutput]

    # Final
    final_response: str
    metadata: dict[str, Any]


def initial_state(
    session_id: str,
    user_id: str,
    user_message: str,
    conversation_history: Optional[list[ConversationTurn]] = None,
    patient_profile: Optional[dict[str, Any]] = None,
    medical_history: Optional[list[dict[str, Any]]] = None,
) -> AgentState:
    """Factory that returns a fully-initialised AgentState."""
    return AgentState(
        session_id=session_id,
        user_id=user_id,
        user_message=user_message,
        conversation_history=conversation_history or [],
        patient_profile=patient_profile,
        medical_history=medical_history or [],
        retrieved_context=[],
        detected_intents=[],
        selected_agents=[],
        agent_outputs=[],
        final_response="",
        metadata={},
    )


# ------------------------------------------------------------------ #
#  Abstract Base Agent                                                 #
# ------------------------------------------------------------------ #

class BaseAgent(ABC):
    """
    Abstract contract every MedAssist agent must satisfy.

    Subclasses declare:
      - name              : unique snake_case identifier
      - description       : human-readable purpose
      - supported_intents : list of intent strings this agent handles
      - tools             : list of LangChain tools (populated in subclass)

    Subclasses implement:
      - execute(state)    : core logic; returns updated AgentState
    """

    name: str
    description: str
    supported_intents: list[str]
    tools: list[Any] = []

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """
        Run agent logic against the shared state.
        Must append exactly one AgentOutput to state['agent_outputs'].
        Must NOT modify state keys other than 'agent_outputs'.
        """

    async def safe_execute(self, state: AgentState) -> AgentState:
        """
        Wrapper that times execution, catches exceptions, and always
        appends a well-formed AgentOutput — even on failure.
        """
        from app.utils.logger import get_logger
        logger = get_logger(f"agent.{self.name}")
        start = time.perf_counter()
        try:
            logger.info("[%s] executing | session=%s", self.name, state["session_id"])
            state = await self.execute(state)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("[%s] done | %.1fms", self.name, elapsed_ms)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("[%s] error | %.1fms | %s", self.name, elapsed_ms, exc)
            state["agent_outputs"].append(
                AgentOutput(
                    agent_name=self.name,
                    response="",
                    confidence=0.0,
                    metadata={},
                    execution_time_ms=elapsed_ms,
                    error=str(exc),
                )
            )
        return state

    def build_output(
        self,
        response: str,
        confidence: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
        execution_time_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> AgentOutput:
        """Helper to construct a typed AgentOutput."""
        return AgentOutput(
            agent_name=self.name,
            response=response,
            confidence=confidence,
            metadata=metadata or {},
            execution_time_ms=execution_time_ms,
            error=error,
        )
