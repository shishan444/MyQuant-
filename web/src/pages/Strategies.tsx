import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Play, Pencil, Trash2, Search, Plus, Upload, Star } from "lucide-react";
import { PageTransition } from "@/components/PageTransition";
import { EmptyState } from "@/components/EmptyState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useStrategies, useDeleteStrategy } from "@/hooks/useStrategies";
import { formatPercent, cn } from "@/lib/utils";
import type { Strategy } from "@/types/api";

type TrendDirection = "up" | "down" | "neutral";

function getReturnTrend(value: number): TrendDirection {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

export function Strategies() {
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [starredIds, setStarredIds] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<Strategy | null>(null);

  const { data, isLoading } = useQuery(
    useStrategies({ sort_by: "created_at", sort_order: "desc", limit: 50 })
  );
  const deleteMutation = useDeleteStrategy();

  const allStrategies: Strategy[] = data?.items ?? [];

  const filteredStrategies = useMemo(() => {
    let result = allStrategies;

    if (sourceFilter !== "all") {
      result = result.filter((s) => s.source === sourceFilter);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.name?.toLowerCase().includes(query) ||
          s.symbol.toLowerCase().includes(query) ||
          s.strategy_id.toLowerCase().includes(query)
      );
    }

    return result;
  }, [allStrategies, sourceFilter, searchQuery]);

  const toggleStar = (id: string) => {
    setStarredIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.strategy_id, {
      onSuccess: () => setDeleteTarget(null),
    });
  };

  if (isLoading) {
    return (
      <PageTransition>
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Skeleton className="h-9 w-28" />
            <Skeleton className="h-9 w-20" />
            <Skeleton className="h-9 w-48 ml-auto" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      </PageTransition>
    );
  }

  if (allStrategies.length === 0) {
    return (
      <PageTransition>
        <EmptyState
          icon={BookOpen}
          title="策略库为空"
          description="还没有保存的策略。通过策略实验室创建你的第一个策略吧。"
          actions={[
            { label: "前往实验室", onClick: () => {} },
            { label: "导入策略", onClick: () => {}, variant: "outline" },
          ]}
        />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* 工具栏 */}
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            新建策略
          </Button>
          <Button size="sm" variant="outline" className="gap-1.5">
            <Upload className="h-3.5 w-3.5" />
            导入
          </Button>

          <span className="text-sm text-text-secondary ml-2">
            已保存策略 ({allStrategies.length})
          </span>

          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
              <Input
                placeholder="搜索策略..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-48 pl-8 text-xs"
              />
            </div>

            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="h-8 w-28 text-xs">
                <SelectValue placeholder="来源" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部来源</SelectItem>
                <SelectItem value="lab">实验室</SelectItem>
                <SelectItem value="evolution">进化</SelectItem>
                <SelectItem value="import">导入</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 策略表格 */}
        <div className="rounded-lg border border-border-default overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-[#0f0f18] hover:bg-[#0f0f18]">
                <TableHead className="text-text-secondary">名称</TableHead>
                <TableHead className="text-text-secondary">收益率</TableHead>
                <TableHead className="text-text-secondary">夏普</TableHead>
                <TableHead className="text-text-secondary">数据</TableHead>
                <TableHead className="text-text-secondary">日期</TableHead>
                <TableHead className="w-28 text-right text-text-secondary">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredStrategies.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-text-muted">
                    未找到匹配的策略
                  </TableCell>
                </TableRow>
              ) : (
                filteredStrategies.map((strategy) => (
                  <StrategyRow
                    key={strategy.strategy_id}
                    strategy={strategy}
                    starred={starredIds.has(strategy.strategy_id)}
                    onToggleStar={() => toggleStar(strategy.strategy_id)}
                    onDelete={() => setDeleteTarget(strategy)}
                  />
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* 删除确认 */}
        <ConfirmDialog
          open={deleteTarget !== null}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null);
          }}
          title="删除策略"
          description={`确定要删除策略「${deleteTarget?.name ?? deleteTarget?.strategy_id}」吗？此操作不可撤销。`}
          confirmLabel="删除"
          variant="destructive"
          onConfirm={handleDelete}
          loading={deleteMutation.isPending}
        />
      </div>
    </PageTransition>
  );
}

interface StrategyRowProps {
  strategy: Strategy;
  starred: boolean;
  onToggleStar: () => void;
  onDelete: () => void;
}

function StrategyRow({ strategy, starred, onToggleStar, onDelete }: StrategyRowProps) {
  const returnRate = strategy.best_score ?? 0;
  const trend: TrendDirection = getReturnTrend(returnRate);

  const paramSummary = useMemo(() => {
    if (!strategy.dna?.signal_genes?.length) return "";
    return strategy.dna.signal_genes
      .slice(0, 2)
      .map((g) => `${g.indicator}(${Object.values(g.params).join(",")})`)
      .join(" / ");
  }, [strategy.dna]);

  return (
    <TableRow className="group">
      {/* 名称列 */}
      <TableCell>
        <div className="flex items-start gap-2">
          <button
            onClick={onToggleStar}
            className="mt-0.5 shrink-0"
            aria-label={starred ? "取消星标" : "添加星标"}
          >
            <Star
              className={cn(
                "h-3.5 w-3.5 transition-colors",
                starred
                  ? "fill-accent-gold text-accent-gold"
                  : "text-text-muted hover:text-accent-gold"
              )}
            />
          </button>
          <div className="flex flex-col">
            <span className="text-sm font-medium text-text-primary">
              {strategy.name ?? strategy.strategy_id.slice(0, 8)}
            </span>
            {paramSummary && (
              <span className="text-[11px] text-text-muted leading-tight">
                {paramSummary}
              </span>
            )}
          </div>
        </div>
      </TableCell>

      {/* 收益率列 */}
      <TableCell>
        <span
          className={cn(
            "font-num text-sm font-medium",
            trend === "up" && "text-profit",
            trend === "down" && "text-loss",
            trend === "neutral" && "text-text-primary"
          )}
        >
          {formatPercent(returnRate)}
        </span>
      </TableCell>

      {/* 夏普列 */}
      <TableCell>
        <span className="font-num text-sm text-text-primary">
          {strategy.best_score != null ? strategy.best_score.toFixed(2) : "-"}
        </span>
      </TableCell>

      {/* 数据列 */}
      <TableCell>
        <span className="text-sm text-text-secondary">
          {strategy.symbol} / {strategy.timeframe}
        </span>
      </TableCell>

      {/* 日期列 */}
      <TableCell>
        <span className="font-num text-xs text-text-muted">
          {new Date(strategy.created_at).toLocaleDateString()}
        </span>
      </TableCell>

      {/* 操作列 */}
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button variant="ghost" size="icon-xs" aria-label="运行回测">
            <Play className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon-xs" aria-label="编辑策略">
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-loss hover:text-loss"
            aria-label="删除策略"
            onClick={onDelete}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}
