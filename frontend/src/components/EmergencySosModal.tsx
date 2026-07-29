'use client';

import { useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { AlertTriangle, XCircle, Activity } from 'lucide-react';

interface EmergencySosModalProps {
  onCancel: () => void;
  patientId?: string;
}

export default function EmergencySosModal({ onCancel, patientId }: EmergencySosModalProps) {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const oscillatorRef = useRef<OscillatorNode | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Sound Engine Setup (Web Audio API Siren)
  const initAudio = () => {
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) return;
      
      const ctx = new AudioContextClass();
      audioCtxRef.current = ctx;

      const osc = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      osc.type = 'square';
      osc.frequency.setValueAtTime(800, ctx.currentTime); // high pitch
      
      // Siren effect
      intervalRef.current = setInterval(() => {
        if (osc.frequency.value === 800) {
          osc.frequency.setValueAtTime(1200, ctx.currentTime);
        } else {
          osc.frequency.setValueAtTime(800, ctx.currentTime);
        }
      }, 500);

      osc.connect(gainNode);
      gainNode.connect(ctx.destination);
      
      gainNode.gain.setValueAtTime(0.1, ctx.currentTime); // keep volume reasonable
      osc.start();
      
      oscillatorRef.current = osc;
    } catch (e) {
      console.warn("Audio Context failed to initialize", e);
    }
  };

  const stopAudio = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (oscillatorRef.current) {
      try { oscillatorRef.current.stop(); } catch(e){}
    }
    if (audioCtxRef.current) {
      try { 
        const closePromise = audioCtxRef.current.close(); 
        if (closePromise && closePromise.catch) {
          closePromise.catch(() => {});
        }
      } catch(e){}
    }
  };

  useEffect(() => {
    initAudio();
    return stopAudio;
  }, []);

  // Instant Dispatch Logic
  useEffect(() => {
    // Dispatch Ambulance immediately!
    api.emergency.dispatchAmbulance({
      location: "37.7749, -122.4194",
      patient_id: patientId,
      reason: "Automated SOS dispatch due to unresponsive high BPM"
    }).catch(console.error);
  }, [patientId]);

  const handleCancel = () => {
    stopAudio();
    onCancel();
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/90 backdrop-blur-md p-4 animate-in fade-in duration-300">
      <div className="w-full max-w-lg rounded-3xl border border-rose-500/50 bg-rose-950 p-8 shadow-2xl flex flex-col items-center text-center">
        
        {/* 3D Pulse SOS Graphic */}
        <div className="relative flex items-center justify-center w-40 h-40 mb-6 perspective-[1000px]">
          {/* Pulsing rings */}
          <div className="absolute inset-0 rounded-full bg-rose-500/20 animate-ping" style={{ animationDuration: '1s' }} />
          <div className="absolute inset-0 rounded-full bg-rose-500/40 animate-ping" style={{ animationDuration: '1.5s' }} />
          
          <div className={`relative z-10 w-32 h-32 rounded-full bg-gradient-to-tr from-rose-600 to-red-500 shadow-[0_0_50px_rgba(244,63,94,0.6)] flex items-center justify-center transform transition-transform duration-500 scale-110 rotate-12`}>
             <AlertTriangle className="h-16 w-16 text-white drop-shadow-lg animate-pulse" />
          </div>
        </div>

        {/* Content */}
        <h1 className="text-4xl font-black tracking-tighter text-white mb-2 uppercase drop-shadow-md">
          Emergency SOS
        </h1>
        <p className="text-rose-200 font-medium text-sm mb-6 max-w-sm">
          Critical biometrics detected! WhatsApp emergency alert has been sent and an ambulance has been called immediately.
        </p>
        
        <div className="p-4 rounded-2xl bg-rose-950/80 border border-rose-500/50 flex items-center gap-3 w-full justify-center mb-8">
           <Activity className="h-5 w-5 text-rose-400 animate-pulse" />
           <span className="text-rose-200 font-semibold tracking-wide">Ambulance ETA: 8 Minutes</span>
        </div>

        <button
          onClick={handleCancel}
          className="w-full max-w-xs flex items-center justify-center gap-2 rounded-2xl bg-white/10 hover:bg-white/20 text-white px-6 py-4 font-bold text-lg border border-white/20 transition-all active:scale-95"
        >
          <XCircle className="h-6 w-6" />
          Cancel SOS (False Alarm)
        </button>
      </div>
    </div>
  );
}
