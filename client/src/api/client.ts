/**
 * API client for the Market Research Pipeline backend.
 * Thin fetch wrapper for /api/runs endpoints.
 */

import type { Run, RunRequest } from '../types/models';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function createRun(request: RunRequest): Promise<{ id: string }> {
  const res = await fetch(`${API_BASE}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to create run');
  }
  return res.json();
}

export async function getRun(id: string): Promise<Run> {
  const res = await fetch(`${API_BASE}/api/runs/${id}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to get run');
  }
  return res.json();
}

export async function exportBrief(id: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/runs/${id}/export`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to export brief');
  }
  return res.blob();
}
