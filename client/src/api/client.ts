/**
 * API client for the Market Research Pipeline backend.
 * Thin fetch wrapper for /api/runs endpoints.
 *
 * All requests carry the shared passcode (stored in sessionStorage by the
 * PasscodeGate) as `Authorization: Bearer <passcode>`. On a 401 we clear the
 * cached passcode and force the user back through the gate — this is what
 * recovers cleanly from a server-side passcode rotation.
 */

import type { Run, RunRequest } from '../types/models';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const PASSCODE_STORAGE_KEY = 'app_passcode';

export function getPasscode(): string | null {
  try {
    return sessionStorage.getItem(PASSCODE_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setPasscode(value: string): void {
  sessionStorage.setItem(PASSCODE_STORAGE_KEY, value);
}

export function clearPasscode(): void {
  sessionStorage.removeItem(PASSCODE_STORAGE_KEY);
}

function authHeaders(): Record<string, string> {
  const passcode = getPasscode();
  return passcode ? { Authorization: `Bearer ${passcode}` } : {};
}

async function handleResponse(res: Response, fallback: string): Promise<void> {
  if (res.status === 401) {
    // Server rejected us — drop the cached passcode and reload so the gate
    // re-mounts. The throw is mostly defensive; the reload usually wins first.
    clearPasscode();
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
    throw new Error('Authentication required');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || fallback);
  }
}

/** Validate a candidate passcode against the server. Used by PasscodeGate. */
export async function checkPasscode(candidate: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/auth/check`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${candidate}` },
  });
  if (res.status === 401) return false;
  if (!res.ok) {
    throw new Error('Auth check failed');
  }
  return true;
}

export async function createRun(request: RunRequest): Promise<{ id: string }> {
  const res = await fetch(`${API_BASE}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(request),
  });
  await handleResponse(res, 'Failed to create run');
  return res.json();
}

export async function getRun(id: string): Promise<Run> {
  const res = await fetch(`${API_BASE}/api/runs/${id}`, {
    headers: { ...authHeaders() },
  });
  await handleResponse(res, 'Failed to get run');
  return res.json();
}

export async function exportBrief(id: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/runs/${id}/export`, {
    headers: { ...authHeaders() },
  });
  await handleResponse(res, 'Failed to export brief');
  return res.blob();
}
