"""
Unit tests for Medicine Orders FastAPI Endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_create_and_list_medicine_order():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create order
        payload = {
            "patient_id": "test-patient-001",
            "pharmacy_name": "Apollo Pharmacy 24/7",
            "pharmacy_address": "124 Healthcare Avenue",
            "medicines": [
                {"name": "Paracetamol 500mg", "quantity": 2, "price": 5.0},
                {"name": "ORS Hydration Pack", "quantity": 1, "price": 3.0}
            ],
            "delivery_address": "100 Main Street",
            "total_amount": 13.0
        }

        res = await client.post("/api/v1/orders", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["pharmacy_name"] == "Apollo Pharmacy 24/7"
        assert data["total_amount"] == 13.0
        assert data["status"] == "PLACED"
        assert "ORD-" in data["tracking_number"]
        order_id = data["id"]

        # 2. Get order by ID
        get_res = await client.get(f"/api/v1/orders/{order_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["id"] == order_id
        assert len(get_data["medicines"]) == 2

        # 3. Update order status
        patch_res = await client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "OUT_FOR_DELIVERY"})
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "OUT_FOR_DELIVERY"

        # 4. List orders
        list_res = await client.get("/api/v1/orders?patient_id=test-patient-001")
        assert list_res.status_code == 200
        orders_list = list_res.json()
        assert len(orders_list) >= 1
        assert any(o["id"] == order_id for o in orders_list)
