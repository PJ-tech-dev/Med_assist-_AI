'use client';

import { usePathname } from 'next/navigation';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';

const SHELL_LESS_PATHS = ['/login'];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isShellLess = SHELL_LESS_PATHS.some((p) => pathname.startsWith(p));

  if (isShellLess) {
    // Login page — no sidebar or topbar, full page
    return <div className="h-screen">{children}</div>;
  }

  return (
    <div className="h-screen overflow-hidden flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
