/**
 * PasscodeGate — shared-secret entry screen.
 *
 * Wraps the app's routes. If no passcode is present in sessionStorage, shows
 * an entry form. On submit, validates against POST /api/auth/check; on success
 * stores the passcode and renders the children. On 401 the API client clears
 * sessionStorage and reloads, which brings the user back here.
 *
 * sessionStorage (not localStorage) is intentional: the passcode is forgotten
 * when the browser session ends, which is the closest thing to "log out by
 * closing the tab" without doing real auth.
 */

import { useEffect, useState } from 'react';
import {
  checkPasscode,
  getPasscode,
  setPasscode as savePasscode,
} from '../api/client';

interface PasscodeGateProps {
  children: React.ReactNode;
}

export function PasscodeGate({ children }: PasscodeGateProps) {
  const [authorized, setAuthorized] = useState<boolean>(() => getPasscode() !== null);
  const [candidate, setCandidate] = useState('');
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Listen for auth clears triggered from other tabs / api/client 401 handler.
  useEffect(() => {
    function onStorage() {
      if (getPasscode() === null) setAuthorized(false);
    }
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!candidate.trim() || isChecking) return;
    setIsChecking(true);
    setError(null);
    try {
      const ok = await checkPasscode(candidate.trim());
      if (!ok) {
        setError('Incorrect passcode.');
        setIsChecking(false);
        return;
      }
      savePasscode(candidate.trim());
      setCandidate('');
      setAuthorized(true);
    } catch {
      setError('Could not reach the server. Check your connection.');
      setIsChecking(false);
    }
  }

  if (authorized) return <>{children}</>;

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: '100%',
          maxWidth: 400,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ marginBottom: 8 }}>
          <div
            className="logo-mark"
            style={{ display: 'inline-flex', marginRight: 8, verticalAlign: 'middle' }}
          >
            M
          </div>
          <span style={{ fontSize: 18, fontWeight: 500 }}>Market Research</span>
        </div>

        <div className="field" style={{ marginBottom: 0 }}>
          <div className="field-label">
            <span className="label-text">Passcode</span>
          </div>
          <p className="field-help">
            Enter the shared passcode to access this app.
          </p>
          <input
            className="field-input"
            type="password"
            autoFocus
            autoComplete="current-password"
            value={candidate}
            onChange={(e) => setCandidate(e.target.value)}
            disabled={isChecking}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          disabled={!candidate.trim() || isChecking}
        >
          {isChecking ? (
            <>
              <i className="ti ti-loader-2" style={{ animation: 'spin 1s linear infinite' }} />
              Checking…
            </>
          ) : (
            <>
              <i className="ti ti-lock-open" /> Enter
            </>
          )}
        </button>

        {error && (
          <div className="info-notice" style={{ borderLeft: '3px solid #b91c1c' }}>
            <i className="ti ti-alert-circle" />
            {error}
          </div>
        )}
      </form>
    </div>
  );
}
