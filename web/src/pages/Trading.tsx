import { useState, useMemo } from "react";
import { TrendingUp, Pause, Eye } from "lucide-react";
import { PageTransition } from "@/components/PageTransition";
import { GlassCard } from "@/components/GlassCard";
import { StatCard } from "@/components/StatCard";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

type TrendDirection = "up" | "down" | "neutral";
type TimeRange = "1w" | "1m" | "all";
type PositionSide = "long" | "short" | "flat";

interface RunningStrategy {
  id: string;
  name: string;
  runningDays: number;
  signalCount: number;
  currentAmount: number;
  returnRate: number;
  position: PositionSide;
}

interface Position {
  id: string;
  strategyName: string;
  side: PositionSide;
  openPrice: number;
  currentPrice: number;
  pnl: number;
  takeProfit: number;
  stopLoss: number;
}

const MOCK_RUNNING_STRATEGIES: RunningStrategy[] = [
  {
    id: "1",
    name: "BTC EMA 交叉策略",
    runningDays: 15,
    signalCount: 8,
    currentAmount: 108500,
    returnRate: 0.085,
    position: "long",
  },
  {
    id: "2",
    name: "ETH RSI 超卖反弹",
    runningDays: 7,
    signalCount: 3,
    currentAmount: 96200,
    returnRate: -0.038,
    position: "short",
  },
  {
    id: "3",
    name: "SOL 布林带突破",
    runningDays: 22,
    signalCount: 12,
    currentAmount: 103100,
    returnRate: 0.031,
    position: "flat",
  },
];

const MOCK_POSITIONS: Position[] = [
  {
    id: "1",
    strategyName: "BTC EMA 交叉策略",
    side: "long",
    openPrice: 95000,
    currentPrice: 101200,
    pnl: 6200,
    takeProfit: 105000,
    stopLoss: 92000,
  },
  {
    id: "2",
    strategyName: "ETH RSI 超卖反弹",
    side: "short",
    openPrice: 2200,
    currentPrice: 2116,
    pnl: 84,
    takeProfit: 2000,
    stopLoss: 2350,
  },
];

const POSITION_BADGE_MAP: Record<PositionSide, { label: string; className: string }> = {
  long: { label: "多头", className: "text-profit border-profit/30" },
  short: { label: "空头", className: "text-loss border-loss/30" },
  flat: { label: "空仓", className: "text-text-muted border-border-default" },
};

function getReturnTrend(value: number): TrendDirection {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

export function Trading() {
  const [timeRange, setTimeRange] = useState<TimeRange>("1m");
  const [strategies] = useState<RunningStrategy[]>(MOCK_RUNNING_STRATEGIES);
  const [positions] = useState<Position[]>(MOCK_POSITIONS);

  const hasRunningStrategies = strategies.length > 0;

  const portfolioStats = useMemo(() => {
    const initialCapital = 100000;
    const currentTotal = strategies.reduce((sum, s) => sum + s.currentAmount, 0);
    const totalReturn = (currentTotal - initialCapital * strategies.length) / (initialCapital * strategies.length);
    return {
      initialCapital,
      current: currentTotal,
      totalReturn,
      vsBtc: totalReturn - 0.042,
    };
  }, [strategies]);

  if (!hasRunningStrategies) {
    return (
      <PageTransition>
        <EmptyState
          icon={TrendingUp}
          title="还没有运行中的模拟交易策略"
          description="添加策略开始模拟交易，实时跟踪策略表现和持仓状态。"
          actions={[
            { label: "添加策略", onClick: () => {} },
            {
              label: "前往策略库",
              onClick: () => {},
              variant: "outline",
            },
          ]}
        />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* 顶部操作栏 */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">模拟交易</h2>
          <Button size="sm" className="gap-1.5">
            添加策略
          </Button>
        </div>

        {/* 资金曲线汇总卡片 */}
        <GlassCard hover={false}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-text-secondary">资金曲线汇总</h3>
            <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
          </div>

          {/* 图表占位区域 */}
          <div className="flex h-48 items-center justify-center rounded-lg bg-[#0a0a0f]/50 mb-4">
            <p className="text-sm text-text-muted">资金曲线将在此展示</p>
          </div>

          {/* 底部统计栏 */}
          <div className="grid grid-cols-4 gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-text-secondary">初始资金</span>
              <span className="text-sm font-num text-text-primary">
                {formatCurrency(portfolioStats.initialCapital)}
              </span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-text-secondary">当前资金</span>
              <span className="text-sm font-num text-text-primary">
                {formatCurrency(portfolioStats.current)}
              </span>
            </div>
            <StatCard
              label="总收益"
              value={formatPercent(portfolioStats.totalReturn)}
              trend={getReturnTrend(portfolioStats.totalReturn)}
              className="p-2"
            />
            <StatCard
              label="vs BTC"
              value={formatPercent(portfolioStats.vsBtc)}
              trend={getReturnTrend(portfolioStats.vsBtc)}
              className="p-2"
            />
          </div>
        </GlassCard>

        {/* 运行中的策略 */}
        <div>
          <h3 className="mb-3 text-sm font-medium text-text-secondary">
            运行中的策略 ({strategies.length})
          </h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {strategies.map((strategy) => (
              <RunningStrategyCard key={strategy.id} strategy={strategy} />
            ))}
          </div>
        </div>

        {/* 持仓详情表格 */}
        {positions.length > 0 && (
          <div>
            <h3 className="mb-3 text-sm font-medium text-text-secondary">
              持仓详情
            </h3>
            <div className="rounded-lg border border-border-default overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#0f0f18] hover:bg-[#0f0f18]">
                    <TableHead className="text-text-secondary">策略</TableHead>
                    <TableHead className="text-text-secondary">方向</TableHead>
                    <TableHead className="text-text-secondary">开仓价</TableHead>
                    <TableHead className="text-text-secondary">当前价</TableHead>
                    <TableHead className="text-text-secondary">盈亏</TableHead>
                    <TableHead className="text-text-secondary">止盈</TableHead>
                    <TableHead className="text-text-secondary">止损</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {positions.map((pos) => (
                    <PositionRow key={pos.id} position={pos} />
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </div>
    </PageTransition>
  );
}

interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (value: TimeRange) => void;
}

function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  const options: { label: string; value: TimeRange }[] = [
    { label: "1周", value: "1w" },
    { label: "1月", value: "1m" },
    { label: "全部", value: "all" },
  ];

  return (
    <div className="flex items-center gap-1 rounded-md bg-[#0a0a0f]/50 p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            "rounded px-2 py-1 text-xs transition-colors",
            value === opt.value
              ? "bg-accent-gold/20 text-accent-gold"
              : "text-text-muted hover:text-text-secondary"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

interface RunningStrategyCardProps {
  strategy: RunningStrategy;
}

function RunningStrategyCard({ strategy }: RunningStrategyCardProps) {
  const trend: TrendDirection = getReturnTrend(strategy.returnRate);
  const positionBadge = POSITION_BADGE_MAP[strategy.position];

  return (
    <GlassCard className="flex flex-col gap-3" hover={false}>
      {/* 策略头部 */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-text-primary">
            {strategy.name}
          </span>
          <span className="text-xs text-text-muted">
            运行 {strategy.runningDays} 天 / {strategy.signalCount} 个信号
          </span>
        </div>
        <Badge variant="outline" className={cn("h-5 text-[10px]", positionBadge.className)}>
          {positionBadge.label}
        </Badge>
      </div>

      {/* 金额与收益率 */}
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-text-secondary">当前金额</span>
          <span className="text-base font-num font-semibold text-text-primary">
            {formatCurrency(strategy.currentAmount)}
          </span>
        </div>
        <span
          className={cn(
            "font-num text-sm font-medium",
            trend === "up" && "text-profit",
            trend === "down" && "text-loss",
            trend === "neutral" && "text-text-primary"
          )}
        >
          {formatPercent(strategy.returnRate)}
        </span>
      </div>

      {/* 收益率进度条 */}
      <Progress
        value={Math.min(Math.abs(strategy.returnRate) * 100, 100)}
        className={cn(
          "h-1.5",
          trend === "up" && "[&>[data-slot=progress-indicator]]:bg-profit",
          trend === "down" && "[&>[data-slot=progress-indicator]]:bg-loss",
          trend === "neutral" && "[&>[data-slot=progress-indicator]]:bg-text-muted"
        )}
      />

      {/* 操作按钮 */}
      <div className="flex items-center gap-2 pt-1">
        <Button variant="outline" size="xs" className="gap-1 text-xs">
          <Pause className="h-3 w-3" />
          暂停
        </Button>
        <Button variant="ghost" size="xs" className="gap-1 text-xs text-text-secondary">
          <Eye className="h-3 w-3" />
          详情
        </Button>
      </div>
    </GlassCard>
  );
}

interface PositionRowProps {
  position: Position;
}

function PositionRow({ position }: PositionRowProps) {
  const pnlTrend: TrendDirection = getReturnTrend(position.pnl);
  const sideBadge = POSITION_BADGE_MAP[position.side];

  return (
    <TableRow>
      <TableCell>
        <span className="text-sm text-text-primary">{position.strategyName}</span>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className={cn("h-5 text-[10px]", sideBadge.className)}>
          {sideBadge.label}
        </Badge>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-text-primary">
          {formatCurrency(position.openPrice)}
        </span>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-text-primary">
          {formatCurrency(position.currentPrice)}
        </span>
      </TableCell>
      <TableCell>
        <span
          className={cn(
            "font-num text-sm font-medium",
            pnlTrend === "up" && "text-profit",
            pnlTrend === "down" && "text-loss",
            pnlTrend === "neutral" && "text-text-primary"
          )}
        >
          {formatCurrency(position.pnl)}
        </span>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-profit">
          {formatCurrency(position.takeProfit)}
        </span>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-loss">
          {formatCurrency(position.stopLoss)}
        </span>
      </TableCell>
    </TableRow>
  );
}
