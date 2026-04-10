import { useLocation } from 'react-router-dom';
import { Bell } from 'lucide-react';

const pageTitles: Record<string, string> = {
  '/lab': 'Strategy Lab',
  '/evolution': 'Evolution Center',
  '/library': 'Strategy Library',
  '/data': 'Data Management',
  '/settings': 'Settings',
};

export function Header() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'QuantTrader';

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-[var(--border)] bg-[var(--bg-card)]">
      <h1 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h1>
      <div className="flex items-center gap-3">
        <button className="relative p-2 rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[var(--color-loss)] rounded-full" />
        </button>
      </div>
    </header>
  );
}
