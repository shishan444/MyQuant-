import { BookOpen } from 'lucide-react';

export function Library() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh]">
      <BookOpen className="w-16 h-16 text-[var(--text-disabled)] mb-4" />
      <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
        Strategy Library
      </h2>
      <p className="text-[var(--text-secondary)] text-sm">
        Coming soon - Browse and manage your strategy collection
      </p>
    </div>
  );
}
