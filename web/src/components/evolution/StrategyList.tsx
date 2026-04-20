import { useMemo, useCallback, memo } from "react";
import { Eye, Save, Dna } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/badge";
import { cn, formatPercent, formatNumber } from "@/lib/utils";
import { getStrategyName, getStrategyType } from "@/lib/strategy-utils";
import type { EvolutionTask, DNA } from "@/types/api";

interface StrategyListProps {
  strategies: EvolutionTask[];
  expandedId: string | null;
  onToggleExpand: (taskId: string) => void;
  onSave: (task: EvolutionTask) => void;
  onSeedEvolve: (dna: DNA) => void;
}

function formatIndicatorLabel(gene: {
  indicator: string;
  params?: Record<string, unknown>;
}): string {
  const period = gene.params?.period;
  if (period) return `${gene.indicator}(${period})`;
  return gene.indicator;
}

function getDnaIndicators(dna: DNA | null | undefined): string {
  if (!dna) return "-";
  if (dna.layers && dna.layers.length > 0) {
    return dna.layers
      .flatMap((l) => l.signal_genes)
      .map(formatIndicatorLabel)
      .join("+");
  }
  return dna.signal_genes.map(formatIndicatorLabel).join("+");
}

function getDnaDescription(dna: DNA | null | undefined): string {
  if (!dna) return "";
  if (dna.layers && dna.layers.length > 0) {
    return dna.layers
      .map((l, i) => {
        const indicators = l.signal_genes.map((g) => g.indicator).join("+");
        if (i === 0 && dna.layers!.length > 1) return `${l.timeframe}趋势过滤`;
        if (i === dna.layers!.length - 1 && dna.layers!.length > 1)
          return `${l.timeframe}入场信号`;
        return `${l.timeframe}:${indicators}`;
      })
      .join("+");
  }
  return dna.signal_genes
    .map((g) => {
      const condType = g.condition.type;
      if (condType === "price_above") return `${g.indicator}价格上方`;
      if (condType === "price_below") return `${g.indicator}价格下方`;
      if (condType === "lt") return `${g.indicator}超卖`;
      if (condType === "gt") return `${g.indicator}超买`;
      if (condType === "cross_above") return `${g.indicator}金叉`;
      if (condType === "cross_below") return `${g.indicator}死叉`;
      return g.indicator;
    })
    .join("+");
}

function getMtfBadge(dna: DNA | null | undefined): string | null {
  if (!dna?.layers || dna.layers.length <= 1) return null;
  return dna.layers.map((l) => l.timeframe.toUpperCase()).join("+");
}

export function StrategyList({
  strategies,
  expandedId,
  onToggleExpand,
  onSave,
  onSeedEvolve,
}: StrategyListProps) {
  if (strategies.length === 0) return null;

  return (
    <div className="flex flex-col gap-1">
      {/* Header row */}
      <div className="flex items-center gap-4 px-4 py-2 text-[11px] text-slate-500">
        <span className="w-7 shrink-0 text-center">排名</span>
        <span className="flex-1">策略(指标组合)</span>
        <span className="w-24 shrink-0 text-right">收益率</span>
        <span className="w-16 shrink-0 text-right">夏普</span>
        <span className="w-20 shrink-0 text-right">操作</span>
      </div>

      {strategies.map((task, idx) => (
        <StrategyRow
          key={task.task_id}
          rank={idx + 1}
          task={task}
          expanded={expandedId === task.task_id}
          onToggle={() => onToggleExpand(task.task_id)}
          onSave={() => onSave(task)}
          onSeedEvolve={() => task.champion_dna && onSeedEvolve(task.champion_dna)}
        />
      ))}
    </div>
  );
}

interface StrategyRowProps {
  rank: number;
  task: EvolutionTask;
  expanded: boolean;
  onToggle: () => void;
  onSave: () => void;
  onSeedEvolve: () => void;
}

const StrategyRow = memo(function StrategyRow({
  rank,
  task,
  expanded,
  onToggle,
  onSave,
  onSeedEvolve,
}: StrategyRowProps) {
  const bestScore = task.best_score ?? 0;
  const returnRate = task.champion_metrics?.annual_return ?? 0;
  const sharpe = task.champion_metrics?.sharpe_ratio ?? 0;
  const mtfBadge = useMemo(() => getMtfBadge(task.champion_dna), [task.champion_dna]);
  const strategyName = useMemo(() => getStrategyName(task.champion_dna), [task.champion_dna]);
  const strategyType = useMemo(() => getStrategyType(task.champion_dna), [task.champion_dna]);
  const indicators = useMemo(
    () => getDnaIndicators(task.champion_dna),
    [task.champion_dna]
  );

  return (
    <div>
      <div
        className={cn(
          "group flex items-center gap-4 rounded-lg px-4 py-3 transition-colors hover:bg-white/[0.03]",
          rank <= 3 && "ring-1 ring-amber-400/20 bg-amber-400/[0.03]"
        )}
      >
        {/* Rank */}
        <span
          className={cn(
            "w-7 shrink-0 text-center font-mono text-sm font-semibold",
            rank === 1
              ? "text-amber-400"
              : rank <= 3
                ? "text-amber-400/70"
                : "text-slate-500"
          )}
        >
          #{rank}
        </span>

        {/* Strategy info */}
        <div className="flex flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-1.5">
            <Badge
              variant="outline"
              className={cn(
                "border-slate-700/50 px-1.5 py-0 text-[10px]",
                strategyType === "趋势"
                  ? "text-blue-400"
                  : strategyType === "动量"
                    ? "text-amber-400"
                    : strategyType === "波动"
                      ? "text-purple-400"
                      : "text-slate-400"
              )}
            >
              {strategyType}
            </Badge>
            {mtfBadge && (
              <Badge
                variant="outline"
                className="border-purple-400/30 px-1 py-0 text-[10px] text-purple-400"
              >
                {mtfBadge}
              </Badge>
            )}
            <span className="truncate text-sm text-slate-100">
              {strategyName}
            </span>
          </div>
          <span className="truncate text-xs text-slate-500">
            {indicators}
          </span>
        </div>

        {/* Return rate */}
        <span
          className={cn(
            "w-24 shrink-0 text-right font-mono text-[13px] font-semibold",
            returnRate >= 0 ? "text-emerald-400" : "text-red-400"
          )}
        >
          {formatPercent(returnRate)}
        </span>

        {/* Sharpe */}
        <span className="w-16 shrink-0 text-right font-mono text-[13px] text-slate-400">
          {formatNumber(sharpe)}
        </span>

        {/* Actions */}
        <div className="flex w-20 shrink-0 items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={onToggle}
            aria-label="查看详情"
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={onSave}
            aria-label="保存策略"
          >
            <Save className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-purple-400"
            onClick={onSeedEvolve}
            aria-label="继续进化"
          >
            <Dna className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && task.champion_dna && (
        <StrategyDetail dna={task.champion_dna} task={task} onClose={onToggle} />
      )}
    </div>
  );
});

interface StrategyDetailProps {
  dna: DNA;
  task: EvolutionTask;
  onClose: () => void;
}

function StrategyDetail({ dna, task, onClose }: StrategyDetailProps) {
  const renderCondition = useCallback(
    (gene: { indicator: string; params?: Record<string, unknown>; condition: { type: string; value?: number } }) => {
      const condLabel: Record<string, string> = {
        lt: "<",
        gt: ">",
        le: "<=",
        ge: ">=",
        cross_above: "金叉",
        cross_below: "死叉",
        price_above: "价格在上方",
        price_below: "价格在下方",
      };
      const label = condLabel[gene.condition.type] ?? gene.condition.type;
      const val =
        gene.condition.value != null ? ` ${gene.condition.value}` : "";
      const period = gene.params?.period;
      const periodStr = period ? `(${period})` : "";
      return `${gene.indicator}${periodStr} ${label}${val}`;
    },
    []
  );

  const entryGenes = dna.layers
    ? dna.layers.flatMap((l) =>
        l.signal_genes.filter(
          (g) => g.role === "entry_trigger" || g.role === "entry_guard"
        )
      )
    : dna.signal_genes.filter(
        (g) => g.role === "entry_trigger" || g.role === "entry_guard"
      );

  const exitGenes = dna.layers
    ? dna.layers.flatMap((l) =>
        l.signal_genes.filter(
          (g) => g.role === "exit_trigger" || g.role === "exit_guard"
        )
      )
    : dna.signal_genes.filter(
        (g) => g.role === "exit_trigger" || g.role === "exit_guard"
      );

  const hasExitGenes = exitGenes.length > 0;

  return (
    <div className="rounded-lg border border-slate-700/30 bg-white/[0.02] px-4 py-3 ml-7 mr-0 mb-2">
      {/* Layers or flat genes */}
      {dna.layers && dna.layers.length > 0 ? (
        dna.layers.map((layer, idx) => {
          const roleLabel =
            idx === 0 && dna.layers!.length > 1
              ? "趋势过滤"
              : idx === dna.layers!.length - 1 && dna.layers!.length > 1
                ? "入场信号"
                : dna.layers!.length > 2
                  ? "确认信号"
                  : undefined;
          return (
            <div key={idx} className="mb-3">
              <div className="mb-1 flex items-center gap-2">
                <span className="text-xs font-medium text-slate-300">
                  Layer {idx + 1} - {layer.timeframe.toUpperCase()}
                </span>
                {roleLabel && (
                  <Badge
                    variant="outline"
                    className="border-slate-700/50 text-[10px] text-slate-500"
                  >
                    {roleLabel}
                  </Badge>
                )}
              </div>
              <div className="flex flex-col gap-1 rounded-lg border border-slate-700/30 p-2">
                {layer.signal_genes.map((gene, gi) => (
                  <div
                    key={gi}
                    className="flex items-center gap-2 text-xs text-slate-400"
                  >
                    <span className="font-mono text-slate-300">
                      {gene.indicator}
                      {gene.params?.period
                        ? `(${gene.params.period})`
                        : ""}
                    </span>
                    <span className="text-slate-600">
                      {gene.condition.type}
                    </span>
                    {gene.condition.value != null && (
                      <span className="font-mono text-slate-300">
                        {gene.condition.value}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {idx < dna.layers!.length - 1 && (
                <div className="my-2 flex items-center gap-2 text-xs text-slate-600">
                  <span className="font-medium">
                    {dna.cross_layer_logic ?? "AND"}
                  </span>
                </div>
              )}
            </div>
          );
        })
      ) : (
        <>
          {/* Entry conditions */}
          <div className="mb-2">
            <span className="text-xs font-medium text-slate-400">
              入场条件 ({dna.logic_genes.entry_logic})
            </span>
            <div className="mt-1 flex flex-col gap-1 rounded-lg border border-slate-700/30 p-2">
              {entryGenes.length > 0 ? (
                entryGenes.map((gene, gi) => (
                  <div
                    key={gi}
                    className="text-xs text-slate-400"
                  >
                    {renderCondition(gene)}
                  </div>
                ))
              ) : (
                dna.signal_genes.map((gene, gi) => (
                  <div
                    key={gi}
                    className="text-xs text-slate-400"
                  >
                    {renderCondition(gene)}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Exit conditions */}
          {hasExitGenes && (
            <div className="mb-2">
              <span className="text-xs font-medium text-slate-400">
                出场条件 ({dna.logic_genes.exit_logic})
              </span>
              <div className="mt-1 flex flex-col gap-1 rounded-lg border border-slate-700/30 p-2">
                {exitGenes.map((gene, gi) => (
                  <div
                    key={gi}
                    className="text-xs text-slate-400"
                  >
                    {renderCondition(gene)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Risk genes */}
      <div className="mb-2 flex items-center gap-4 text-xs text-slate-500">
        <span>
          风控: 止损 {(dna.risk_genes.stop_loss * 100).toFixed(1)}%
        </span>
        {dna.risk_genes.take_profit != null && (
          <span>
            止盈 {(dna.risk_genes.take_profit * 100).toFixed(1)}%
          </span>
        )}
        <span>
          仓位 {(dna.risk_genes.position_size * 100).toFixed(0)}%
        </span>
      </div>

      {/* Execution */}
      <div className="mb-2 text-xs text-slate-500">
        执行: {dna.execution_genes.symbol} /{" "}
        {dna.execution_genes.timeframe.toUpperCase()}
      </div>

      {/* Backtest score summary */}
      {task.champion_metrics ? (
        <div className="rounded-lg border border-slate-700/30 p-2">
          <div className="mb-1.5 text-xs font-medium text-slate-300">
            回测指标
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <MetricLine
              label="年化收益率"
              value={`${(task.champion_metrics.annual_return * 100).toFixed(1)}%`}
              score={task.champion_dimension_scores?.annual_return}
              positive={task.champion_metrics.annual_return > 0}
            />
            <MetricLine
              label="夏普比率"
              value={task.champion_metrics.sharpe_ratio.toFixed(2)}
              score={task.champion_dimension_scores?.sharpe_ratio}
              positive={task.champion_metrics.sharpe_ratio > 0}
            />
            <MetricLine
              label="最大回撤"
              value={`${(task.champion_metrics.max_drawdown * 100).toFixed(1)}%`}
              score={task.champion_dimension_scores?.max_drawdown}
              positive={false}
            />
            <MetricLine
              label="胜率"
              value={`${(task.champion_metrics.win_rate * 100).toFixed(1)}%`}
              score={task.champion_dimension_scores?.win_rate}
              positive={task.champion_metrics.win_rate > 0.5}
            />
          </div>
          <div className="mt-1.5 text-[10px] text-slate-600">
            综合评分: <span className="font-mono text-emerald-400">{(task.best_score ?? 0).toFixed(1)}</span>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span>
            最优分数:{" "}
            <span className="font-mono font-semibold text-emerald-400">
              {(task.best_score ?? 0).toFixed(1)}
            </span>
          </span>
        </div>
      )}

      {/* Actions */}
      <div className="mt-3 flex items-center gap-2">
        <Button
          variant="ghost"
          size="xs"
          className="text-slate-500"
          onClick={onClose}
        >
          收起
        </Button>
      </div>
    </div>
  );
}

function MetricLine({
  label,
  value,
  score,
  positive,
}: {
  label: string;
  value: string;
  score?: number;
  positive: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-slate-500">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className={positive ? "text-emerald-400" : "text-red-400"}>
          {value}
        </span>
        {score != null && (
          <span className="text-[10px] text-slate-600">
            ({score.toFixed(1)})
          </span>
        )}
      </div>
    </div>
  );
}
