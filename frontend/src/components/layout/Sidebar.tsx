'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  MessageSquarePlus,
  FileText,
  Pill,
  Activity,
  History,
  User,
  Settings,
  Siren,
  Dna,
  Sparkles,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  { name: 'AI Consultation', href: '/chat', icon: MessageSquarePlus, color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
  { name: 'Medical Reports', href: '/reports', icon: FileText, color: 'text-violet-400', bg: 'bg-violet-500/10' },
  { name: 'Medicines & Order', href: '/medicines', icon: Pill, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  { name: 'Health Analytics', href: '/analytics', icon: Activity, color: 'text-rose-400', bg: 'bg-rose-500/10' },
  { name: 'History', href: '/history', icon: History, color: 'text-amber-400', bg: 'bg-amber-500/10' },
  { name: 'Profile', href: '/profile', icon: User, color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
  { name: 'Settings', href: '/settings', icon: Settings, color: 'text-slate-400', bg: 'bg-slate-500/10' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full w-64 flex-col border-r border-border/50 bg-card/40 backdrop-blur-xl relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute top-0 left-0 w-full h-40 bg-gradient-to-b from-blue-600/5 to-transparent pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-full h-32 bg-gradient-to-t from-indigo-600/5 to-transparent pointer-events-none" />

      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-5 border-b border-border/50 relative z-10">
        <motion.div
          animate={{ rotate: [0, 360] }}
          transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
          className="p-1.5 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-md shadow-blue-500/20"
        >
          <Dna className="h-4 w-4 text-white" />
        </motion.div>
        <div>
          <span className="text-base font-black bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent tracking-tight">
            MedAssist
          </span>
          <span className="text-base font-black text-foreground"> AI</span>
        </div>
        <motion.div
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="ml-auto"
        >
          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
        </motion.div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-4 relative z-10 overflow-y-auto">
        {navigation.map((item, idx) => {
          const isActive = pathname === item.href;
          return (
            <motion.div
              key={item.name}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05, duration: 0.3 }}
            >
              <Link
                href={item.href}
                className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-gradient-to-r from-blue-600/20 to-indigo-600/10 text-foreground border border-blue-500/20 shadow-sm'
                    : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
                }`}
              >
                {/* Active indicator bar */}
                {isActive && (
                  <motion.div
                    layoutId="activeNav"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-gradient-to-b from-blue-400 to-indigo-500 rounded-full"
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}

                <div className={`p-1.5 rounded-lg ${isActive ? item.bg : 'bg-transparent group-hover:' + item.bg} transition-all`}>
                  <item.icon className={`h-4 w-4 ${isActive ? item.color : 'text-muted-foreground group-hover:' + item.color} transition-colors`} />
                </div>
                <span>{item.name}</span>

                {/* Active glow */}
                {isActive && (
                  <motion.span
                    className="ml-auto h-1.5 w-1.5 rounded-full bg-blue-400"
                    animate={{ scale: [1, 1.3, 1], opacity: [1, 0.6, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                )}
              </Link>
            </motion.div>
          );
        })}
      </nav>

      {/* Emergency link */}
      <div className="p-3 border-t border-border/50 relative z-10">
        <motion.div
          animate={{ boxShadow: ['0 0 0 rgba(239,68,68,0)', '0 0 16px rgba(239,68,68,0.3)', '0 0 0 rgba(239,68,68,0)'] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="rounded-xl overflow-hidden"
        >
          <Link
            href="/emergency"
            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold transition-all ${
              pathname === '/emergency'
                ? 'bg-rose-600 text-white shadow-lg shadow-rose-500/30'
                : 'text-rose-400 hover:bg-rose-500/10 border border-rose-500/20'
            }`}
          >
            <div className="p-1.5 rounded-lg bg-rose-500/20">
              <Siren className={`h-4 w-4 ${pathname === '/emergency' ? 'text-white' : 'text-rose-400'} ${pathname !== '/emergency' ? 'animate-pulse' : ''}`} />
            </div>
            Emergency SOS
            {pathname !== '/emergency' && (
              <span className="ml-auto px-1.5 py-0.5 rounded-full bg-rose-500 text-white text-[9px] font-black animate-pulse">
                24/7
              </span>
            )}
          </Link>
        </motion.div>

        <div className="mt-3 px-2 text-[10px] text-muted-foreground/50 text-center">
          MedAssist AI v2.0 · HIPAA Compliant
        </div>
      </div>
    </div>
  );
}
