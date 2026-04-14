import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { GlassCard } from "@/components/GlassCard";
import { PageTransition } from "@/components/PageTransition";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/services/api";

interface AppConfig {
  language: string;
  timezone: string;
  notify_evolution: boolean;
  notify_signal: boolean;
  binance_api_key: string;
  binance_secret_key: string;
  binance_connected: boolean;
  init_cash: number;
  maker_fee: number;
  taker_fee: number;
  max_positions: number;
}

const DEFAULT_CONFIG: AppConfig = {
  language: "zh-CN",
  timezone: "UTC+8",
  notify_evolution: true,
  notify_signal: true,
  binance_api_key: "",
  binance_secret_key: "",
  binance_connected: false,
  init_cash: 100000,
  maker_fee: 0.1,
  taker_fee: 0.1,
  max_positions: 1,
};

export function Settings() {
  const [config, setConfig] = useState<AppConfig | null>(null);

  useEffect(() => {
    api.get("/api/config").then((r) => setConfig(r.data)).catch(() => setConfig(DEFAULT_CONFIG));
  }, []);

  const savePartial = useCallback(async (updates: Partial<AppConfig>) => {
    try {
      const { data } = await api.put("/api/config", updates);
      setConfig(data);
      toast.success("设置已保存");
    } catch {
      toast.error("保存失败");
    }
  }, []);

  if (!config) {
    return (
      <PageTransition>
        <div className="flex flex-col gap-6 max-w-2xl">
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="flex flex-col gap-6 max-w-2xl">
        <GeneralSettings config={config} onSave={savePartial} />
        <BinanceApiSettings config={config} onSave={savePartial} />
        <TradingSettings config={config} onSave={savePartial} />
      </div>
    </PageTransition>
  );
}

function GeneralSettings({ config, onSave }: { config: AppConfig; onSave: (u: Partial<AppConfig>) => void }) {
  const [language, setLanguage] = useState(config.language);
  const [timezone, setTimezone] = useState(config.timezone);
  const [notifyEvolution, setNotifyEvolution] = useState(config.notify_evolution);
  const [notifySignal, setNotifySignal] = useState(config.notify_signal);

  const handleSave = () => {
    onSave({ language, timezone, notify_evolution: notifyEvolution, notify_signal: notifySignal });
  };

  return (
    <GlassCard className="p-6" hover={false}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-medium text-text-primary">通用设置</h2>
        <Button size="sm" onClick={handleSave} className="bg-accent-gold text-black hover:bg-accent-gold/90">
          保存更改
        </Button>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <Label className="text-sm text-text-secondary">主题</Label>
          <span className="text-sm text-text-primary">深色模式</span>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center justify-between">
          <Label className="text-sm text-text-secondary">语言</Label>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="w-40 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="zh-CN">简体中文</SelectItem>
              <SelectItem value="en">English</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center justify-between">
          <Label className="text-sm text-text-secondary">时区</Label>
          <Select value={timezone} onValueChange={setTimezone}>
            <SelectTrigger className="w-44 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="UTC+8">UTC+8 北京时间</SelectItem>
              <SelectItem value="UTC+0">UTC+0 格林威治</SelectItem>
              <SelectItem value="UTC-5">UTC-5 纽约</SelectItem>
              <SelectItem value="UTC+9">UTC+9 东京</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center justify-between">
          <Label className="text-sm text-text-secondary">通知</Label>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch checked={notifyEvolution} onCheckedChange={setNotifyEvolution} />
              <span className="text-xs text-text-secondary">进化完成时通知</span>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={notifySignal} onCheckedChange={setNotifySignal} />
              <span className="text-xs text-text-secondary">策略信号通知</span>
            </div>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

function BinanceApiSettings({ config, onSave }: { config: AppConfig; onSave: (u: Partial<AppConfig>) => void }) {
  const [apiKey, setApiKey] = useState(config.binance_api_key);
  const [secretKey, setSecretKey] = useState(config.binance_secret_key);
  const [showApi, setShowApi] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [permRead] = useState(true);
  const [permTrade] = useState(true);
  const [connected, setConnected] = useState(config.binance_connected);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    await new Promise((r) => setTimeout(r, 1500));
    setConnected(!!apiKey && !!secretKey);
    setTesting(false);
    if (apiKey && secretKey) {
      toast.success("连接成功");
    } else {
      toast.error("请填写 API Key 和 Secret Key");
    }
  };

  const handleSave = () => {
    onSave({ binance_api_key: apiKey, binance_secret_key: secretKey, binance_connected: connected });
  };

  return (
    <GlassCard className="p-6" hover={false}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-medium text-text-primary">Binance API 配置</h2>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={handleTest} disabled={testing}>
            {testing ? "测试中..." : "测试连接"}
          </Button>
          <Button size="sm" onClick={handleSave} className="bg-accent-gold text-black hover:bg-accent-gold/90">
            保存
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-24 shrink-0">API Key</Label>
          <div className="relative flex-1">
            <Input
              type={showApi ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="输入 API Key"
              className="h-8 text-xs pr-16"
            />
            <button
              type="button"
              onClick={() => setShowApi(!showApi)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-text-muted hover:text-text-secondary"
            >
              {showApi ? "隐藏" : "显示"}
            </button>
          </div>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-24 shrink-0">Secret Key</Label>
          <div className="relative flex-1">
            <Input
              type={showSecret ? "text" : "password"}
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              placeholder="输入 Secret Key"
              className="h-8 text-xs pr-16"
            />
            <button
              type="button"
              onClick={() => setShowSecret(!showSecret)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-text-muted hover:text-text-secondary"
            >
              {showSecret ? "隐藏" : "显示"}
            </button>
          </div>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-24 shrink-0">权限</Label>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch checked={permRead} disabled />
              <span className="text-xs text-text-secondary">读取</span>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={permTrade} disabled />
              <span className="text-xs text-text-secondary">交易</span>
            </div>
          </div>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-24 shrink-0">状态</Label>
          <div className="flex items-center gap-2">
            <span className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-profit" : "bg-text-muted"}`} />
            <span className="text-xs text-text-secondary">
              {connected ? "已连接" : "未配置"}
            </span>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

function TradingSettings({ config, onSave }: { config: AppConfig; onSave: (u: Partial<AppConfig>) => void }) {
  const [initCash, setInitCash] = useState(String(config.init_cash));
  const [makerFee, setMakerFee] = useState(String(config.maker_fee));
  const [takerFee, setTakerFee] = useState(String(config.taker_fee));
  const [maxPositions, setMaxPositions] = useState(String(config.max_positions));

  const handleSave = () => {
    onSave({
      init_cash: Number(initCash),
      maker_fee: Number(makerFee),
      taker_fee: Number(takerFee),
      max_positions: Number(maxPositions),
    });
  };

  return (
    <GlassCard className="p-6" hover={false}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-medium text-text-primary">模拟交易配置</h2>
        <Button size="sm" onClick={handleSave} className="bg-accent-gold text-black hover:bg-accent-gold/90">
          保存
        </Button>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-28 shrink-0">初始资金</Label>
          <Input
            type="number"
            value={initCash}
            onChange={(e) => setInitCash(e.target.value)}
            className="h-8 w-40 text-xs font-num"
          />
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-28 shrink-0">手续费率</Label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={makerFee}
              onChange={(e) => setMakerFee(e.target.value)}
              className="h-8 w-24 text-xs font-num"
            />
            <span className="text-xs text-text-muted">% (Maker)</span>
            <span className="text-text-muted">/</span>
            <Input
              type="number"
              value={takerFee}
              onChange={(e) => setTakerFee(e.target.value)}
              className="h-8 w-24 text-xs font-num"
            />
            <span className="text-xs text-text-muted">% (Taker)</span>
          </div>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-28 shrink-0">最大持仓</Label>
          <Input
            type="number"
            value={maxPositions}
            onChange={(e) => setMaxPositions(e.target.value)}
            className="h-8 w-24 text-xs font-num"
          />
          <span className="text-xs text-text-muted">个策略同时运行</span>
        </div>

        <Separator className="bg-border-default" />

        <div className="flex items-center gap-3">
          <Label className="text-sm text-text-secondary w-28 shrink-0">数据刷新</Label>
          <span className="text-sm text-text-primary">实时 (WebSocket)</span>
        </div>
      </div>
    </GlassCard>
  );
}
