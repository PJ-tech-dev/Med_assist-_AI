/**
 * MedAssist AI — Location & Map Utilities
 * ========================================
 * All map data fetches are proxied through the MedAssist backend so the
 * Google Maps API key stays server-side and never reaches the browser.
 *
 * Fallback chain (automatic — no config needed in frontend):
 *   1. Backend /maps/* endpoints  → Google Maps Platform (if GOOGLE_MAPS_API_KEY set)
 *   2. Backend /maps/* endpoints  → Gemini LLM / OpenStreetMap Overpass (auto-fallback)
 *   3. Overpass API direct from browser (if backend is offline)
 *   4. Google Maps search URL     (always works, manual fallback)
 */

import { api } from './api';

// ── Interfaces ───────────────────────────────────────────────────────────────

export interface RealPharmacy {
  id: string;
  name: string;
  address: string;
  distance: string;
  distanceKm: number;
  rating: string;
  status: string;
  deliveryTime: string;
  lat: number;
  lng: number;
  source?: 'google' | 'openstreetmap' | 'gemini' | 'fallback';
}

export interface NearestHospital {
  id: string;
  name: string;
  address: string;
  distance: string;
  distanceKm: number;
  travelTime?: string;
  lat: number;
  lng: number;
  phone?: string;
  rating?: string;
  status?: string;
  emergency?: string;
  amenity?: string;
  directions_url: string;
  source?: 'google' | 'openstreetmap' | 'fallback';
}

export interface UserLocation {
  lat: number;
  lng: number;
  address: string;
  city: string;
  postcode: string;
}

export type MapSource = 'google' | 'openstreetmap' | 'gemini' | 'fallback' | 'unknown';

// ── Helpers ──────────────────────────────────────────────────────────────────

const BACKEND = typeof window !== 'undefined'
  ? (localStorage.getItem('medassist_api_url') || 'http://127.0.0.1:8000/api/v1')
  : 'http://127.0.0.1:8000/api/v1';

/**
 * Calculates distance between two GPS coordinates in km (Haversine formula).
 */
export function calcDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
    Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLon / 2) ** 2;
  return Math.round(6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)) * 10) / 10;
}

// ── Map source status ────────────────────────────────────────────────────────

let _cachedMapSource: MapSource | null = null;

/**
 * Query the backend to find out if Google Maps or OpenStreetMap is active.
 * Result is cached for the session.
 */
export async function getMapSource(): Promise<MapSource> {
  if (_cachedMapSource) return _cachedMapSource;
  try {
    const resp = await fetch(`${BACKEND}/maps/status`, { signal: AbortSignal.timeout(5000) });
    if (resp.ok) {
      const json = await resp.json();
      _cachedMapSource = json.source as MapSource;
      return _cachedMapSource;
    }
  } catch {}
  return 'unknown';
}

// ── Reverse Geocoding ────────────────────────────────────────────────────────

/**
 * Convert GPS coordinates to a human-readable address.
 * Routes through backend (which uses Google Geocoding API or Nominatim).
 */
export async function getRealLocationAddress(lat: number, lng: number): Promise<UserLocation> {
  // ── Attempt 1: Backend /maps/fetch (proxies Google Geocoding / Nominatim) ──
  try {
    const resp = await fetch(`${BACKEND}/maps/fetch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lng }),
      signal: AbortSignal.timeout(10000),
    });
    if (resp.ok) {
      const json = await resp.json();
      const loc = json?.data?.location;
      if (loc?.address) return { lat, lng, address: loc.address, city: loc.city || '', postcode: loc.postcode || '' };
    }
  } catch (err) {
    console.warn('Backend geocoding failed, trying Puter AI:', err);
  }

  // ── Attempt 2: Puter AI (client-side AI reverse geocoding) ─────────────────
  try {
    if (typeof window !== 'undefined' && (window as any).puter?.ai?.chat) {
      const prompt = `Given GPS coordinates Latitude: ${lat}, Longitude: ${lng}, identify the city and street address. Return ONLY valid JSON (no markdown):
{"address": "Street or Neighborhood name", "city": "City name", "postcode": "Postal code"}`;
      const res = await (window as any).puter.ai.chat(prompt);
      let jsonStr = typeof res === 'string' ? res
        : res?.message?.content
          ? (Array.isArray(res.message.content) ? res.message.content.map((c: any) => c.text).join('') : res.message.content)
          : String(res);
      jsonStr = jsonStr.replace(/```json|```/g, '').trim();
      const data = JSON.parse(jsonStr);
      if (data.city) return { lat, lng, address: data.address || `${lat.toFixed(4)}°N ${lng.toFixed(4)}°E`, city: data.city, postcode: data.postcode || '' };
    }
  } catch (err) {
    console.warn('Puter AI geocoding fallback:', err);
  }

  return { lat, lng, address: `GPS Location (${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E)`, city: 'Local Region', postcode: '' };
}

// ── Pharmacies ───────────────────────────────────────────────────────────────

/**
 * Fetch nearby pharmacies.
 * Routes through backend (Google Places API or Gemini/Overpass fallback).
 */
export async function fetchRealNearbyPharmacies(lat: number, lng: number): Promise<RealPharmacy[]> {
  // ── Attempt 1: Backend /maps/pharmacies ────────────────────────────────────
  try {
    const resp = await fetch(`${BACKEND}/maps/pharmacies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lng, radius_m: 3000, limit: 5 }),
      signal: AbortSignal.timeout(15000),
    });
    if (resp.ok) {
      const json = await resp.json();
      const pharmacies: RealPharmacy[] = json?.data?.pharmacies ?? [];
      if (pharmacies.length > 0) return pharmacies;
    }
  } catch (err) {
    console.warn('Backend pharmacy fetch failed, trying Puter AI:', err);
  }

  // ── Attempt 2: Puter AI ─────────────────────────────────────────────────────
  try {
    if (typeof window !== 'undefined' && (window as any).puter?.ai?.chat) {
      const prompt = `Given GPS coordinates Latitude: ${lat}, Longitude: ${lng}, suggest 3 real nearby pharmacies/medical shops. Return ONLY a raw JSON array (no markdown):
[{"id":"1","name":"Pharmacy Name","address":"Short Address","distance":"0.5 km away","distanceKm":0.5,"rating":"4.5 ★","status":"Open Now","deliveryTime":"15-20 mins"}]`;
      const res = await (window as any).puter.ai.chat(prompt);
      let jsonStr = typeof res === 'string' ? res
        : res?.message?.content
          ? (Array.isArray(res.message.content) ? res.message.content.map((c: any) => c.text).join('') : res.message.content)
          : String(res);
      jsonStr = jsonStr.replace(/```json|```/g, '').trim();
      const start = jsonStr.indexOf('[');
      const end = jsonStr.lastIndexOf(']');
      if (start !== -1 && end !== -1) {
        const pharmacies = JSON.parse(jsonStr.slice(start, end + 1));
        if (Array.isArray(pharmacies) && pharmacies.length > 0) {
          return pharmacies.map((p: any) => ({
            ...p,
            lat: lat + (Math.random() * 0.01 - 0.005),
            lng: lng + (Math.random() * 0.01 - 0.005),
            source: 'gemini' as const,
          }));
        }
      }
    }
  } catch (err) {
    console.warn('Puter AI pharmacy fallback:', err);
  }

  // ── Static fallback ─────────────────────────────────────────────────────────
  return [{
    id: 'fallback-pharmacy',
    name: 'Nearest Medical Shop',
    address: 'Enable GPS & internet to find real pharmacies',
    distance: 'Unknown',
    distanceKm: 0,
    rating: 'Not rated',
    status: 'Open Now',
    deliveryTime: 'Unknown',
    lat, lng,
    source: 'fallback',
  }];
}

// ── Hospitals (Emergency) ────────────────────────────────────────────────────

/**
 * Fetch nearest hospitals for emergency situations.
 *
 * Fallback chain:
 *   1. Backend /maps/hospitals (Google Places or Overpass — server-side)
 *   2. Overpass API direct from browser
 *   3. Google Maps search link
 */
export async function fetchNearestHospitals(
  lat: number,
  lng: number,
  radiusM: number = 5000
): Promise<NearestHospital[]> {
  // ── Attempt 1: Backend endpoint ──────────────────────────────────────────
  try {
    const resp = await fetch(`${BACKEND}/maps/hospitals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lng, radius_m: radiusM, limit: 5 }),
      signal: AbortSignal.timeout(15000),
    });
    if (resp.ok) {
      const json = await resp.json();
      const hospitals: NearestHospital[] = json?.data?.hospitals ?? [];
      if (hospitals.length > 0) return hospitals;
    }
  } catch (err) {
    console.warn('Backend hospital fetch failed, trying Overpass directly:', err);
  }

  // ── Attempt 2: Overpass API direct from browser ──────────────────────────
  try {
    const query = [
      `[out:json][timeout:15];`,
      `(`,
      `  node["amenity"="hospital"](around:${radiusM},${lat},${lng});`,
      `  way["amenity"="hospital"](around:${radiusM},${lat},${lng});`,
      `  node["amenity"="clinic"](around:${radiusM},${lat},${lng});`,
      `);`,
      `out center;`,
    ].join('');

    const resp = await fetch('https://overpass-api.de/api/interpreter', {
      method: 'POST',
      body: query,
      signal: AbortSignal.timeout(18000),
    });

    if (resp.ok) {
      const data = await resp.json();
      const hospitals: NearestHospital[] = [];

      for (const elem of data?.elements ?? []) {
        const h_lat: number = elem.lat ?? elem.center?.lat;
        const h_lng: number = elem.lon ?? elem.center?.lon;
        if (!h_lat || !h_lng) continue;

        const tags = elem.tags || {};
        const name = tags['name'] || tags['name:en'] || (tags['amenity'] === 'clinic' ? 'Clinic' : 'Hospital');
        const address = [tags['addr:housenumber'], tags['addr:street'], tags['addr:city']]
          .filter(Boolean).join(', ') || 'Address not listed';
        const distanceKm = calcDistanceKm(lat, lng, h_lat, h_lng);

        hospitals.push({
          id: String(elem.id || name),
          name,
          address,
          distanceKm,
          distance: `${distanceKm} km away`,
          lat: h_lat,
          lng: h_lng,
          phone: tags['phone'] || tags['contact:phone'] || '',
          emergency: tags['emergency'] || 'yes',
          amenity: tags['amenity'] || 'hospital',
          directions_url: `https://www.google.com/maps/dir/?api=1&destination=${h_lat},${h_lng}&travelmode=driving`,
          source: 'openstreetmap',
        });
      }

      if (hospitals.length > 0) {
        hospitals.sort((a, b) => a.distanceKm - b.distanceKm);
        return hospitals.slice(0, 5);
      }
    }
  } catch (err) {
    console.warn('Overpass direct fetch failed:', err);
  }

  // ── Attempt 3: Google Maps search fallback ───────────────────────────────
  return [{
    id: 'fallback-gmaps',
    name: 'Find Nearest Hospital',
    address: 'Tap "Get Directions" to search Google Maps for hospitals near you',
    distanceKm: 0,
    distance: 'Tap for directions',
    lat, lng,
    phone: '',
    emergency: 'yes',
    amenity: 'hospital',
    directions_url: `https://www.google.com/maps/search/hospital+near+me/@${lat},${lng},14z`,
    source: 'fallback',
  }];
}

// ── PharmEasy deep link ──────────────────────────────────────────────────────

/**
 * Opens PharmEasy search for a given medicine name.
 */
export function openPharmEasyOrderSummary(medicineName: string, pincode?: string) {
  const cleanMed = encodeURIComponent(medicineName.split('(')[0].trim());
  const pincodeParam = pincode ? `&pincode=${encodeURIComponent(pincode)}` : '';
  if (typeof window !== 'undefined') {
    window.open(`https://pharmeasy.in/search/all?name=${cleanMed}${pincodeParam}`, '_blank', 'noopener,noreferrer');
  }
}
