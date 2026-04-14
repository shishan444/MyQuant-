import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DNA, TimeframeLayerModel } from "@/types/api";

interface StrategyDetailProps {
  dna: DNA;
  className?: string;
}

export function StrategyDetail({ dna, className }: StrategyDetailProps) {
  const hasLayers = dna.layers && dna.layers.length > 0;

  const renderCondition = (
    gene: {
      indicator: string;
      params?: Record<string, unknown>;
      condition: { type: string; value?: number };
    },
    compact = false
  ) => {
    const condLabel: Record<string, string> = {
      lt: "<",
      gt: ">",
      le: "<=",
      ge: ">=",
      cross_above: "cross_above",
      cross_below: "cross_below",
      price_above: "price_above",
      price_below: "price_below",
    };
    const period = gene.params?.period;
    const periodStr = period ? `(${period})` : "";
    const cond = condLabel[gene.condition.type] ?? gene.condition.type;
    const val = gene.condition.value != null ? ` ${gene.condition.value}` : "";

    if (compact) {
      return `${gene.indicator}${periodStr} ${cond}${val}`;
    }
    return `${gene.indicator}${periodStr} ${cond}${val}`;
  };

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* MTF layers display */}
      {hasLayers &&
        (dna.layers as TimeframeLayerModel[]).map((layer, idx) => {
          const layers = dna.layers as TimeframeLayerModel[];
          const isMultiLayer = layers.length > 1;
          const role =
            isMultiLayer
              ? idx === 0
                ? "趋势过滤"
                : idx === layers.length - 1
                  ? "入场信号"
                  : "确认信号"
              : null;

          return (
            <div key={idx}>
              <div className="mb-1 flex items-center gap-2">
                <span className="text-xs font-medium text-slate-300">
                  Layer {idx + 1}: {layer.timeframe.toUpperCase()}
                </span>
                {role && (
                  <Badge
                    variant="outline"
                    className="border-slate-700/50 text-[10px] text-slate-500"
                  >
                    {role}
                  </Badge>
                )}
              </div>
              <div className="flex flex-col gap-0.5 rounded-lg border border-slate-700/30 p-2">
                {layer.signal_genes.length > 0 ? (
                  layer.signal_genes.map((gene, gi) => (
                    <div
                      key={gi}
                      className="text-xs text-slate-400"
                    >
                      {renderCondition(gene)}
                    </div>
                  ))
                ) : (
                  <span className="text-xs text-slate-600">无信号条件</span>
                )}
              </div>
            </div>
          );
        })}

      {/* Flat genes display (non-MTF) */}
      {!hasLayers && (
        <>
          <div>
            <span className="text-xs font-medium text-slate-400">
              入场条件 ({dna.logic_genes.entry_logic})
            </span>
            <div className="mt-1 flex flex-col gap-0.5 rounded-lg border border-slate-700/30 p-2">
              {dna.signal_genes
                .filter(
                  (g) =>
                    g.role === "entry_trigger" ||
                    g.role === "entry_guard"
                )
                .map((gene, gi) => (
                  <div key={gi} className="text-xs text-slate-400">
                    {renderCondition(gene)}
                  </div>
                ))}
            </div>
          </div>
          {dna.signal_genes.some(
            (g) =>
              g.role === "exit_trigger" || g.role === "exit_guard"
          ) && (
            <div>
              <span className="text-xs font-medium text-slate-400">
                出场条件 ({dna.logic_genes.exit_logic})
              </span>
              <div className="mt-1 flex flex-col gap-0.5 rounded-lg border border-slate-700/30 p-2">
                {dna.signal_genes
                  .filter(
                    (g) =>
                      g.role === "exit_trigger" ||
                      g.role === "exit_guard"
                  )
                  .map((gene, gi) => (
                    <div key={gi} className="text-xs text-slate-400">
                      {renderCondition(gene)}
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Cross layer logic */}
      {hasLayers && (dna.layers as TimeframeLayerModel[]).length > 1 && (
        <div className="text-xs text-slate-500">
          跨层逻辑: <span className="font-medium text-slate-400">{dna.cross_layer_logic ?? "AND"}</span>
        </div>
      )}

      {/* Risk genes */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span>
          止损 {(dna.risk_genes.stop_loss * 100).toFixed(1)}%
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
      <div className="text-xs text-slate-500">
        执行: {dna.execution_genes.symbol} / {dna.execution_genes.timeframe.toUpperCase()}
      </div>
    </div>
  );
}
