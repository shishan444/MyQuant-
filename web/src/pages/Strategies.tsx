import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { motion, AnimatePresence } from "framer-motion";
import { BookOpen, Play, Pencil, Trash2, Search, Star, TrendingUp, Shield, Target, Dna, FlaskConical } from "lucide-react";
import { PageTransition } from "@/components/PageTransition";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useStrategies, useDeleteStrategy, useUpdateStrategy } from "@/hooks/useStrategies";
import { cn } from "@/lib/utils";
import type { Strategy } from "@/types/api";

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function fmtReturn(value: number | undefined | null): string {
  if (value == null) return "--";
  const pct = value * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

function fmtSharpe(value: number | undefined | null): string {
  if (value == null) return "--";
  return value.toFixed(2);
}

function fmtDrawdown(value: number | undefined | null): string {
  if (value == null) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function fmtWinRate(value: number | undefined | null): string {
  if (value == null) return "--";
  return `${(value * 100).toFixed(0)}%`;
}

// ---------------------------------------------------------------------------
// Source badge
// ---------------------------------------------------------------------------

const SOURCE_STYLES: Record<string, { bg: string; text: string; icon: React.ElementType }> = {
  evolution: { bg: "bg-accent-purple/15", text: "text-accent-purple", icon: Dna },
  lab: { bg: "bg-accent-gold/15", text: "text-accent-gold", icon: FlaskConical },
  manual: { bg: "bg-accent-gold/15", text: "text-accent-gold", icon: FlaskConical },
  import: { bg: "bg-info/15", text: "text-info", icon: BookOpen },
};

function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source] ?? SOURCE_STYLES.manual;
  const Icon = style.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium", style.bg, style.text)}>
      <Icon className="h-2.5 w-2.5" />
      {source === "evolution" ? "进化" : source === "lab" ? "实验室" : source === "import" ? "导入" : source}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Edit dialog
// ---------------------------------------------------------------------------

function EditStrategyDialog({
  open,
  strategy,
  onClose,
}: {
  open: boolean;
  strategy: Strategy | null;
  onClose: () => void;
}) {
  const updateMutation = useUpdateStrategy();
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [notes, setNotes] = useState("");

  const syncForm = () => {
    if (strategy) {
      setName(strategy.name ?? "");
      setTags(strategy.tags ?? "");
      setNotes(strategy.notes ?? "");
    }
  };

  const handleOpen = (val: boolean) => {
    if (val) syncForm();
    else onClose();
  };

  if (!strategy) return null;

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={handleOpen}
      title="编辑策略"
      confirmLabel="保存"
      onConfirm={() => {
        updateMutation.mutate(
          { id: strategy.strategy_id, payload: { name: name || undefined, tags: tags || undefined, notes: notes || undefined } },
          { onSuccess: onClose },
        );
      }}
      loading={updateMutation.isPending}
    >
      <div className="flex flex-col gap-3 py-2">
        <div>
          <label className="text-xs text-text-muted mb-1 block">名称</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="策略名称" className="h-8 text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">标签</label>
          <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="用逗号分隔" className="h-8 text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">备注</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="策略备注..."
            rows={3}
            className="w-full rounded-md border border-border-default bg-transparent px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent-gold/50"
          />
        </div>
      </div>
    </ConfirmDialog>
  );
}

// ---------------------------------------------------------------------------
// Strategy card row
// ---------------------------------------------------------------------------

const rowVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.04, duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] },
  }),
  exit: { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

interface StrategyRowProps {
  strategy: Strategy;
  index: number;
  starred: boolean;
  onToggleStar: () => void;
  onDelete: () => void;
  onEdit: () => void;
  onRun: () => void;
}

function StrategyCardRow({ strategy, index, starred, onToggleStar, onDelete, onEdit, onRun }: StrategyRowProps) {
  const m = strategy.metrics;
  const annualReturn = m?.annual_return;
  const returnTrend = annualReturn != null ? (annualReturn > 0 ? "up" : annualReturn < 0 ? "down" : "neutral") : "neutral";

  const paramSummary = useMemo(() => {
    if (!strategy.dna?.signal_genes?.length) return "";
    return strategy.dna.signal_genes
      .slice(0, 2)
      .map((g) => `${g.indicator}(${Object.values(g.params).join(",")})`)
      .join(" / ");
  }, [strategy.dna]);

  return (
    <motion.tr
      custom={index}
      variants={rowVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      layout
      className="group relative border-b border-border-default/50 transition-all duration-200 hover:bg-white/[0.03] hover:shadow-[-2px_0_0_0_var(--color-accent-gold)]"
      style={{ originY: 0 }}
    >
      {/* Name */}
      <td className="py-3 pl-4 pr-2">
        <div className="flex items-center gap-2.5">
          <motion.button
            onClick={onToggleStar}
            whileTap={{ scale: 1.4 }}
            transition={{ type: "spring", stiffness: 500, damping: 15 }}
            className="shrink-0"
            aria-label={starred ? "取消星标" : "添加星标"}
          >
            <Star
              className={cn(
                "h-3.5 w-3.5 transition-all duration-200",
                starred
                  ? "fill-accent-gold text-accent-gold drop-shadow-[0_0_4px_rgba(245,158,11,0.5)]"
                  : "text-text-muted/50 hover:text-accent-gold"
              )}
            />
          </motion.button>
          <div className="flex flex-col gap-0.5 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-text-primary truncate">
                {strategy.name ?? strategy.strategy_id.slice(0, 8)}
              </span>
              <SourceBadge source={strategy.source} />
            </div>
            {paramSummary && (
              <span className="text-xs text-text-muted font-mono leading-tight truncate">
                {paramSummary}
              </span>
            )}
          </div>
        </div>
      </td>

      {/* Annual return - hero metric */}
      <td className="py-3 px-2">
        <div className={cn(
          "inline-flex flex-col items-start",
        )}>
          <span
            className={cn(
              "font-mono text-[15px] font-semibold tabular-nums tracking-tight",
              returnTrend === "up" && "text-profit",
              returnTrend === "down" && "text-loss",
              returnTrend === "neutral" && "text-text-secondary"
            )}
          >
            {fmtReturn(annualReturn)}
          </span>
          {returnTrend !== "neutral" && (
            <TrendingUp className={cn(
              "h-2.5 w-2.5 mt-0.5",
              returnTrend === "up" ? "text-profit/60" : "text-loss/60 rotate-180"
            )} />
          )}
        </div>
      </td>

      {/* Sharpe */}
      <td className="py-3 px-2">
        <MetricPill value={fmtSharpe(m?.sharpe_ratio)} icon={Target} color={m?.sharpe_ratio != null && m.sharpe_ratio > 1 ? "good" : "neutral"} />
      </td>

      {/* Drawdown */}
      <td className="py-3 px-2">
        <MetricPill value={fmtDrawdown(m?.max_drawdown)} icon={Shield} color="danger" />
      </td>

      {/* Win rate */}
      <td className="py-3 px-2">
        <MetricPill value={fmtWinRate(m?.win_rate)} color={m?.win_rate != null && m.win_rate > 0.5 ? "good" : "neutral"} />
      </td>

      {/* Data */}
      <td className="py-3 px-2">
        <span className="text-xs text-text-muted font-mono">
          {strategy.symbol} <span className="text-text-muted/40">/</span> {strategy.timeframe}
        </span>
      </td>

      {/* Date */}
      <td className="py-3 px-2">
        <span className="font-mono text-xs text-text-muted/60 tabular-nums">
          {new Date(strategy.created_at).toLocaleDateString()}
        </span>
      </td>

      {/* Actions */}
      <td className="py-3 pr-4 text-right">
        <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0 transition-all duration-200">
          <motion.div whileHover={{ scale: 1.15 }} whileTap={{ scale: 0.9 }}>
            <Button variant="ghost" size="icon-xs" aria-label="运行回测" onClick={onRun} className="text-profit/70 hover:text-profit hover:bg-profit/10">
              <Play className="h-3.5 w-3.5" />
            </Button>
          </motion.div>
          <motion.div whileHover={{ scale: 1.15 }} whileTap={{ scale: 0.9 }}>
            <Button variant="ghost" size="icon-xs" aria-label="编辑策略" onClick={onEdit} className="text-text-muted hover:text-accent-gold hover:bg-accent-gold/10">
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          </motion.div>
          <motion.div whileHover={{ scale: 1.15 }} whileTap={{ scale: 0.9 }}>
            <Button variant="ghost" size="icon-xs" className="text-loss/60 hover:text-loss hover:bg-loss/10" aria-label="删除策略" onClick={onDelete}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </motion.div>
        </div>
      </td>
    </motion.tr>
  );
}

// ---------------------------------------------------------------------------
// Metric pill
// ---------------------------------------------------------------------------

function MetricPill({ value, icon: Icon, color }: { value: string; icon?: React.ElementType; color: "good" | "danger" | "neutral" }) {
  return (
    <div className={cn(
      "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[13px] font-mono tabular-nums",
      color === "good" && "bg-profit/8 text-profit/90",
      color === "danger" && "bg-loss/8 text-loss/80",
      color === "neutral" && "bg-white/[0.04] text-text-secondary",
    )}>
      {Icon && <Icon className="h-2.5 w-2.5 opacity-60" />}
      {value}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state with animation
// ---------------------------------------------------------------------------

function AnimatedEmptyState({ onNavigate }: { onNavigate: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="flex flex-col items-center justify-center gap-5 py-16"
    >
      <motion.div
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        className="relative"
      >
        <BookOpen className="h-14 w-14 text-accent-gold/30" />
        <motion.div
          className="absolute inset-0 rounded-full bg-accent-gold/5 blur-xl"
          animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
      </motion.div>
      <div className="flex flex-col items-center gap-2 text-center">
        <h3 className="text-lg font-medium text-text-primary">策略库为空</h3>
        <p className="text-sm text-text-secondary max-w-xs">
          通过策略实验室创建你的第一个策略，或启动进化任务自动发现策略
        </p>
      </div>
      <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
        <Button onClick={onNavigate} className="gap-2 bg-accent-gold/90 hover:bg-accent-gold text-bg-base font-medium">
          <FlaskConical className="h-4 w-4" />
          前往实验室
        </Button>
      </motion.div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="h-6 w-32 animate-pulse rounded bg-white/[0.04]" />
          <div className="ml-auto flex gap-2">
            <div className="h-7 w-44 animate-pulse rounded-md bg-white/[0.04]" />
            <div className="h-7 w-24 animate-pulse rounded-md bg-white/[0.04]" />
          </div>
        </div>
        <div className="rounded-xl border border-border-default/50 overflow-hidden">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-3.5 border-b border-border-default/30">
              <div className="h-3.5 w-3.5 rounded animate-pulse bg-white/[0.04]" />
              <div className="h-4 w-32 animate-pulse rounded bg-white/[0.04]" />
              <div className="ml-auto h-4 w-16 animate-pulse rounded bg-white/[0.04]" />
              <div className="h-4 w-12 animate-pulse rounded bg-white/[0.04]" />
              <div className="h-4 w-14 animate-pulse rounded bg-white/[0.04]" />
              <div className="h-4 w-20 animate-pulse rounded bg-white/[0.04]" />
            </div>
          ))}
        </div>
      </div>
    </PageTransition>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function Strategies() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [starredIds, setStarredIds] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<Strategy | null>(null);
  const [editTarget, setEditTarget] = useState<Strategy | null>(null);

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
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.strategy_id, {
      onSuccess: () => setDeleteTarget(null),
    });
  };

  const handleRun = (strategy: Strategy) => {
    if (!strategy.dna) return;
    navigate("/lab", {
      state: { dna: strategy.dna, symbol: strategy.symbol, timeframe: strategy.timeframe },
    });
  };

  // --- Loading ---
  if (isLoading) return <LoadingSkeleton />;

  // --- Empty ---
  if (allStrategies.length === 0) {
    return (
      <PageTransition>
        <AnimatedEmptyState onNavigate={() => navigate("/lab")} />
      </PageTransition>
    );
  }

  // --- Main ---
  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">
              已保存策略
            </span>
            <span className="font-mono text-xs text-accent-gold bg-accent-gold/10 rounded px-1.5 py-0.5 tabular-nums">
              {allStrategies.length}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <div className="relative group/search">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted/60 group-focus-within/search:text-text-secondary transition-colors" />
              <Input
                placeholder="搜索策略..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-48 pl-8 text-xs bg-white/[0.03] border-border-default/50 focus:border-accent-gold/30 transition-colors"
              />
            </div>

            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="h-8 w-28 text-xs bg-white/[0.03] border-border-default/50">
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

        {/* Strategy table */}
        <div className="rounded-xl border border-border-default/50 overflow-hidden bg-white/[0.01]">
          <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: "26%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "12%" }} />
            </colgroup>
            <thead>
              <tr className="border-b border-border-default/40">
                {["名称", "年化收益", "夏普", "回撤", "胜率", "数据", "日期", ""].map((h, i) => (
                  <th
                    key={h}
                    className={cn(
                      "py-2.5 text-left text-xs font-medium uppercase tracking-wider text-text-muted/60 whitespace-nowrap overflow-hidden text-ellipsis",
                      i === 0 && "pl-4",
                      i === 7 && "text-right pr-4",
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <AnimatePresence mode="popLayout">
                {filteredStrategies.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="h-24 text-center text-text-muted text-sm">
                      未找到匹配的策略
                    </td>
                  </tr>
                ) : (
                  filteredStrategies.map((strategy, i) => (
                    <StrategyCardRow
                      key={strategy.strategy_id}
                      strategy={strategy}
                      index={i}
                      starred={starredIds.has(strategy.strategy_id)}
                      onToggleStar={() => toggleStar(strategy.strategy_id)}
                      onDelete={() => setDeleteTarget(strategy)}
                      onEdit={() => setEditTarget(strategy)}
                      onRun={() => handleRun(strategy)}
                    />
                  ))
                )}
              </AnimatePresence>
            </tbody>
          </table>
        </div>

        {/* Delete confirm */}
        <ConfirmDialog
          open={deleteTarget !== null}
          onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
          title="删除策略"
          description={`确定要删除策略「${deleteTarget?.name ?? deleteTarget?.strategy_id}」吗？此操作不可撤销。`}
          confirmLabel="删除"
          variant="destructive"
          onConfirm={handleDelete}
          loading={deleteMutation.isPending}
        />

        {/* Edit dialog */}
        <EditStrategyDialog
          open={editTarget !== null}
          strategy={editTarget}
          onClose={() => setEditTarget(null)}
        />
      </div>
    </PageTransition>
  );
}
