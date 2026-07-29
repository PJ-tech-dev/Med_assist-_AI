import pytest
from httpx import AsyncClient


# ------------------------------------------------------------------ #
#  POST /api/v1/chat                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/chat", json={"message": "hello"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_basic_message(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/chat",
        json={"message": "I have a headache"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "final_response" in data
    assert data["final_response"] != ""
    assert isinstance(data["detected_intents"], list)
    assert isinstance(data["selected_agents"], list)
    assert isinstance(data["agent_outputs"], list)
    assert data["total_execution_ms"] > 0


@pytest.mark.asyncio
async def test_chat_creates_session(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/chat",
        json={"message": "check my blood pressure"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    assert session_id is not None


@pytest.mark.asyncio
async def test_chat_continues_existing_session(client: AsyncClient, auth_headers: dict):
    # First message — creates session
    resp1 = await client.post(
        "/api/v1/chat",
        json={"message": "I have a fever"},
        headers=auth_headers,
    )
    session_id = resp1.json()["session_id"]

    # Second message — continues same session
    resp2 = await client.post(
        "/api/v1/chat",
        json={"message": "What medicine should I take?", "session_id": session_id},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_chat_emergency_intent(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/chat",
        json={"message": "I have severe chest pain and can't breathe"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "emergency_triage" in data["detected_intents"]
    assert "EmergencyTriageAgent" in data["selected_agents"]


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/chat",
        json={"message": "   "},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_agent_outputs_structure(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/chat",
        json={"message": "Is paracetamol safe to take?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    for output in resp.json()["agent_outputs"]:
        assert "agent_name" in output
        assert "response" in output
        assert "confidence" in output
        assert "execution_time_ms" in output


# ------------------------------------------------------------------ #
#  GET /api/v1/chat/sessions                                           #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, auth_headers: dict):
    # Create a session first
    await client.post(
        "/api/v1/chat",
        json={"message": "hello"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/chat/sessions", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ------------------------------------------------------------------ #
#  DELETE /api/v1/chat/sessions/{id}                                   #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_close_session(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/chat",
        json={"message": "hello"},
        headers=auth_headers,
    )
    session_id = create_resp.json()["session_id"]

    del_resp = await client.delete(
        f"/api/v1/chat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204
