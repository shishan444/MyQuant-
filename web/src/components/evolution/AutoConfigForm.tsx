import { useState, useCallback } from "react";
import { Play, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  SYMBOL_OPTIONS,
  TIMEFRAME_POOL_OPTIONS,
  TIMEFRAME_LABELS,
  INDICATOR_GROUPS,
  OPTIMIZE_TARGETS,
} from "@/lib/constants";

interface AutoConfigFormProps {
  disabled: boolean;
  isPending: boolean;
  symbolOptions?: { value: string; label: string }[];
  onSubmit: (config: {
    symbol: string;
    timeframePool: string[];
    indicatorPool: string[];
    scoreTemplate: string;
    populationSize: number;
    maxGenerations: number;
    targetScore: number;
  }) => void;
}

export function AutoConfigForm({
  disabled,
  isPending,
  onSubmit,
  symbolOptions,
}: AutoConfigFormProps) {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframePool, setTimeframePool] = useState<string[]>(["4h"]);
  const [indicatorPool, setIndicatorPool] = useState<string[]>([
    "EMA",
    "RSI",
  ]);
  const [scoreTemplate, setScoreTemplate] = useState("profit_first");
  const [advOpen, setAdvOpen] = useState(false);
  const [populationSize, setPopulationSize] = useState(15);
  const [maxGenerations, setMaxGenerations] = useState(200);
  const [targetScore, setTargetScore] = useState(80);

  const toggleTimeframe = useCallback((tf: string) => {
    setTimeframePool((prev) => {
      if (prev.includes(tf)) {
        return prev.length > 1 ? prev.filter((t) => t !== tf) : prev;
      }
      return prev.length >= 4 ? prev : [...prev, tf];
    });
  }, []);

  const toggleIndicator = useCallback((ind: string) => {
    setIndicatorPool((prev) =>
      prev.includes(ind) ? prev.filter((i) => i !== ind) : [...prev, ind]
    );
  }, []);

  const canSubmit = indicatorPool.length >= 2 && !disabled;

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;
    onSubmit({
      symbol,
      timeframePool,
      indicatorPool,
      scoreTemplate,
      populationSize,
      maxGenerations,
      targetScore,
    });
  }, [
    canSubmit,
    onSubmit,
    symbol,
    timeframePool,
    indicatorPool,
    scoreTemplate,
    populationSize,
    maxGenerations,
    targetScore,
  ]);

  return (
    <div className="flex flex-col gap-4">
      {/* Data source row */}
      <div className="flex items-center gap-3">
        <span className="w-14 shrink-0 text-xs text-slate-400">数据源</span>
        <Select value={symbol} onValueChange={setSymbol}>
          <SelectTrigger className="h-7 w-28 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(symbolOptions ?? SYMBOL_OPTIONS).map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Timeframe pool */}
      <div className="flex items-start gap-3">
        <span className="mt-1 w-14 shrink-0 text-xs text-slate-400">
          周期池
        </span>
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap gap-1.5">
            {TIMEFRAME_POOL_OPTIONS.map((tf) => {
              const selected = timeframePool.includes(tf);
              return (
                <Badge
                  key={tf}
                  variant="outline"
                  className={cn(
                    "cursor-pointer text-[11px] transition-colors",
                    selected
                      ? "border-amber-400/30 bg-amber-400/20 text-amber-400 hover:bg-amber-400/30"
                      : "border-slate-700/50 text-slate-400 hover:text-slate-300"
                  )}
                  onClick={() => toggleTimeframe(tf)}
                >
                  {TIMEFRAME_LABELS[tf]}
                </Badge>
              );
            })}
          </div>
          <span className="text-[11px] text-slate-500">
            {timeframePool.length >= 2
              ? `已选${timeframePool.length}个: ${timeframePool.map((t) => TIMEFRAME_LABELS[t]).join("+")} ${
                  timeframePool.length >= 2 ? "跨周期探索" : ""
                }`
              : "选多个周期开启跨周期策略探索"}
          </span>
        </div>
      </div>

      {/* Indicator pool */}
      <div className="flex items-start gap-3">
        <span className="mt-1 w-14 shrink-0 text-xs text-slate-400">
          指标池
        </span>
        <div className="flex flex-col gap-2">
          <span className="text-[11px] text-slate-500">
            已选 {indicatorPool.length}/21, 至少需要2个
          </span>
          {INDICATOR_GROUPS.map((group) => (
            <div key={group.label} className="flex flex-wrap items-center gap-1.5">
              <span className="w-10 text-[10px] text-slate-600">
                {group.label}
              </span>
              {group.items.map((ind) => {
                const selected = indicatorPool.includes(ind);
                return (
                  <Badge
                    key={ind}
                    variant="outline"
                    className={cn(
                      "cursor-pointer text-[11px] transition-colors",
                      selected
                        ? "border-amber-400/30 bg-amber-400/20 text-amber-400 hover:bg-amber-400/30"
                        : "border-slate-700/50 text-slate-400 hover:text-slate-300"
                    )}
                    onClick={() => toggleIndicator(ind)}
                  >
                    {ind}
                  </Badge>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Optimize target */}
      <div className="flex items-center gap-3">
        <span className="w-14 shrink-0 text-xs text-slate-400">
          优化目标
        </span>
        <Select value={scoreTemplate} onValueChange={setScoreTemplate}>
          <SelectTrigger className="h-7 w-36 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPTIMIZE_TARGETS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Advanced params (collapsible) */}
      <div className="flex flex-col gap-2">
        <button
          type="button"
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-400"
          onClick={() => setAdvOpen((v) => !v)}
        >
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 transition-transform",
              advOpen && "rotate-180"
            )}
          />
          高级参数
        </button>
        {advOpen && (
          <div className="flex items-center gap-4 rounded-lg border border-slate-700/30 bg-white/[0.02] p-3">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-slate-500">种群大小 (10-50)</label>
              <Input
                type="number"
                min={10}
                max={50}
                value={populationSize}
                onChange={(e) =>
                  setPopulationSize(Number(e.target.value) || 15)
                }
                className="h-7 w-24 text-xs"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-slate-500">最大代数 (50-500)</label>
              <Input
                type="number"
                min={50}
                max={500}
                value={maxGenerations}
                onChange={(e) =>
                  setMaxGenerations(Number(e.target.value) || 200)
                }
                className="h-7 w-24 text-xs"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-slate-500">目标分数 (60-100)</label>
              <Input
                type="number"
                min={60}
                max={100}
                value={targetScore}
                onChange={(e) =>
                  setTargetScore(Number(e.target.value) || 80)
                }
                className="h-7 w-24 text-xs"
              />
            </div>
          </div>
        )}
      </div>

      {/* Submit */}
      <Button
        size="sm"
        className="w-full gap-1.5 bg-amber-400 text-black hover:bg-amber-400/90"
        disabled={!canSubmit || isPending}
        onClick={handleSubmit}
      >
        <Play className="h-3.5 w-3.5" />
        {isPending ? "创建中..." : "开始探索"}
      </Button>
    </div>
  );
}
