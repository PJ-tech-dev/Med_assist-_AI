import motor.motor_asyncio
from beanie import init_beanie
from app.core.settings import settings
from app.models import (
    User,
    PatientProfile,
    MedicalHistory,
    Medication,
    HealthMetrics,
    MedicalReport,
    ReportAnalysisResult,
    MedicineOrder,
    ChatSession,
    AgentExecutionLog
)

async def init_db():
    """Initialize MongoDB connection and Beanie ODM."""
    client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
    
    # Use database 'medassist' from connection string or default to medassist
    db = client.get_default_database("medassist")
    
    await init_beanie(
        database=db,
        document_models=[
            User,
            PatientProfile,
            MedicalHistory,
            Medication,
            HealthMetrics,
            MedicalReport,
            ReportAnalysisResult,
            MedicineOrder,
            ChatSession,
            AgentExecutionLog
        ]
    )

# Note: get_db is no longer needed as Beanie uses class-level database contexts.
# However, to avoid breaking fast API dependencies instantly across all routes, 
# we can yield a dummy session or remove it entirely. We will remove it and update dependencies.
