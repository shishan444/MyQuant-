import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { Play, ChevronDown, Plus, X } from "lucide-react";
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
  TIMEFRAME_FORM_OPTIONS as TIMEFRAME_OPTIONS,
  INDICATOR_FLAT_LIST as INDICATOR_OPTIONS,
  INDICATOR_LABELS,
  CONDITION_OPTIONS,
  OPTIMIZE_TARGETS,
  LEVERAGE_OPTIONS,
  DIRECTION_OPTIONS,
} from "@/lib/constants";
import type { SignalGene, TimeframeLayerModel, DNA } from "@/types/api";

interface LayerData {
  timeframe: string;
  conditions: Array<{
    indicator: string;
    conditionType: string;
    value: string;
  }>;
}

interface SeedConfigFormProps {
  disabled: boolean;
  isPending: boolean;
  symbolOptions?: { value: string; label: string }[];
  onSubmit: (config: {
    symbol: string;
    initialDna: DNA;
    scoreTemplate: string;
    populationSize: number;
    maxGenerations: number;
    targetScore: number;
    leverage: number;
    direction: "long" | "short" | "mixed";
  }) => void;
  seedDna?: DNA | null;
}

function inferRole(
  layers: LayerData[],
  index: number
): string | null {
  if (layers.length <= 1) return null;

  const tfOrder = ["1d", "4h", "1h", "15m"];
  const sorted = [...layers].sort(
    (a, b) => tfOrder.indexOf(a.timeframe) - tfOrder.indexOf(b.timeframe)
  );
  const layer = layers[index];
  const sortedIdx = sorted.findIndex((l) => l === layer);

  if (sortedIdx === 0) return "趋势过滤";
  if (sortedIdx === sorted.length - 1) return "入场信号";
  return "确认信号";
}

const TF_ORDER = ["1d", "4h", "1h", "15m"];

function sortLayers(layers: LayerData[]): LayerData[] {
  return [...layers].sort(
    (a, b) => TF_ORDER.indexOf(a.timeframe) - TF_ORDER.indexOf(b.timeframe)
  );
}

export function SeedConfigForm({
  disabled,
  isPending,
  onSubmit,
  seedDna,
  symbolOptions,
}: SeedConfigFormProps) {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [scoreTemplate, setScoreTemplate] = useState("profit_first");
  const [advOpen, setAdvOpen] = useState(false);
  const [populationSize, setPopulationSize] = useState(15);
  const [maxGenerations, setMaxGenerations] = useState(200);
  const [targetScore, setTargetScore] = useState(80);
  const [crossLayerLogic, setCrossLayerLogic] = useState<"AND" | "OR">("AND");
  const [stopLoss, setStopLoss] = useState(5);
  const [takeProfit, setTakeProfit] = useState(10);
  const [positionSize, setPositionSize] = useState(30);
  const [leverage, setLeverage] = useState(1);
  const [direction, setDirection] = useState<"long" | "short" | "mixed">("long");

  const initialLayers = useMemo((): LayerData[] => {
    if (seedDna?.layers && seedDna.layers.length > 0) {
      return seedDna.layers.map((layer) => ({
        timeframe: layer.timeframe,
        conditions: layer.signal_genes.map((sg) => ({
          indicator: sg.indicator,
          conditionType: sg.condition.type,
          value: sg.condition.value?.toString() ?? "",
        })),
      }));
    }
    return [
      {
        timeframe: "4h",
        conditions: [{ indicator: "RSI", conditionType: "lt", value: "30" }],
      },
    ];
  }, [seedDna]);

  const [layers, setLayers] = useState<LayerData[]>(initialLayers);

  // Reset layers when seedDna changes
  const prevSeedRef = useRef(seedDna);
  useEffect(() => {
    if (prevSeedRef.current === seedDna) return;
    prevSeedRef.current = seedDna;
    if (seedDna?.layers && seedDna.layers.length > 0) {
      setLayers(
        seedDna.layers.map((layer) => ({
          timeframe: layer.timeframe,
          conditions: layer.signal_genes.map((sg) => ({
            indicator: sg.indicator,
            conditionType: sg.condition.type,
            value: sg.condition.value?.toString() ?? "",
          })),
        }))
      );
      if (seedDna.risk_genes) {
        setStopLoss(Math.round(seedDna.risk_genes.stop_loss * 100));
        setTakeProfit(
          seedDna.risk_genes.take_profit != null
            ? Math.round(seedDna.risk_genes.take_profit * 100)
            : 10
        );
        setPositionSize(Math.round(seedDna.risk_genes.position_size * 100));
        setLeverage(seedDna.risk_genes.leverage ?? 1);
        setDirection(seedDna.risk_genes.direction ?? "long");
      }
      if (seedDna.cross_layer_logic) {
        setCrossLayerLogic(seedDna.cross_layer_logic);
      }
    }
  }, [seedDna]);

  const sortedLayers = useMemo(() => sortLayers(layers), [layers]);

  const addLayer = useCallback(() => {
    if (layers.length >= 3) return;
    const usedTfs = layers.map((l) => l.timeframe);
    const available = TIMEFRAME_OPTIONS.find(
      (t) => !usedTfs.includes(t.value)
    );
    if (!available) return;
    setLayers((prev) => [
      ...prev,
      { timeframe: available.value, conditions: [] },
    ]);
  }, [layers]);

  const removeLayer = useCallback(
    (index: number) => {
      if (layers.length <= 1) return;
      setLayers((prev) => prev.filter((_, i) => i !== index));
    },
    [layers]
  );

  const updateLayerTimeframe = useCallback(
    (index: number, tf: string) => {
      setLayers((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], timeframe: tf };
        return next;
      });
    },
    []
  );

  const addCondition = useCallback((layerIdx: number) => {
    setLayers((prev) => {
      const next = [...prev];
      next[layerIdx] = {
        ...next[layerIdx],
        conditions: [
          ...next[layerIdx].conditions,
          { indicator: "EMA", conditionType: "gt", value: "" },
        ],
      };
      return next;
    });
  }, []);

  const removeCondition = useCallback(
    (layerIdx: number, condIdx: number) => {
      setLayers((prev) => {
        const next = [...prev];
        next[layerIdx] = {
          ...next[layerIdx],
          conditions: next[layerIdx].conditions.filter(
            (_, i) => i !== condIdx
          ),
        };
        return next;
      });
    },
    []
  );

  const updateCondition = useCallback(
    (
      layerIdx: number,
      condIdx: number,
      field: "indicator" | "conditionType" | "value",
      val: string
    ) => {
      setLayers((prev) => {
        const next = [...prev];
        const conds = [...next[layerIdx].conditions];
        conds[condIdx] = { ...conds[condIdx], [field]: val };
        next[layerIdx] = { ...next[layerIdx], conditions: conds };
        return next;
      });
    },
    []
  );

  const hasConditions = sortedLayers.some((l) => l.conditions.length > 0);
  const canSubmit = hasConditions && !disabled;

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;

    const tfLayers: TimeframeLayerModel[] = sortedLayers.map((layer) => ({
      timeframe: layer.timeframe,
      signal_genes: layer.conditions.map(
        (cond): SignalGene => ({
          indicator: cond.indicator,
          params: {},
          role: "entry_trigger",
          condition: {
            type: cond.conditionType as SignalGene["condition"]["type"],
            ...(cond.value ? { value: Number(cond.value) } : {}),
          },
        })
      ),
      logic_genes: { entry_logic: "AND", exit_logic: "AND" },
    }));

    const shortestTf = sortedLayers[sortedLayers.length - 1]?.timeframe ?? "4h";

    const dna: DNA = {
      layers: tfLayers,
      cross_layer_logic: crossLayerLogic,
      execution_genes: { timeframe: shortestTf, symbol },
      risk_genes: {
        stop_loss: stopLoss / 100,
        take_profit: takeProfit / 100,
        position_size: positionSize / 100,
        leverage,
        direction,
      },
      signal_genes: [],
      logic_genes: { entry_logic: "AND", exit_logic: "AND" },
      generation: 0,
      parent_ids: [],
      mutation_ops: [],
    };

    onSubmit({
      symbol,
      initialDna: dna,
      scoreTemplate,
      populationSize,
      maxGenerations,
      targetScore,
      leverage,
      direction,
    });
  }, [
    canSubmit,
    onSubmit,
    sortedLayers,
    crossLayerLogic,
    symbol,
    stopLoss,
    takeProfit,
    positionSize,
    leverage,
    direction,
    scoreTemplate,
    populationSize,
    maxGenerations,
    targetScore,
  ]);

  return (
    <div className="flex flex-col gap-4">
      {/* Data source */}
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

      {/* MTF Layer builder */}
      <div className="flex flex-col gap-2">
        <span className="text-xs text-slate-400">
          策略结构 (按周期分层, 每层定义该周期的信号条件)
        </span>

        {sortedLayers.map((layer, layerIdx) => {
          const originalIdx = layers.indexOf(layer);
          const role = inferRole(sortedLayers, layerIdx);
          return (
            <div
              key={originalIdx}
              className="flex flex-col gap-2 rounded-xl border border-slate-700/50 bg-white/[0.02] p-3"
            >
              {/* Layer header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-300">
                    Layer {layerIdx + 1}:
                  </span>
                  <Select
                    value={layer.timeframe}
                    onValueChange={(v) =>
                      updateLayerTimeframe(originalIdx, v)
                    }
                  >
                    <SelectTrigger className="h-6 w-16 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEFRAME_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {role && (
                    <Badge
                      variant="outline"
                      className="border-slate-700/50 text-[10px] text-slate-500"
                    >
                      {role}
                    </Badge>
                  )}
                </div>
                {layers.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    className="text-slate-600 hover:text-red-400"
                    onClick={() => removeLayer(originalIdx)}
                    aria-label="删除层"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>

              {/* Conditions */}
              {layer.conditions.map((cond, condIdx) => (
                <div
                  key={condIdx}
                  className="flex items-center gap-2 pl-2"
                >
                  <Select
                    value={cond.indicator}
                    onValueChange={(v) =>
                      updateCondition(originalIdx, condIdx, "indicator", v)
                    }
                  >
                    <SelectTrigger className="h-6 w-24 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {INDICATOR_OPTIONS.map((ind) => (
                        <SelectItem key={ind} value={ind}>
                          {INDICATOR_LABELS[ind] ?? ind}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Select
                    value={cond.conditionType}
                    onValueChange={(v) =>
                      updateCondition(
                        originalIdx,
                        condIdx,
                        "conditionType",
                        v
                      )
                    }
                  >
                    <SelectTrigger className="h-6 w-24 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CONDITION_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {![
                    "price_above",
                    "price_below",
                    "cross_above",
                    "cross_below",
                  ].includes(cond.conditionType) && (
                    <Input
                      type="number"
                      value={cond.value}
                      onChange={(e) =>
                        updateCondition(
                          originalIdx,
                          condIdx,
                          "value",
                          e.target.value
                        )
                      }
                      className="h-6 w-20 text-xs"
                      placeholder="阈值"
                    />
                  )}

                  <Button
                    variant="ghost"
                    size="icon-xs"
                    className="text-slate-600 hover:text-red-400"
                    onClick={() => removeCondition(originalIdx, condIdx)}
                    aria-label="删除条件"
                  >
                    <X className="h-3 w-3.5" />
                  </Button>
                </div>
              ))}

              <Button
                variant="ghost"
                size="xs"
                className="w-fit gap-1 text-[11px] text-slate-500 hover:text-slate-400"
                onClick={() => addCondition(originalIdx)}
              >
                <Plus className="h-3 w-3" />
                添加条件
              </Button>
            </div>
          );
        })}

        {layers.length < 3 && (
          <Button
            variant="outline"
            size="xs"
            className="w-full gap-1 border-dashed border-slate-700/50 text-[11px] text-slate-500"
            onClick={addLayer}
          >
            <Plus className="h-3 w-3" />
            添加周期层
          </Button>
        )}

        {layers.length > 1 && (
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>跨层组合:</span>
            <Select
              value={crossLayerLogic}
              onValueChange={(v) => setCrossLayerLogic(v as "AND" | "OR")}
            >
              <SelectTrigger className="h-6 w-16 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="AND">AND</SelectItem>
                <SelectItem value="OR">OR</SelectItem>
              </SelectContent>
            </Select>
            <span className="text-slate-600">
              {crossLayerLogic === "AND"
                ? "所有层信号同时满足才入场"
                : "任一层信号即可入场"}
            </span>
          </div>
        )}
      </div>

      {/* Risk params */}
      <div className="flex items-center gap-4">
        <span className="w-14 shrink-0 text-xs text-slate-400">风控</span>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">止损</span>
          <Input
            type="number"
            step="1"
            min={1}
            max={20}
            value={stopLoss}
            onChange={(e) => setStopLoss(Number(e.target.value) || 5)}
            className="h-6 w-16 text-xs"
          />
          <span className="text-[11px] text-slate-600">%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">止盈</span>
          <Input
            type="number"
            step="1"
            min={1}
            max={50}
            value={takeProfit}
            onChange={(e) => setTakeProfit(Number(e.target.value) || 10)}
            className="h-6 w-16 text-xs"
          />
          <span className="text-[11px] text-slate-600">%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">仓位</span>
          <Input
            type="number"
            step="1"
            min={10}
            max={100}
            value={positionSize}
            onChange={(e) => setPositionSize(Number(e.target.value) || 30)}
            className="h-6 w-16 text-xs"
          />
          <span className="text-[11px] text-slate-600">%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">杠杆</span>
          <Select value={String(leverage)} onValueChange={(v) => setLeverage(Number(v))}>
            <SelectTrigger className="h-6 w-16 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LEVERAGE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={String(opt.value)}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">方向</span>
          <Select value={direction} onValueChange={(v) => setDirection(v as "long" | "short" | "mixed")}>
            <SelectTrigger className="h-6 w-16 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DIRECTION_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {leverage > 1 && (
        <p className="text-[11px] text-amber-500/80">
          {leverage}x 杠杆: 每 8 小时收取 0.1% 资金费用, 保证金亏损超过 90% 触发爆仓
        </p>
      )}

      {/* Optimize target */}
      <div className="flex items-start gap-3">
        <span className="mt-1 w-14 shrink-0 text-xs text-slate-400">
          优化目标
        </span>
        <div className="flex flex-col gap-1.5">
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
          <span className="text-[10px] text-slate-600">
            {OPTIMIZE_TARGETS.find((t) => t.value === scoreTemplate)?.description}
          </span>
        </div>
      </div>

      {/* Note */}
      <p className="text-[11px] leading-relaxed text-slate-600">
        这些条件作为进化的起点(种子), 进化会在其基础上变异优化.
        包括: 调整参数/替换指标/改变周期/增减条件/增减周期层
      </p>

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
              <label className="text-[11px] text-slate-500">
                种群大小 (10-50)
              </label>
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
              <label className="text-[11px] text-slate-500">
                最大代数 (50-500)
              </label>
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
              <label className="text-[11px] text-slate-500">
                目标分数 (60-100)
              </label>
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
