/**
 * AppBar — persistent top bar with logo, title, and contextual actions.
 */

import { useNavigate } from 'react-router-dom';

interface AppBarProps {
  /** Action buttons to render on the right side */
  actions?: React.ReactNode;
}

export function AppBar({ actions }: AppBarProps) {
  const navigate = useNavigate();

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
      {actions && <div className="app-bar-actions">{actions}</div>}
    </header>
  );
}
