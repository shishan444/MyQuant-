import type { PopulationState } from '@/types';

interface PopulationStatusProps {
  population: PopulationState;
}

function getDiversityLevel(value: number): { label: string; color: string; bgColor: string } {
  if (value >= 0.7) return { label: 'High', color: 'text-[var(--color-profit)]', bgColor: 'bg-[var(--color-profit)]' };
  if (value >= 0.4) return { label: 'Medium', color: 'text-[var(--color-warn)]', bgColor: 'bg-[var(--color-warn)]' };
  return { label: 'Low', color: 'text-[var(--color-loss)]', bgColor: 'bg-[var(--color-loss)]' };
}

export function PopulationStatus({ population }: PopulationStatusProps) {
  const diversity = getDiversityLevel(population.diversity);
  const maxScore = Math.max(...population.score_distribution, 1);
  const barCount = Math.min(population.score_distribution.length, 20);

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--border)]">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">Population Status</h3>
      </div>
      <div className="p-3 space-y-3">
        {/* Diversity Bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">Diversity</span>
            <span className={`text-xs font-medium ${diversity.color}`}>
              {(population.diversity * 100).toFixed(0)}% ({diversity.label})
            </span>
          </div>
          <div className="h-2 bg-[var(--bg-primary)] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${diversity.bgColor}`}
              style={{ width: `${population.diversity * 100}%` }}
            />
          </div>
        </div>

        {/* Score Distribution */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">Score Distribution</span>
            <span className="text-xs text-[var(--text-disabled)]">
              {population.elite_count} elite / {population.total_count} total
            </span>
          </div>
          <div className="flex items-end gap-px h-10 bg-[var(--bg-primary)] rounded p-1">
            {population.score_distribution.slice(0, barCount).map((score, idx) => (
              <div
                key={idx}
                className="flex-1 rounded-sm transition-all duration-300"
                style={{
                  height: `${(score / maxScore) * 100}%`,
                  backgroundColor: score >= 80 ? '#00C853' : score >= 60 ? '#2196F3' : score >= 40 ? '#FFD600' : '#FF1744',
                  minHeight: '2px',
                }}
              />
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-[var(--text-disabled)]">
            <span>Low</span>
            <span>High</span>
          </div>
        </div>
      </div>
    </div>
  );
}
