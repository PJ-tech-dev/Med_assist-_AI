'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, ensureAuth } from '@/lib/api';
import { sendWhatsappAlert, getEmergencyContact } from '@/lib/whatsapp';
import { 
  Activity, 
  Heart, 
  Bluetooth,
  Watch,
  XCircle,
  HeartPulse,
  AlertTriangle,
  MessageSquare,
  Sparkles,
  RefreshCw,
  Plus,
  Brain,
  Zap,
  TrendingUp
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import EmergencySosModal from '@/components/EmergencySosModal';

export default function AnalyticsPage() {
  const [patientId, setPatientId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [metricsList, setMetricsList] = useState<any[]>([]);

  // Bluetooth SmartWatch Live State
  const [btStatus, setBtStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [deviceName, setDeviceName] = useState<string>('');
  const [livePulse, setLivePulse] = useState(0);
  const [pulsePing, setPulsePing] = useState(false);
  const [highBpmAlert, setHighBpmAlert] = useState(false);
  const highBpmAlertRef = useRef(false);
  const [showSosModal, setShowSosModal] = useState(false);
  const [isDispatching, setIsDispatching] = useState(false);
  
  // AI Suggestions
  const [aiSuggestion, setAiSuggestion] = useState<string>('Connect a smartwatch to receive live AI suggestions based on your biometrics.');
  const [isAiThinking, setIsAiThinking] = useState(false);
  
  const pulseRef = useRef(0);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      await ensureAuth();
      let pid = patientId;
      const pList = await api.patients.list();
      if (pList.items && pList.items.length > 0) {
        pid = pList.items[0].id;
      } else {
        const newP = await api.patients.create({
          full_name: 'Patient User',
          gender: 'male',
          date_of_birth: '1990-01-01',
          blood_group: 'O+',
        });
        pid = newP.id;
      }
      setPatientId(pid);

      const res = await api.patients.getVitals(pid);
      if (res.items && Array.isArray(res.items)) {
        setMetricsList(res.items);
      }
    } catch (e) {
      console.warn(e);
    }
    setLoading(false);
  };

  const triggerHighBpmWhatsappAlert = async (bpm: number) => {
    if (highBpmAlertRef.current) return;
    try {
      highBpmAlertRef.current = true;
      setHighBpmAlert(true);
      setIsDispatching(true);
      const contact = getEmergencyContact();
      await sendWhatsappAlert(
        `HIGH HEART RATE CRITICAL ALERT (${bpm} BPM)`,
        `SmartWatch PPG telemetry detected elevated heart rate of ${bpm} bpm (threshold: ${contact.highBpmThreshold} bpm). Patient may be experiencing acute tachycardia or cardiac distress.`
      );
    } catch (err) {
      console.error("SOS Alert Failed to send:", err);
    } finally {
      setIsDispatching(false);
      setShowSosModal(true);
    }
  };

  // Connect to Real Web Bluetooth GATT service
  const handleConnectBluetooth = async () => {
    setBtStatus('connecting');
    try {
      if (typeof window !== 'undefined' && 'bluetooth' in navigator) {
        try {
          const device = await (navigator as any).bluetooth.requestDevice({
            filters: [{ services: ['heart_rate'] }]
          });
          setDeviceName(device.name || 'Bluetooth LE Device');
          
          const server = await device.gatt.connect();
          const service = await server.getPrimaryService('heart_rate');
          const characteristic = await service.getCharacteristic('heart_rate_measurement');
          await characteristic.startNotifications();
          
          characteristic.addEventListener('characteristicvaluechanged', (e: any) => {
            const value = e.target.value;
            const flags = value.getUint8(0);
            const rate16Bits = flags & 0x1;
            let heartRate = 0;
            if (rate16Bits) {
              heartRate = value.getUint16(1, /*littleEndian=*/true);
            } else {
              heartRate = value.getUint8(1);
            }
            
            setLivePulse(heartRate);
            pulseRef.current = heartRate;
            
            setPulsePing(true);
            setTimeout(() => setPulsePing(false), 200);
            
            if (heartRate >= 120 && !highBpmAlertRef.current) {
              triggerHighBpmWhatsappAlert(heartRate);
            }
          });
          
          setBtStatus('connected');
          return;
        } catch (e) {
          console.warn("Bluetooth connection failed or cancelled by user", e);
        }
      }
      
      // Simulation fallback for browsers/devices without paired BLE hardware
      setTimeout(() => {
        setDeviceName('SmartWatch Pro (Simulated)');
        setBtStatus('connected');
        setAiSuggestion("Simulated Heart Rate connected. Fetching AI evaluation...");
        
        // Sim pulse loop
        setInterval(() => {
           const simBpm = 70 + Math.floor(Math.random() * 15);
           setLivePulse(simBpm);
           pulseRef.current = simBpm;
           setPulsePing(true);
           setTimeout(() => setPulsePing(false), 200);
        }, 3000);
        
      }, 1500);
    } catch (err) {
      setBtStatus('disconnected');
    }
  };

  const handleDisconnectBluetooth = () => {
    setBtStatus('disconnected');
    setLivePulse(0);
  };

  // DB Sync and AI Generation Loop (Every 15 Seconds)
  useEffect(() => {
    if (btStatus === 'connected' && patientId) {
      const dbInterval = setInterval(async () => {
        const bpm = pulseRef.current;
        if (bpm > 0) {
          // 1. Save to MongoDB
          try {
             await api.patients.addVitals(patientId, { 
                heart_rate: bpm, 
                device_source: deviceName 
             });
             fetchHistory(); // Refresh history table
          } catch(err) {
             console.warn("Failed saving vitals", err);
          }
          
          // 2. Fetch AI Suggestion based on current vitals
          try {
             setIsAiThinking(true);
             const prompt = `The patient's live heart rate is currently ${bpm} bpm. Give a very short 1-2 sentence medical observation or suggestion (do not use markdown, keep it friendly and direct).`;
             if (typeof window !== 'undefined' && (window as any).puter?.ai?.chat) {
               const res = await (window as any).puter.ai.chat(prompt);
               let txt = '';
               if (typeof res === 'string') txt = res;
               else if (res?.message?.content) txt = Array.isArray(res.message.content) ? res.message.content.map((c: any) => c.text).join('') : res.message.content;
               else txt = String(res);
               setAiSuggestion(txt.trim());
             }
             setIsAiThinking(false);
          } catch (e) {
             setIsAiThinking(false);
          }
        }
      }, 15000);
      return () => clearInterval(dbInterval);
    }
  }, [btStatus, patientId, deviceName]);

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-background p-6 gap-6 overflow-y-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row md:items-center justify-between border-b border-border/50 pb-5 gap-4"
      >
        <div>
          <h1 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-rose-500 to-pink-600 shadow-md shadow-rose-500/20">
              <Activity className="h-5 w-5 text-white" />
            </div>
            Health Metrics &amp; Vital Analytics
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time biometric monitoring, BLE telemetry &amp; AI risk scoring
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {btStatus === 'disconnected' && (
            <button
              onClick={handleConnectBluetooth}
              className="flex items-center gap-2 rounded-xl bg-blue-600 text-white hover:bg-blue-700 px-4 py-2 text-xs font-semibold transition-all shadow-md shadow-blue-500/20"
            >
              <Bluetooth className="h-4 w-4" />
              Connect Bluetooth Device
            </button>
          )}

          {btStatus === 'connecting' && (
            <div className="flex items-center gap-2 rounded-xl bg-blue-500/10 text-blue-600 border border-blue-500/30 px-4 py-2 text-xs font-semibold animate-pulse">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Requesting BLE Permission...
            </div>
          )}

          {btStatus === 'connected' && (
            <div className="flex items-center gap-2">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-2 rounded-xl bg-emerald-500/10 text-emerald-600 border border-emerald-500/30 px-3 py-1.5 text-xs font-medium"
              >
                <Watch className="h-4 w-4 text-emerald-500 animate-bounce" />
                <span>Streaming from <strong>{deviceName}</strong></span>
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
              </motion.div>
              <button
                onClick={() => {
                  setLivePulse(138);
                  triggerHighBpmWhatsappAlert(138);
                }}
                className="px-3 py-1.5 rounded-lg border border-rose-500/30 text-rose-500 hover:bg-rose-500/10 text-xs font-bold transition-all animate-pulse"
              >
                Simulate 138 BPM
              </button>
              <button
                onClick={handleDisconnectBluetooth}
                className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-rose-400 hover:border-rose-500/30 text-xs transition-all"
                title="Disconnect"
              >
                <XCircle className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Live Vitals */}
        <div className="lg:col-span-2 space-y-5">
          {/* Live Vitals Banner */}
          <AnimatePresence mode="wait">
          {btStatus === 'connected' ? (
            <motion.div
              key="connected"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.97 }}
              className="rounded-3xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/60 via-teal-950/40 to-blue-950/30 p-6 shadow-xl space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <motion.div
                    animate={{ scale: livePulse > 0 ? [1, 1.15, 1] : 1 }}
                    transition={{ duration: 0.6, repeat: livePulse > 0 ? Infinity : 0, ease: 'easeInOut' }}
                    className="p-4 rounded-2xl bg-emerald-500 text-white shadow-xl shadow-emerald-500/40"
                  >
                    <HeartPulse className="h-8 w-8" />
                  </motion.div>
                  <div>
                    <h2 className="text-xl font-black text-white flex items-center gap-2">
                      Live Telemetry
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500 text-white text-[10px] font-black uppercase tracking-wider animate-pulse">
                        GATT Heart Rate
                      </span>
                    </h2>
                    <p className="text-sm text-emerald-200/60 mt-1">BLE connection established · {deviceName}</p>
                  </div>
                </div>

                {/* 3D BPM Display */}
                <motion.div
                  key={livePulse}
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="relative text-center bg-card/20 backdrop-blur-md px-8 py-4 rounded-2xl border border-white/10 shadow-inner"
                >
                  <div className="text-[10px] uppercase font-black text-emerald-300/70 tracking-widest mb-1">BPM</div>
                  <div className={`text-5xl font-black tabular-nums ${
                    livePulse >= 120 ? 'text-rose-400' : livePulse >= 90 ? 'text-amber-400' : 'text-emerald-300'
                  }`}>
                    {livePulse > 0 ? livePulse : '--'}
                  </div>
                  <div className="text-[10px] text-emerald-300/50 mt-1">
                    {livePulse >= 120 ? '⚠️ Tachycardia' : livePulse >= 90 ? '⚡ Elevated' : livePulse > 0 ? '✓ Normal' : 'Waiting...'}
                  </div>
                </motion.div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="disconnected"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="rounded-3xl border border-dashed border-border/60 bg-card/30 p-10 flex flex-col items-center justify-center text-center gap-4"
            >
              <motion.div
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="h-20 w-20 rounded-full bg-secondary/60 flex items-center justify-center"
              >
                <Bluetooth className="h-10 w-10 text-muted-foreground/40" />
              </motion.div>
              <h2 className="text-lg font-bold text-foreground">Awaiting Bluetooth Device</h2>
              <p className="text-sm text-muted-foreground max-w-sm">
                Connect your Bluetooth SmartWatch to stream live heart rate data and receive AI clinical observations every 15s.
              </p>
            </motion.div>
          )}
          </AnimatePresence>
          
          {/* History DB Feed */}
          <div className="rounded-3xl border bg-card p-6">
             <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
               <Heart className="h-5 w-5 text-rose-500" />
               Historical Database Logs
             </h2>
             {loading ? (
                <div className="py-10 text-center text-sm text-muted-foreground animate-pulse">Loading database records...</div>
             ) : metricsList.length === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground bg-secondary/30 rounded-2xl border border-dashed">
                  No heart rate metrics saved yet. Connect device to begin logging.
                </div>
             ) : (
                <div className="space-y-2">
                   {metricsList.map((m: any, idx: number) => (
                      <div key={idx} className="flex items-center justify-between p-3 rounded-xl hover:bg-secondary/50 border bg-background transition-colors">
                         <div className="flex items-center gap-3">
                            <div className="p-2 bg-rose-500/10 text-rose-600 rounded-lg">
                               <HeartPulse className="h-4 w-4" />
                            </div>
                            <div>
                               <div className="font-semibold text-sm text-foreground">{m.heart_rate} BPM</div>
                               <div className="text-[10px] text-muted-foreground">{m.device_source || 'Unknown Device'}</div>
                            </div>
                         </div>
                         <div className="text-xs text-muted-foreground font-mono">
                            {new Date(m.recorded_at).toLocaleString()}
                         </div>
                      </div>
                   ))}
                </div>
             )}
          </div>
        </div>

        {/* Right Column: AI Suggestion */}
        <div className="space-y-5">
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-3xl border border-violet-500/20 bg-gradient-to-b from-violet-950/40 via-purple-950/20 to-transparent p-6 shadow-xl relative overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-24 h-24 rounded-full bg-violet-500/10 blur-2xl pointer-events-none" />
            <div className="flex items-center gap-2 font-bold mb-4">
              <div className="p-2 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-md">
                <Brain className={`h-4 w-4 text-white ${isAiThinking ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <div className="text-sm font-black text-foreground">Live AI Health Agent</div>
                <div className="text-[10px] text-muted-foreground">Updates every 15 seconds</div>
              </div>
            </div>
            <AnimatePresence mode="wait">
              <motion.p
                key={aiSuggestion}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-sm text-foreground/90 leading-relaxed"
              >
                {aiSuggestion}
              </motion.p>
            </AnimatePresence>
            {btStatus === 'connected' && (
              <div className="mt-4 pt-4 border-t border-violet-500/10 text-[10px] text-muted-foreground/60 font-mono flex items-center gap-1.5">
                <Zap className="h-3 w-3 text-violet-400" />
                Agent analyzes telemetry every 15s automatically.
              </div>
            )}
          </motion.div>
        </div>
      </div>
      
      {showSosModal && (
        <EmergencySosModal 
           patientId={patientId} 
           onCancel={() => setShowSosModal(false)} 
        />
      )}
    </div>
  );
}
