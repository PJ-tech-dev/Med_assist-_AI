from typing import Optional, Dict, List, Any
from beanie import Document, Indexed, PydanticObjectId
from app.models.base import TimestampMixin

class MedicineOrder(Document, TimestampMixin):
    user_id: Indexed(PydanticObjectId)
    patient_id: Optional[Indexed(str)] = None
    pharmacy_name: str
    pharmacy_address: str
    medicines_json: str  # JSON string or could be changed to List[Dict] if preferred
    total_amount: float = 0.0
    delivery_address: str
    status: Indexed(str) = "PLACED"
    tracking_number: Indexed(str, unique=True)
    estimated_delivery: str = "15-20 mins"

    class Settings:
        name = "medicine_orders"
