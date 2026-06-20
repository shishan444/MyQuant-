import { OptionDropdown } from "./OptionDropdown";

interface SubjectOption {
  value: string;
  label: string;
  category: string;
}

const SUBJECT_OPTIONS: SubjectOption[] = [
  { value: "close", label: "收盘价", category: "价格类" },
  { value: "price", label: "收盘价(price)", category: "价格类" },
  { value: "open", label: "开盘价", category: "价格类" },
  { value: "high", label: "最高价", category: "价格类" },
  { value: "low", label: "最低价", category: "价格类" },
  { value: "volume", label: "成交量", category: "量能类" },
  { value: "ema", label: "EMA", category: "趋势类" },
  { value: "sma", label: "SMA", category: "趋势类" },
  { value: "adx", label: "ADX", category: "趋势类" },
  { value: "rsi", label: "RSI", category: "震荡类" },
  { value: "macd", label: "MACD", category: "震荡类" },
  { value: "kdj", label: "KDJ", category: "震荡类" },
  { value: "cci", label: "CCI", category: "震荡类" },
  { value: "roc", label: "ROC", category: "震荡类" },
  { value: "aroon_up", label: "Aroon Up", category: "震荡类" },
  { value: "aroon_down", label: "Aroon Down", category: "震荡类" },
  { value: "aroon_osc", label: "Aroon OSC", category: "震荡类" },
  { value: "cmo", label: "CMO", category: "震荡类" },
  { value: "trix", label: "TRIX", category: "震荡类" },
  { value: "bb_upper", label: "布林带上轨", category: "波动类" },
  { value: "bb_middle", label: "布林带中轨", category: "波动类" },
  { value: "bb_lower", label: "布林带下轨", category: "波动类" },
  { value: "atr", label: "ATR", category: "波动类" },
  { value: "obv", label: "OBV", category: "量能类" },
  { value: "mfi", label: "MFI", category: "量能类" },
  { value: "cmf", label: "CMF", category: "量能类" },
  { value: "rvol", label: "RVOL", category: "量能类" },
  { value: "vroc", label: "VROC", category: "量能类" },
  { value: "ad", label: "AD", category: "量能类" },
  { value: "cvd", label: "CVD", category: "量能类" },
  { value: "vwma", label: "VWMA", category: "量能类" },
  { value: "vp_poc", label: "VP-POC", category: "结构类" },
  { value: "vp_vah", label: "VP-VAH", category: "结构类" },
  { value: "vp_val", label: "VP-VAL", category: "结构类" },
  { value: "prev_high_n", label: "前N根最高价", category: "动态参考" },
  { value: "prev_low_n", label: "前N根最低价", category: "动态参考" },
  { value: "prev_close_avg_n", label: "前N根收盘均价", category: "动态参考" },
];

interface SubjectDropdownProps {
  value: string;
  onChange: (v: string) => void;
}

const LABEL_MAP: Record<string, string> = {};
for (const opt of SUBJECT_OPTIONS) {
  LABEL_MAP[opt.value] = opt.label;
}

export function getSubjectLabel(value: string): string {
  return LABEL_MAP[value] ?? value;
}

export function SubjectDropdown({ value, onChange }: SubjectDropdownProps) {
  return (
    <OptionDropdown
      value={value}
      label={getSubjectLabel(value)}
      options={SUBJECT_OPTIONS}
      onChange={onChange}
      searchable
      width={176}
      maxHeightClass="max-h-56"
      searchPlaceholder="搜索指标..."
    />
  );
}
