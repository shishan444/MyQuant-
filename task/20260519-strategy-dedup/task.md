# Task: 策略库策略重复问题根因分析

## 症状
策略库50条策略中：
1. 同名策略重复出现（如 "DEMA趋势 混合 15M-3E89" 出现3次）
2. 不同名称但完全相同的指标组合（如多个策略都是 "EMA(20) / ADX(14)"）
3. 同一个 hash 后缀出现多次但指标不同（说明数据不一致）

## 根因分析

### 根因1：手动保存绕过去重（主因）

save_strategy() 的去重条件（api/db_ext.py:815）:
```python
if gene_signature and best_score is not None:
```

三个保存入口中，只有进化引擎自动发现（api/runner.py:508-545）会传入 best_score。
Lab 页面手动保存（Lab.tsx:409-449）和 Evolution 页面手动保存（Evolution.tsx:337-351）
都不传 best_score，导致 gene_signature 去重被跳过，完全相同的 DNA 每次保存都 INSERT 新记录。

### 根因2：DB 无唯一约束

gene_signature 列（migrations/008_strategy_dedup.sql）只有普通索引，没有 UNIQUE 约束。
即使去重逻辑失效，DB 层也无法阻止重复插入。

### 根因3：名称区分度不足（次要）

generate_strategy_name()（core/strategy/dna.py:366-389）只用 ENTRY_TRIGGER 的 indicator 名
作为前缀。EMA(20)+ADX(14) 和 EMA(50)+ADX(14) 都生成 "DEMA趋势 混合 15M-{hash}"。
区分完全依赖4位MD5哈希，但哈希不包含 condition/field_name/layers，碰撞概率不低。
