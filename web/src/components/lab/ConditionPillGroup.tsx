import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConditionInput } from "@/types/api";
import { ConditionPill } from "./ConditionPill";

interface ConditionPillGroupProps {
  label: "WHEN" | "THEN";
  description: string;
  conditions: ConditionInput[];
  onConditionsChange: (conditions: ConditionInput[]) => void;
  isThen?: boolean;
}

function AndOrConnector({
  logic,
  onToggle,
}: {
  logic: "AND" | "OR";
  onToggle: (v: "AND" | "OR") => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        className={cn(
          "h-6 min-w-[48px] rounded border px-2 text-[11px] font-semibold",
          "border-border-default text-text-muted transition-colors hover:border-accent-gold/50",
        )}
        onClick={() => setOpen(!open)}
      >
        {logic}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className={cn(
              "absolute left-0 top-full z-50 mt-1 w-16 overflow-hidden rounded-md",
              "border border-border-default bg-bg-surface shadow-xl",
            )}
          >
            {(["AND", "OR"] as const).map((v) => (
              <button
                key={v}
                type="button"
                className={cn(
                  "flex w-full items-center justify-center px-2 py-1.5 text-[11px] font-semibold transition-colors",
                  logic === v
                    ? "bg-accent-gold/10 text-accent-gold"
                    : "text-text-muted hover:bg-white/5",
                )}
                onClick={() => {
                  onToggle(v);
                  setOpen(false);
                }}
              >
                {v}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function ConditionPillGroup({
  label,
  description,
  conditions,
  onConditionsChange,
  isThen = false,
}: ConditionPillGroupProps) {
  const handleAdd = () => {
    const newCondition: ConditionInput = {
      subject: "",
      action: "",
      target: "",
      logic: "AND",
      ...(isThen ? { window: 8 } : {}),
    };
    onConditionsChange([...conditions, newCondition]);
  };

  const handleUpdate = (index: number, updated: ConditionInput) => {
    const next = [...conditions];
    next[index] = updated;
    onConditionsChange(next);
  };

  const handleDelete = (index: number) => {
    onConditionsChange(conditions.filter((_, i) => i !== index));
  };

  const handleLogicToggle = (index: number, logic: "AND" | "OR") => {
    const next = [...conditions];
    next[index] = { ...next[index], logic };
    onConditionsChange(next);
  };

  const handleClear = () => {
    onConditionsChange([]);
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-accent-gold">{label}</span>
          <span className="text-xs text-text-muted">{description}</span>
        </div>
        {conditions.length > 0 && (
          <button
            type="button"
            onClick={handleClear}
            className="flex items-center gap-1 text-xs text-text-muted transition-colors hover:text-loss"
          >
            <Trash2 className="h-3 w-3" />
            清空条件
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {conditions.map((cond, i) => (
          <div key={i} className="flex items-center gap-2">
            {i > 0 && (
              <AndOrConnector
                logic={cond.logic}
                onToggle={(v) => handleLogicToggle(i, v)}
              />
            )}
            <ConditionPill
              condition={cond}
              onChange={(updated) => handleUpdate(i, updated)}
              onDelete={() => handleDelete(i)}
              isThen={isThen}
            />
          </div>
        ))}

        <button
          type="button"
          onClick={handleAdd}
          className={cn(
            "flex items-center gap-1 rounded-full border border-dashed px-3 py-1.5",
            "border-border-default text-xs text-text-muted transition-colors",
            "hover:border-solid hover:border-accent-gold/50 hover:text-text-secondary",
          )}
        >
          <Plus className="h-3 w-3" />
          添加
        </button>
      </div>
    </div>
  );
}
