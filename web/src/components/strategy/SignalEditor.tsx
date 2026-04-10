import { Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { SignalGene, SignalRole, ConditionType } from '@/types';

const INDICATORS = [
  'RSI', 'MACD', 'EMA', 'SMA', 'BB', 'ATR', 'Stochastic',
  'CCI', 'ROC', 'OBV', 'CMF', 'MFI', 'ADX', 'VWAP',
  'WMA', 'DEMA', 'TEMA', 'PSAR',
] as const;

const CONDITIONS_BY_INDICATOR: Record<string, ConditionType[]> = {
  RSI: ['lt', 'gt', 'le', 'ge'],
  MACD: ['cross_above', 'cross_below', 'gt', 'lt'],
  EMA: ['price_above', 'price_below', 'cross_above', 'cross_below'],
  SMA: ['price_above', 'price_below', 'cross_above', 'cross_below'],
  BB: ['price_above', 'price_below'],
  ATR: ['gt', 'lt'],
  Stochastic: ['lt', 'gt', 'le', 'ge'],
  CCI: ['gt', 'lt', 'le', 'ge'],
  ROC: ['gt', 'lt', 'cross_above', 'cross_below'],
  OBV: ['gt', 'lt', 'cross_above', 'cross_below'],
  CMF: ['gt', 'lt'],
  MFI: ['lt', 'gt', 'le', 'ge'],
  ADX: ['gt', 'lt'],
  VWAP: ['price_above', 'price_below'],
  WMA: ['price_above', 'price_below', 'cross_above', 'cross_below'],
  DEMA: ['price_above', 'price_below', 'cross_above', 'cross_below'],
  TEMA: ['price_above', 'price_below', 'cross_above', 'cross_below'],
  PSAR: ['price_above', 'price_below'],
};

const DEFAULT_CONDITIONS: ConditionType[] = ['gt', 'lt'];

const CONDITION_LABELS: Record<ConditionType, string> = {
  gt: '>',
  lt: '<',
  ge: '>=',
  le: '<=',
  cross_above: 'Cross Above',
  cross_below: 'Cross Below',
  price_above: 'Price Above',
  price_below: 'Price Below',
};

const ROLE_LABELS: Record<SignalRole, string> = {
  entry_trigger: 'Entry Trigger',
  entry_guard: 'Entry Guard',
  exit_trigger: 'Exit Trigger',
  exit_guard: 'Exit Guard',
};

const DEFAULT_PARAMS: Record<string, Record<string, number>> = {
  RSI: { period: 14 },
  MACD: { fast: 12, slow: 26, signal: 9 },
  EMA: { period: 20 },
  SMA: { period: 20 },
  BB: { period: 20, std: 2 },
  ATR: { period: 14 },
  Stochastic: { k_period: 14, d_period: 3 },
  CCI: { period: 20 },
  ROC: { period: 12 },
  OBV: {},
  CMF: { period: 20 },
  MFI: { period: 14 },
  ADX: { period: 14 },
  VWAP: {},
  WMA: { period: 20 },
  DEMA: { period: 20 },
  TEMA: { period: 20 },
  PSAR: { step: 0.02, max: 0.2 },
};

interface SignalEditorProps {
  title: string;
  logicLabel: string;
  signals: SignalGene[];
  allowedRoles: SignalRole[];
  onChange: (signals: SignalGene[]) => void;
}

function generateId(): string {
  return `sig_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function createDefaultSignal(role: SignalRole): SignalGene {
  return {
    id: generateId(),
    indicator: 'RSI',
    params: { period: 14 },
    role,
    condition: 'lt',
    threshold: 30,
  };
}

export function SignalEditor({ title, logicLabel, signals, allowedRoles, onChange }: SignalEditorProps) {
  const addSignal = () => {
    const role = allowedRoles[0];
    const newSignal = createDefaultSignal(role);
    onChange([...signals, newSignal]);
  };

  const removeSignal = (id: string) => {
    onChange(signals.filter((s) => s.id !== id));
  };

  const updateSignal = (id: string, updates: Partial<SignalGene>) => {
    onChange(
      signals.map((s) => {
        if (s.id !== id) return s;
        const updated = { ...s, ...updates };
        if (updates.indicator) {
          const newParams = DEFAULT_PARAMS[updates.indicator] ?? {};
          updated.params = newParams;
          const conditions = CONDITIONS_BY_INDICATOR[updates.indicator] ?? DEFAULT_CONDITIONS;
          if (!conditions.includes(updated.condition)) {
            updated.condition = conditions[0];
          }
        }
        return updated;
      }),
    );
  };

  const updateParam = (id: string, key: string, value: number) => {
    onChange(
      signals.map((s) => {
        if (s.id !== id) return s;
        return { ...s, params: { ...s.params, [key]: value } };
      }),
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">{title}</h3>
        <span className="text-xs text-[var(--text-disabled)] bg-[var(--bg-hover)] px-2 py-0.5 rounded">
          {logicLabel}
        </span>
      </div>

      {signals.length === 0 && (
        <div className="text-xs text-[var(--text-disabled)] py-2 text-center border border-dashed border-[var(--border)] rounded">
          No signals configured
        </div>
      )}

      {signals.map((signal) => {
        const conditions = CONDITIONS_BY_INDICATOR[signal.indicator] ?? DEFAULT_CONDITIONS;
        const paramEntries = Object.entries(signal.params);

        return (
          <div
            key={signal.id}
            className="flex items-center gap-1.5 bg-[var(--bg-hover)] rounded p-2 text-xs"
          >
            {/* Indicator select */}
            <select
              value={signal.indicator}
              onChange={(e) => updateSignal(signal.id, { indicator: e.target.value })}
              className="bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-1.5 py-1 text-xs min-w-[70px]"
            >
              {INDICATORS.map((ind) => (
                <option key={ind} value={ind}>{ind}</option>
              ))}
            </select>

            {/* Params */}
            {paramEntries.map(([key, val]) => (
              <div key={key} className="flex items-center gap-0.5">
                <span className="text-[var(--text-disabled)]">{key.slice(0, 3)}</span>
                <input
                  type="number"
                  value={val}
                  onChange={(e) => updateParam(signal.id, key, Number(e.target.value))}
                  className="bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-1 py-0.5 w-12 text-xs"
                />
              </div>
            ))}

            {/* Role */}
            <select
              value={signal.role}
              onChange={(e) => updateSignal(signal.id, { role: e.target.value as SignalRole })}
              className="bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-1 py-1 text-xs min-w-[55px]"
            >
              {allowedRoles.map((role) => (
                <option key={role} value={role}>{ROLE_LABELS[role]}</option>
              ))}
            </select>

            {/* Condition */}
            <select
              value={signal.condition}
              onChange={(e) => updateSignal(signal.id, { condition: e.target.value as ConditionType })}
              className="bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-1 py-1 text-xs min-w-[50px]"
            >
              {conditions.map((c) => (
                <option key={c} value={c}>{CONDITION_LABELS[c]}</option>
              ))}
            </select>

            {/* Threshold */}
            <input
              type="number"
              value={signal.threshold}
              onChange={(e) => updateSignal(signal.id, { threshold: Number(e.target.value) })}
              className="bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-1 py-0.5 w-14 text-xs"
            />

            {/* Delete */}
            <button
              type="button"
              onClick={() => removeSignal(signal.id)}
              className="text-[var(--text-disabled)] hover:text-[var(--color-loss)] transition-colors p-0.5"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}

      <Button variant="ghost" size="sm" onClick={addSignal} className="w-full text-xs">
        <Plus className="w-3.5 h-3.5" />
        Add Signal
      </Button>
    </div>
  );
}
