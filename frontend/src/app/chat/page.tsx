'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence, useSpring, useTransform } from 'framer-motion';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
import { SosEmergencyModal } from '@/components/ui/SosEmergencyModal';
import { OrderPharmacyModal } from '@/components/ui/OrderPharmacyModal';
import {
  Send,
  Sparkles,
  Pill,
  FileText,
  Activity,
  Stethoscope,
  RefreshCw,
  Info,
  Clock,
  AlertCircle,
  Copy,
  Check,
  Zap,
  ShieldCheck,
  Trash2,
  Siren,
  ShoppingBag,
  Bot,
  User,
  Mic,
  CornerDownLeft,
  Brain,
  Dna,
  HeartPulse,
} from 'lucide-react';
import { api, ensureAuth } from '@/lib/api';
import { getRealLocationAddress, fetchRealNearbyPharmacies } from '@/lib/location';
import { getEmergencyContact } from '@/lib/whatsapp';

// ─── Types ───────────────────────────────────────────────
interface Message {
  id: string;
  sender: 'user' | 'agent';
  agentName?: string;
  intent?: string;
  executionTime?: number;
  confidence?: number;
  text: string;
  timestamp: string;
  isError?: boolean;
}

// ─── System prompt for neat structured Puter AI output ───
const MEDASSIST_SYSTEM_PROMPT = `You are MedAssist AI — an elite, empathetic clinical intelligence assistant.

STRICT FORMATTING RULES (always follow):
1. Use **bold** for key terms, diagnoses, drug names, and warnings.
2. Use ### headings to separate logical sections (e.g., ### Assessment, ### Recommendations, ### Warning Signs).
3. Use bullet lists (- item) for multiple items — never run them into a paragraph.
4. For drug interactions or comparisons, always use a Markdown table with columns: | Parameter | Details |
5. For lab values, use a table: | Test | Value | Normal Range | Status |
6. Always end with a ### ⚠️ Disclaimer section reminding the user to consult a licensed physician.
7. Keep tone professional yet warm. Use concise, scannable paragraphs.
8. Never write walls of plain text — always structure with sections, bullets, and highlights.
9. If any value is CRITICAL or DANGEROUS, use ⚠️ emoji prominently.
10. Maximum response length: 600 words. Be thorough but efficient.`;

// ─── Quick-action prompts ─────────────────────────────────
const suggestedPrompts = [
  { icon: Stethoscope, label: 'Symptom Check', gradient: 'from-blue-500 to-cyan-500', text: 'I have a mild fever (100.4°F), persistent headache, and sore throat for 2 days. What could this be?' },
  { icon: Pill, label: 'Drug Safety', gradient: 'from-violet-500 to-purple-600', text: 'Can I take Ibuprofen 400mg while on Metformin 500mg daily? Are there interactions?' },
  { icon: FileText, label: 'Lab Report', gradient: 'from-emerald-500 to-teal-500', text: 'Explain my blood test: HbA1c 6.8%, Fasting Glucose 135 mg/dL, Total Cholesterol 215 mg/dL.' },
  { icon: Activity, label: 'Vitals Read', gradient: 'from-rose-500 to-pink-600', text: 'My BP is 138/88 mmHg and resting HR is 92 bpm. Is this concerning?' },
];

// ─── 3D Floating DNA Orb ─────────────────────────────────
function DNAOrb({ size = 120 }: { size?: number }) {
  return (
    <div
      className="relative select-none pointer-events-none"
      style={{ width: size, height: size }}
    >
      {/* Core glowing sphere */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: 'radial-gradient(circle at 35% 35%, #60a5fa, #3b82f6 40%, #1d4ed8 70%, #0f172a)',
          boxShadow: '0 0 40px 12px rgba(59,130,246,0.25), inset -8px -8px 20px rgba(0,0,0,0.4), inset 4px 4px 12px rgba(255,255,255,0.15)',
        }}
        animate={{ rotateY: [0, 360] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
      />
      {/* Orbit ring 1 */}
      <motion.div
        className="absolute inset-0 rounded-full border border-blue-400/30"
        style={{ transform: 'rotateX(75deg)' }}
        animate={{ rotate: [0, 360] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'linear' }}
      />
      {/* Orbit ring 2 */}
      <motion.div
        className="absolute inset-0 rounded-full border border-indigo-400/20"
        style={{ transform: 'rotateX(60deg) rotateZ(45deg)' }}
        animate={{ rotate: [360, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: 'linear' }}
      />
      {/* DNA icon center */}
      <div className="absolute inset-0 flex items-center justify-center">
        <Dna className="text-white/80 drop-shadow-lg" style={{ width: size * 0.36, height: size * 0.36 }} />
      </div>
      {/* Sparkle particles */}
      {[0, 60, 120, 180, 240, 300].map((deg, i) => (
        <motion.div
          key={i}
          className="absolute w-1.5 h-1.5 rounded-full bg-blue-300"
          style={{
            top: '50%',
            left: '50%',
            transformOrigin: `0 0`,
          }}
          animate={{
            x: [
              Math.cos((deg * Math.PI) / 180) * (size / 2 - 4),
              Math.cos(((deg + 180) * Math.PI) / 180) * (size / 2 - 4),
              Math.cos((deg * Math.PI) / 180) * (size / 2 - 4),
            ],
            y: [
              Math.sin((deg * Math.PI) / 180) * (size / 2 - 4),
              Math.sin(((deg + 180) * Math.PI) / 180) * (size / 2 - 4),
              Math.sin((deg * Math.PI) / 180) * (size / 2 - 4),
            ],
            opacity: [1, 0.3, 1],
            scale: [1, 0.5, 1],
          }}
          transition={{ duration: 3 + i * 0.3, repeat: Infinity, ease: 'easeInOut', delay: i * 0.2 }}
        />
      ))}
    </div>
  );
}

// ─── Thinking Dots Loader ─────────────────────────────────
function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 px-2 py-1">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-2 h-2 rounded-full bg-blue-500"
          animate={{ y: [0, -6, 0], opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }}
        />
      ))}
    </div>
  );
}

// ─── Neural Network background SVG ───────────────────────
function NeuralBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-[0.04]">
      <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="neural" x="0" y="0" width="120" height="120" patternUnits="userSpaceOnUse">
            <circle cx="60" cy="60" r="2" fill="currentColor" />
            <circle cx="0" cy="0" r="2" fill="currentColor" />
            <circle cx="120" cy="0" r="2" fill="currentColor" />
            <circle cx="0" cy="120" r="2" fill="currentColor" />
            <circle cx="120" cy="120" r="2" fill="currentColor" />
            <line x1="60" y1="60" x2="0" y2="0" stroke="currentColor" strokeWidth="0.5" />
            <line x1="60" y1="60" x2="120" y2="0" stroke="currentColor" strokeWidth="0.5" />
            <line x1="60" y1="60" x2="0" y2="120" stroke="currentColor" strokeWidth="0.5" />
            <line x1="60" y1="60" x2="120" y2="120" stroke="currentColor" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#neural)" className="text-blue-500" />
      </svg>
    </div>
  );
}

// ─── Agent Avatar ─────────────────────────────────────────
function AgentAvatar({ isError }: { isError?: boolean }) {
  return (
    <motion.div
      className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl font-bold text-white shadow-lg ${isError
          ? 'bg-gradient-to-br from-rose-500 to-red-700 shadow-rose-500/30'
          : 'bg-gradient-to-br from-blue-500 to-indigo-700 shadow-blue-500/30'
        }`}
      whileHover={{ scale: 1.05, rotate: 3 }}
      transition={{ type: 'spring', stiffness: 400 }}
    >
      {/* 3D highlight */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/20 to-transparent" />
      {isError ? (
        <AlertCircle className="h-5 w-5 relative z-10" />
      ) : (
        <Brain className="h-5 w-5 relative z-10" />
      )}
      {/* Pulse ring for agent */}
      {!isError && (
        <motion.div
          className="absolute inset-0 rounded-2xl border-2 border-blue-400/60"
          animate={{ scale: [1, 1.15, 1], opacity: [0.6, 0, 0.6] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
    </motion.div>
  );
}

// ─── User Avatar ─────────────────────────────────────────
function UserAvatar() {
  return (
    <motion.div
      className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-600 to-slate-800 border border-white/10 shadow-lg shadow-black/30"
      whileHover={{ scale: 1.05, rotate: -3 }}
      transition={{ type: 'spring', stiffness: 400 }}
    >
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-transparent" />
      <User className="h-5 w-5 text-white/80 relative z-10" />
    </motion.div>
  );
}

// ─── Main Chat Page ───────────────────────────────────────
export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'agent',
      agentName: 'MedAssist AI',
      intent: 'Welcome',
      text: `### 👋 Welcome to MedAssist AI

I'm your **intelligent clinical assistant**, powered by a multi-agent AI orchestration system.

### What I Can Help With

- **Symptom Assessment & Triage** — Analyze your symptoms with clinical precision
- **Medication Safety Checks** — Drug interaction detection and dosage guidance  
- **Lab Report Interpretation** — Explain complex blood work, imaging, and diagnostics
- **Vital Sign Analysis** — Assess BP, heart rate, glucose levels, and more

### Quick Start

Select a prompt below or type your health question. All responses are **structured**, **evidence-based**, and clearly formatted for easy reading.

> 💡 *For medical emergencies, call 911 immediately. I am an AI assistant, not a substitute for professional medical care.*`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [patientReportsContext, setPatientReportsContext] = useState('');
  const [userLocationContext, setUserLocationContext] = useState('');
  const [activeAgent, setActiveAgent] = useState('Multi-Agent Orchestrator');
  const [backendOnline, setBackendOnline] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [sosModalOpen, setSosModalOpen] = useState(false);
  const [detectedEmergencyType, setDetectedEmergencyType] = useState('Cardiac Event (Heart Attack)');
  const [pharmacyModalOpen, setPharmacyModalOpen] = useState(false);
  const [selectedCondition, setSelectedCondition] = useState('General Health Relief');
  const [inputFocused, setInputFocused] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // ── Init data ──
  useEffect(() => {
    const initData = async () => {
      await ensureAuth();
      try {
        const data = await api.reports.list();
        if (Array.isArray(data) && data.length > 0) {
          const summaries = data.map((r: any) => {
            let details = `Report: ${r.filename} (${r.report_type || r.type}) - ${r.summary}`;
            const labs = r.labValues || r.extracted_values || [];
            if (labs && labs.length > 0) {
              details += `\nLab Results:\n` + labs.map((l: any) => `- ${l.name || l.test_name}: ${l.value} (Range: ${l.range || l.normal_range}) [${l.status}]`).join('\n');
            }
            return details;
          }).join('\n\n');
          setPatientReportsContext(summaries + "\n\nINSTRUCTION: When presenting lab values, always use a Markdown table with columns: Test | Value | Normal Range | Status. Mark abnormal values with ⚠️.");
        }
      } catch (e) {
        console.warn('Failed to fetch patient reports.', e);
      }

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            try {
              const lat = pos.coords.latitude;
              const lng = pos.coords.longitude;
              const loc = await getRealLocationAddress(lat, lng);
              const shops = await fetchRealNearbyPharmacies(lat, lng);
              let locStr = `The user is located at: ${loc.address}, ${loc.city}.`;
              if (shops.length > 0) {
                locStr += `\n\nNearby Medical Shops:\n` + shops.map((s: any) => `- ${s.name} (${s.distance}) - Rating: ${s.rating}`).join('\n');
              }
              setUserLocationContext(locStr);
            } catch (err) {
              console.warn('Failed to fetch location.', err);
            }
          },
          (err) => console.warn('Geolocation denied:', err)
        );
      }
    };
    initData();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleClear = () => {
    setMessages([{
      id: Date.now().toString(),
      sender: 'agent',
      agentName: 'MedAssist AI',
      intent: 'Session Reset',
      text: '### 🔄 Session Reset\n\nYour chat history has been cleared. **How can I assist you today?**',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }]);
  };

  const handleSearchAndOrderPharmEasy = (messageText: string) => {
    const commonMeds = ['Paracetamol', 'Ibuprofen', 'Amoxicillin', 'Cetirizine', 'Metformin', 'Antacid', 'Omeprazole', 'Azithromycin', 'Dolo', 'Disprin', 'Pantoprazole', 'Aspirin', 'Vitamin C', 'ORS', 'Cough Syrup'];
    let matchedMed = 'Paracetamol';
    for (const med of commonMeds) {
      if (messageText.toLowerCase().includes(med.toLowerCase())) { matchedMed = med; break; }
    }
    const cleanQuery = encodeURIComponent(matchedMed);
    if (typeof window !== 'undefined') window.open(`https://pharmeasy.in/search/all?name=${cleanQuery}`, '_blank', 'noopener,noreferrer');
    router.push(`/medicines?med=${cleanQuery}&pharmeasy=true`);
  };

  const handleSend = async (customText?: string) => {
    const textToSend = customText || input;
    if (!textToSend.trim() || loading) return;

    const lowerInput = textToSend.toLowerCase();
    if (lowerInput.includes('heart attack') || lowerInput.includes('cardiac') || lowerInput.includes('chest pain') || lowerInput.includes('cannot breathe') || lowerInput.includes("can't breathe")) {
      setDetectedEmergencyType('Heart Attack / Cardiac Emergency');
      setSosModalOpen(true);

      // Auto-redirect to WhatsApp synchronously to avoid popup blockers
      if (typeof window !== 'undefined') {
        try {
          const contact = getEmergencyContact();
          if (contact.enableWhatsapp) {
            const cleanPhone = contact.phone.replace(/[^0-9+]/g, '');
            const messageText = `🚨 *MEDASSIST AI REAL-TIME EMERGENCY ALERT* 🚨\n\n*ALERT TYPE*: Heart Attack / Cardiac Emergency\n*DETAILS*: Patient reported symptoms consistent with a Heart Attack / Cardiac Emergency. Immediate assistance requested.\n\n⚠️ *URGENT*: Immediate medical response or check-in is requested!`;
            const encodedText = encodeURIComponent(messageText);
            const whatsappUrl = `whatsapp://send?phone=${cleanPhone.replace('+', '')}&text=${encodedText}`;
            window.open(whatsappUrl, '_blank', 'noopener,noreferrer');
          }
        } catch (e) {
          console.error('Failed to parse emergency contact for auto-redirect', e);
        }
      }
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!customText) setInput('');
    setLoading(true);

    try {
      const chatHistory: any[] = messages.map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));

      // Insert system prompts
      chatHistory.unshift({ role: 'system', content: MEDASSIST_SYSTEM_PROMPT });
      if (patientReportsContext) {
        chatHistory.unshift({ role: 'system', content: `Patient medical records on file:\n\n${patientReportsContext}` });
      }
      if (userLocationContext) {
        chatHistory.unshift({ role: 'system', content: userLocationContext });
      }
      chatHistory.push({ role: 'user', content: textToSend });

      const res = await (window as any).puter.ai.chat(chatHistory);

      let responseText = '';
      if (typeof res === 'string') {
        responseText = res;
      } else if (res?.message?.content) {
        responseText = Array.isArray(res.message.content)
          ? res.message.content.map((c: any) => c.text || '').join('')
          : res.message.content;
      } else {
        responseText = String(res);
      }

      setBackendOnline(true);
      setMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        agentName: 'MedAssist AI',
        intent: 'Clinical Analysis',
        text: responseText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);
      setActiveAgent('Puter AI — GPT-4o');
    } catch (error: any) {
      console.error('Chat failed:', error);
      setMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        agentName: 'System Monitor',
        intent: 'Error',
        isError: true,
        text: `**Connection error:** ${error.message || 'Puter AI offline. Please retry.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);
    } finally {
      setLoading(false);
    }
  };

  // ── Message bubble spring animation variants ──
  const bubbleVariants = {
    hidden: (sender: string) => ({
      opacity: 0,
      x: sender === 'user' ? 30 : -30,
      y: 10,
      scale: 0.95,
    }),
    visible: {
      opacity: 1,
      x: 0,
      y: 0,
      scale: 1,
      transition: {
        type: 'spring' as const,
        stiffness: 320,
        damping: 28,
        mass: 0.8,
      },
    },
  };

  return (
    <div className="relative flex h-[calc(100vh-4rem)] flex-col bg-background overflow-hidden max-w-7xl mx-auto w-full">

      {/* ── Neural network background texture ── */}
      <NeuralBackground />

      {/* ── Ambient glow orbs ── */}
      <div className="absolute top-[-80px] left-[-80px] w-80 h-80 rounded-full bg-blue-600/8 blur-3xl pointer-events-none" />
      <div className="absolute bottom-[-80px] right-[-80px] w-96 h-96 rounded-full bg-indigo-600/8 blur-3xl pointer-events-none" />

      <div className="relative flex flex-col h-full p-4 md:p-5 gap-4 z-10">

        {/* ── Header ── */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-border/50 pb-4 gap-3"
        >
          <div className="flex items-center gap-4">
            {/* 3D orb */}
            <DNAOrb size={52} />
            <div>
              <h1 className="text-xl md:text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
                MedAssist
                <span className="bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent">AI</span>
                <span className="text-base font-normal text-muted-foreground">Clinical Consultation</span>
              </h1>
              <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Multi-agent RAG
                </span>
                <span>·</span>
                <span>Drug safety engine · Clinical NLP</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Backend status */}
            <div className="flex items-center gap-1.5 bg-card/70 px-3 py-1.5 rounded-full text-xs font-medium border border-border/60 backdrop-blur-sm">
              <span className={`h-2 w-2 rounded-full ${backendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
              <span className="text-muted-foreground">API <strong className="text-foreground">{backendOnline ? 'Online' : 'Offline'}</strong></span>
            </div>

            {/* Active agent */}
            <motion.div
              key={activeAgent}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="flex items-center gap-1.5 bg-blue-500/10 px-3 py-1.5 rounded-full text-xs font-medium border border-blue-500/20 text-blue-400"
            >
              <Zap className="h-3.5 w-3.5" />
              <span>{activeAgent}</span>
            </motion.div>

            {/* Clear */}
            <motion.button
              whileHover={{ scale: 1.08, rotate: 10 }}
              whileTap={{ scale: 0.92 }}
              onClick={handleClear}
              title="Reset chat"
              className="p-2.5 rounded-xl text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
            </motion.button>
          </div>
        </motion.div>

        {/* ── Quick action chips ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.45 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-2"
        >
          {suggestedPrompts.map((p, idx) => (
            <motion.button
              key={idx}
              onClick={() => handleSend(p.text)}
              disabled={loading}
              whileHover={{ y: -2, scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              transition={{ type: 'spring', stiffness: 400, damping: 25 }}
              className="relative overflow-hidden flex items-start gap-2.5 p-3 text-left rounded-2xl border border-border/60 bg-card/50 hover:bg-card/80 hover:border-border/80 backdrop-blur-sm transition-colors group shadow-xs hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {/* Gradient shimmer on hover */}
              <div className={`absolute inset-0 opacity-0 group-hover:opacity-5 transition-opacity bg-gradient-to-br ${p.gradient} rounded-2xl`} />

              <div className={`p-1.5 rounded-xl bg-gradient-to-br ${p.gradient} text-white shadow-sm group-hover:scale-110 transition-transform shrink-0`}>
                <p.icon className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-bold text-foreground text-xs">{p.label}</div>
                <div className="text-muted-foreground line-clamp-1 mt-0.5 text-[10px] leading-snug">{p.text}</div>
              </div>
            </motion.button>
          ))}
        </motion.div>

        {/* ── Messages area ── */}
        <div className="flex-1 overflow-y-auto rounded-3xl border border-border/50 bg-card/20 backdrop-blur-md p-4 md:p-5 space-y-5 shadow-inner scroll-smooth"
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(99,102,241,0.2) transparent' }}
        >
          <AnimatePresence initial={false}>
            {messages.map((msg, idx) => (
              <motion.div
                key={msg.id}
                custom={msg.sender}
                variants={bubbleVariants}
                initial="hidden"
                animate="visible"
                exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.2 } }}
                className={`flex gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {/* Agent avatar */}
                {msg.sender === 'agent' && <AgentAvatar isError={msg.isError} />}

                <div className={`max-w-[82%] md:max-w-[75%] flex flex-col gap-1.5 ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>

                  {/* Meta header for agent */}
                  {msg.sender === 'agent' && (
                    <div className="flex items-center gap-2 flex-wrap px-1">
                      <span className="font-black text-[11px] text-blue-400 flex items-center gap-1">
                        <Brain className="h-3 w-3" />
                        {msg.agentName}
                      </span>
                      {msg.intent && (
                        <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-[10px] font-mono border border-blue-500/20">
                          {msg.intent}
                        </span>
                      )}
                      <span className="text-[10px] text-muted-foreground ml-auto flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {msg.timestamp}
                      </span>
                    </div>
                  )}

                  {/* Bubble */}
                  <div className="relative group">
                    <motion.div
                      whileHover={msg.sender === 'agent' ? { scale: 1.005 } : undefined}
                      className={`rounded-3xl px-5 py-4 text-sm leading-relaxed shadow-sm ${msg.sender === 'user'
                          ? 'bg-gradient-to-br from-blue-600 to-indigo-700 text-white font-medium rounded-tr-sm shadow-blue-600/20'
                          : msg.isError
                            ? 'bg-rose-500/8 border border-rose-500/25 text-rose-300 rounded-tl-sm'
                            : 'bg-card border border-border/70 text-foreground rounded-tl-sm'
                        }`}
                    >
                      {/* 3D gloss on user message */}
                      {msg.sender === 'user' && (
                        <div className="absolute inset-0 rounded-3xl rounded-tr-sm bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />
                      )}

                      {msg.sender === 'user' ? (
                        <p className="whitespace-pre-wrap relative z-10">{msg.text}</p>
                      ) : (
                        <div className="prose prose-sm dark:prose-invert max-w-none">
                          <MarkdownRenderer content={msg.text} />
                        </div>
                      )}
                    </motion.div>

                    {/* Quick actions for agent messages */}
                    {msg.sender === 'agent' && !msg.isError && (
                      <>
                        {/* Pharmacy buttons */}
                        {(msg.text.toLowerCase().includes('paracetamol') || msg.text.toLowerCase().includes('ibuprofen') || msg.text.toLowerCase().includes('medication') || msg.text.toLowerCase().includes('symptom') || msg.text.toLowerCase().includes('prescri')) && (
                          <motion.div
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            className="mt-2 flex items-center gap-2 flex-wrap"
                          >
                            <button
                              onClick={() => handleSearchAndOrderPharmEasy(msg.text)}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-teal-500/10 hover:bg-teal-500/20 text-teal-400 border border-teal-500/25 text-[11px] font-bold transition-all hover:scale-105 active:scale-95"
                            >
                              <Pill className="h-3.5 w-3.5" />
                              Search PharmEasy
                            </button>
                            <button
                              onClick={() => { setSelectedCondition(msg.intent || 'Symptom Relief'); setPharmacyModalOpen(true); }}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/25 text-[11px] font-bold transition-all hover:scale-105 active:scale-95"
                            >
                              <ShoppingBag className="h-3.5 w-3.5" />
                              Order Nearby
                            </button>
                          </motion.div>
                        )}

                        {/* Copy button */}
                        <motion.button
                          onClick={() => handleCopy(msg.text, msg.id)}
                          title="Copy response"
                          initial={{ opacity: 0 }}
                          whileHover={{ scale: 1.1 }}
                          className="absolute top-3 right-3 p-1.5 rounded-lg bg-background/70 hover:bg-secondary text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-all border border-border/50 backdrop-blur-sm"
                        >
                          {copiedId === msg.id ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                        </motion.button>
                      </>
                    )}
                  </div>

                  {/* User timestamp */}
                  {msg.sender === 'user' && (
                    <div className="text-[10px] text-muted-foreground pr-1 flex items-center gap-1">
                      <Check className="h-3 w-3 text-blue-400" />
                      {msg.timestamp}
                    </div>
                  )}
                </div>

                {/* User avatar */}
                {msg.sender === 'user' && <UserAvatar />}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* ── Thinking loader ── */}
          <AnimatePresence>
            {loading && (
              <motion.div
                initial={{ opacity: 0, x: -20, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -20, scale: 0.95 }}
                transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                className="flex gap-3 justify-start"
              >
                <AgentAvatar />
                <div className="flex flex-col gap-1.5 items-start">
                  <div className="flex items-center gap-2 px-1">
                    <span className="font-black text-[11px] text-blue-400 flex items-center gap-1">
                      <Brain className="h-3 w-3" />
                      MedAssist AI
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-[10px] font-mono border border-amber-500/20 animate-pulse">
                      Processing...
                    </span>
                  </div>
                  <div className="rounded-3xl rounded-tl-sm px-5 py-4 bg-card border border-border/70 shadow-sm">
                    <div className="flex items-center gap-3">
                      <ThinkingDots />
                      <div className="flex flex-col">
                        <span className="text-xs font-semibold text-foreground">Analyzing your query</span>
                        <span className="text-[10px] text-muted-foreground">Running clinical RAG pipeline...</span>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={messagesEndRef} />
        </div>

        {/* ── Input bar ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-2"
        >
          {/* Disclaimer */}
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70 px-1">
            <Info className="h-3 w-3 text-amber-500/70 shrink-0" />
            <span>MedAssist AI is for education only. Consult a licensed physician for any medical decisions.</span>
          </div>

          {/* Input box */}
          <motion.div
            animate={{
              boxShadow: inputFocused
                ? '0 0 0 2px rgba(99,102,241,0.4), 0 4px 24px rgba(99,102,241,0.12)'
                : '0 1px 4px rgba(0,0,0,0.08)',
              borderColor: inputFocused ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.1)',
            }}
            transition={{ duration: 0.2 }}
            className="flex items-center gap-2 rounded-2xl border bg-card/80 backdrop-blur-md p-2 pr-2"
          >
            {/* Left icon */}
            <div className="pl-2">
              <HeartPulse className={`h-4 w-4 transition-colors ${inputFocused ? 'text-indigo-400 animate-pulse' : 'text-muted-foreground/50'}`} />
            </div>

            <input
              ref={inputRef}
              type="text"
              id="medassist-chat-input"
              placeholder="Describe symptoms, ask about medications, or paste lab values..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              disabled={loading}
              className="flex-1 bg-transparent px-2 py-2 text-sm text-foreground focus:outline-none placeholder:text-muted-foreground/50 disabled:opacity-60"
            />

            {/* Send button */}
            <motion.button
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              whileHover={input.trim() && !loading ? { scale: 1.05 } : undefined}
              whileTap={input.trim() && !loading ? { scale: 0.94 } : undefined}
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all shadow-md ${input.trim() && !loading
                  ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-blue-500/30 hover:shadow-blue-500/50'
                  : 'bg-secondary text-muted-foreground opacity-50 cursor-not-allowed shadow-none'
                }`}
            >
              <AnimatePresence mode="wait">
                {loading ? (
                  <motion.div key="loading" initial={{ rotate: 0 }} animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
                    <RefreshCw className="h-4 w-4" />
                  </motion.div>
                ) : (
                  <motion.div key="send" initial={{ scale: 0.8 }} animate={{ scale: 1 }}>
                    <Send className="h-4 w-4" />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.button>
          </motion.div>

          {/* Keyboard hint */}
          <div className="flex items-center justify-end gap-1 text-[10px] text-muted-foreground/50 pr-1">
            <CornerDownLeft className="h-3 w-3" />
            <span>Enter to send</span>
          </div>
        </motion.div>
      </div>

      {/* ── Modals ── */}
      <SosEmergencyModal isOpen={sosModalOpen} onClose={() => setSosModalOpen(false)} emergencyType={detectedEmergencyType} />
      <OrderPharmacyModal isOpen={pharmacyModalOpen} onClose={() => setPharmacyModalOpen(false)} diseaseName={selectedCondition} />
    </div>
  );
}
