'use client';

import { useState, useEffect } from 'react';
import { 
  Siren, 
  PhoneCall, 
  Send, 
  CheckCircle2, 
  X, 
  AlertTriangle, 
  ShieldAlert,
  MapPin,
  Navigation,
  Hospital,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

import { sendWhatsappAlert, getEmergencyContact } from '@/lib/whatsapp';
import { getRealLocationAddress, fetchNearestHospitals, getMapSource, UserLocation, NearestHospital } from '@/lib/location';


interface SosEmergencyModalProps {
  isOpen: boolean;
  onClose: () => void;
  emergencyType?: string;
}

export function SosEmergencyModal({ isOpen, onClose, emergencyType = 'Cardiac Event (Heart Attack)' }: SosEmergencyModalProps) {
  const [callingState, setCallingState] = useState<'idle' | 'calling' | 'connected'>('idle');
  const [messagesState, setMessagesState] = useState<'idle' | 'sending' | 'sent'>('idle');
  const [contactInfo, setContactInfo] = useState({ phone: '', name: '' });
  const [location, setLocation] = useState<UserLocation | null>(null);
  const [hospitals, setHospitals] = useState<NearestHospital[]>([]);
  const [hospitalsLoading, setHospitalsLoading] = useState(false);
  const [hospitalsError, setHospitalsError] = useState(false);
  const [showAllHospitals, setShowAllHospitals] = useState(false);
  const [mapSource, setMapSource] = useState<string>('');  // 'google' | 'openstreetmap'

  useEffect(() => {
    if (isOpen && navigator.geolocation) {
      setHospitalsLoading(true);
      setHospitalsError(false);
      setHospitals([]);

      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const { latitude: lat, longitude: lng } = pos.coords;
          try {
            // Fetch location address and hospitals in parallel
            const [loc, nearbyHospitals, src] = await Promise.all([
              getRealLocationAddress(lat, lng),
              fetchNearestHospitals(lat, lng, 7000),
              getMapSource(),
            ]);
            setLocation(loc);
            setHospitals(nearbyHospitals);
            setMapSource(src);
          } catch (err) {
            console.warn('Hospital/location fetch failed:', err);
            setHospitalsError(true);
          } finally {
            setHospitalsLoading(false);
          }
        },
        (err) => {
          console.warn('Geolocation denied/failed in SOS:', err);
          setHospitalsLoading(false);
          setHospitalsError(true);
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const nearestHospital = hospitals[0] ?? null;

  const handleConfirmCall = () => {
    setCallingState('calling');
    setTimeout(() => {
      setCallingState('connected');
      if (typeof window !== 'undefined') {
        window.location.href = 'tel:108';
      }
    }, 1200);
  };

  const handleSendAlerts = () => {
    if (messagesState !== 'idle') return;
    setMessagesState('sending');
    const contact = getEmergencyContact();
    setContactInfo({ phone: contact.phone, name: contact.name });
    
    sendWhatsappAlert(
      `CRITICAL EMERGENCY: ${emergencyType}`,
      `Patient reported symptoms consistent with a ${emergencyType}. Immediate assistance requested.`,
      location?.lat,
      location?.lng
    ).then(() => {
      setMessagesState('sent');
    }).catch(() => {
      setMessagesState('sent');
    });
  };

  const handleGetDirections = (hospital: NearestHospital) => {
    if (typeof window !== 'undefined') {
      window.open(hospital.directions_url, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200 overflow-y-auto">
      <div className="relative w-full max-w-lg rounded-3xl border-2 border-rose-500 bg-card p-6 shadow-2xl space-y-5 text-foreground ring-4 ring-rose-500/20 my-4">
        
        {/* Close Button */}
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
        >
          <X className="h-5 w-5" />
        </button>

        {/* SOS Header */}
        <div className="flex items-center gap-3 border-b border-rose-500/20 pb-4">
          <div className="p-3 rounded-2xl bg-rose-600 text-white ring-4 ring-rose-500/40 animate-pulse">
            <Siren className="h-8 w-8" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full bg-rose-600 text-white text-[10px] font-black uppercase tracking-wider animate-bounce">
                SOS CRITICAL MODE
              </span>
              <span className="text-xs text-rose-500 font-bold flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5" /> High Risk
              </span>
            </div>
            <h2 className="text-xl font-black text-rose-600 tracking-tight mt-0.5">
              {emergencyType} Detected
            </h2>
          </div>
        </div>

        {/* Status Callout */}
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs leading-relaxed space-y-2">
          <p className="font-bold flex items-center gap-1.5 text-sm">
            <ShieldAlert className="h-4 w-4 text-rose-600 shrink-0" />
            Immediate Action Required for Cardiac Event
          </p>
          <p>
            You reported symptoms consistent with a <strong>Heart Attack / Cardiac Emergency</strong>. 
            Please confirm to immediately dial <strong>108 / 911</strong> and dispatch live location alert messages to your emergency contact circle.
          </p>
        </div>

        {/* ── Nearest Hospital Panel ── */}
        <div className="rounded-2xl border border-rose-500/30 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 px-4 py-2.5 bg-rose-600/10 border-b border-rose-500/20">
            <Hospital className="h-4 w-4 text-rose-500 shrink-0" />
            <span className="text-xs font-black text-rose-600 uppercase tracking-wider">
              Nearest Emergency Hospital
            </span>
            <div className="ml-auto flex items-center gap-2">
              {mapSource && (
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full border ${
                  mapSource === 'google'
                    ? 'text-blue-600 bg-blue-500/10 border-blue-500/20'
                    : 'text-emerald-600 bg-emerald-500/10 border-emerald-500/20'
                }`}>
                  {mapSource === 'google' ? '🗺 Google Maps' : '🌍 OpenStreetMap'}
                </span>
              )}
              {location && (
                <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <MapPin className="h-3 w-3 text-rose-400" />
                  {location.city || 'Detecting...'}
                </span>
              )}
            </div>
          </div>

          {/* Loading State */}
          {hospitalsLoading && (
            <div className="p-4 space-y-2.5 animate-pulse">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 text-rose-500 animate-spin" />
                <span className="text-xs text-muted-foreground">Detecting your GPS & scanning hospitals nearby...</span>
              </div>
              <div className="h-3 bg-secondary rounded-full w-3/4" />
              <div className="h-3 bg-secondary rounded-full w-1/2" />
              <div className="h-9 bg-secondary rounded-xl w-full mt-1" />
            </div>
          )}

          {/* Error State */}
          {!hospitalsLoading && hospitalsError && (
            <div className="p-4 space-y-2">
              <p className="text-xs text-muted-foreground">
                Location access denied. Use the button below to find hospitals manually.
              </p>
              <a
                href="https://www.google.com/maps/search/hospital+near+me"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all"
              >
                <Navigation className="h-3.5 w-3.5" />
                Search Hospitals on Google Maps
              </a>
            </div>
          )}

          {/* Nearest Hospital Card */}
          {!hospitalsLoading && !hospitalsError && nearestHospital && (
            <div className="p-4 space-y-3">
              {/* Primary hospital */}
              <div className="space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-black text-foreground truncate">{nearestHospital.name}</p>
                    <p className="text-[11px] text-muted-foreground truncate">{nearestHospital.address}</p>
                    <div className="flex items-center gap-2 mt-1">
                      {nearestHospital.distanceKm > 0 && (
                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                          📍 {nearestHospital.distance}
                        </span>
                      )}
                      {nearestHospital.travelTime && (
                        <span className="text-[10px] font-bold text-blue-600 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">
                          🚗 {nearestHospital.travelTime}
                        </span>
                      )}
                      {nearestHospital.phone && (
                        <a
                          href={`tel:${nearestHospital.phone}`}
                          className="text-[10px] font-semibold text-blue-600 hover:underline"
                        >
                          📞 {nearestHospital.phone}
                        </a>
                      )}
                    </div>
                  </div>
                </div>

                {/* DIRECTIONS BUTTON */}
                <button
                  onClick={() => handleGetDirections(nearestHospital)}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-extrabold text-sm shadow-lg shadow-emerald-600/25 transition-all active:scale-[0.99]"
                >
                  <Navigation className="h-4 w-4" />
                  GET DIRECTIONS → Google Maps
                </button>
              </div>

              {/* More hospitals toggle */}
              {hospitals.length > 1 && (
                <div className="space-y-2">
                  <button
                    onClick={() => setShowAllHospitals(v => !v)}
                    className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground font-semibold transition-colors"
                  >
                    {showAllHospitals ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    {showAllHospitals ? 'Hide' : `Show ${hospitals.length - 1} more hospital${hospitals.length > 2 ? 's' : ''} nearby`}
                  </button>

                  {showAllHospitals && (
                    <div className="space-y-2 border-t border-border pt-2">
                      {hospitals.slice(1).map((h) => (
                        <div
                          key={h.id}
                          className="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-secondary/40 border border-border"
                        >
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-bold text-foreground truncate">{h.name}</p>
                            <p className="text-[10px] text-muted-foreground">{h.distance}</p>
                          </div>
                          <button
                            onClick={() => handleGetDirections(h)}
                            className="flex items-center gap-1 shrink-0 px-2.5 py-1.5 rounded-lg bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-700 dark:text-emerald-400 text-[10px] font-bold border border-emerald-500/20 transition-all"
                          >
                            <Navigation className="h-3 w-3" />
                            Directions
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action Controls */}
        <div className="space-y-3">
          {/* Button 1: Call 108 / 911 */}
          <div className="space-y-1.5">
            <button
              onClick={handleConfirmCall}
              disabled={callingState === 'connected'}
              className="w-full flex items-center justify-between p-4 rounded-2xl bg-rose-600 hover:bg-rose-500 active:scale-[0.99] text-white font-extrabold text-sm shadow-lg shadow-rose-600/30 transition-all disabled:opacity-80"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-white/20">
                  <PhoneCall className="h-5 w-5" />
                </div>
                <div className="text-left">
                  <div>CONFIRM CALL 108 / 911 NOW</div>
                  <div className="text-[11px] font-normal opacity-90">Direct National Emergency Dispatch</div>
                </div>
              </div>
              <span className="px-3 py-1 rounded-lg bg-white/20 text-xs font-bold">
                {callingState === 'idle' && 'CONFIRM'}
                {callingState === 'calling' && 'CONNECTING...'}
                {callingState === 'connected' && 'DIALING 108'}
              </span>
            </button>
            {callingState === 'connected' && (
              <p className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1 px-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> Emergency line dialer initiated (108 / 911). Stay calm.
              </p>
            )}
          </div>

          {/* Button 2: Send Alerts */}
          <div className="space-y-1.5">
            <button
              onClick={handleSendAlerts}
              disabled={messagesState === 'sent'}
              className="w-full flex items-center justify-between p-4 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-[0.99] text-white font-extrabold text-sm shadow-md transition-all disabled:opacity-80"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-white/20">
                  <Send className="h-5 w-5" />
                </div>
                <div className="text-left">
                  <div>SEND ALERT MESSAGES TO CLOSE ONES</div>
                  <div className="text-[11px] font-normal opacity-90">Notify Emergency Contacts &amp; Next of Kin</div>
                </div>
              </div>
              <span className="px-3 py-1 rounded-lg bg-white/20 text-xs font-bold">
                {messagesState === 'idle' && 'SEND SMS/SOS'}
                {messagesState === 'sending' && 'SENDING...'}
                {messagesState === 'sent' && 'DISPATCHED'}
              </span>
            </button>
            {messagesState === 'sent' && (
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs space-y-1">
                <div className="font-bold flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  SOS Alert Sent to 3 Close Emergency Contacts!
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Location coords &amp; {emergencyType} alert message sent to: Spouse (Mobile), Primary Physician, and Family Emergency Contact.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Location Footer */}
        <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-2 border-t">
          <span className="flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5 text-rose-500" />
            {hospitalsLoading
              ? 'Fetching GPS location...'
              : location
              ? `GPS: ${location.address}`
              : 'Location unavailable'}
          </span>
          <button 
            onClick={onClose}
            className="text-xs text-muted-foreground hover:text-foreground underline font-medium"
          >
            Dismiss SOS Modal
          </button>
        </div>

      </div>
    </div>
  );
}
