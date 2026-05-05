import { useState } from "react";
import { TrendingUp } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface CreateTaskDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategyName: string | null;
  symbol: string;
  timeframe: string;
  initialCash: number;
  onConfirm: (initialCash: number) => void;
}

export function CreateTaskDialog({
  open,
  onOpenChange,
  strategyName,
  symbol,
  timeframe,
  initialCash: defaultCash,
  onConfirm,
}: CreateTaskDialogProps) {
  const [cash, setCash] = useState(defaultCash);

  // Sync when dialog opens with a new default
  const [prevDefault, setPrevDefault] = useState(defaultCash);
  if (defaultCash !== prevDefault) {
    setPrevDefault(defaultCash);
    setCash(defaultCash);
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-accent-gold" />
            Create Paper Trading Task
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-text-secondary">
              <p>
                Start paper trading with this strategy. The runner will process
                historical bars first, then switch to real-time mode.
              </p>
              <div className="grid grid-cols-2 gap-2 rounded-lg border border-border-default p-3">
                <div>
                  <span className="text-xs text-text-muted">Strategy</span>
                  <p className="font-medium text-text-primary">
                    {strategyName || "Unnamed"}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-text-muted">Market</span>
                  <p className="font-medium text-text-primary">
                    {symbol} / {timeframe}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-text-muted">Initial Capital</span>
                  <input
                    type="number"
                    min={100}
                    step={10000}
                    value={cash}
                    onChange={(e) => setCash(Number(e.target.value) || 10000)}
                    className="w-full rounded border border-border-default bg-transparent px-2 py-1 font-num text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-gold"
                  />
                </div>
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={() => onConfirm(cash)}>
            Create Task
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
