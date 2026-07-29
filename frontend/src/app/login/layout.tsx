import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sign In — MedAssist AI',
  description: 'Sign in with Google to access your MedAssist AI health dashboard.',
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
