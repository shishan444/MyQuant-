import { useState, useEffect, useCallback } from 'react';
import { Save, Loader2, AlertCircle, CheckCircle2, Key, Dna } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/Button';
import { getConfig, updateConfig } from '@/api/strategies';
import type { AppConfig, EvolutionConfig } from '@/types';

// ============================================================
// Default config
// ============================================================

const DEFAULT_EVOLUTION: EvolutionConfig = {
  population_size: 50,
  max_generations: 100,
  parallel_count: 4,
  target_score: 80,
  mutation_rate_early: 0.3,
  mutation_rate_mid: 0.2,
  mutation_rate_late: 0.1,
  stagnation_threshold: 0.5,
  stagnation_generations: 10,
  degradation_generations: 5,
};

// ============================================================
// Tab definition
// ============================================================

type TabKey = 'evolution' | 'api';

const TABS: { key: TabKey; label: string; icon: typeof Dna }[] = [
  { key: 'evolution', label: 'Evolution Config', icon: Dna },
  { key: 'api', label: 'API Keys', icon: Key },
];

// ============================================================
// Evolution config form
// ============================================================

function EvolutionConfigForm({
  config,
  onChange,
}: {
  config: EvolutionConfig;
  onChange: (update: Partial<EvolutionConfig>) => void;
}) {
  return (
    <div className="space-y-6">
      {/* Basic parameters */}
      <section>
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-3">
          Basic Parameters
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <NumberField
            label="Population Size"
            value={config.population_size}
            min={10}
            max={500}
            onChange={(v) => onChange({ population_size: v })}
          />
          <NumberField
            label="Max Generations"
            value={config.max_generations}
            min={10}
            max={1000}
            onChange={(v) => onChange({ max_generations: v })}
          />
          <NumberField
            label="Parallel Count"
            value={config.parallel_count}
            min={1}
            max={16}
            onChange={(v) => onChange({ parallel_count: v })}
          />
          <NumberField
            label="Target Score"
            value={config.target_score}
            min={0}
            max={100}
            step={0.1}
            onChange={(v) => onChange({ target_score: v })}
          />
        </div>
      </section>

      {/* Mutation rates */}
      <section>
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-3">
          Mutation Rate
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <NumberField
            label="Early Phase"
            value={config.mutation_rate_early}
            min={0}
            max={1}
            step={0.01}
            onChange={(v) => onChange({ mutation_rate_early: v })}
          />
          <NumberField
            label="Mid Phase"
            value={config.mutation_rate_mid}
            min={0}
            max={1}
            step={0.01}
            onChange={(v) => onChange({ mutation_rate_mid: v })}
          />
          <NumberField
            label="Late Phase"
            value={config.mutation_rate_late}
            min={0}
            max={1}
            step={0.01}
            onChange={(v) => onChange({ mutation_rate_late: v })}
          />
        </div>
      </section>

      {/* Early stopping */}
      <section>
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-3">
          Early Stopping
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <NumberField
            label="Stagnation Threshold"
            value={config.stagnation_threshold}
            min={0}
            max={10}
            step={0.1}
            onChange={(v) => onChange({ stagnation_threshold: v })}
          />
          <NumberField
            label="Stagnation Generations"
            value={config.stagnation_generations}
            min={1}
            max={50}
            onChange={(v) => onChange({ stagnation_generations: v })}
          />
          <NumberField
            label="Degradation Generations"
            value={config.degradation_generations}
            min={1}
            max={20}
            onChange={(v) => onChange({ degradation_generations: v })}
          />
        </div>
      </section>
    </div>
  );
}

// ============================================================
// API keys form
// ============================================================

function ApiKeysForm({
  apiKey,
  onChange,
}: {
  apiKey: string;
  onChange: (key: string) => void;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
          Claude API Key
        </label>
        <p className="text-xs text-[var(--text-secondary)] mb-2">
          Used for natural language strategy parsing
        </p>
        <div className="relative">
          <input
            type={visible ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => onChange(e.target.value)}
            placeholder="sk-ant-..."
            className="w-full h-9 px-3 pr-16 bg-[var(--bg-primary)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--color-blue)]"
          />
          <button
            type="button"
            onClick={() => setVisible(!visible)}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-0.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            {visible ? 'Hide' : 'Show'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Number input field
// ============================================================

function NumberField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <label className="block text-xs text-[var(--text-secondary)]">
        {label}
      </label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const v = parseFloat(e.target.value);
          if (!isNaN(v) && v >= min && v <= max) {
            onChange(v);
          }
        }}
        className="w-full h-9 px-3 bg-[var(--bg-primary)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--color-blue)]"
      />
    </div>
  );
}

// ============================================================
// Settings page
// ============================================================

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>('evolution');
  const [saveMessage, setSaveMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  // Fetch config
  const {
    data: remoteConfig,
    isLoading,
    error: fetchError,
  } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  });

  // Local form state
  const [evolution, setEvolution] = useState<EvolutionConfig>(
    DEFAULT_EVOLUTION,
  );
  const [claudeApiKey, setClaudeApiKey] = useState('');

  // Sync remote -> local
  useEffect(() => {
    if (remoteConfig) {
      setEvolution(remoteConfig.evolution);
      setClaudeApiKey(remoteConfig.claude_api_key);
    }
  }, [remoteConfig]);

  // On fetch error, keep defaults
  useEffect(() => {
    if (fetchError) {
      setEvolution(DEFAULT_EVOLUTION);
      setClaudeApiKey('');
    }
  }, [fetchError]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (config: Partial<AppConfig>) => updateConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      setSaveMessage({ type: 'success', text: 'Settings saved successfully' });
      setTimeout(() => setSaveMessage(null), 3000);
    },
    onError: (err: Error) => {
      setSaveMessage({
        type: 'error',
        text: err.message || 'Failed to save settings',
      });
    },
  });

  const handleSave = useCallback(() => {
    saveMutation.mutate({ evolution, claude_api_key: claudeApiKey });
  }, [saveMutation, evolution, claudeApiKey]);

  const handleEvolutionChange = useCallback(
    (update: Partial<EvolutionConfig>) => {
      setEvolution((prev) => ({ ...prev, ...update }));
    },
    [],
  );

  return (
    <div className="max-w-3xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Settings
        </h2>
        <Button
          variant="primary"
          size="md"
          disabled={saveMutation.isPending}
          onClick={handleSave}
        >
          {saveMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save
        </Button>
      </div>

      {/* Save message */}
      {saveMessage && (
        <div
          className={`flex items-center gap-2 p-3 rounded-md text-sm ${
            saveMessage.type === 'success'
              ? 'text-[var(--color-profit)] bg-[var(--color-profit)]/10'
              : 'text-[var(--color-loss)] bg-[var(--color-loss)]/10'
          }`}
        >
          {saveMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          <span>{saveMessage.text}</span>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                active
                  ? 'text-[var(--color-blue)] border-[var(--color-blue)]'
                  : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)]'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12 gap-2 text-[var(--text-secondary)]">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading configuration...</span>
        </div>
      )}

      {/* Error state */}
      {fetchError && !isLoading && (
        <div className="flex items-center gap-2 text-[var(--color-warn)] p-3 bg-[var(--color-warn)]/10 rounded-md text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>API unavailable - editing local defaults</span>
        </div>
      )}

      {/* Tab content */}
      {!isLoading && (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-5">
          {activeTab === 'evolution' && (
            <EvolutionConfigForm
              config={evolution}
              onChange={handleEvolutionChange}
            />
          )}
          {activeTab === 'api' && (
            <ApiKeysForm
              apiKey={claudeApiKey}
              onChange={setClaudeApiKey}
            />
          )}
        </div>
      )}
    </div>
  );
}
