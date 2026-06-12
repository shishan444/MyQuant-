# 进化中心页面排版重构分析

> 日期: 2026-05-26
> 状态: 研究阶段 A1 完成

## 一、核心问题

设计方案（8.1 节，第 287-369 行）明确规定了参数的可见性分层：
- **直接可见**：5 个"运行要求"参数（年化收益/最大回撤/胜率/交易数/盈亏比），以 grid-cols-5 网格布局
- **折叠保留**：仅 2 个引擎技术参数（种群大小/最大代数）
- **删除**：优化目标 Select、目标分数 Input、策略提取阈值 Input

当前实现完全未遵循此分层——requirements（运行要求）被折叠在高级参数内，已应删除的旧字段仍存在，预设参数未被实际应用。

## 二、设计规格 vs 实现现状

### AutoConfigForm.tsx（620 行）

#### 应直接可见的"运行要求"参数（设计方案第 302-335 行）

| 规格 | 状态 | 当前位置 |
|------|------|----------|
| 5 个 requirements 以 grid-cols-5 直接展示 | **未实现** | 折叠在 advOpen 区域内（行 507-599） |
| "运行要求"行替代原"优化目标"行 | **未实现** | 无"运行要求"标签 |
| 年化收益和回撤为必填校验 | **未实现** | 无此校验 |

#### 应删除的旧字段（设计方案第 296-299 行）

| 旧字段 | 状态 | 证据 |
|--------|------|------|
| 优化目标 Select（scoreTemplate） | **未删除** | AutoConfigForm 行 315-336，直接可见 |
| 目标分数 Input（targetScore） | **未删除** | 折叠区内行 452-464，标签"适应度阈值 (0-1)" |
| 策略提取阈值 Input（strategyThreshold） | **未删除** | 折叠区内行 466-478 |
| 最低年化收益 % (旧位置) | **未删除** | 折叠区内行 479-490，标签"最低年化收益 %" |
| 最大回撤限制 % (旧位置) | **未删除** | 折叠区内行 492-504，标签"最大回撤限制 %" |

#### 折叠区域应简化为 2 项（设计方案第 343-348 行）

| 规格 | 状态 | 当前实际 |
|------|------|----------|
| 折叠区仅含种群大小+最大代数 | **未实现** | 折叠区含 11 个参数（6 算法 + 5 requirements） |

### SeedConfigForm.tsx（790 行）

与 AutoConfigForm 同样的问题：

| 规格 | 状态 | 证据 |
|------|------|------|
| requirements 直接可见 | **未实现** | 折叠在 advOpen 区域内（行 697-789） |
| scoreTemplate 删除 | **未删除** | 行 602-623 直接可见 |
| targetScore 删除 | **未删除** | 折叠区内行 679-694 |
| 折叠区简化为 2 项 | **未实现** | 折叠区含 8 个参数（3 算法 + 5 requirements） |

### QuickPresets.tsx — 预设参数未应用

| 规格 | 状态 | 证据 |
|------|------|------|
| 预设参数应用到表单 | **未实现** | Evolution.tsx 行 302-313，`handlePresetSelect` 中参数名用 `_preset`（下划线前缀表示未使用），仅切换模式+滚动，未传递 indicators/timeframePool/scoreTemplate/requirements |

### constants.ts

| 规格 | 状态 | 证据 |
|------|------|------|
| 删除 OPTIMIZE_TARGETS | **未删除** | 行 236-252 仍存在 |
| 删除 SCORE_TEMPLATE_LABELS | **未删除** | 行 226-234 仍存在 |
| REQUIREMENTS_DEFAULTS 值修正 | **未修正** | 行 258-264 值为 0.15/0.30/0.40/10/1.2，设计方案要求改为 15/30/40/10/1.2（百分比格式） |

## 三、遗漏项汇总

### 严重（直接影响用户体验）

| # | 遗漏 | 影响 |
|---|------|------|
| 1 | 5 个 requirements 折叠而非直接可见 | 用户必须展开高级参数才能看到和配置核心达标要求，违背"重要参数直接可见"的产品设计原则 |
| 2 | scoreTemplate Select 未删除 | 进化不再使用评分模板概念，保留会误导用户 |
| 3 | targetScore/strategyThreshold 未删除 | 进化已改为 fitness 达标机制，旧参数无意义 |
| 4 | minAnnualReturn/maxDrawdownLimit 旧字段未删除 | 与 requirements 新字段重复，用户困惑 |
| 5 | QuickPresets 参数未实际应用到表单 | 预设功能形同虚设，点击预设后参数不变化 |

### 中等（影响页面一致性）

| # | 遗漏 | 影响 |
|---|------|------|
| 6 | REQUIREMENTS_DEFAULTS 值格式（小数 vs 百分比） | 设计方案要求 Input 直接显示百分比（15/30/40），当前实现用小数（0.15/0.30/0.40） |
| 7 | OPTIMIZE_TARGETS 和 SCORE_TEMPLATE_LABELS 未删除 | 死代码，虽不影响功能但增加维护负担 |
| 8 | 折叠区域未简化为 2 项 | 展开后参数过多，用户体验差 |

### 低（不影响功能）

| # | 遗漏 | 影响 |
|---|------|------|
| 9 | 年化收益和回撤必填校验未添加 | 用户可能提交空值 |
| 10 | "运行要求"行标签和提示文案 | 视觉一致性 |

## 四、正确布局对比

### 设计方案要求（AutoConfigForm）

```
直接可见区域:
  数据源行              (不变)
  数据范围信息条        (不变)
  周期组合行            (不变)
  指标池行              (不变)
  ─── 运行要求行 (新增,替代原"优化目标") ───
    grid-cols-5: 年化收益% | 最大回撤% | 最低胜率% | 最少交易 | 盈亏比
    提示: "至少配置收益和回撤两项"
  约束行                (不变)
  时间范围行            (不变)
  ─── 高级参数折叠 (仅 2 项) ───
    种群大小 | 最大代数
  [开始探索] 按钮
```

### 当前实际布局（AutoConfigForm）

```
直接可见区域:
  数据源行
  数据范围信息条
  周期组合行
  指标池行
  优化目标 Select    ← 应删除
  约束行
  时间范围行
  ─── 高级参数折叠 (11 项!) ───
    种群大小 | 最大代数 | 适应度阈值 | 策略提取阈值    ← 后3个应删除
    最低年化收益% | 最大回撤限制%                      ← 应删除(移到运行要求)
    ── 达标要求 ──
    最低年化收益 | 最大回撤 | 最低胜率 | 最少交易 | 最低盈亏比  ← 应提升到直接可见
  [开始探索] 按钮
```

## 五、实施结果

> 日期: 2026-05-26
> 状态: 已完成，构建通过，221 测试全部通过

### 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `AutoConfigForm.tsx` | 删除 scoreTemplate/targetScore/strategyThreshold/minAnnualReturn/maxDrawdownLimit 状态和 UI；新增"运行要求" grid-cols-5 直接可见区；高级参数简化为 2 项；添加 initialPreset 属性支持预设应用 |
| `SeedConfigForm.tsx` | 删除 scoreTemplate/targetScore 状态和 UI；新增"运行要求" grid-cols-5 直接可见区；高级参数简化为 2 项 |
| `Evolution.tsx` | handleStartAuto/handleStartSeed 移除旧字段映射；handlePresetSelect 实际传递预设参数；新增 presetToApply 状态传递给 AutoConfigForm |
| `constants.ts` | 删除 OPTIMIZE_TARGETS（仅被已修改的 2 个表单引用）；保留 SCORE_TEMPLATE_LABELS（仍被 TaskDetailDrawer 和 Evolution 使用） |

### 遗漏项解决情况

| # | 遗漏 | 解决 |
|---|------|------|
| 1 | 5 个 requirements 折叠而非直接可见 | 已提升为 grid-cols-5 直接可见的"运行要求"行 |
| 2 | scoreTemplate Select 未删除 | 已删除 |
| 3 | targetScore/strategyThreshold 未删除 | 已删除 |
| 4 | minAnnualReturn/maxDrawdownLimit 旧字段未删除 | 已删除 |
| 5 | QuickPresets 参数未实际应用到表单 | 已通过 initialPreset 属性实现参数传递 |
| 6 | REQUIREMENTS_DEFAULTS 值格式 | 已改为百分比显示（15/30/40）|
| 7 | OPTIMIZE_TARGETS 死代码 | 已删除 |
| 8 | 折叠区域未简化 | 已简化为仅 2 项（种群大小+最大代数）|
| 9 | 年化收益和回撤必填校验 | 已在 canSubmit 中添加 |
| 10 | "运行要求"行标签 | 已添加标签和提示文案 |
