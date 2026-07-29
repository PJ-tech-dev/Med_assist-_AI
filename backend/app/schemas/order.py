from beanie import PydanticObjectId
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class OrderItemSchema(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Paracetamol 500mg"})
    quantity: int = Field(default=1, json_schema_extra={"example": 1})
    price: float = Field(default=5.0, json_schema_extra={"example": 5.0})


class OrderCreateRequest(BaseModel):
    patient_id: Optional[str] = Field(None, json_schema_extra={"example": "patient-123"})
    pharmacy_name: str = Field(..., json_schema_extra={"example": "Apollo Pharmacy 24/7"})
    pharmacy_address: str = Field(..., json_schema_extra={"example": "124 Healthcare Avenue"})
    medicines: List[OrderItemSchema] = Field(..., min_length=1)
    delivery_address: str = Field(..., json_schema_extra={"example": "100 Main Street"})
    total_amount: Optional[float] = Field(0.0, json_schema_extra={"example": 15.0})


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "OUT_FOR_DELIVERY"})


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    tracking_number: str
    patient_id: Optional[str] = None
    pharmacy_name: str
    pharmacy_address: str
    medicines: List[OrderItemSchema]
    total_amount: float
    delivery_address: str
    status: str
    estimated_delivery: str
    created_at: datetime
