"""
Maps API Endpoints
==================
All map queries are proxied through the backend so the Google Maps API key
stays server-side and never reaches the browser.

Endpoints:
  POST /maps/fetch        - Location + nearby pharmacies
  POST /maps/hospitals    - Nearest hospitals (emergency)
  GET  /maps/hospitals    - Same, via query params
  POST /maps/pharmacies   - Nearby pharmacies
  GET  /maps/pharmacies   - Same, via query params
  GET  /maps/status       - Reports which map data source is active
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import logging

from app.agents.map_agent import MapAgent
from app.core.settings import settings

logger = logging.getLogger("api.maps")
router = APIRouter(prefix="/maps", tags=["maps"])


# ── Request schemas ──────────────────────────────────────────────────────────

class MapFetchRequest(BaseModel):
    lat: float
    lng: float
    query: Optional[str] = None


class HospitalFetchRequest(BaseModel):
    lat: float
    lng: float
    radius_m: Optional[int] = 5000
    limit: Optional[int] = 5


class PharmacyFetchRequest(BaseModel):
    lat: float
    lng: float
    radius_m: Optional[int] = 3000
    limit: Optional[int] = 5


# ── Helpers ──────────────────────────────────────────────────────────────────

def _agent() -> MapAgent:
    """Create a MapAgent instance (raises 503 if both Gemini and Maps keys missing)."""
    try:
        return MapAgent()
    except Exception as e:
        logger.error("MapAgent init error: %s", e)
        raise HTTPException(status_code=503, detail=f"Map service unavailable: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def map_service_status():
    """
    Returns which map data source is currently active.
    Useful for frontend to display a badge: 'Google Maps' or 'OpenStreetMap'.
    """
    has_gmaps_key = bool(settings.google_maps_api_key)
    return {
        "source": "google" if has_gmaps_key else "openstreetmap",
        "google_maps_enabled": has_gmaps_key,
        "fallback": "openstreetmap",
        "message": (
            "Google Maps Platform active (Places, Geocoding, Distance Matrix)"
            if has_gmaps_key
            else "Using OpenStreetMap / Overpass API (free). Set GOOGLE_MAPS_API_KEY to enable Google Maps."
        ),
    }


@router.post("/fetch")
async def fetch_map_data(request: MapFetchRequest):
    """Location + nearby pharmacies combined query."""
    try:
        agent = _agent()
        result = await agent.process_location_query(request.lat, request.lng, request.query)
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fetch_map_data error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hospitals")
async def fetch_nearest_hospitals(request: HospitalFetchRequest):
    """
    Emergency endpoint — find nearest hospitals.
    Uses Google Places API when GOOGLE_MAPS_API_KEY is set,
    falls back to OpenStreetMap Overpass API automatically.
    Returns hospitals sorted by distance with Google Maps directions URLs.
    """
    try:
        agent = _agent()
        hospitals, location_data = await __import__("asyncio").gather(
            agent.fetch_nearest_hospitals(
                lat=request.lat,
                lng=request.lng,
                radius_m=request.radius_m or 5000,
                limit=request.limit or 5,
            ),
            agent.fetch_real_location(request.lat, request.lng),
        )
        return {
            "status": "success",
            "data": {
                "location": location_data,
                "hospitals": hospitals,
                "count": len(hospitals),
                "source": hospitals[0].get("source", "unknown") if hospitals else "none",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fetch_nearest_hospitals error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hospitals")
async def fetch_nearest_hospitals_get(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(5000),
    limit: int = Query(5),
):
    """GET convenience version of the hospitals endpoint."""
    try:
        agent = _agent()
        import asyncio
        hospitals, location_data = await asyncio.gather(
            agent.fetch_nearest_hospitals(lat, lng, radius_m, limit),
            agent.fetch_real_location(lat, lng),
        )
        return {
            "status": "success",
            "data": {
                "location": location_data,
                "hospitals": hospitals,
                "count": len(hospitals),
                "source": hospitals[0].get("source", "unknown") if hospitals else "none",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fetch_nearest_hospitals_get error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pharmacies")
async def fetch_nearby_pharmacies(request: PharmacyFetchRequest):
    """
    Nearby pharmacies endpoint.
    Uses Google Places API when key is set, else Gemini LLM then Overpass fallback.
    """
    try:
        agent = _agent()
        import asyncio
        pharmacies, location_data = await asyncio.gather(
            agent.fetch_pharmacies(
                lat=request.lat,
                lng=request.lng,
                radius_m=request.radius_m or 3000,
                limit=request.limit or 5,
            ),
            agent.fetch_real_location(request.lat, request.lng),
        )
        return {
            "status": "success",
            "data": {
                "location": location_data,
                "pharmacies": pharmacies,
                "count": len(pharmacies),
                "source": pharmacies[0].get("source", "unknown") if pharmacies else "none",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fetch_nearby_pharmacies error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pharmacies")
async def fetch_nearby_pharmacies_get(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(3000),
    limit: int = Query(5),
):
    """GET convenience version of the pharmacies endpoint."""
    try:
        agent = _agent()
        import asyncio
        pharmacies, location_data = await asyncio.gather(
            agent.fetch_pharmacies(lat, lng, radius_m, limit),
            agent.fetch_real_location(lat, lng),
        )
        return {
            "status": "success",
            "data": {
                "location": location_data,
                "pharmacies": pharmacies,
                "count": len(pharmacies),
                "source": pharmacies[0].get("source", "unknown") if pharmacies else "none",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fetch_nearby_pharmacies_get error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
