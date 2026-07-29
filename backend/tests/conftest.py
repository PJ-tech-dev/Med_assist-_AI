import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import motor.motor_asyncio
from beanie import init_beanie

from app.main import app
from app.core.security import hash_password
from app.models.user import User
from app.models.patient_profile import PatientProfile
from app.models.medical_history import MedicalHistory
from app.models.medication import Medication
from app.models.health_metrics import HealthMetrics
from app.models.medical_report import MedicalReport, ReportAnalysisResult
from app.models.order import MedicineOrder
from app.models.chat_session import ChatSession, AgentExecutionLog


TEST_MONGODB_URL = "mongodb://localhost:27017"
TEST_DB_NAME = "medassist_test"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    client = motor.motor_asyncio.AsyncIOMotorClient(TEST_MONGODB_URL)
    db = client[TEST_DB_NAME]
    
    await init_beanie(
        database=db,
        document_models=[
            User, PatientProfile, MedicalHistory, Medication, HealthMetrics,
            MedicalReport, ReportAnalysisResult, MedicineOrder, ChatSession, AgentExecutionLog
        ]
    )
    yield
    # Cleanup after all tests
    await client.drop_database(TEST_DB_NAME)


@pytest_asyncio.fixture(autouse=True)
async def clear_collections():
    """Clear all collections before each test"""
    models = [
        User, PatientProfile, MedicalHistory, Medication, HealthMetrics,
        MedicalReport, ReportAnalysisResult, MedicineOrder, ChatSession, AgentExecutionLog
    ]
    for model in models:
        await model.delete_all()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """Return JWT auth headers, creating the test user only if it does not exist."""
    user = await User.find_one(User.email == "test@medassist.com")
    if not user:
        user = User(
            email="test@medassist.com",
            full_name="Test User",
            hashed_password=hash_password("TestPass123!"),
            is_active=True,
        )
        await user.insert()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@medassist.com", "password": "TestPass123!"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}