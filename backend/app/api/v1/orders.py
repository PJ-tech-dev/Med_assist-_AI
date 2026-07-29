import json
import random
from typing import List, Optional
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, status
from pymongo import DESCENDING

from app.models.order import MedicineOrder
from app.schemas.order import (
    OrderCreateRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
    OrderItemSchema,
)
from app.utils.logger import get_logger

logger = get_logger("api.orders")

router = APIRouter(prefix="/orders", tags=["medicine_orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_medicine_order(
    payload: OrderCreateRequest,
):
    """
    Create a new medicine order with a nearby pharmacy/medical shop.
    """
    if not payload.medicines:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one medicine is required")

    logger.info("CREATING MEDICINE ORDER | pharmacy=%s | items_count=%d", payload.pharmacy_name, len(payload.medicines))

    tracking_no = f"ORD-{random.randint(100000, 999999)}"
    medicines_str = json.dumps([item.model_dump() for item in payload.medicines])

    # Recalculate total server-side from actual item prices × quantities
    calculated_total = sum(item.price * item.quantity for item in payload.medicines)
    if calculated_total <= 0:
        # Fallback: accept client-provided total if items have no prices
        calculated_total = payload.total_amount or len(payload.medicines) * 45.0

    # Estimate delivery time dynamically based on number of items
    # (distance data not available server-side without geocoding, so approximate)
    item_count = len(payload.medicines)
    if item_count <= 2:
        delivery_estimate = "10-15 mins"
    elif item_count <= 5:
        delivery_estimate = "15-25 mins"
    else:
        delivery_estimate = "25-40 mins"

    # If delivery_address contains a known km hint, refine estimate
    if "km" in (payload.delivery_address or "").lower():
        delivery_estimate = "20-35 mins"

    order_obj = MedicineOrder(
        patient_id=payload.patient_id,
        pharmacy_name=payload.pharmacy_name,
        pharmacy_address=payload.pharmacy_address,
        medicines_json=medicines_str,
        total_amount=calculated_total,
        delivery_address=payload.delivery_address,
        status="PLACED",
        tracking_number=tracking_no,
        estimated_delivery=delivery_estimate,
    )

    await order_obj.insert()

    logger.info("MEDICINE ORDER PLACED | order_id=%s | tracking=%s | total=%.2f | delivery=%s",
                order_obj.id, tracking_no, calculated_total, delivery_estimate)

    items_list = [OrderItemSchema(**item) for item in json.loads(order_obj.medicines_json)]

    return OrderResponse(
        id=order_obj.id,
        tracking_number=order_obj.tracking_number,
        patient_id=order_obj.patient_id,
        pharmacy_name=order_obj.pharmacy_name,
        pharmacy_address=order_obj.pharmacy_address,
        medicines=items_list,
        total_amount=order_obj.total_amount,
        delivery_address=order_obj.delivery_address,
        status=order_obj.status,
        estimated_delivery=order_obj.estimated_delivery,
        created_at=order_obj.created_at,
    )


@router.get("", response_model=List[OrderResponse])
async def list_medicine_orders(
    patient_id: Optional[str] = None,
):
    """
    List medicine orders. Filterable by patient_id.
    """
    query = MedicineOrder.find_all()
    if patient_id:
        query = MedicineOrder.find(MedicineOrder.patient_id == patient_id)

    orders = await query.sort([("created_at", DESCENDING)]).to_list()

    response_list = []
    for order in orders:
        items_list = [OrderItemSchema(**item) for item in json.loads(order.medicines_json)]
        response_list.append(
            OrderResponse(
                id=order.id,
                tracking_number=order.tracking_number,
                patient_id=order.patient_id,
                pharmacy_name=order.pharmacy_name,
                pharmacy_address=order.pharmacy_address,
                medicines=items_list,
                total_amount=order.total_amount,
                delivery_address=order.delivery_address,
                status=order.status,
                estimated_delivery=order.estimated_delivery,
                created_at=order.created_at,
            )
        )

    return response_list


@router.get("/{order_id}", response_model=OrderResponse)
async def get_medicine_order(
    order_id: PydanticObjectId,
):
    """
    Get medicine order details by ID.
    """
    order = await MedicineOrder.find_one(MedicineOrder.id == order_id)

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine order not found")

    items_list = [OrderItemSchema(**item) for item in json.loads(order.medicines_json)]

    return OrderResponse(
        id=order.id,
        tracking_number=order.tracking_number,
        patient_id=order.patient_id,
        pharmacy_name=order.pharmacy_name,
        pharmacy_address=order.pharmacy_address,
        medicines=items_list,
        total_amount=order.total_amount,
        delivery_address=order.delivery_address,
        status=order.status,
        estimated_delivery=order.estimated_delivery,
        created_at=order.created_at,
    )


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: PydanticObjectId,
    payload: OrderStatusUpdateRequest,
):
    """
    Update status of a medicine order (e.g., PHARMACY_CONFIRMED, OUT_FOR_DELIVERY, DELIVERED).
    """
    order = await MedicineOrder.find_one(MedicineOrder.id == order_id)

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine order not found")

    order.status = payload.status
    await order.save()

    logger.info("ORDER STATUS UPDATED | order_id=%s | new_status=%s", order_id, payload.status)

    items_list = [OrderItemSchema(**item) for item in json.loads(order.medicines_json)]

    return OrderResponse(
        id=order.id,
        tracking_number=order.tracking_number,
        patient_id=order.patient_id,
        pharmacy_name=order.pharmacy_name,
        pharmacy_address=order.pharmacy_address,
        medicines=items_list,
        total_amount=order.total_amount,
        delivery_address=order.delivery_address,
        status=order.status,
        estimated_delivery=order.estimated_delivery,
        created_at=order.created_at,
    )
