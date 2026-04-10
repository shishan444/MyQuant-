import { NavLink } from 'react-router-dom';
import {
  FlaskConical,
  Dna,
  Library,
  Database,
  Settings,
  ChevronsLeft,
  ChevronsRight,
  Activity,
} from 'lucide-react';
import { useAppStore } from '@/stores/app';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/lab', icon: FlaskConical, label: 'Strategy Lab' },
  { to: '/evolution', icon: Dna, label: 'Evolution Center' },
  { to: '/library', icon: Library, label: 'Strategy Library' },
  { to: '/data', icon: Database, label: 'Data Management' },
  { to: '/settings', icon: Settings, label: 'Settings' },
] as const;

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-[var(--bg-card)] border-r border-[var(--border)] transition-all duration-200 shrink-0',
        sidebarCollapsed ? 'w-16' : 'w-[200px]',
      )}
    >
      {/* Header */}
      <div className="flex items-center h-14 px-3 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-md bg-[var(--color-blue)] flex items-center justify-center shrink-0">
            <span className="text-white font-bold text-sm">QT</span>
          </div>
          {!sidebarCollapsed && (
            <span className="text-[var(--text-primary)] font-semibold text-sm truncate">
              QuantTrader
            </span>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-[var(--color-blue)]/15 text-[var(--color-blue)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
                sidebarCollapsed && 'justify-center px-0',
              )
            }
            title={sidebarCollapsed ? item.label : undefined}
          >
            <item.icon className="w-5 h-5 shrink-0" />
            {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Active Evolution Task */}
      {!sidebarCollapsed && (
        <div className="px-3 py-3 border-t border-[var(--border)]">
          <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)] mb-2">
            <Activity className="w-3.5 h-3.5" />
            <span>Active Evolution</span>
          </div>
          <div className="bg-[var(--bg-hover)] rounded-md px-3 py-2">
            <div className="text-xs text-[var(--text-primary)] font-medium">
              BTC Trend Follow
            </div>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-1 bg-[var(--border)] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[var(--color-purple)] rounded-full"
                  style={{ width: '67%' }}
                />
              </div>
              <span className="text-[10px] text-[var(--text-secondary)]">G12/20</span>
            </div>
          </div>
        </div>
      )}

      {/* Collapse Toggle */}
      <div className="border-t border-[var(--border)] p-2">
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center h-8 rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors"
        >
          {sidebarCollapsed ? (
            <ChevronsRight className="w-4 h-4" />
          ) : (
            <ChevronsLeft className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
