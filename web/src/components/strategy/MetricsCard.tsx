interface MetricsCardProps {
  label: string;
  value: string | number;
  color?: 'default' | 'profit' | 'loss' | 'warn' | 'info';
}

const COLOR_MAP = {
  default: 'text-[var(--text-primary)]',
  profit: 'text-[var(--color-profit)]',
  loss: 'text-[var(--color-loss)]',
  warn: 'text-[var(--color-warn)]',
  info: 'text-[var(--color-info)]',
};

export function MetricsCard({ label, value, color = 'default' }: MetricsCardProps) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-3 flex flex-col gap-1">
      <span className="text-xs text-[var(--text-secondary)]">{label}</span>
      <span className={`text-lg font-semibold ${COLOR_MAP[color]}`}>
        {value}
      </span>
    </div>
  );
}
