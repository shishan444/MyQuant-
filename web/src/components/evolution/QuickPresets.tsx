import { cn } from "@/lib/utils";

interface Preset {
  id: string;
  title: string;
  description: string;
  indicators: string[];
  timeframePool: string[];
  scoreTemplate: string;
  mode: "auto";
}

const PRESETS: Preset[] = [
  {
    id: "rsi-oversold",
    title: "RSI超卖反弹",
    description: "RSI+BB, 4H单周期, 收益优先",
    indicators: ["RSI", "BB"],
    timeframePool: ["4h"],
    scoreTemplate: "profit_first",
    mode: "auto",
  },
  {
    id: "ema-trend",
    title: "EMA趋势跟踪",
    description: "EMA+ADX, 4H单周期, 稳健优先",
    indicators: ["EMA", "ADX"],
    timeframePool: ["4h"],
    scoreTemplate: "steady",
    mode: "auto",
  },
  {
    id: "mtf-resonance",
    title: "多周期趋势共振",
    description: "1D:EMA + 4H:RSI+BB, 收益优先",
    indicators: ["EMA", "RSI", "BB"],
    timeframePool: ["1d", "4h"],
    scoreTemplate: "profit_first",
    mode: "auto",
  },
];

interface QuickPresetsProps {
  onSelect: (preset: Preset) => void;
}

export function QuickPresets({ onSelect }: QuickPresetsProps) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs text-slate-500">快速开始:</span>
      <div className="grid grid-cols-3 gap-3">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => onSelect(preset)}
            className={cn(
              "flex flex-col gap-1.5 rounded-[10px] border border-slate-700/50 p-3 text-left transition-all duration-150",
              "hover:border-amber-400/30 hover:bg-white/[0.03]"
            )}
          >
            <span className="text-[13px] font-medium text-slate-200">
              {preset.title}
            </span>
            <span className="text-[11px] leading-relaxed text-slate-500">
              {preset.description}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export type { Preset };
