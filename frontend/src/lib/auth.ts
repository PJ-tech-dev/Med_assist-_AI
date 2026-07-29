/**
 * Puter.js Auth Integration — Google OAuth via Puter
 * No client ID needed — Puter handles OAuth internally.
 */

export interface PuterUser {
  username: string;
  email?: string;
  uuid?: string;
  profile?: {
    name?: string;
    picture?: string;
  };
}

// ── Check if user is signed in via Puter ──────────────────────
export async function puterIsSignedIn(): Promise<boolean> {
  try {
    if (typeof window === 'undefined') return false;
    const puter = (window as any).puter;
    if (!puter?.auth) return false;
    return await puter.auth.isSignedIn();
  } catch {
    return false;
  }
}

// ── Get the signed-in Puter user ──────────────────────────────
export async function puterGetUser(): Promise<PuterUser | null> {
  try {
    if (typeof window === 'undefined') return null;
    const puter = (window as any).puter;
    if (!puter?.auth) return null;
    const signedIn = await puter.auth.isSignedIn();
    if (!signedIn) return null;
    const user = await puter.auth.getUser();
    return user as PuterUser;
  } catch {
    return null;
  }
}

// ── Sign in with Puter (Google popup) ────────────────────────
export async function puterSignIn(): Promise<PuterUser | null> {
  try {
    const puter = (window as any).puter;
    if (!puter?.auth) throw new Error('Puter.js not loaded');
    await puter.auth.signIn();
    const user = await puter.auth.getUser();
    return user as PuterUser;
  } catch (err: any) {
    console.error('Puter sign-in failed:', err);
    throw err;
  }
}

// ── Sign out from Puter ───────────────────────────────────────
export async function puterSignOut(): Promise<void> {
  try {
    const puter = (window as any).puter;
    if (!puter?.auth) return;
    await puter.auth.signOut();
  } catch (err) {
    console.error('Puter sign-out failed:', err);
  }
}

// ── Store user info in localStorage for app use ───────────────
export function saveUserToLocal(user: PuterUser): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('medassist_user', JSON.stringify(user));
  // Also set a fake token so ensureAuth() is satisfied
  const fakeToken = `puter_${user.uuid || user.username}_${Date.now()}`;
  localStorage.setItem('medassist_token', fakeToken);
}

export function getUserFromLocal(): PuterUser | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('medassist_user');
    if (!raw) return null;
    return JSON.parse(raw) as PuterUser;
  } catch {
    return null;
  }
}

export function clearUserFromLocal(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('medassist_user');
  localStorage.removeItem('medassist_token');
}
