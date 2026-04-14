import { cn } from "@/lib/utils";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
  id?: string;
}

function GlassCard({
  children,
  className,
  hover = true,
  onClick,
  id,
}: GlassCardProps) {
  return (
    <div
      id={id}
      className={cn(
        "glass-card p-4",
        hover && "cursor-pointer hover:scale-[1.01]",
        onClick && "cursor-pointer",
        className
      )}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}

export { GlassCard };
export type { GlassCardProps };
