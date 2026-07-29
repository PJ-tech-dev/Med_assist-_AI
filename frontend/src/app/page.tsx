'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users, FileText, Pill, Activity, MessageSquarePlus,
  Sparkles, CheckCircle2, AlertTriangle, ArrowRight,
  RefreshCw, Server, HeartPulse, Brain, Zap, Shield,
  TrendingUp, Clock, Star
} from 'lucide-react';
import { api, ensureAuth } from '@/lib/api';

const featureCards = [
  {
    href: '/chat',
    icon: MessageSquarePlus,
    gradient: 'from-blue-500 to-indigo-600',
    glow: 'shadow-blue-500/20',
    badge: 'GPT-4o',
    title: 'AI Multi-Agent Consultation',
    desc: 'Consult specialized agents: Symptom Checker, Drug Safety, Report Analysis & Emergency Triage.',
  },
  {
    href: '/reports',
    icon: FileText,
    gradient: 'from-violet-500 to-purple-600',
    glow: 'shadow-violet-500/20',
    badge: 'OCR',
    title: 'Medical Reports & Analysis',
    desc: 'Upload blood work & imaging PDFs for automated Tesseract OCR parsing and AI lab extraction.',
  },
  {
    href: '/emergency',
    icon: AlertTriangle,
    gradient: 'from-rose-500 to-red-600',
    glow: 'shadow-rose-500/20',
    badge: '24/7',
    title: 'Emergency Triage Portal',
    desc: 'Red flag symptom checklist, panic SOS button, 10s countdown & 911/108 dispatch.',
  },
  {
    href: '/analytics',
    icon: Activity,
    gradient: 'from-emerald-500 to-teal-600',
    glow: 'shadow-emerald-500/20',
    badge: 'BLE',
    title: 'Live Health Analytics',
    desc: 'Real-time Bluetooth SmartWatch biometric streaming, heart rate monitoring & AI risk scoring.',
  },
  {
    href: '/medicines',
    icon: Pill,
    gradient: 'from-amber-500 to-orange-500',
    glow: 'shadow-amber-500/20',
    badge: 'GPS',
    title: 'Medicines & Pharmacy',
    desc: 'AI-powered symptom-to-medicine recommendation, Google Maps pharmacy locator & PharmEasy orders.',
  },
  {
    href: '/history',
    icon: Clock,
    gradient: 'from-cyan-500 to-blue-500',
    glow: 'shadow-cyan-500/20',
    badge: 'LIVE',
    title: 'Medical History Timeline',
    desc: 'Chronological audit trail of diagnoses, allergies, surgeries & vaccination records.',
  },
];

const statsConfig = [
  { key: 'patients', label: 'Active Patients', icon: Users, gradient: 'from-blue-500 to-indigo-600', suffix: '' },
  { key: 'reports', label: 'Analyzed Reports', icon: FileText, gradient: 'from-violet-500 to-purple-600', suffix: '' },
  { key: 'medications', label: 'Active Medications', icon: Pill, gradient: 'from-emerald-500 to-teal-600', suffix: '' },
  { key: 'chatSessions', label: 'AI Sessions', icon: Brain, gradient: 'from-amber-500 to-orange-500', suffix: '' },
];

// Animated number counter
function CountUp({ target }: { target: number }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const step = Math.ceil(target / 20);
    let current = 0;
    const t = setInterval(() => {
      current = Math.min(current + step, target);
      setCount(current);
      if (current >= target) clearInterval(t);
    }, 50);
    return () => clearInterval(t);
  }, [target]);
  return <>{count}</>;
}

export default function Home() {
  const [stats, setStats] = useState({ patients: 1, reports: 2, medications: 3, chatSessions: 12 });
  const [backendStatus, setBackendStatus] = useState<'connected' | 'offline' | 'checking'>('checking');

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      await ensureAuth();
      const health = await api.checkHealth();
      if (health.status === 'ok') setBackendStatus('connected');
      const pList = await api.patients.list();
      if (pList.total !== undefined) setStats((p) => ({ ...p, patients: pList.total }));
      const rList = await api.reports.list();
      if (Array.isArray(rList)) setStats((p) => ({ ...p, reports: rList.length }));
    } catch {
      setBackendStatus('offline');
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-6">
      {/* ── Hero Banner ── */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative overflow-hidden rounded-3xl border border-blue-500/20 bg-gradient-to-br from-blue-950/60 via-indigo-950/50 to-violet-950/40 p-7 shadow-xl"
      >
        {/* Animated grid bg */}
        <div className="absolute inset-0 opacity-5">
          <svg width="100%" height="100%">
            <defs>
              <pattern id="hero-grid" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#hero-grid)" />
          </svg>
        </div>
        {/* Glow orbs */}
        <div className="absolute top-[-30px] right-[-30px] w-48 h-48 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="absolute bottom-[-20px] left-[-20px] w-36 h-36 rounded-full bg-indigo-500/10 blur-2xl" />

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-3 py-1 rounded-full bg-blue-500/20 border border-blue-500/30 text-blue-300 text-[11px] font-bold tracking-wider uppercase flex items-center gap-1.5">
                <Star className="h-3 w-3" />
                Multi-Agent AI Platform
              </span>
            </div>
            <h1 className="text-3xl md:text-4xl font-black tracking-tight text-white">
              MedAssist AI
              <span className="block text-lg font-medium text-blue-200/70 mt-1">Health Operations Center</span>
            </h1>
            <p className="text-sm text-blue-100/60 mt-2 max-w-lg">
              Autonomous clinical agents for triage, report parsing, drug safety & real-time biometric monitoring
            </p>
          </div>

          <div className="flex flex-col items-start md:items-end gap-3">
            {/* Backend status */}
            <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-4 py-2 rounded-full text-xs font-semibold backdrop-blur-sm">
              <Server className="h-3.5 w-3.5 text-blue-300" />
              <span className="text-white/60">FastAPI:</span>
              {backendStatus === 'connected' && (
                <span className="text-emerald-400 flex items-center gap-1 font-bold">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Online
                </span>
              )}
              {backendStatus === 'offline' && (
                <span className="text-amber-400 flex items-center gap-1 font-bold">
                  <AlertTriangle className="h-3.5 w-3.5" /> Standby
                </span>
              )}
              {backendStatus === 'checking' && (
                <span className="text-white/40 flex items-center gap-1">
                  <RefreshCw className="h-3 w-3 animate-spin" /> Checking...
                </span>
              )}
            </div>

            <Link
              href="/chat"
              className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:from-blue-400 hover:to-indigo-500 px-5 py-2.5 text-sm font-bold shadow-lg shadow-blue-500/30 transition-all hover:scale-105 active:scale-95"
            >
              <MessageSquarePlus className="h-4 w-4" />
              Start AI Consultation
            </Link>
          </div>
        </div>
      </motion.div>

      {/* ── Stats Cards ── */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statsConfig.map((stat, idx) => (
          <motion.div
            key={stat.key}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + idx * 0.08, duration: 0.4 }}
            className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/60 p-5 space-y-3 shadow-sm hover:shadow-md transition-shadow group"
          >
            {/* BG glow */}
            <div className={`absolute top-0 right-0 w-24 h-24 rounded-full bg-gradient-to-br ${stat.gradient} opacity-5 blur-2xl group-hover:opacity-10 transition-opacity`} />

            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground">{stat.label}</span>
              <div className={`p-2.5 rounded-xl bg-gradient-to-br ${stat.gradient} shadow-sm`}>
                <stat.icon className="h-4 w-4 text-white" />
              </div>
            </div>
            <div className="text-4xl font-black text-foreground tabular-nums">
              <CountUp target={stats[stat.key as keyof typeof stats]} />
            </div>
            <div className="flex items-center gap-1 text-[11px] text-emerald-500 font-semibold">
              <TrendingUp className="h-3 w-3" />
              <span>Live from FastAPI</span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* ── Feature Grid ── */}
      <div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="flex items-center gap-2 mb-4"
        >
          <Zap className="h-4 w-4 text-amber-400" />
          <h2 className="font-bold text-foreground text-sm">Clinical Agent Modules</h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {featureCards.map((card, idx) => (
            <motion.div
              key={card.href}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 + idx * 0.07, duration: 0.4 }}
            >
              <Link
                href={card.href}
                className={`group relative overflow-hidden flex flex-col rounded-2xl border border-border/60 bg-card/60 p-5 space-y-3 hover:border-border transition-all hover:shadow-lg ${card.glow} hover:shadow-md`}
              >
                {/* Hover gradient overlay */}
                <div className={`absolute inset-0 opacity-0 group-hover:opacity-5 transition-opacity bg-gradient-to-br ${card.gradient}`} />

                <div className="flex items-start justify-between relative z-10">
                  <div className={`p-3 rounded-xl bg-gradient-to-br ${card.gradient} shadow-md`}>
                    <card.icon className="h-5 w-5 text-white" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-full bg-gradient-to-r ${card.gradient} text-white text-[10px] font-black uppercase`}>
                      {card.badge}
                    </span>
                    <motion.div
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      whileHover={{ x: 2 }}
                    >
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </motion.div>
                  </div>
                </div>

                <div className="relative z-10">
                  <h3 className="font-bold text-foreground text-sm group-hover:text-foreground transition-colors">{card.title}</h3>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{card.desc}</p>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── AI Agent Status Row ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="flex flex-wrap gap-2"
      >
        {['Symptom Analyzer', 'Drug Safety Engine', 'OCR Parser', 'Emergency Dispatcher', 'Biometric Monitor', 'Pharmacy Locator'].map((agent, i) => (
          <div key={agent} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-card/60 border border-border/50 text-[11px] font-medium text-muted-foreground">
            <motion.span
              className="h-1.5 w-1.5 rounded-full bg-emerald-500"
              animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.3 }}
            />
            {agent}
          </div>
        ))}
      </motion.div>
    </div>
  );
}
