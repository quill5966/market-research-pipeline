/**
 * AppBar — persistent top bar with logo, title, and contextual actions.
 */

import { useNavigate } from 'react-router-dom';
import { clearPasscode } from '../api/client';

interface AppBarProps {
  /** Action buttons to render on the right side */
  actions?: React.ReactNode;
}

export function AppBar({ actions }: AppBarProps) {
  const navigate = useNavigate();

  function handleSignOut() {
    clearPasscode();
    // Full reload so PasscodeGate re-renders against the now-empty session.
    window.location.reload();
  }

  return (
    <header className="app-bar">
      <div
        className="app-brand"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <span className="logo-mark">M</span>
        Market Research
      </div>
      <div className="app-bar-actions">
        {actions}
        <button
          className="btn btn-ghost"
          onClick={handleSignOut}
          title="Forget the passcode for this session"
        >
          <i className="ti ti-logout" /> Sign out
        </button>
      </div>
    </header>
  );
}
