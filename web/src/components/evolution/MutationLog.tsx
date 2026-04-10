import type { MutationLogEntry } from '@/types';

interface MutationLogProps {
  entries: MutationLogEntry[];
}

const OPERATION_COLORS: Record<string, string> = {
  crossover: 'text-[var(--color-blue)]',
  mutate: 'text-[var(--color-purple)]',
  elite_preserve: 'text-[var(--color-profit)]',
  selection: 'text-[var(--color-warn)]',
  random_insert: 'text-[var(--color-info)]',
};

function getScoreDeltaColor(delta: number): string {
  if (delta > 0) return 'text-[var(--color-profit)]';
  if (delta < 0) return 'text-[var(--color-loss)]';
  return 'text-[var(--text-disabled)]';
}

function formatScoreDelta(delta: number): string {
  if (delta > 0) return `+${delta.toFixed(2)}`;
  if (delta < 0) return delta.toFixed(2);
  return '0.00';
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export function MutationLog({ entries }: MutationLogProps) {
  if (entries.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden h-full">
        <div className="px-3 py-2 border-b border-[var(--border)]">
          <h3 className="text-sm font-medium text-[var(--text-primary)]">Mutation Log</h3>
        </div>
        <div className="flex items-center justify-center py-12">
          <p className="text-xs text-[var(--text-disabled)]">No mutation records yet</p>
        </div>
      </div>
    );
  }

  const displayed = entries.slice(-20);

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden flex flex-col h-full">
      <div className="px-3 py-2 border-b border-[var(--border)] flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">Mutation Log</h3>
        <span className="text-xs text-[var(--text-disabled)]">{entries.length} records</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {displayed.map((entry, idx) => (
          <div
            key={`${entry.generation}-${idx}`}
            className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-[var(--bg-hover)] transition-colors"
          >
            <div className="flex flex-col items-center shrink-0 mt-0.5">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-purple)]" />
              {idx < displayed.length - 1 && (
                <div className="w-px h-full bg-[var(--border)] mt-0.5" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-[var(--text-secondary)]">
                  G{entry.generation}
                </span>
                <span className={`text-xs font-medium ${OPERATION_COLORS[entry.operation] ?? 'text-[var(--text-primary)]'}`}>
                  {entry.operation}
                </span>
                <span className={`text-xs font-mono ml-auto ${getScoreDeltaColor(entry.score_delta)}`}>
                  {formatScoreDelta(entry.score_delta)}
                </span>
              </div>
              <p className="text-xs text-[var(--text-disabled)] truncate">{entry.description}</p>
            </div>
            <span className="text-[10px] text-[var(--text-disabled)] shrink-0 mt-0.5">
              {formatTime(entry.timestamp)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
