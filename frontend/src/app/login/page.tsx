'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Mail, Lock, User as UserIcon, ArrowRight,
  ShieldCheck, AlertCircle, Dna, Sparkles,
  HeartPulse, Brain, Activity, RefreshCw, LogIn, UserPlus
} from 'lucide-react';
import { setAuthToken, getApiBaseUrl, getAuthToken } from '@/lib/api';
import {
  puterIsSignedIn, puterSignIn, puterGetUser,
  saveUserToLocal, getUserFromLocal
} from '@/lib/auth';

// ── Google "G" Icon SVG ───────────────────────────────────────
function GoogleIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

// ── Floating orbs background ──────────────────────────────────
function FloatingOrbs() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <motion.div
        className="absolute top-1/4 left-1/4 w-80 h-80 rounded-full bg-blue-600/8 blur-3xl"
        animate={{ x: [0, 20, 0], y: [0, -15, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full bg-indigo-600/6 blur-3xl"
        animate={{ x: [0, -15, 0], y: [0, 20, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
      />
      <motion.div
        className="absolute top-2/3 left-1/2 w-60 h-60 rounded-full bg-violet-600/5 blur-3xl"
        animate={{ scale: [1, 1.1, 1] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
      />
    </div>
  );
}

// ── Feature badges shown beside the card ─────────────────────
const features = [
  { icon: Brain, label: 'Multi-Agent AI', desc: 'Clinical diagnosis & drug safety' },
  { icon: HeartPulse, label: 'Live Vitals', desc: 'Bluetooth biometric streaming' },
  { icon: Activity, label: 'OCR Reports', desc: 'Instant lab value extraction' },
  { icon: ShieldCheck, label: 'HIPAA Secure', desc: 'Google-auth encrypted access' },
];

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'signin' | 'register'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [puterReady, setPuterReady] = useState(false);

  // Check if already signed in
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      router.push('/');
      return;
    }
    // Wait for Puter.js to load
    const checkPuter = setInterval(() => {
      if (typeof window !== 'undefined' && (window as any).puter?.auth) {
        setPuterReady(true);
        clearInterval(checkPuter);
        // Check if already signed into Puter
        puterIsSignedIn().then((signedIn) => {
          if (signedIn) {
            puterGetUser().then((user) => {
              if (user) {
                saveUserToLocal(user);
                router.push('/');
              }
            });
          }
        });
      }
    }, 300);
    return () => clearInterval(checkPuter);
  }, [router]);

  // ── Google Sign-in via Puter ──────────────────────────────
  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setError(null);
    try {
      const user = await puterSignIn();
      if (user) {
        saveUserToLocal(user);
        router.push('/');
      } else {
        throw new Error('Google sign-in cancelled or failed.');
      }
    } catch (err: any) {
      setError(err.message || 'Google sign-in failed. Please try again.');
    } finally {
      setGoogleLoading(false);
    }
  };

  // ── Email/Password via FastAPI ────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError(null);

    const baseUrl = getApiBaseUrl();
    const endpoint = mode === 'register'
      ? `${baseUrl}/auth/register`
      : `${baseUrl}/auth/login`;

    try {
      const payload = mode === 'register'
        ? { email, password, full_name: fullName }
        : { email, password };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Authentication failed');

      if (data.access_token) {
        setAuthToken(data.access_token);
        // Persist user info
        const userInfo = {
          username: email.split('@')[0],
          email,
          uuid: data.user_id || undefined,
          profile: { name: fullName || email.split('@')[0] },
        };
        localStorage.setItem('medassist_user', JSON.stringify(userInfo));
        router.push('/');
      } else {
        throw new Error('Token not returned from server');
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden p-4">
      <FloatingOrbs />

      {/* Neural grid background */}
      <div className="absolute inset-0 opacity-[0.025] pointer-events-none">
        <svg width="100%" height="100%">
          <defs>
            <pattern id="auth-grid" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="white" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#auth-grid)" />
        </svg>
      </div>

      <div className="relative z-10 w-full max-w-5xl mx-auto flex flex-col lg:flex-row gap-10 items-center">

        {/* ── Left: Brand Panel ── */}
        <motion.div
          initial={{ opacity: 0, x: -40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="flex-1 hidden lg:flex flex-col gap-8"
        >
          {/* Logo */}
          <div className="flex items-center gap-4">
            <motion.div
              animate={{ rotate: [0, 360] }}
              transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
              className="p-3 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-xl shadow-blue-500/30"
            >
              <Dna className="h-8 w-8 text-white" />
            </motion.div>
            <div>
              <h1 className="text-3xl font-black text-foreground tracking-tight">
                MedAssist <span className="bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">AI</span>
              </h1>
              <p className="text-sm text-muted-foreground">Multi-Agent Healthcare Platform</p>
            </div>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-foreground leading-tight">
              Your clinical AI assistant,<br />
              <span className="text-blue-400">always by your side.</span>
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed max-w-sm">
              Sign in with Google to access real-time symptom analysis, drug safety checks, lab report parsing, and emergency dispatch.
            </p>
          </div>

          {/* Feature list */}
          <div className="grid grid-cols-1 gap-3">
            {features.map((f, i) => (
              <motion.div
                key={f.label}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + i * 0.1 }}
                className="flex items-center gap-3 p-3 rounded-2xl bg-card/40 border border-border/50 backdrop-blur-sm"
              >
                <div className="p-2 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 border border-blue-500/20">
                  <f.icon className="h-4 w-4 text-blue-400" />
                </div>
                <div>
                  <div className="text-xs font-bold text-foreground">{f.label}</div>
                  <div className="text-[10px] text-muted-foreground">{f.desc}</div>
                </div>
              </motion.div>
            ))}
          </div>

          <div className="flex items-center gap-2 text-[11px] text-muted-foreground/60">
            <ShieldCheck className="h-4 w-4 text-emerald-500/60" />
            HIPAA-compliant · End-to-end encrypted · SOC 2 Type II
          </div>
        </motion.div>

        {/* ── Right: Auth Card ── */}
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="w-full max-w-md"
        >
          <div className="bg-card/80 backdrop-blur-xl border border-border/60 rounded-3xl shadow-2xl p-8 space-y-6">

            {/* Card Header */}
            <div className="space-y-1 text-center lg:text-left">
              <div className="flex items-center gap-2 justify-center lg:justify-start mb-3 lg:hidden">
                <div className="p-2 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600">
                  <Dna className="h-5 w-5 text-white" />
                </div>
                <span className="font-black text-foreground text-lg">MedAssist AI</span>
              </div>
              <h2 className="text-xl font-black text-foreground">
                {mode === 'signin' ? 'Welcome back' : 'Create your account'}
              </h2>
              <p className="text-xs text-muted-foreground">
                {mode === 'signin'
                  ? 'Sign in to your health dashboard'
                  : 'Join MedAssist AI for free'}
              </p>
            </div>

            {/* Error */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/25 text-rose-400 text-xs flex items-center gap-2"
                >
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Google Sign-In Button ── */}
            <motion.button
              onClick={handleGoogleSignIn}
              disabled={googleLoading || !puterReady}
              whileHover={puterReady && !googleLoading ? { scale: 1.02, y: -1 } : undefined}
              whileTap={puterReady && !googleLoading ? { scale: 0.98 } : undefined}
              className="w-full flex items-center justify-center gap-3 py-3.5 px-5 rounded-2xl border-2 border-border/70 bg-card hover:bg-secondary/60 hover:border-border transition-all font-bold text-sm text-foreground shadow-sm disabled:opacity-60 disabled:cursor-not-allowed group"
            >
              {googleLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
                  <span className="text-muted-foreground">Connecting to Google...</span>
                </>
              ) : !puterReady ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
                  <span className="text-muted-foreground text-xs">Loading auth...</span>
                </>
              ) : (
                <>
                  <GoogleIcon size={20} />
                  <span>Continue with Google</span>
                </>
              )}
            </motion.button>

            {/* Divider */}
            <div className="relative flex items-center">
              <div className="flex-1 border-t border-border/50" />
              <span className="mx-3 text-[11px] text-muted-foreground/60 font-medium">or continue with email</span>
              <div className="flex-1 border-t border-border/50" />
            </div>

            {/* Email/Password Form */}
            <form onSubmit={handleSubmit} className="space-y-3.5">
              <AnimatePresence>
                {mode === 'register' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <label className="block text-xs font-semibold text-foreground mb-1.5">Full Name</label>
                    <div className="relative">
                      <UserIcon className="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground" />
                      <input
                        type="text"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="Johnathan Doe"
                        className="w-full rounded-xl border border-border/60 bg-background pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500/40 transition-all"
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-border/60 bg-background pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500/40 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-border/60 bg-background pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500/40 transition-all"
                  />
                </div>
              </div>

              <motion.button
                type="submit"
                disabled={loading}
                whileHover={!loading ? { scale: 1.02, y: -1 } : undefined}
                whileTap={!loading ? { scale: 0.98 } : undefined}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-sm transition-all shadow-lg shadow-blue-500/25 disabled:opacity-60 disabled:cursor-not-allowed mt-1"
              >
                {loading ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Authenticating...</span>
                  </>
                ) : mode === 'signin' ? (
                  <>
                    <LogIn className="h-4 w-4" />
                    <span>Sign In to Dashboard</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                ) : (
                  <>
                    <UserPlus className="h-4 w-4" />
                    <span>Create Account</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </motion.button>
            </form>

            {/* Mode toggle */}
            <div className="text-center text-xs text-muted-foreground">
              {mode === 'signin' ? (
                <>
                  Don&apos;t have an account?{' '}
                  <button
                    onClick={() => { setMode('register'); setError(null); }}
                    className="text-blue-400 font-bold hover:text-blue-300 transition-colors"
                  >
                    Register for free
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{' '}
                  <button
                    onClick={() => { setMode('signin'); setError(null); }}
                    className="text-blue-400 font-bold hover:text-blue-300 transition-colors"
                  >
                    Sign in
                  </button>
                </>
              )}
            </div>

            {/* Security badge */}
            <div className="flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground/50 pt-1 border-t border-border/30">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-500/60" />
              <span>Secured by Puter.js · Google OAuth 2.0 · HIPAA Compliant</span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
