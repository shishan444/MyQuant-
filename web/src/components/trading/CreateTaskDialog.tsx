import { useState } from "react";
import { TrendingUp } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const LEVERAGE_OPTIONS = [1, 2, 3, 5, 10];

const DIRECTION_OPTIONS: { value: string; label: string }[] = [
  { value: "long", label: "仅多" },
  { value: "short", label: "仅空" },
  { value: "mixed", label: "混合" },
];

interface CreateTaskDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategyName: string | null;
  symbol: string;
  timeframe: string;
  initialCash: number;
  leverage: number;
  direction: string;
  onConfirm: (params: { initialCash: number; leverage: number; direction: string; confidenceSizingEnabled: boolean }) => void;
}

export function CreateTaskDialog({
  open,
  onOpenChange,
  strategyName,
  symbol,
  timeframe,
  initialCash: defaultCash,
  leverage: defaultLeverage,
  direction: defaultDirection,
  onConfirm,
}: CreateTaskDialogProps) {
  const [cash, setCash] = useState(defaultCash);
  const [leverage, setLeverage] = useState(defaultLeverage);
  const [direction, setDirection] = useState(defaultDirection);
  const [confidenceSizing, setConfidenceSizing] = useState(false);

  // Sync when dialog opens with new defaults
  const [prevCash, setPrevCash] = useState(defaultCash);
  const [prevLeverage, setPrevLeverage] = useState(defaultLeverage);
  const [prevDirection, setPrevDirection] = useState(defaultDirection);
  if (defaultCash !== prevCash) { setPrevCash(defaultCash); setCash(defaultCash); }
  if (defaultLeverage !== prevLeverage) { setPrevLeverage(defaultLeverage); setLeverage(defaultLeverage); }
  if (defaultDirection !== prevDirection) { setPrevDirection(defaultDirection); setDirection(defaultDirection); }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-accent-gold" />
            创建模拟交易任务
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-text-secondary">
              <p>
                使用该策略启动模拟交易。运行引擎将先处理历史数据，然后切换至实时模式。
              </p>
              <div className="grid grid-cols-2 gap-2 rounded-lg border border-border-default p-3">
                <div>
                  <span className="text-xs text-text-muted">策略</span>
                  <p className="font-medium text-text-primary">
                    {strategyName || "未命名策略"}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-text-muted">交易对</span>
                  <p className="font-medium text-text-primary">
                    {symbol} / {timeframe}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-text-muted">初始资金</span>
                  <input
                    type="number"
                    min={100}
                    step={10000}
                    value={cash}
                    onChange={(e) => setCash(Number(e.target.value) || 10000)}
                    className="w-full rounded border border-border-default bg-transparent px-2 py-1 font-num text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-gold"
                  />
                </div>
                <div>
                  <span className="text-xs text-text-muted">杠杆倍数</span>
                  <div className="flex gap-1 mt-0.5">
                    {LEVERAGE_OPTIONS.map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => setLeverage(opt)}
                        className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                          leverage === opt
                            ? "bg-accent-gold/20 text-accent-gold border border-accent-gold/40"
                            : "border border-border-default text-text-muted hover:text-text-primary hover:border-text-muted"
                        }`}
                      >
                        {opt}x
                      </button>
                    ))}
                  </div>
                </div>
                <div className="col-span-2">
                  <span className="text-xs text-text-muted">交易方向</span>
                  <div className="flex gap-1 mt-0.5">
                    {DIRECTION_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setDirection(opt.value)}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          direction === opt.value
                            ? "bg-accent-gold/20 text-accent-gold border border-accent-gold/40"
                            : "border border-border-default text-text-muted hover:text-text-primary hover:border-text-muted"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="col-span-2 flex items-center justify-between">
                  <div>
                    <span className="text-xs text-text-muted">置信度仓位缩放</span>
                    <p className="text-xs text-text-muted/60">根据信号置信度动态调整入场仓位大小</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setConfidenceSizing(!confidenceSizing)}
                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border transition-colors ${
                      confidenceSizing
                        ? "bg-accent-gold border-accent-gold"
                        : "bg-bg-secondary border-border-default"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                        confidenceSizing ? "translate-x-4" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction onClick={() => onConfirm({ initialCash: cash, leverage, direction, confidenceSizingEnabled: confidenceSizing })}>
            创建任务
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
