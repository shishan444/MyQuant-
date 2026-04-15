import { useState, useCallback, useRef, useMemo, useEffect } from "react";
import {
  Play,
  Save,
  FlaskConical,
  ChevronDown,
  ChevronUp,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";

import { PageTransition } from "@/components/PageTransition";
import { GlassCard } from "@/components/GlassCard";
import { KlineChart } from "@/components/charts/KlineChart";
import type { KlineChartHandle } from "@/components/charts/KlineChart";
import { ChartToolbar } from "@/components/charts/ChartToolbar";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  ConditionPillGroup,
  ValidationConclusion,
  DistributionChart,
  ReferencePanel,
  TriggerTable,
  TriggerDetailDrawer,
  SaveStrategyDialog,
} from "@/components/lab";

import { useValidateHypothesis } from "@/hooks/useValidation";
import { useCreateStrategy } from "@/hooks/useStrategies";
import { useAvailableSources } from "@/hooks/useDatasets";
import { getOhlcvBySymbol, getChartIndicators } from "@/services/datasets";
import { SYMBOL_OPTIONS, TIMEFRAME_SELECT_OPTIONS } from "@/lib/constants";
import type {
  ConditionInput,
  ValidateResponse,
  TriggerRecord,
  ChartIndicatorsResponse,
} from "@/types/api";
import type { IndicatorData } from "@/components/charts/KlineChart";
import type { BollingerBandData } from "@/types/chart";
import { useChartSettings } from "@/stores/chart-settings";
import { useQuery } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const QUICK_DATES = [
  { label: "近3月", days: 90 },
  { label: "近6月", days: 180 },
  { label: "近1年", days: 365 },
  { label: "今年", days: -1 },
  { label: "全部", days: 0 },
];

const EXAMPLE_PRESETS = [
  {
    label: "上轨触碰后下跌",
    when: [
      { subject: "close", action: "touch", target: "bb_upper", logic: "AND" as const },
    ],
    then: [
      { subject: "close", action: "drop", target: "0", window: 8, logic: "AND" as const },
    ],
  },
  {
    label: "放量突破后上涨",
    when: [
      { subject: "close", action: "breakout", target: "bb_upper", logic: "AND" as const },
      { subject: "volume", action: "spike", target: "2", logic: "AND" as const },
    ],
    then: [
      { subject: "close", action: "rise", target: "0", window: 8, logic: "AND" as const },
    ],
  },
  {
    label: "RSI超买后回调",
    when: [
      { subject: "rsi", action: "gt", target: "70", logic: "AND" as const },
    ],
    then: [
      { subject: "close", action: "drop", target: "0", window: 12, logic: "AND" as const },
    ],
  },
];

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

/** Format a Date as YYYY-MM-DD in local timezone (avoids toISOString UTC shift). */
function toLocalDateStr(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Clamp a YYYY-MM-DD string to a valid date (e.g. 04-31 -> 04-30). */
function clampDate(dateStr: string): string {
  if (!dateStr) return dateStr;
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  const lastDay = new Date(y, m, 0).getDate();
  const clampedDay = Math.min(d, lastDay);
  const mm = String(m).padStart(2, "0");
  const dd = String(clampedDay).padStart(2, "0");
  return `${y}-${mm}-${dd}`;
}

function getDefaultDates(): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setFullYear(start.getFullYear() - 1);
  return {
    start: toLocalDateStr(start),
    end: toLocalDateStr(end),
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Lab() {
  // -- Builder state --
  const [pair, setPair] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("4h");
  const [dateRange, setDateRange] = useState(getDefaultDates);
  const [whenConditions, setWhenConditions] = useState<ConditionInput[]>([]);
  const [thenConditions, setThenConditions] = useState<ConditionInput[]>([]);
  const [builderCollapsed, setBuilderCollapsed] = useState(false);

  // -- Result state --
  const [result, setResult] = useState<ValidateResponse | null>(null);
  const [candleData, setCandleData] = useState<Array<{ timestamp: string; open: number; high: number; low: number; close: number; volume?: number }>>([]);
  const [detailTrigger, setDetailTrigger] = useState<TriggerRecord | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [indicatorResponse, setIndicatorResponse] = useState<ChartIndicatorsResponse | null>(null);

  // -- Refs --
  const chartRef = useRef<KlineChartHandle>(null);

  // -- Chart settings --
  const chartSettings = useChartSettings();

  // -- Mutations --
  const validateMutation = useValidateHypothesis();
  const createStrategyMutation = useCreateStrategy();

  // -- Available data sources --
  const { data: sourcesData } = useQuery(useAvailableSources());

  // Build dynamic symbol and timeframe options from available sources
  const dynamicSymbolOptions = useMemo(() => {
    if (!sourcesData?.sources?.length) return SYMBOL_OPTIONS;
    const seen = new Set<string>();
    const opts: { value: string; label: string }[] = [];
    for (const s of sourcesData.sources) {
      if (!seen.has(s.symbol)) {
        seen.add(s.symbol);
        opts.push({ value: s.symbol, label: s.symbol });
      }
    }
    return opts.length > 0 ? opts : SYMBOL_OPTIONS;
  }, [sourcesData]);

  const dynamicTimeframeOptions = useMemo(() => {
    if (!sourcesData?.sources?.length) return TIMEFRAME_SELECT_OPTIONS;
    const filtered = sourcesData.sources.filter((s) => s.symbol === pair);
    if (filtered.length === 0) return TIMEFRAME_SELECT_OPTIONS;
    const seen = new Set<string>();
    const opts: { value: string; label: string }[] = [];
    for (const s of filtered) {
      if (!seen.has(s.timeframe)) {
        seen.add(s.timeframe);
        opts.push({ value: s.timeframe, label: s.timeframe });
      }
    }
    return opts.length > 0 ? opts : TIMEFRAME_SELECT_OPTIONS;
  }, [sourcesData, pair]);

  // Auto-set default date range
  useEffect(() => {
    const match = sourcesData?.sources?.find(
      (s) => s.symbol === pair && s.timeframe === timeframe
    );
    if (match?.time_end) {
      const end = new Date(match.time_end);
      const start = new Date(end);
      start.setFullYear(start.getFullYear() - 1);
      const startDate = toLocalDateStr(start);
      const clampStart = match.time_start && startDate < match.time_start
        ? match.time_start
        : startDate;
      const newEnd = toLocalDateStr(end);
      setDateRange((prev) => {
        if (prev.start === clampStart && prev.end === newEnd) return prev;
        return { start: clampStart, end: newEnd };
      });
    }
  }, [pair, timeframe, sourcesData]);

  // -- baseTimeframe = timeframe (data source period) --
  const baseTimeframe = timeframe;

  // -- Derived --
  const hasConditions = whenConditions.length > 0 && thenConditions.length > 0;
  const isLoading = validateMutation.isPending;
  const hasResult = result !== null;

  // Collect referenced timeframes from conditions
  const referencedTimeframes = useMemo(() => {
    const tfs = new Set<string>();
    for (const c of [...whenConditions, ...thenConditions]) {
      if (c.timeframe && c.timeframe !== baseTimeframe) {
        tfs.add(c.timeframe);
      }
    }
    return Array.from(tfs);
  }, [whenConditions, thenConditions, baseTimeframe]);

  // Extract volume data from candle data
  const volumeData = useMemo(
    () =>
      candleData
        .filter((d) => d.volume != null)
        .map((d) => ({
          time: d.timestamp,
          value: d.volume!,
          color: d.close >= d.open ? "rgba(0,200,83,0.2)" : "rgba(255,23,68,0.2)",
        })),
    [candleData],
  );

  // -- Handlers --
  const handleQuickDate = useCallback((days: number) => {
    const end = new Date();
    if (days === 0) {
      const match = sourcesData?.sources?.find(
        (s) => s.symbol === pair && s.timeframe === timeframe
      );
      const start = match?.time_start ?? "2024-01-01";
      setDateRange({ start, end: toLocalDateStr(end) });
      return;
    }
    const start = new Date();
    if (days === -1) {
      start.setMonth(0, 1);
      start.setHours(0, 0, 0, 0);
    } else {
      start.setDate(start.getDate() - days);
    }
    setDateRange({
      start: toLocalDateStr(start),
      end: toLocalDateStr(end),
    });
  }, [pair, timeframe, sourcesData]);

  const handleValidate = useCallback(async () => {
    if (whenConditions.length === 0) {
      toast.error("请至少添加一个WHEN条件");
      return;
    }
    if (thenConditions.length === 0) {
      toast.error("请至少添加一个THEN条件");
      return;
    }

    // Validate dates before submitting
    if (!dateRange.start || !dateRange.end) {
      toast.error("请输入有效的日期范围（非法日期如 04-31 会被浏览器清除）");
      return;
    }
    if (dateRange.start > dateRange.end) {
      toast.error("开始日期不能晚于结束日期");
      return;
    }

    // Clamp dates before submitting (fixes invalid dates like 04-31)
    const safeStart = clampDate(dateRange.start);
    const safeEnd = clampDate(dateRange.end);

    try {
      const res = await validateMutation.mutateAsync({
        pair,
        timeframe,
        base_timeframe: baseTimeframe,
        start: safeStart,
        end: safeEnd,
        when: whenConditions,
        then: thenConditions,
      });
      setResult(res);

      // Fetch OHLCV and chart indicators independently (each can fail without blocking the other)
      const enabledEma = chartSettings.emaList.filter((e) => e.enabled);
      const indParams = {
        start: safeStart,
        end: safeEnd,
        ema_periods: enabledEma.map((e) => e.period).join(",") || undefined,
        boll_enabled: chartSettings.boll.enabled,
        boll_period: chartSettings.boll.period,
        boll_std: chartSettings.boll.std,
        rsi_enabled: chartSettings.rsi.enabled,
        rsi_period: chartSettings.rsi.period,
      };

      // Fetch OHLCV data (critical for chart)
      try {
        const ohlcvRes = await getOhlcvBySymbol(pair, timeframe, {
          start: safeStart,
          end: safeEnd,
          limit: 10000,
        });
        setCandleData(ohlcvRes.data);
      } catch (err) {
        // silently handle
      }

      // Fetch indicator data (optional, failure should not affect chart)
      try {
        const indRes = await getChartIndicators(pair, timeframe, indParams);
        setIndicatorResponse(indRes);
      } catch (err) {
        // indicators unavailable - chart still works without them
      }
    } catch {
      // handled by mutation
    }
  }, [pair, timeframe, baseTimeframe, dateRange, whenConditions, thenConditions, validateMutation]);

  const handleClearAll = useCallback(() => {
    setWhenConditions([]);
    setThenConditions([]);
    setResult(null);
    setCandleData([]);
    setIndicatorResponse(null);
  }, []);

  const handlePreset = useCallback((idx: number) => {
    const preset = EXAMPLE_PRESETS[idx];
    setWhenConditions([...preset.when]);
    setThenConditions([...preset.then]);
    setResult(null);
  }, []);

  const handleLocate = useCallback((trigger: TriggerRecord) => {
    chartRef.current?.scrollToTime(trigger.time);
    const chartEl = document.getElementById("lab-kline-section");
    if (chartEl) {
      chartEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  const handleViewDetail = useCallback((trigger: TriggerRecord) => {
    setDetailTrigger(trigger);
    setDrawerOpen(true);
  }, []);

  const handleSaveStrategy = useCallback(async (data: { name: string; description: string; tags: string }) => {
    if (!result) return;
    try {
      await createStrategyMutation.mutateAsync({
        name: data.name,
        dna: undefined,
        symbol: pair,
        timeframe,
        source: "lab",
        tags: data.tags,
        notes: data.description,
      });
      toast.success("策略已保存");
      setSaveDialogOpen(false);
    } catch {
      // handled by mutation
    }
  }, [result, pair, timeframe, createStrategyMutation]);

  // -- Trigger markers for chart --
  const triggerMarkers = useMemo(
    () =>
      result?.triggers?.map((t) => ({
        id: t.id,
        time: t.time,
        matched: t.matched,
      })) ?? [],
    [result?.triggers],
  );

  // -- Chart indicator data for KlineChart --
  const chartIndicators = useMemo<IndicatorData[] | undefined>(() => {
    if (!indicatorResponse) return undefined;
    const indicators: IndicatorData[] = [];

    // EMA indicators
    const emaList = chartSettings.emaList.filter((e) => e.enabled);
    for (const ema of emaList) {
      const emaData = indicatorResponse.ema?.[String(ema.period)];
      if (emaData) {
        indicators.push({
          id: `ema_${ema.period}`,
          type: "ema",
          color: ema.color,
          data: emaData,
        });
      }
    }

    // RSI indicator
    if (chartSettings.rsi.enabled && indicatorResponse.rsi) {
      indicators.push({
        id: "rsi",
        type: "rsi",
        color: "#A78BFA",
        data: indicatorResponse.rsi,
      });
    }

    return indicators.length > 0 ? indicators : undefined;
  }, [indicatorResponse, chartSettings.emaList, chartSettings.rsi.enabled]);

  const chartBollData = useMemo<BollingerBandData | undefined>(() => {
    if (!indicatorResponse?.boll || !chartSettings.boll.enabled) return undefined;
    return indicatorResponse.boll;
  }, [indicatorResponse?.boll, chartSettings.boll.enabled]);

  // -- Collapsed summary --
  const collapsedSummary = useMemo(() => {
    const parts = [`${pair} ${timeframe}`];
    if (whenConditions.length > 0) {
      const whenStr = whenConditions
        .filter((c) => c.subject)
        .map((c) => `${c.subject} ${c.action} ${c.target}`)
        .join("+");
      parts.push(`WHEN: ${whenStr}`);
    }
    if (thenConditions.length > 0) {
      const thenStr = thenConditions
        .filter((c) => c.subject)
        .map((c) => `${c.subject} ${c.action} ${c.target}`)
        .join("+");
      parts.push(`THEN: ${thenStr}`);
    }
    return parts.join(" / ");
  }, [pair, timeframe, whenConditions, thenConditions]);

  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* Region 1: Condition Builder */}
        <GlassCard className="p-4" hover={false}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">规律构建器</h3>
            <button
              type="button"
              onClick={() => setBuilderCollapsed(!builderCollapsed)}
              className="flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-text-secondary"
            >
              {builderCollapsed ? (
                <><ChevronUp className="h-3.5 w-3.5" />展开</>
              ) : (
                <><ChevronDown className="h-3.5 w-3.5" />收起</>
              )}
            </button>
          </div>

          {builderCollapsed ? (
            <div className="flex items-center justify-between py-1">
              <span className="truncate text-xs text-text-secondary">
                {collapsedSummary}
              </span>
              <button
                type="button"
                onClick={() => setBuilderCollapsed(false)}
                className="text-xs text-accent-gold"
              >
                展开
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {/* Data source row */}
              <div>
                <span className="mb-1.5 block text-xs font-medium text-text-muted">
                  数据源
                </span>
                <div className="flex flex-wrap items-center gap-3">
                  <Select value={pair} onValueChange={setPair}>
                    <SelectTrigger className="h-8 w-36 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {dynamicSymbolOptions.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Select value={timeframe} onValueChange={setTimeframe}>
                    <SelectTrigger className="h-8 w-24 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {dynamicTimeframeOptions.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <input
                    type="date"
                    value={dateRange.start}
                    onChange={(e) =>
                      setDateRange((prev) => ({ ...prev, start: e.target.value }))
                    }
                    className="h-8 w-28 cursor-pointer rounded-md border border-border-default bg-bg-surface px-2 text-xs text-text-primary outline-none focus:border-accent-gold [::-webkit-calendar-picker-indicator]:cursor-pointer"
                  />
                  <span className="text-xs text-text-muted">~</span>
                  <input
                    type="date"
                    value={dateRange.end}
                    onChange={(e) =>
                      setDateRange((prev) => ({ ...prev, end: e.target.value }))
                    }
                    className="h-8 w-28 cursor-pointer rounded-md border border-border-default bg-bg-surface px-2 text-xs text-text-primary outline-none focus:border-accent-gold [::-webkit-calendar-picker-indicator]:cursor-pointer"
                  />

                  <div className="flex items-center gap-1">
                    {QUICK_DATES.map((qd) => (
                      <button
                        key={qd.label}
                        type="button"
                        onClick={() => handleQuickDate(qd.days)}
                        className="rounded px-2 py-1 text-[11px] text-text-muted transition-colors hover:bg-white/5 hover:text-text-secondary"
                      >
                        {qd.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* WHEN conditions */}
              <ConditionPillGroup
                label="WHEN"
                description='找出"什么情况下"'
                conditions={whenConditions}
                onConditionsChange={setWhenConditions}
                baseTimeframe={baseTimeframe}
                referencedTimeframes={referencedTimeframes}
              />

              {/* THEN conditions */}
              <ConditionPillGroup
                label="THEN"
                description='验证"触发后会发生什么"'
                conditions={thenConditions}
                onConditionsChange={setThenConditions}
                isThen
                baseTimeframe={baseTimeframe}
                referencedTimeframes={referencedTimeframes}
              />

              {/* Action buttons */}
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={handleClearAll}
                  className="flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-loss"
                >
                  <RotateCcw className="h-3 w-3" />
                  清空全部
                </button>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleValidate}
                    disabled={isLoading || !hasConditions}
                    className="gap-1.5 bg-accent-gold text-black hover:bg-accent-gold/90"
                  >
                    <Play className="h-3.5 w-3.5" />
                    {isLoading ? "验证中..." : "验证规律"}
                  </Button>

                  {hasResult && result.total_count > 0 && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSaveDialogOpen(true)}
                      disabled={createStrategyMutation.isPending}
                      className="gap-1.5 border-accent-gold/30 text-accent-gold hover:bg-accent-gold/10"
                    >
                      <Save className="h-3.5 w-3.5" />
                      保存为策略
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}
        </GlassCard>

        {/* Empty state / Loading / Results */}

        {!hasResult && !isLoading && (
          <GlassCard className="p-8" hover={false}>
            <div className="flex flex-col items-center gap-4">
              <FlaskConical className="h-16 w-16 text-text-muted/30" />
              <div className="flex flex-col items-center gap-1 text-center">
                <h3 className="text-base font-medium text-text-secondary">
                  定义你的交易假设, 验证它的可靠性
                </h3>
                <p className="text-sm text-text-muted">
                  添加WHEN和THEN条件, 然后点击"验证规律"
                </p>
              </div>
              <div className="flex items-center gap-3">
                {EXAMPLE_PRESETS.map((preset, i) => (
                  <Button
                    key={i}
                    size="sm"
                    variant="outline"
                    onClick={() => handlePreset(i)}
                    className="text-xs"
                  >
                    示例{i + 1}: {preset.label}
                  </Button>
                ))}
              </div>
            </div>
          </GlassCard>
        )}

        {isLoading && (
          <>
            <GlassCard className="p-4" hover={false}>
              <div className="flex items-center gap-6">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-6 w-40" />
              </div>
            </GlassCard>
            <GlassCard className="p-4" hover={false}>
              <Skeleton className="h-[450px] w-full rounded-lg" />
            </GlassCard>
          </>
        )}

        {hasResult && !isLoading && (
          <>
            {/* Region 2: Validation Conclusion */}
            <ValidationConclusion
              result={result}
              onSave={result.total_count > 0 ? () => setSaveDialogOpen(true) : undefined}
            />

            {/* Low match rate suggestion */}
            {result.total_count > 0 && result.match_rate < 20 && (
              <GlassCard className="p-3" hover={false}>
                <p className="text-xs text-text-muted">
                  符合率较低 ({result.match_rate}%)。建议：扩大时间范围、调整条件参数、或切换到更高周期进行验证。
                </p>
              </GlassCard>
            )}

            {/* No matches suggestion */}
            {result.total_count === 0 && (
              <GlassCard className="p-4" hover={false}>
                <div className="flex flex-col items-center gap-3 text-center">
                  <p className="text-sm text-text-muted">未找到符合条件的触发记录</p>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" onClick={handleClearAll}>
                      调整条件
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleQuickDate(0)}>
                      扩大时间范围
                    </Button>
                  </div>
                </div>
              </GlassCard>
            )}

            {/* Region 3: KlineChart */}
            <GlassCard className="p-4" hover={false} id="lab-kline-section">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-3 text-xs text-text-muted">
                  <span className="font-medium text-text-secondary">
                    {pair} / {timeframe}
                  </span>
                  {result.match_count > 0 && (
                    <span className="text-profit">符合 {result.match_count}</span>
                  )}
                  {result.mismatch_count > 0 && (
                    <span className="text-loss">不符合 {result.mismatch_count}</span>
                  )}
                </div>
                <ChartToolbar
                  onZoomIn={() => chartRef.current?.zoomIn()}
                  onZoomOut={() => chartRef.current?.zoomOut()}
                  onReset={() => chartRef.current?.resetView()}
                  onFullscreen={() => {
                    const el = document.getElementById("lab-kline-section");
                    if (el && !document.fullscreenElement) {
                      el.requestFullscreen().catch(() => {});
                    } else {
                      document.exitFullscreen().catch(() => {});
                    }
                  }}
                />
              </div>
              <KlineChart
                ref={chartRef}
                data={candleData}
                indicators={chartIndicators}
                bollData={chartBollData}
                triggers={triggerMarkers}
                height={650}
                volumeData={volumeData}
              />
            </GlassCard>

            {/* Region 4: Distribution + Reference */}
            {result.total_count > 0 && (
              <GlassCard className="p-4" hover={false}>
                <div className="grid grid-cols-2 gap-6">
                  <DistributionChart distribution={result.distribution} />
                  <ReferencePanel
                    percentiles={result.percentiles}
                    concentration={result.concentration}
                    signal_frequency={result.signal_frequency}
                    extremes={result.extremes}
                  />
                </div>
              </GlassCard>
            )}

            {/* Region 5: Trigger Table */}
            {result.triggers.length > 0 && (
              <GlassCard className="p-4" hover={false}>
                <TriggerTable
                  triggers={result.triggers}
                  onLocate={handleLocate}
                  onViewDetail={handleViewDetail}
                  pair={pair}
                  timeframe={timeframe}
                />
              </GlassCard>
            )}
          </>
        )}

        {/* Trigger Detail Drawer */}
        <TriggerDetailDrawer
          trigger={detailTrigger}
          open={drawerOpen}
          onClose={() => {
            setDrawerOpen(false);
            setDetailTrigger(null);
          }}
        />

        {/* Save Strategy Dialog */}
        <SaveStrategyDialog
          open={saveDialogOpen}
          onClose={() => setSaveDialogOpen(false)}
          onSave={handleSaveStrategy}
          pair={pair}
          timeframe={timeframe}
          matchRate={result?.match_rate ?? 0}
          totalCount={result?.total_count ?? 0}
        />
      </div>
    </PageTransition>
  );
}
