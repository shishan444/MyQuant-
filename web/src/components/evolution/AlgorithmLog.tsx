import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface MutationEntry {
  generation: number;
  scoreChange: number;
  operation: string;
  details: string;
}

interface AlgorithmLogProps {
  mutations: MutationEntry[];
  diversity?: number;
}

const OPERATION_COLORS: Record<string, string> = {
  mutate_params: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  mutate_indicator: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  mutate_logic: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  mutate_risk: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  crossover: "bg-green-500/20 text-green-400 border-green-500/30",
  fresh_blood: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  add_layer: "bg-green-500/20 text-green-400 border-green-500/30",
  remove_layer: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  mutate_layer_timeframe: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  mutate_cross_logic: "bg-orange-500/20 text-orange-400 border-orange-500/30",
};

export function AlgorithmLog({ mutations, diversity }: AlgorithmLogProps) {
  const [open, setOpen] = useState(false);

  if (mutations.length === 0 && diversity == null) return null;

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-400"
        onClick={() => setOpen((v) => !v)}
      >
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 transition-transform",
            open && "rotate-180"
          )}
        />
        算法日志 (专家模式)
      </button>

      {open && (
        <div className="flex flex-col gap-3">
          {/* Mutation records */}
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-slate-500">
              最近变异记录
            </span>
            <div className="max-h-[300px] overflow-y-auto rounded-lg border border-slate-700/30 bg-white/[0.01]">
              {mutations.slice(0, 10).map((entry, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 border-b border-slate-700/20 px-3 py-2 last:border-b-0"
                >
                  <span className="shrink-0 font-mono text-[11px] text-slate-600">
                    Gen{entry.generation}
                  </span>
                  <span
                    className={cn(
                      "shrink-0 font-mono text-[11px] font-medium",
                      entry.scoreChange > 0
                        ? "text-emerald-400"
                        : entry.scoreChange < 0
                          ? "text-red-400"
                          : "text-slate-600"
                    )}
                  >
                    {entry.scoreChange > 0 ? "+" : ""}
                    {entry.scoreChange.toFixed(1)}
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "shrink-0 px-1.5 py-0 text-[10px]",
                      OPERATION_COLORS[entry.operation] ??
                        "bg-slate-500/20 text-slate-400 border-slate-500/30"
                    )}
                  >
                    {entry.operation}
                  </Badge>
                  <span className="truncate text-xs text-slate-500">
                    {entry.details}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Population diversity */}
          {diversity != null && (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">种群多样性</span>
                <span className="font-mono text-slate-400">
                  {diversity.toFixed(2)}
                </span>
              </div>
              <Progress
                value={diversity * 100}
                className="h-1.5 bg-slate-700/30 [&>[data-slot=progress-indicator]]:bg-gradient-to-r [&>[data-slot=progress-indicator]]:from-blue-500 [&>[data-slot=progress-indicator]]:to-purple-500"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
