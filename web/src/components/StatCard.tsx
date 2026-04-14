import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/GlassCard";

interface StatCardProps {
  label: string;
  value: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

const trendColorMap: Record<string, string> = {
  up: "text-profit",
  down: "text-loss",
  neutral: "text-text-primary",
};

function StatCard({ label, value, trend = "neutral", className }: StatCardProps) {
  return (
    <GlassCard className={cn("flex flex-col gap-1", className)}>
      <span className="text-xs text-text-secondary">{label}</span>
      <span
        className={cn(
          "text-xl font-semibold font-num",
          trendColorMap[trend]
        )}
      >
        {value}
      </span>
    </GlassCard>
  );
}

export { StatCard };
export type { StatCardProps };
