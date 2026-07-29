"use client";

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Bell, Moon, Sun, LogOut, Settings, User, ShieldCheck, ChevronDown } from 'lucide-react';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/button';
import { logout } from '@/lib/api';
import { EmergencyPanicButton } from '@/components/ui/EmergencyPanicButton';
import { puterSignOut, getUserFromLocal, clearUserFromLocal, puterGetUser, puterIsSignedIn, type PuterUser } from '@/lib/auth';

export function Topbar() {
  const { setTheme, theme } = useTheme();
  const [showMenu, setShowMenu] = useState(false);
  const [user, setUser] = useState<PuterUser | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Load user info on mount
  useEffect(() => {
    const localUser = getUserFromLocal();
    if (localUser) {
      setUser(localUser);
      return;
    }
    // Try to fetch from Puter if signed in
    puterIsSignedIn().then((signedIn) => {
      if (signedIn) {
        puterGetUser().then((u) => {
          if (u) setUser(u);
        });
      }
    });
  }, []);

  // Close menu on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleLogout = async () => {
    setShowMenu(false);
    try {
      await puterSignOut();
    } catch {}
    clearUserFromLocal();
    logout(); // clears token and redirects to /login
  };

  // Get display name from user
  const displayName = user?.profile?.name || user?.username || 'Patient';
  const displayEmail = user?.email || (user?.username ? `${user.username}@puter` : 'Signed in');
  const initials = displayName.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  const avatarUrl = user?.profile?.picture;

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-border/50 bg-background/80 backdrop-blur-xl px-6 relative z-50">
      {/* Search */}
      <div className="flex flex-1 items-center gap-4">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="search"
            placeholder="Search symptoms, reports, medications..."
            className="flex h-9 w-full rounded-full border border-border/60 bg-card/50 px-3 py-1 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500/40 pl-9 transition-all"
          />
        </div>
      </div>

      {/* Emergency Panic Button */}
      <EmergencyPanicButton />

      <div className="flex items-center gap-2">
        {/* Notifications */}
        <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground rounded-full relative">
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-rose-500" />
        </Button>

        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground rounded-full"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>

        {/* User dropdown */}
        <div className="relative" ref={menuRef}>
          <motion.button
            onClick={() => setShowMenu(!showMenu)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            className="flex items-center gap-2.5 pl-1 pr-3 py-1 rounded-full bg-card/80 border border-border/60 hover:border-border transition-all shadow-sm"
          >
            {/* Avatar */}
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={displayName}
                className="w-7 h-7 rounded-full object-cover ring-2 ring-blue-500/30"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-[11px] font-black shadow-md">
                {initials}
              </div>
            )}
            <div className="hidden sm:block text-left">
              <div className="text-xs font-bold text-foreground leading-tight truncate max-w-[100px]">{displayName}</div>
            </div>
            <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${showMenu ? 'rotate-180' : ''}`} />
          </motion.button>

          <AnimatePresence>
            {showMenu && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: -8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -8 }}
                transition={{ type: 'spring', stiffness: 350, damping: 28 }}
                className="absolute right-0 mt-2 w-72 rounded-2xl border border-border/60 bg-card/95 backdrop-blur-xl p-3 shadow-2xl space-y-2 z-50"
              >
                {/* User info card */}
                <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-blue-600/10 to-indigo-600/10 border border-blue-500/10">
                  {avatarUrl ? (
                    <img
                      src={avatarUrl}
                      alt={displayName}
                      className="w-10 h-10 rounded-full object-cover ring-2 ring-blue-500/30 shrink-0"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-black shrink-0 shadow-md">
                      {initials}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="font-bold text-sm text-foreground truncate">{displayName}</div>
                    <div className="text-[11px] text-muted-foreground truncate">{displayEmail}</div>
                  </div>
                </div>

                {/* Verified badge */}
                <div className="flex items-center gap-1.5 px-2 text-[10px] font-semibold text-emerald-500">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span>Verified · Puter Google Auth</span>
                </div>

                <div className="border-t border-border/50 pt-2 space-y-0.5">
                  <button
                    onClick={() => { setShowMenu(false); router.push('/profile'); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-foreground hover:bg-secondary/60 rounded-xl transition-all"
                  >
                    <User className="h-4 w-4 text-blue-400" />
                    View Profile
                  </button>
                  <button
                    onClick={() => { setShowMenu(false); router.push('/settings'); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-foreground hover:bg-secondary/60 rounded-xl transition-all"
                  >
                    <Settings className="h-4 w-4 text-muted-foreground" />
                    Settings
                  </button>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-bold text-rose-400 hover:bg-rose-500/10 rounded-xl transition-all"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
