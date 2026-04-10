import { Dna } from 'lucide-react';

export function Evolution() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh]">
      <Dna className="w-16 h-16 text-[var(--text-disabled)] mb-4" />
      <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
        Evolution Center
      </h2>
      <p className="text-[var(--text-secondary)] text-sm">
        Coming soon - Genetic evolution for strategy optimization
      </p>
    </div>
  );
}
