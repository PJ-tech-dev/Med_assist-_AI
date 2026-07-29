'use client';

import { useState, useEffect } from 'react';
import { 
  Siren, 
  PhoneCall, 
  AlertOctagon, 
  MapPin, 
  Navigation,
  Hospital,
  Loader2,
  CheckSquare, 
  ArrowRight,
  Sparkles,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { EmergencyPanicButton } from '@/components/ui/EmergencyPanicButton';
import { fetchNearestHospitals, getRealLocationAddress, NearestHospital, UserLocation } from '@/lib/location';

const redFlags = [
  'Crushing chest pain radiating to jaw, neck, or left arm',
  'Sudden weakness or numbness on one side of face or body',
  'Severe shortness of breath or inability to speak full sentences',
  'Loss of consciousness, fainting, or sudden confusion',
  'Severe uncontrolled bleeding or traumatic injury',
];

export default function EmergencyPage() {
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [triageResult, setTriageResult] = useState<'critical' | 'urgent' | 'stable' | null>(null);

  // Hospital detection state
  const [hospitals, setHospitals] = useState<NearestHospital[]>([]);
  const [location, setLocation] = useState<UserLocation | null>(null);
  const [hospitalsLoading, setHospitalsLoading] = useState(false);
  const [hospitalsError, setHospitalsError] = useState(false);
  const [locationDenied, setLocationDenied] = useState(false);

  // Auto-detect hospitals on page load
  useEffect(() => {
    if (!navigator.geolocation) {
      setHospitalsError(true);
      return;
    }
    setHospitalsLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords;
        try {
          const [loc, nearbyHospitals] = await Promise.all([
            getRealLocationAddress(lat, lng),
            fetchNearestHospitals(lat, lng, 7000),
          ]);
          setLocation(loc);
          setHospitals(nearbyHospitals);
        } catch {
          setHospitalsError(true);
        } finally {
          setHospitalsLoading(false);
        }
      },
      () => {
        setHospitalsLoading(false);
        setLocationDenied(true);
        setHospitalsError(true);
      },
      { enableHighAccuracy: true, timeout: 12000 }
    );
  }, []);

  const toggleSymptom = (sym: string) => {
    if (selectedSymptoms.includes(sym)) {
      setSelectedSymptoms(selectedSymptoms.filter((s) => s !== sym));
    } else {
      setSelectedSymptoms([...selectedSymptoms, sym]);
    }
  };

  const handleEvaluate = () => {
    if (selectedSymptoms.length > 0) {
      setTriageResult('critical');
    } else {
      setTriageResult('stable');
    }
  };

  const openDirections = (hospital: NearestHospital) => {
    if (typeof window !== 'undefined') {
      window.open(hospital.directions_url, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-background p-6 gap-6 overflow-y-auto">
      {/* Emergency SOS Panic Button Hero Card */}
      <div className="rounded-2xl border-2 border-rose-600/60 bg-gradient-to-r from-rose-950 via-red-950 to-rose-950 p-6 shadow-2xl shadow-rose-900/30 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-rose-600/30 text-rose-300 ring-2 ring-rose-500/50 animate-pulse">
            <Siren className="h-8 w-8" />
          </div>
          <div>
            <h2 className="text-xl font-black text-rose-100 tracking-tight">⚠️ Need Immediate Help?</h2>
            <p className="text-xs text-rose-300/80 mt-0.5">Press the button — 10 sec countdown auto-dispatches WhatsApp alert &amp; calls 911</p>
          </div>
        </div>
        <div className="scale-125 origin-right">
          <EmergencyPanicButton />
        </div>
      </div>

      {/* Red Alert Banner */}
      <div className="rounded-2xl border bg-gradient-to-r from-rose-950 via-rose-900 to-rose-950 text-white p-6 space-y-4 shadow-lg border-rose-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-rose-600/30 text-rose-300 ring-2 ring-rose-500/50 animate-pulse">
              <Siren className="h-8 w-8" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-rose-100 flex items-center gap-2">
                Emergency Triage &amp; Urgent Alert Portal
              </h1>
              <p className="text-xs text-rose-200/80">
                Immediate clinical danger evaluation &amp; emergency medical service dispatch support
              </p>
            </div>
          </div>
          <a
            href="tel:911"
            className="flex items-center gap-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-sm px-5 py-3 shadow-lg transition-transform hover:scale-105"
          >
            <PhoneCall className="h-5 w-5" />
            CALL 911 / 108 NOW
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Red Flag Checklist */}
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-2xl border bg-card p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="font-bold text-foreground text-base flex items-center gap-2">
                <AlertOctagon className="h-5 w-5 text-rose-500" />
                Red Flag Emergency Symptoms Check
              </h2>
              <span className="text-xs text-rose-500 font-semibold">Immediate Assessment</span>
            </div>

            <p className="text-xs text-muted-foreground">
              Select any severe symptoms currently experienced by the patient:
            </p>

            <div className="space-y-2.5">
              {redFlags.map((symptom, idx) => {
                const selected = selectedSymptoms.includes(symptom);
                return (
                  <div
                    key={idx}
                    onClick={() => toggleSymptom(symptom)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-start gap-3 text-xs ${
                      selected
                        ? 'border-rose-500 bg-rose-500/10 text-rose-700 font-semibold'
                        : 'border-border bg-secondary/30 hover:bg-secondary/70 text-foreground'
                    }`}
                  >
                    <div
                      className={`h-4 w-4 mt-0.5 rounded flex items-center justify-center border ${
                        selected ? 'bg-rose-600 border-rose-600 text-white' : 'border-muted-foreground'
                      }`}
                    >
                      {selected && <CheckSquare className="h-3 w-3" />}
                    </div>
                    <span>{symptom}</span>
                  </div>
                );
              })}
            </div>

            <button
              onClick={handleEvaluate}
              className="w-full rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold py-3 text-xs shadow transition-all flex items-center justify-center gap-2"
            >
              <Sparkles className="h-4 w-4" />
              Evaluate Clinical Triage Priority
            </button>
          </div>

          {/* Triage Outcome */}
          {triageResult && (
            <div
              className={`rounded-2xl border p-6 space-y-3 shadow-md ${
                triageResult === 'critical'
                  ? 'bg-rose-500/10 border-rose-500/30 text-rose-700'
                  : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700'
              }`}
            >
              <div className="flex items-center gap-2 font-bold text-base">
                <Siren className="h-5 w-5" />
                {triageResult === 'critical'
                  ? 'RED TRIAGE STATUS: CRITICAL EMERGENCY DETECTED'
                  : 'GREEN TRIAGE STATUS: NO IMMEDIATE RED FLAGS DETECTED'}
              </div>
              <p className="text-xs leading-relaxed">
                {triageResult === 'critical'
                  ? 'The reported symptoms indicate a potentially life-threatening medical emergency. Please call emergency services (911/108) immediately or proceed to the nearest emergency department without delay.'
                  : 'No high-risk emergency criteria selected. If symptoms worsen or severe distress occurs, initiate urgent clinical evaluation.'}
              </p>
              {/* Quick directions to nearest hospital on critical */}
              {triageResult === 'critical' && hospitals.length > 0 && (
                <button
                  onClick={() => openDirections(hospitals[0])}
                  className="flex items-center gap-2 mt-2 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition-all"
                >
                  <Navigation className="h-3.5 w-3.5" />
                  Navigate to {hospitals[0].name} ({hospitals[0].distance})
                </button>
              )}
            </div>
          )}
        </div>

        {/* Sidebar: Hotlines + ER Locator */}
        <div className="space-y-6">
          {/* Emergency Hotlines */}
          <div className="rounded-2xl border bg-card p-5 space-y-4 shadow-sm">
            <h3 className="font-bold text-foreground text-sm flex items-center gap-2">
              <PhoneCall className="h-4 w-4 text-rose-500" />
              Emergency Hotlines
            </h3>
            <div className="space-y-2 text-xs">
              <a
                href="tel:911"
                className="flex items-center justify-between p-3 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 font-bold border border-rose-500/20"
              >
                <span>National Emergency Ambulance</span>
                <span>911 / 108</span>
              </a>
              <a
                href="tel:18002221222"
                className="flex items-center justify-between p-3 rounded-xl bg-secondary hover:bg-secondary/80 text-foreground font-semibold border"
              >
                <span>Poison Control Helpline</span>
                <span>1-800-222-1222</span>
              </a>
              <a
                href="tel:988"
                className="flex items-center justify-between p-3 rounded-xl bg-secondary hover:bg-secondary/80 text-foreground font-semibold border"
              >
                <span>Mental Health Emergency</span>
                <span>988</span>
              </a>
            </div>
          </div>

          {/* ── Nearest Emergency Hospitals (Live) ── */}
          <div className="rounded-2xl border bg-card p-5 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-foreground text-sm flex items-center gap-2">
                <Hospital className="h-4 w-4 text-primary" />
                Nearest Emergency Facilities
              </h3>
              {location && (
                <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <MapPin className="h-3 w-3 text-rose-500" />
                  {location.city}
                </span>
              )}
            </div>

            {/* Loading skeleton */}
            {hospitalsLoading && (
              <div className="space-y-2.5 animate-pulse">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-rose-500" />
                  Detecting your location &amp; hospitals...
                </div>
                {[0, 1, 2].map((i) => (
                  <div key={i} className="p-3 rounded-xl bg-secondary/40 border space-y-1.5">
                    <div className="h-3 bg-secondary rounded-full w-3/4" />
                    <div className="h-2.5 bg-secondary rounded-full w-1/2" />
                    <div className="h-8 bg-secondary rounded-lg w-full mt-1" />
                  </div>
                ))}
              </div>
            )}

            {/* Error / Location denied */}
            {!hospitalsLoading && hospitalsError && (
              <div className="space-y-2">
                <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-xs">
                  <ShieldAlert className="h-4 w-4 mt-0.5 shrink-0" />
                  <p>
                    {locationDenied
                      ? 'Location access denied. Enable GPS and refresh to detect nearby hospitals.'
                      : 'Unable to detect hospitals. Try the Google Maps search below.'}
                  </p>
                </div>
                <a
                  href="https://www.google.com/maps/search/hospital+emergency+near+me"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-3 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary font-bold border border-primary/20 text-xs transition-all"
                >
                  <span className="flex items-center gap-2">
                    <Navigation className="h-3.5 w-3.5" />
                    Search Hospitals on Google Maps
                  </span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </a>
              </div>
            )}

            {/* Hospital list */}
            {!hospitalsLoading && !hospitalsError && hospitals.length > 0 && (
              <div className="space-y-2">
                {hospitals.map((h, idx) => (
                  <div
                    key={h.id}
                    className={`p-3 rounded-xl border space-y-2 text-xs transition-all ${
                      idx === 0
                        ? 'border-emerald-500/30 bg-emerald-500/5'
                        : 'border-border bg-secondary/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          {idx === 0 && (
                            <span className="text-[9px] font-black uppercase tracking-wider text-emerald-600 bg-emerald-500/15 px-1.5 py-0.5 rounded-full border border-emerald-500/20">
                              NEAREST
                            </span>
                          )}
                        </div>
                        <p className="font-bold text-foreground truncate mt-0.5">{h.name}</p>
                        <p className="text-muted-foreground truncate">{h.address}</p>
                        {h.distanceKm > 0 && (
                          <p className="text-emerald-600 font-semibold mt-0.5">📍 {h.distance}</p>
                        )}
                        {h.phone && (
                          <a href={`tel:${h.phone}`} className="text-blue-600 hover:underline text-[10px]">
                            📞 {h.phone}
                          </a>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => openDirections(h)}
                      className={`w-full flex items-center justify-center gap-1.5 py-2 rounded-lg font-bold transition-all text-xs ${
                        idx === 0
                          ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-md'
                          : 'bg-secondary hover:bg-secondary/70 text-foreground border border-border'
                      }`}
                    >
                      <Navigation className="h-3.5 w-3.5" />
                      Get Directions → Google Maps
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
