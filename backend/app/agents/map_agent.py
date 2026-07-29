"""
MedAssist AI — Map Agent
========================
Primary:  Google Maps Platform APIs (Geocoding, Places Nearby, Distance Matrix)
Fallback: OpenStreetMap Overpass API (free, no key needed)

To enable Google Maps:
  Set GOOGLE_MAPS_API_KEY in backend/.env
  (console.cloud.google.com -> APIs & Services -> Credentials)
  Enable: Places API, Geocoding API, Distance Matrix API
"""

import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.settings import settings

logger = logging.getLogger("map_agent")

# ── Google Maps Platform base URLs ─────────────────────────────────────────
GMAPS_GEOCODE_URL    = "https://maps.googleapis.com/maps/api/geocode/json"
GMAPS_PLACES_URL     = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
GMAPS_DETAILS_URL    = "https://maps.googleapis.com/maps/api/place/details/json"
GMAPS_DISTANCE_URL   = "https://maps.googleapis.com/maps/api/distancematrix/json"

# ── OpenStreetMap fallback URLs ─────────────────────────────────────────────
OSM_NOMINATIM_URL    = "https://nominatim.openstreetmap.org/reverse"
OSM_OVERPASS_URL     = "https://overpass-api.de/api/interpreter"

HEADERS = {"User-Agent": "MedAssistAI-Backend/2.0"}


# ── Helpers ─────────────────────────────────────────────────────────────────

def calc_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km, rounded to 1 decimal."""
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def _gmaps_directions_url(dest_lat: float, dest_lng: float) -> str:
    return (
        f"https://www.google.com/maps/dir/?api=1"
        f"&destination={dest_lat},{dest_lng}&travelmode=driving"
    )


def _open_hours_to_status(opening_hours: Optional[Dict]) -> str:
    if not opening_hours:
        return "Hours unknown"
    return "Open Now" if opening_hours.get("open_now") else "Closed"


# ── MapAgent class ──────────────────────────────────────────────────────────

class MapAgent:
    def __init__(self):
        self.gmaps_key = settings.google_maps_api_key or ""
        self.use_gmaps  = bool(self.gmaps_key)

        # Gemini LLM for AI-assisted pharmacy generation fallback
        self.gemini_key = settings.gemini_maps_api_key or settings.google_api_key or ""
        self.llm = None
        if self.gemini_key:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=settings.gemini_model,
                    google_api_key=self.gemini_key,
                    temperature=0.0,
                    max_retries=0,
                )
            except Exception as e:
                logger.warning("Gemini LLM init failed: %s", e)

        if self.use_gmaps:
            logger.info("MapAgent: Google Maps Platform ENABLED (Places, Geocoding, Distance Matrix)")
        elif self.llm:
            logger.info(
                "MapAgent: Gemini AI ENABLED for map intelligence (geocoding, hospital/pharmacy lookup). "
                "Set GOOGLE_MAPS_API_KEY for live real-time data."
            )
        else:
            logger.info(
                "MapAgent: Using OpenStreetMap / Overpass API only (free, no key needed). "
                "Set GEMINI_MAPS_API_KEY or GOOGLE_MAPS_API_KEY in backend/.env for richer results."
            )

    # ── Geocoding ────────────────────────────────────────────────────────────

    async def fetch_real_location(self, lat: float, lng: float) -> Dict[str, Any]:
        """Reverse geocode lat/lng. Chain: Google Geocoding → Nominatim → Gemini LLM."""
        if self.use_gmaps:
            result = await self._geocode_google(lat, lng)
            if result:
                return result

        # Try Nominatim (OpenStreetMap) — always free
        result = await self._geocode_nominatim(lat, lng)
        if result:
            return result

        # Gemini LLM geocoding (uses AI knowledge of world geography)
        if self.llm:
            result = await self._geocode_gemini(lat, lng)
            if result:
                return result

        return {
            "lat": lat, "lng": lng,
            "address": f"GPS Location ({lat:.4f}° N, {lng:.4f}° E)",
            "city": "Local Region", "postcode": "",
        }

    async def _geocode_google(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        params = {"latlng": f"{lat},{lng}", "key": self.gmaps_key}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(GMAPS_GEOCODE_URL, params=params, timeout=8.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "OK" and data.get("results"):
                        result = data["results"][0]
                        components = {c["types"][0]: c["long_name"]
                                      for c in result.get("address_components", [])
                                      if c.get("types")}
                        street    = components.get("route") or components.get("sublocality") or "Current Location"
                        city      = (components.get("locality")
                                     or components.get("administrative_area_level_2")
                                     or components.get("administrative_area_level_1", ""))
                        postcode  = components.get("postal_code", "")
                        address   = result.get("formatted_address", f"{street}, {city}")
                        logger.debug("Google Geocoding OK: %s", address)
                        return {"lat": lat, "lng": lng, "address": address, "city": city, "postcode": postcode}
                    else:
                        logger.warning("Google Geocoding status: %s", data.get("status"))
        except Exception as e:
            logger.warning("Google Geocoding error: %s", e)
        return None

    async def _geocode_nominatim(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        params = {"format": "json", "lat": lat, "lon": lng}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(OSM_NOMINATIM_URL, params=params, headers=HEADERS, timeout=6.0)
                if resp.status_code == 200:
                    data = resp.json()
                    addr     = data.get("address", {})
                    street   = addr.get("road") or addr.get("suburb") or addr.get("neighbourhood") or "Current Location"
                    city     = (addr.get("city") or addr.get("town")
                                or addr.get("county") or addr.get("state") or "")
                    postcode = addr.get("postcode", "")
                    full     = street + (f", {city}" if city else "") + (f" {postcode}" if postcode else "")
                    return {"lat": lat, "lng": lng, "address": full or data.get("display_name", ""), "city": city, "postcode": postcode}
        except Exception as e:
            logger.warning("Nominatim geocoding error: %s", e)
        return None

    async def _geocode_gemini(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        Use Gemini LLM knowledge to identify a location from GPS coordinates.
        Works with GEMINI_MAPS_API_KEY — no Google Maps Platform key required.
        """
        if not self.llm:
            return None
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a geographic AI assistant. Return ONLY valid JSON, no markdown."),
            ("user",
             f"GPS coordinates: Latitude {lat:.6f}, Longitude {lng:.6f}.\n"
             "Identify the most likely street address, neighbourhood, city, and postal code for these coordinates.\n"
             'Return ONLY this JSON: {{"address": "street or area name", "city": "city name", "postcode": "postal code or empty string"}}'),
        ])
        try:
            response = await (prompt | self.llm).ainvoke({})
            content = response.content.strip().replace("```json", "").replace("```", "").strip()
            start, end = content.find("{"), content.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(content[start:end + 1])
                if data.get("city"):
                    logger.debug("Gemini geocoding OK: %s", data)
                    return {
                        "lat": lat, "lng": lng,
                        "address": data.get("address", f"{lat:.4f}°N {lng:.4f}°E"),
                        "city": data["city"],
                        "postcode": data.get("postcode", ""),
                    }
        except Exception as e:
            logger.warning("Gemini geocoding error: %s", e)
        return None

    # ── Places Nearby (Hospitals & Pharmacies) ────────────────────────────────

    async def _google_places_nearby(
        self, lat: float, lng: float, radius_m: int, place_type: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Call Google Maps Places Nearby Search.
        Returns raw Google results with name, vicinity, geometry, rating, opening_hours.
        """
        if not self.use_gmaps:
            return []
        params = {
            "location": f"{lat},{lng}",
            "radius": radius_m,
            "type": place_type,
            "key": self.gmaps_key,
        }
        results = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(GMAPS_PLACES_URL, params=params, timeout=12.0)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status == "OK":
                        results = data.get("results", [])[:limit]
                        logger.info("Google Places (%s): %d results", place_type, len(results))
                    elif status == "ZERO_RESULTS":
                        logger.info("Google Places: no %s found within %dm", place_type, radius_m)
                    else:
                        logger.warning("Google Places status: %s", status)
        except Exception as e:
            logger.warning("Google Places Nearby error: %s", e)
        return results

    async def _google_place_phone(self, place_id: str) -> str:
        """Fetch phone number via Place Details API."""
        if not self.use_gmaps or not place_id:
            return ""
        params = {"place_id": place_id, "fields": "formatted_phone_number", "key": self.gmaps_key}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(GMAPS_DETAILS_URL, params=params, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("result", {}).get("formatted_phone_number", "")
        except Exception:
            pass
        return ""

    # ── Distance Matrix (real road travel time) ─────────────────────────────

    async def get_travel_time(
        self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
    ) -> str:
        """
        Get real driving travel time using Google Distance Matrix API.
        Falls back to estimated time from Haversine distance.
        """
        if self.use_gmaps:
            try:
                params = {
                    "origins": f"{origin_lat},{origin_lng}",
                    "destinations": f"{dest_lat},{dest_lng}",
                    "mode": "driving",
                    "key": self.gmaps_key,
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.get(GMAPS_DISTANCE_URL, params=params, timeout=8.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        element = (data.get("rows") or [{}])[0].get("elements", [{}])[0]
                        if element.get("status") == "OK":
                            return element["duration"]["text"]  # e.g. "12 mins"
                        logger.warning("Distance Matrix element status: %s", element.get("status"))
            except Exception as e:
                logger.warning("Distance Matrix error: %s", e)

        # Fallback: estimate from Haversine km
        km = calc_distance_km(origin_lat, origin_lng, dest_lat, dest_lng)
        if km < 1:   return "5-10 mins"
        if km < 3:   return "10-15 mins"
        if km < 7:   return "15-25 mins"
        if km < 15:  return "25-40 mins"
        return "40+ mins"

    # ── Hospitals ────────────────────────────────────────────────────────────

    async def fetch_nearest_hospitals(
        self, lat: float, lng: float, radius_m: int = 5000, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find nearest hospitals.
        Chain: Google Maps Places → Gemini AI → Overpass → fallback URL.
        Gemini works with GEMINI_MAPS_API_KEY — no Google Maps Platform key required.
        """
        hospitals: List[Dict[str, Any]] = []

        # ── Attempt 1: Google Maps Places API ──────────────────────────────
        if self.use_gmaps:
            raw = await self._google_places_nearby(lat, lng, radius_m, "hospital", limit)
            if not raw:
                # Also try clinic type for more results
                raw += await self._google_places_nearby(lat, lng, radius_m, "clinic", limit)

            for place in raw[:limit]:
                geo  = place.get("geometry", {}).get("location", {})
                h_lat, h_lng = geo.get("lat"), geo.get("lng")
                if not h_lat or not h_lng:
                    continue
                dist_km = calc_distance_km(lat, lng, h_lat, h_lng)
                travel  = await self.get_travel_time(lat, lng, h_lat, h_lng)
                hospitals.append({
                    "id":             place.get("place_id", ""),
                    "name":           place.get("name", "Hospital"),
                    "address":        place.get("vicinity", "Address not listed"),
                    "distanceKm":     dist_km,
                    "distance":       f"{dist_km} km away",
                    "travelTime":     travel,
                    "lat":            h_lat,
                    "lng":            h_lng,
                    "rating":         str(place.get("rating", "")) + " ★" if place.get("rating") else "",
                    "status":         _open_hours_to_status(place.get("opening_hours")),
                    "phone":          "",  # requires extra Details call; left for front-end if needed
                    "emergency":      "yes",
                    "amenity":        place.get("types", ["hospital"])[0],
                    "directions_url": _gmaps_directions_url(h_lat, h_lng),
                    "source":         "google",
                })

            if hospitals:
                hospitals.sort(key=lambda x: x["distanceKm"])
                logger.info("Hospitals from Google: %d", len(hospitals))
                return hospitals[:limit]

        # ── Attempt 2: Gemini AI (works with GEMINI_MAPS_API_KEY) ───────────
        if self.llm:
            logger.info("Trying Gemini AI for hospital lookup")
            hospitals = await self.fetch_hospitals_gemini(lat, lng)
            if hospitals:
                logger.info("Hospitals from Gemini: %d", len(hospitals))
                return hospitals[:limit]

        # ── Attempt 3: Overpass API (OpenStreetMap) fallback ────────────────
        logger.info("Falling back to Overpass API for hospitals")
        hospitals = await self._overpass_hospitals(lat, lng, radius_m, limit)

        if not hospitals:
            # ── Attempt 4: Google Maps search link ──────────────────────────
            hospitals = [{
                "id":             "fallback-gmaps",
                "name":           "Find Nearest Hospital",
                "address":        "Tap 'Get Directions' to open Google Maps hospital search",
                "distanceKm":     0,
                "distance":       "Tap for directions",
                "travelTime":     "Unknown",
                "lat":            lat,
                "lng":            lng,
                "rating":         "",
                "status":         "Unknown",
                "phone":          "",
                "emergency":      "yes",
                "amenity":        "hospital",
                "directions_url": f"https://www.google.com/maps/search/hospital+emergency+near+me/@{lat},{lng},14z",
                "source":         "fallback",
            }]

        return hospitals

    async def _overpass_hospitals(
        self, lat: float, lng: float, radius_m: int, limit: int
    ) -> List[Dict[str, Any]]:
        query = (
            f"[out:json][timeout:15];"
            f"("
            f"  node[\"amenity\"=\"hospital\"](around:{radius_m},{lat},{lng});"
            f"  way[\"amenity\"=\"hospital\"](around:{radius_m},{lat},{lng});"
            f"  node[\"amenity\"=\"clinic\"](around:{radius_m},{lat},{lng});"
            f");"
            f"out center;"
        )
        hospitals = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(OSM_OVERPASS_URL, content=query, headers=HEADERS, timeout=20.0)
                if resp.status_code == 200:
                    for elem in resp.json().get("elements", []):
                        h_lat = elem.get("lat") or (elem.get("center") or {}).get("lat")
                        h_lng = elem.get("lon") or (elem.get("center") or {}).get("lon")
                        if not h_lat or not h_lng:
                            continue
                        tags = elem.get("tags", {})
                        name = tags.get("name") or tags.get("name:en") or "Hospital"
                        address_parts = [p for p in [
                            tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:city")
                        ] if p]
                        address  = ", ".join(address_parts) or "Address not listed"
                        dist_km  = calc_distance_km(lat, lng, h_lat, h_lng)
                        hospitals.append({
                            "id":             str(elem.get("id", "")),
                            "name":           name,
                            "address":        address,
                            "distanceKm":     dist_km,
                            "distance":       f"{dist_km} km away",
                            "travelTime":     await self.get_travel_time(lat, lng, h_lat, h_lng),
                            "lat":            h_lat,
                            "lng":            h_lng,
                            "rating":         "",
                            "status":         "Unknown",
                            "phone":          tags.get("phone") or tags.get("contact:phone") or "",
                            "emergency":      tags.get("emergency") or "yes",
                            "amenity":        tags.get("amenity", "hospital"),
                            "directions_url": _gmaps_directions_url(h_lat, h_lng),
                            "source":         "openstreetmap",
                        })
        except Exception as e:
            logger.error("Overpass hospital fetch error: %s", e)

        hospitals.sort(key=lambda x: x["distanceKm"])
        return hospitals[:limit]

    # ── Pharmacies ───────────────────────────────────────────────────────────

    async def fetch_pharmacies(
        self, lat: float, lng: float, radius_m: int = 3000, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find nearby pharmacies. Uses Google Places API first, then Gemini LLM,
        then static fallback.
        """
        # ── Attempt 1: Google Maps Places ──────────────────────────────────
        if self.use_gmaps:
            raw = await self._google_places_nearby(lat, lng, radius_m, "pharmacy", limit)
            if raw:
                pharmacies = []
                for place in raw[:limit]:
                    geo   = place.get("geometry", {}).get("location", {})
                    p_lat = geo.get("lat", lat)
                    p_lng = geo.get("lng", lng)
                    dist_km = calc_distance_km(lat, lng, p_lat, p_lng)
                    travel  = await self.get_travel_time(lat, lng, p_lat, p_lng)
                    rating  = place.get("rating")
                    pharmacies.append({
                        "id":           place.get("place_id", f"gmaps-{len(pharmacies)}"),
                        "name":         place.get("name", "Pharmacy"),
                        "address":      place.get("vicinity", ""),
                        "distance":     f"{dist_km} km away",
                        "distanceKm":   dist_km,
                        "rating":       f"{rating} ★" if rating else "Not rated",
                        "status":       _open_hours_to_status(place.get("opening_hours")),
                        "deliveryTime": travel,
                        "lat":          p_lat,
                        "lng":          p_lng,
                        "source":       "google",
                    })
                if pharmacies:
                    logger.info("Pharmacies from Google: %d", len(pharmacies))
                    return sorted(pharmacies, key=lambda x: x["distanceKm"])

        # ── Attempt 2: Gemini LLM (AI-assisted) ────────────────────────────
        if self.llm:
            location_str = f"coordinates ({lat:.4f}, {lng:.4f})"
            try:
                pharmacies = await self.fetch_pharmacies_gemini(lat, lng, location_str)
                if pharmacies:
                    logger.info("Pharmacies from Gemini: %d", len(pharmacies))
                    return pharmacies
            except Exception as e:
                logger.warning("Gemini pharmacy fallback error: %s", e)

        # ── Attempt 3: Overpass ─────────────────────────────────────────────
        pharmacies = await self._overpass_pharmacies(lat, lng, radius_m, limit)
        if pharmacies:
            return pharmacies

        # ── Attempt 4: Static fallback ──────────────────────────────────────
        return [{
            "id": "fallback-pharmacy",
            "name": "Nearest Medical Shop",
            "address": "Tap below to search Google Maps",
            "distance": "Tap for directions",
            "distanceKm": 0,
            "rating": "Not rated",
            "status": "Unknown",
            "deliveryTime": "Unknown",
            "lat": lat, "lng": lng,
            "source": "fallback",
        }]

    async def _overpass_pharmacies(
        self, lat: float, lng: float, radius_m: int, limit: int
    ) -> List[Dict[str, Any]]:
        query = (
            f"[out:json][timeout:12];"
            f"node[\"amenity\"=\"pharmacy\"](around:{radius_m},{lat},{lng});"
            f"out center {limit};"
        )
        pharmacies = []
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(OSM_OVERPASS_URL, content=query, headers=HEADERS, timeout=15.0)
                if resp.status_code == 200:
                    for elem in resp.json().get("elements", []):
                        p_lat = elem.get("lat", lat)
                        p_lng = elem.get("lon", lng)
                        tags  = elem.get("tags", {})
                        name  = tags.get("name") or "Pharmacy"
                        dist_km = calc_distance_km(lat, lng, p_lat, p_lng)
                        pharmacies.append({
                            "id":           str(elem.get("id", "")),
                            "name":         name,
                            "address":      tags.get("addr:street") or "Address not listed",
                            "distance":     f"{dist_km} km away",
                            "distanceKm":   dist_km,
                            "rating":       "Not rated",
                            "status":       "Open Now",
                            "deliveryTime": await self.get_travel_time(lat, lng, p_lat, p_lng),
                            "lat":          p_lat,
                            "lng":          p_lng,
                            "source":       "openstreetmap",
                        })
        except Exception as e:
            logger.warning("Overpass pharmacy fetch error: %s", e)
        return sorted(pharmacies, key=lambda x: x["distanceKm"])[:limit]

    async def fetch_hospitals_gemini(
        self, lat: float, lng: float
    ) -> List[Dict[str, Any]]:
        """Use Gemini LLM to find hospitals based on geographic knowledge."""
        if not self.llm:
            return []
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert geographic AI. Return ONLY a raw JSON array of 3-5 real "
             "hospitals or major clinics near the user's location. No markdown. Raw array only."),
            ("user",
             f"User Location: (Lat: {lat:.4f}, Lng: {lng:.4f}).\n\n"
             "Generate the JSON array where each object has these exact keys:\n"
             "- id (string)\n- name (string)\n- address (string)\n"
             "- distance (string, e.g., '1.2 km away')\n- distanceKm (float)\n"
             "- travelTime (string, e.g., '15 mins')\n"
             "- lat (float)\n- lng (float)\n"
             "- phone (string or empty)\n- rating (string, e.g., '4.5 ★')\n"
             "- status (string, e.g., 'Open 24/7')\n"
             "- emergency ('yes' or 'no')\n- amenity (string, e.g., 'hospital')"),
        ])
        chain = prompt | self.llm
        try:
            response = await chain.ainvoke({})
            content = response.content.strip()
            # Strip markdown if any
            for tag in ("```json", "```"):
                content = content.replace(tag, "")
            start = content.find("[")
            end   = content.rfind("]")
            if start != -1 and end != -1:
                hospitals = json.loads(content[start:end + 1])
                if isinstance(hospitals, list):
                    hospitals.sort(key=lambda x: x.get("distanceKm", 0))
                    for h in hospitals:
                        h["source"] = "gemini"
                        if "directions_url" not in h:
                            h["directions_url"] = _gmaps_directions_url(h.get("lat", lat), h.get("lng", lng))
                    return hospitals
        except Exception as e:
            logger.error("Gemini hospital LLM error: %s", e)
        return []

    # ── Gemini LLM AI pharmacy (kept as fallback) ────────────────────────────

    async def fetch_pharmacies_gemini(
        self, lat: float, lng: float, location_str: str
    ) -> List[Dict[str, Any]]:
        if not self.llm:
            return []
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert geographic AI. Return ONLY a raw JSON array of 3-5 real "
             "medical shops/pharmacies near the user's location. No markdown. Raw array only."),
            ("user",
             f"User Location: {location_str} (Lat: {lat}, Lng: {lng}).\n\n"
             "Generate the JSON array where each object has these exact keys:\n"
             "- id (string)\n- name (string)\n- address (string)\n"
             "- distance (string, e.g., '1.2 km away')\n- distanceKm (float)\n"
             "- rating (string, e.g., '4.5 \u2605')\n- status ('Open Now' or 'Open 24/7')\n"
             "- deliveryTime (string, e.g., '15-20 mins')\n"
             "- lat (float)\n- lng (float)"),
        ])
        chain = prompt | self.llm
        try:
            response = await chain.ainvoke({})
            content = response.content.strip()
            # Strip markdown if any
            for tag in ("```json", "```"):
                content = content.replace(tag, "")
            start = content.find("[")
            end   = content.rfind("]")
            if start != -1 and end != -1:
                shops = json.loads(content[start:end + 1])
                if isinstance(shops, list):
                    shops.sort(key=lambda x: x.get("distanceKm", 0))
                    for s in shops:
                        s["source"] = "gemini"
                    return shops
        except Exception as e:
            logger.error("Gemini pharmacy LLM error: %s", e)
        return []

    # ── Emergency combined fetch ─────────────────────────────────────────────

    async def fetch_emergency_data(self, lat: float, lng: float) -> Dict[str, Any]:
        """Fetch location + nearest hospitals in parallel for emergency mode."""
        location_data, hospitals = await asyncio.gather(
            self.fetch_real_location(lat, lng),
            self.fetch_nearest_hospitals(lat, lng),
        )
        return {"location": location_data, "hospitals": hospitals}

    # ── Combined location query ──────────────────────────────────────────────

    async def process_location_query(
        self, lat: float, lng: float, query: Optional[str] = None
    ) -> Dict[str, Any]:
        location_data, pharmacies = await asyncio.gather(
            self.fetch_real_location(lat, lng),
            self.fetch_pharmacies(lat, lng),
        )
        return {
            "location": location_data,
            "pharmacies": pharmacies,
            "query":    query or "",
            "source":   "google" if self.use_gmaps else "openstreetmap",
        }
