'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getAuthToken } from '@/lib/api';
import { Dna } from 'lucide-react';
import { motion } from 'framer-motion';

const PUBLIC_PATHS = ['/login'];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
    if (isPublic) {
      setChecking(false);
      return;
    }

    // Swallow Puter.js noisy unhandled rejections for 401 Unauthorized
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      if (event.reason && event.reason.status === 401 && event.reason.message === 'Unauthorized') {
        event.preventDefault(); // Prevent Next.js error overlay
      }
    };
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    const token = getAuthToken();
    if (!token) {
      router.replace('/login');
    } else {
      setChecking(false);
    }

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [pathname, router]);

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  if (isPublic) return <>{children}</>;
  if (checking) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <motion.div
          animate={{ rotate: [0, 360] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
          className="p-3 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600"
        >
          <Dna className="h-7 w-7 text-white" />
        </motion.div>
      </div>
    );
  }

  return <>{children}</>;
}
