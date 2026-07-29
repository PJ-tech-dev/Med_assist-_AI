"""
PharmacyOrderAgent — Production implementation.

Handles retrieving past order history and creating new medicine orders
directly via the chat interface, saving securely to MongoDB.
"""

import time
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentState
from app.agents.pharmacy_order.tools import fetch_order_history, create_medicine_order_from_chat
from app.core.settings import settings
from app.utils.logger import get_logger

logger = get_logger("agent.pharmacy_order")

ORDER_RESPONSE_PROMPT = """You are a helpful AI Pharmacy Assistant for the MedAssist AI platform.
The user is asking about their medicine order history, or attempting to place a new order.

Context provided from the database:
{database_context}

User's message:
{user_message}

Instructions:
1. If the user asked for their order history, summarize the past orders clearly and concisely (e.g. date, items, pharmacy, and status).
2. If the user placed a new order, confirm the details, provide the tracking number, and let them know it has been placed.
3. Be polite and concise.
4. Do NOT make up any tracking numbers or orders that are not in the provided context. If the history is empty, simply tell them they haven't placed any orders yet.
"""

class PharmacyOrderAgent(BaseAgent):
    """Agent for fetching and creating medicine orders."""

    name = "PharmacyOrderAgent"
    description = "Handles fetching order history and placing new medicine orders in the database."
    supported_intents = ["order_history"]
    tools: list = []

    async def execute(self, state: AgentState) -> AgentState:
        start = time.perf_counter()
        logger.info(
            "PharmacyOrderAgent START | session=%s",
            state["session_id"]
        )

        try:
            # Check if this is an intent to create an order or just fetch history
            user_message_lower = state["user_message"].lower()
            
            database_context = ""
            
            # Very simple heuristic: if they say "order [something]", we create an order.
            # In a real setup, we'd use function calling or an LLM step to extract items.
            if "order " in user_message_lower and "history" not in user_message_lower and "past" not in user_message_lower:
                # Extract potential medicines (naive extraction for demo, assumes everything after "order" is a med)
                parts = user_message_lower.split("order ")
                if len(parts) > 1:
                    raw_meds = parts[1].replace("please", "").strip()
                    # Just split by comma or 'and'
                    meds = [m.strip() for m in raw_meds.replace(" and ", ",").split(",") if m.strip()]
                    
                    if meds:
                        result = await create_medicine_order_from_chat(
                            patient_id=state.get("user_id", ""),
                            medicines=meds,
                            delivery_address="Home (User Profile Default)"
                        )
                        database_context = f"Successfully placed a new order! Tracking Number: {result.get('tracking_number')}. Pharmacy: {result.get('pharmacy')}. Items: {', '.join(meds)}."
                    else:
                        database_context = "Could not identify which medicines to order."
            else:
                # Fetch history
                history = await fetch_order_history(patient_id=state.get("user_id", ""))
                if history:
                    db_lines = []
                    for idx, order in enumerate(history, 1):
                        db_lines.append(f"{idx}. {order['date']} | {order['status']} | Items: {', '.join(order['items'])} | Total: ₹{order['total_amount']} | Tracking: {order['tracking_number']}")
                    database_context = "User's Past Orders:\n" + "\n".join(db_lines)
                else:
                    database_context = "The user has no past medicine orders in the database."

            # Generate natural response
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.3)
            
            prompt = ORDER_RESPONSE_PROMPT.format(
                database_context=database_context,
                user_message=state.get("user_message", "")
            )
            
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            response_text = str(response.content).strip()

        except Exception as exc:
            logger.error("PharmacyOrderAgent failed: %s", exc)
            response_text = "I'm sorry, I encountered an error while accessing the order database. Please try again."

        elapsed_ms = (time.perf_counter() - start) * 1000

        state["agent_outputs"].append(
            self.build_output(
                response=response_text,
                confidence=1.0,
                metadata={"database_context": database_context},
                execution_time_ms=elapsed_ms,
            )
        )
        return state
