# 策略实验室（/lab）产品重设计

## 任务定义（用户意图，待门控确认）
策略实验室应是"**策略可视化验证工作台**"。承担 2 职责：
1. **手动创建策略验证想法**：构建策略 → 视觉看买卖点 + 盈利曲线
2. **选策略库策略视觉验证**：从策略库选 → 视觉看买卖点 + 盈利曲线

当前问题：①"假设验证"产品差、不符合"验证想法"意图；②手动创建/策略库选取入口混乱、无法入手。需从产品设计层重设计。

## 现状研究（2 subagent，文件:行号证据）

### 当前 lab 结构：3 模式 + 2 套后端（割裂根因）
- `web/src/pages/Lab.tsx:103` 主组件，3 个互斥 mode tab（Lab.tsx:488-525）：
  - **hypothesis 假设验证（默认页）**：配入场/出场规则 → `POST /api/validate/rules`（services/validation.ts:11）→ RuleValidateResponse（**无 equity_curve**，types/api.ts:410）
  - **backtest 策略回测**：策略库下拉选 → `POST /api/strategies/backtest`（services/strategies.ts:55）→ BacktestResponse（**含 equity_curve + signals**，types/api.ts:84,106-107）
  - **scene 场景验证**：多场景批量

### 可视化能力（lightweight-charts）
| 能力 | hypothesis | backtest |
|---|---|---|
| K线+买卖点标注 | ✅ | ✅ |
| 盈利曲线 | ❌ 后端不返回 | ✅ EquityCurveChart |
| 副图切换(vol/macd/rsi/equity) | ❌ 锁死 volume(Lab.tsx:160 无切换UI) | ✅ 5按钮切换 |

### 后端数据底座（关键）
- `POST /api/strategies/backtest`（strategies.py:236-398）**完备**：equity_curve（逐bar）+ signals（买卖点 type/timestamp/price，backtest_service.py:36-67）+ 支持 strategy_id 或 dna 两种入参
- `GET /api/data/ohlcv/{symbol}/{timeframe}`（data.py:445-486）：K线 OHLCV 完备
- `GET /api/strategies/{id}`（strategies.py:181）：策略库 DNA 可加载
- `/api/validate/rules` 是 backtest 的**子集**（无 equity_curve），是多余的并行路径

### "假设验证产品差"根因（具体）
1. 无盈利曲线（RuleValidateResponse 无 equity_curve）
2. 副图锁死（hypoSubChartType 硬编码 volume）
3. 规则表达力弱（扁平 AND/OR + 百分比阈值 + 写死出场，无括号分组/止损止盈）
4. 无即时反馈（必须凑齐入场+出场才能验证）
5. 规则与 DNA 不互通（hypothesis 规则 vs backtest DNA 两套表达，Lab.tsx:413-434 手动拍扁）

### "选择无法入手"根因
- 默认落 hypothesis 模式（无策略库入口），策略库跳转进 backtest 模式（Lab.tsx:117-119）
- 3 个 mode tab 各自独立，认知负担大

## 推理链方向（待关键决策确认后细化）
**核心策略候选**：统一为"一个验证工作台，两种策略来源"——废弃 hypothesis/backtest 割裂，统一走 `/api/strategies/backtest`（数据底座已完备）。手动创建 = 规则配置产出 DNA → backtest；策略库选取 = strategy_id → backtest。可视化结果统一（K线+买卖点+盈利曲线+副图切换）。

## 待用户决策的关键设计点（门控前澄清）
1. 手动创建策略的形态（保留规则配置修复 / 重新设计）
2. 信息架构（统一工作台 / 保留多模式）
3. 后端路径（统一 /backtest / 保留 validate/rules 补全）
4. 范围（全量重设计 / 渐进改进优先解决"看盈利曲线+入口清晰"）
