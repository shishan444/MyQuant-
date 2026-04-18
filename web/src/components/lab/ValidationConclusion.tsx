import { Save, BarChart3, Dna } from "lucide-react";
import { useNavigate } from "react-router";
import { cn } from "@/lib/utils";
import type { ValidateResponse, DNA } from "@/types/api";
import { Button } from "@/components/ui/Button";

interface ValidationConclusionProps {
  result: ValidateResponse;
  onSave?: () => void;
  onBacktest?: (dna: DNA) => void;
  seedDna?: DNA;
}

function getScoreColor(rate: number): string {
  if (rate > 70) return "text-profit";
  if (rate >= 50) return "text-yellow-500";
  return "text-loss";
}

export function ValidationConclusion({ result, onSave, onBacktest, seedDna }: ValidationConclusionProps) {
  const { match_rate, total_count, match_count, mismatch_count } = result;
  const navigate = useNavigate();

  if (total_count === 0) {
    return (
      <div className="flex items-center justify-center gap-6 rounded-xl border border-border-default bg-bg-surface/50 px-6 py-3">
        <span className="text-sm text-text-muted">未找到匹配的触发条件</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-xl border border-border-default bg-bg-surface/50 px-6 py-3">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-secondary">符合率</span>
          <span className={cn("font-num text-lg font-semibold", getScoreColor(match_rate))}>
            {match_rate}%
          </span>
        </div>

        <div className="flex items-center gap-1 text-sm">
          <span className="text-text-primary">出现 {total_count} 次</span>
          <span className="text-text-secondary">(</span>
          <span className="text-profit">符合 {match_count}</span>
          <span className="text-text-secondary"> / </span>
          <span className="text-loss">不符合 {mismatch_count}</span>
          <span className="text-text-secondary">)</span>
        </div>

        {match_rate < 20 && (
          <span className="text-xs text-loss">
            该规律在历史数据中符合率较低, 建议调整条件或参数
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {onBacktest && seedDna && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onBacktest(seedDna)}
            className="gap-1.5 border-blue-400/30 text-blue-400 hover:bg-blue-400/10"
          >
            <BarChart3 className="h-3.5 w-3.5" />
            可视化回测
          </Button>
        )}
        {seedDna && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate("/evolution", { state: { seedDna } })}
            className="gap-1.5 border-purple-400/30 text-purple-400 hover:bg-purple-400/10"
          >
            <Dna className="h-3.5 w-3.5" />
            以此为种子进化
          </Button>
        )}
        {onSave && (
          <Button
            size="sm"
            variant="outline"
            onClick={onSave}
            className="gap-1.5 border-accent-gold/30 text-accent-gold hover:bg-accent-gold/10"
          >
            <Save className="h-3.5 w-3.5" />
            保存策略
          </Button>
        )}
      </div>
    </div>
  );
}
