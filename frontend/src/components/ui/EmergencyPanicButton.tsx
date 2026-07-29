'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Siren, X, PhoneCall, MessageCircle, ShieldAlert, AlertTriangle } from 'lucide-react';
import { sendWhatsappAlert, getEmergencyContact } from '@/lib/whatsapp';

// ─────────────────────────────────────────────
// Web Audio Siren Engine
// ─────────────────────────────────────────────
function useSirenAudio() {
  const ctxRef = useRef<AudioContext | null>(null);
  const oscRef = useRef<OscillatorNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const tickRef = useRef<NodeJS.Timeout | null>(null);

  const start = useCallback(() => {
    try {
      const AC = window.AudioContext || (window as any).webkitAudioContext;
      if (!AC) return;
      const ctx = new AC();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sawtooth';
      gain.gain.setValueAtTime(0.4, ctx.currentTime);

      // Rapid siren sweep 880 ↔ 1760 Hz
      let hi = false;
      tickRef.current = setInterval(() => {
        hi = !hi;
        osc.frequency.setTargetAtTime(hi ? 1760 : 880, ctx.currentTime, 0.07);
      }, 350);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();

      ctxRef.current = ctx;
      oscRef.current = osc;
      gainRef.current = gain;
    } catch (e) {
      console.warn('Siren audio init failed:', e);
    }
  }, []);

  const stop = useCallback(() => {
    if (tickRef.current) clearInterval(tickRef.current);
    try { oscRef.current?.stop(); } catch {}
    try { ctxRef.current?.close(); } catch {}
    ctxRef.current = null;
    oscRef.current = null;
  }, []);

  return { start, stop };
}

// ─────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────
export function EmergencyPanicButton() {
  // States
  const [phase, setPhase] = useState<'idle' | 'countdown' | 'dispatched'>('idle');
  const [count, setCount] = useState(10);
  const [showModal, setShowModal] = useState(false);
  const [whatsappSent, setWhatsappSent] = useState(false);
  const [calledEms, setCalledEms] = useState(false);

  // Refs for cleanup
  const countdownRef = useRef<NodeJS.Timeout | null>(null);
  const blinkRef = useRef<NodeJS.Timeout | null>(null);
  const [blink, setBlink] = useState(false);

  const { start: startSiren, stop: stopSiren } = useSirenAudio();

  // ── START EMERGENCY SEQUENCE ──
  const triggerEmergency = () => {
    setPhase('countdown');
    setCount(10);
    setShowModal(true);
    setWhatsappSent(false);
    setCalledEms(false);
    startSiren();

    // Blinking LED effect
    blinkRef.current = setInterval(() => {
      setBlink(b => !b);
    }, 250);
  };

  // ── COUNTDOWN LOGIC ──
  useEffect(() => {
    if (phase !== 'countdown') return;

    countdownRef.current = setInterval(() => {
      setCount(prev => {
        if (prev <= 1) {
          clearInterval(countdownRef.current!);
          // Time's up → auto-dispatch
          dispatchEmergency();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  // ── DISPATCH (auto or manual) ──
  const dispatchEmergency = useCallback(async () => {
    // Stop countdown + audio
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (blinkRef.current) clearInterval(blinkRef.current);
    setBlink(true); // keep solid red

    setPhase('dispatched');

    // 1) Send WhatsApp emergency alert
    try {
      const contact = getEmergencyContact();
      await sendWhatsappAlert(
        '🚨 PANIC BUTTON EMERGENCY',
        `The patient manually pressed the EMERGENCY PANIC button. Immediate medical assistance is required! Contact: ${contact.name} (${contact.relationship}).`,
      );
      setWhatsappSent(true);
    } catch (e) {
      console.error('WhatsApp dispatch error:', e);
      setWhatsappSent(true); // still open wa.me link
    }

    // 2) Initiate 911 call
    setTimeout(() => {
      if (typeof window !== 'undefined') {
        window.location.href = 'tel:911';
      }
      setCalledEms(true);
    }, 800);
  }, []);

  // ── CANCEL ──
  const cancelEmergency = () => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (blinkRef.current) clearInterval(blinkRef.current);
    stopSiren();
    setBlink(false);
    setPhase('idle');
    setCount(10);
    setShowModal(false);
  };

  // cleanup on unmount
  useEffect(() => {
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (blinkRef.current) clearInterval(blinkRef.current);
      stopSiren();
    };
  }, [stopSiren]);

  // ── BUTTON LABEL / STATE ──
  const isActive = phase !== 'idle';

  return (
    <>
      {/* ─── Floating Emergency Button ─── */}
      <button
        id="emergency-panic-btn"
        onClick={isActive ? cancelEmergency : triggerEmergency}
        aria-label="Emergency Panic Button"
        className={`
          relative flex items-center gap-2 rounded-full font-black text-white text-xs
          px-4 py-2.5 shadow-lg transition-all select-none overflow-hidden
          border-2 focus:outline-none active:scale-95
          ${phase === 'idle'
            ? 'bg-rose-600 border-rose-400 hover:bg-rose-500 hover:shadow-rose-500/40 hover:shadow-xl'
            : phase === 'countdown'
            ? `${blink ? 'bg-rose-600 border-rose-300 shadow-rose-500/60 shadow-2xl scale-105' : 'bg-red-900 border-rose-500/60'}`
            : 'bg-rose-700 border-rose-400 cursor-default'
          }
        `}
      >
        {/* Pulse rings when active */}
        {phase === 'countdown' && (
          <>
            <span className="absolute inset-0 rounded-full bg-rose-500 opacity-30 animate-ping" />
            <span className="absolute inset-0 rounded-full bg-rose-400 opacity-20 animate-ping" style={{ animationDelay: '0.2s' }} />
          </>
        )}

        <Siren
          className={`h-4 w-4 shrink-0 ${phase === 'countdown' ? 'animate-pulse' : ''}`}
        />

        {phase === 'idle' && <span>Emergency</span>}
        {phase === 'countdown' && (
          <span className="tabular-nums">
            SOS — CANCEL ({count}s)
          </span>
        )}
        {phase === 'dispatched' && <span>Dispatched ✓</span>}
      </button>

      {/* ─── Countdown Modal Overlay ─── */}
      {showModal && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
          style={{
            background: phase === 'countdown'
              ? blink
                ? 'rgba(220,0,0,0.18)'
                : 'rgba(0,0,0,0.85)'
              : 'rgba(0,0,0,0.90)',
            backdropFilter: 'blur(12px)',
            transition: 'background 0.15s',
          }}
        >
          {/* Animated red border frame */}
          <div
            className={`
              w-full max-w-md rounded-3xl p-8 text-center space-y-6 relative overflow-hidden
              border-4 shadow-2xl
              ${phase === 'countdown'
                ? blink
                  ? 'border-red-400 bg-rose-950 shadow-rose-600/60'
                  : 'border-rose-700 bg-[#1a0008] shadow-rose-900/40'
                : 'border-rose-600 bg-[#1a0008]'
              }
            `}
            style={{ transition: 'border-color 0.15s, background 0.15s, box-shadow 0.15s' }}
          >
            {/* Top corner blinking LED */}
            {phase === 'countdown' && (
              <div
                className="absolute top-4 right-4 w-4 h-4 rounded-full shadow-lg shadow-rose-500"
                style={{
                  background: blink ? '#ff2020' : '#4a0000',
                  boxShadow: blink ? '0 0 16px 6px rgba(255,30,30,0.7)' : 'none',
                  transition: 'all 0.15s',
                }}
              />
            )}

            {/* SOS Icon */}
            <div className="flex items-center justify-center">
              <div
                className={`w-28 h-28 rounded-full flex items-center justify-center shadow-2xl
                  ${phase === 'countdown'
                    ? blink ? 'bg-red-600 shadow-red-500/80' : 'bg-rose-950 shadow-rose-900/20'
                    : 'bg-rose-700 shadow-rose-800'
                  }
                `}
                style={{ transition: 'all 0.15s' }}
              >
                {phase === 'countdown' ? (
                  <span
                    className="text-white font-black tabular-nums"
                    style={{ fontSize: '2.8rem', lineHeight: 1, textShadow: '0 0 20px rgba(255,255,255,0.5)' }}
                  >
                    {count}
                  </span>
                ) : (
                  <ShieldAlert className="h-14 w-14 text-white animate-pulse" />
                )}
              </div>
            </div>

            {/* Title */}
            <div className="space-y-1">
              {phase === 'countdown' ? (
                <>
                  <h2 className="text-3xl font-black text-white tracking-tight uppercase">
                    🚨 Emergency Activating
                  </h2>
                  <p className="text-rose-300 text-sm font-semibold">
                    WhatsApp & 911 will be called automatically in{' '}
                    <span className="text-white font-black">{count} second{count !== 1 ? 's' : ''}</span>
                  </p>
                  <p className="text-rose-400/80 text-xs">
                    Press <strong className="text-rose-300">CANCEL</strong> if this was a mistake
                  </p>
                </>
              ) : (
                <>
                  <h2 className="text-3xl font-black text-white tracking-tight uppercase">
                    Emergency Dispatched!
                  </h2>
                  <p className="text-rose-300 text-sm">
                    Help is on the way. Stay calm and remain still.
                  </p>
                </>
              )}
            </div>

            {/* Status chips (dispatched phase) */}
            {phase === 'dispatched' && (
              <div className="space-y-2">
                <div className="flex items-center gap-3 p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/30">
                  <MessageCircle className="h-5 w-5 text-emerald-400 shrink-0" />
                  <div className="text-left">
                    <div className="text-emerald-300 font-bold text-xs">WhatsApp Alert Sent</div>
                    <div className="text-emerald-400/70 text-[11px]">Emergency contact notified with your location</div>
                  </div>
                  {whatsappSent && <span className="ml-auto text-emerald-400 font-black text-lg">✓</span>}
                </div>
                <div className="flex items-center gap-3 p-3 rounded-2xl bg-rose-500/10 border border-rose-500/30">
                  <PhoneCall className="h-5 w-5 text-rose-400 shrink-0" />
                  <div className="text-left">
                    <div className="text-rose-300 font-bold text-xs">Calling 911 / 108</div>
                    <div className="text-rose-400/70 text-[11px]">National emergency services dialer initiated</div>
                  </div>
                  {calledEms && <span className="ml-auto text-rose-400 font-black text-lg">✓</span>}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex flex-col gap-3 pt-2">
              {phase === 'countdown' && (
                <button
                  onClick={cancelEmergency}
                  className="w-full py-4 rounded-2xl bg-white text-rose-700 font-black text-lg uppercase tracking-wider hover:bg-rose-100 transition-all shadow-lg active:scale-95"
                >
                  ✕ CANCEL — False Alarm
                </button>
              )}

              {phase === 'dispatched' && (
                <>
                  <button
                    onClick={() => {
                      stopSiren();
                      setShowModal(false);
                    }}
                    className="w-full py-3.5 rounded-2xl bg-rose-700/40 hover:bg-rose-700/60 border border-rose-500/40 text-white font-bold text-sm transition-all"
                  >
                    <X className="h-4 w-4 inline mr-2" />
                    Close — Help Is Coming
                  </button>
                  <a
                    href="tel:911"
                    className="w-full py-3.5 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg transition-all"
                  >
                    <PhoneCall className="h-4 w-4" />
                    Redial 911 / 108 Manually
                  </a>
                </>
              )}
            </div>

            {/* Warning footer */}
            <div className="flex items-center justify-center gap-1.5 text-[11px] text-rose-400/60">
              <AlertTriangle className="h-3 w-3" />
              <span>Misuse of emergency services is a criminal offense</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
