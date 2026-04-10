import { Settings } from 'lucide-react';

export function SettingsPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh]">
      <Settings className="w-16 h-16 text-[var(--text-disabled)] mb-4" />
      <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
        Settings
      </h2>
      <p className="text-[var(--text-secondary)] text-sm">
        Coming soon - Application configuration
      </p>
    </div>
  );
}
