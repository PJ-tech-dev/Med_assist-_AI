import json
import random
from typing import List, Dict, Any, Optional
from pymongo import DESCENDING

from app.models.order import MedicineOrder
from app.utils.logger import get_logger

logger = get_logger("agent.pharmacy_order.tools")

async def fetch_order_history(patient_id: str) -> List[Dict[str, Any]]:
    """Fetch past medicine orders from MongoDB for a specific patient."""
    logger.info("Fetching order history for patient_id=%s", patient_id)
    
    if not patient_id:
        return []

    # Query MongoDB collection
    orders = await MedicineOrder.find(MedicineOrder.patient_id == patient_id).sort(
        [("created_at", DESCENDING)]
    ).to_list()
    
    result = []
    for order in orders:
        items = json.loads(order.medicines_json) if order.medicines_json else []
        result.append({
            "tracking_number": order.tracking_number,
            "pharmacy": order.pharmacy_name,
            "total_amount": float(order.total_amount),
            "status": order.status,
            "items": [item.get("name") for item in items],
            "date": order.created_at.strftime("%Y-%m-%d %H:%M") if order.created_at else "Unknown",
        })
        
    return result


async def create_medicine_order_from_chat(
    patient_id: str, 
    medicines: List[str], 
    delivery_address: str, 
    pharmacy_name: Optional[str] = "Auto-Assigned Pharmacy"
) -> Dict[str, Any]:
    """Create a new medicine order in MongoDB via chat."""
    logger.info("Creating chat order for patient_id=%s | items=%s", patient_id, medicines)
    
    if not patient_id:
        return {"error": "Missing patient ID to place an order."}

    tracking_no = f"ORD-{random.randint(100000, 999999)}"
    
    # Create simple items dict since we don't have price via chat
    items_list = [{"name": med, "quantity": 1, "price": 0.0} for med in medicines]
    
    order_obj = MedicineOrder(
        patient_id=patient_id,
        pharmacy_name=pharmacy_name or "MedAssist Auto-Pharmacy",
        pharmacy_address="Assigned via AI",
        medicines_json=json.dumps(items_list),
        total_amount=0.0,
        delivery_address=delivery_address or "User Default Address",
        status="PLACED",
        tracking_number=tracking_no,
        estimated_delivery="15-30 mins"
    )

    await order_obj.insert()
    logger.info("Created new order from chat: %s", tracking_no)
    
    return {
        "success": True,
        "tracking_number": tracking_no,
        "pharmacy": order_obj.pharmacy_name,
        "status": order_obj.status,
    }
