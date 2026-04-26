# Skills 整合规划

将 8 个 Claude Code skills 融入 trader-obsidian 分析流程。

## 整合映射

| Skill | 新建模块 | 集成点 | 优先级 |
|-------|---------|--------|--------|
| yfinance-data | 扩展 `data/manager.py` | 现有数据层增强 | P1 |
| earnings-preview | `data/earnings.py` | one_shot_analysis Step 1.5 | P1 |
| earnings-recap | `data/earnings.py` (扩展) | one_shot_analysis / backtest | P2 |
| finance-sentiment | 扩展 `data/search.py` | one_shot_analysis Step 2 | P1 |
| stock-correlation | `data/correlation.py` | wiki 交叉引用 section | P2 |
| stock-liquidity | `data/liquidity.py` | one_shot_analysis 新增字段 | P2 |
| etf-premium | `data/etf.py` | 判断股票是否为ETF时启用 | P3 |
| options-payoff | `data/options.py` | one_shot_analysis 新增字段 | P3 |

## 数据流

```
one_shot_analysis.py
├── Step 0: Wiki 历史 (已有)
├── Step 1: 行情 + 基本面 (已有, 增强分析师目标)
├── Step 1.5: 财报预期 (earnings-preview) ← 新增
├── Step 1b: K线 + 技术指标 (已有)
├── Step 1c: 流动性分析 (stock-liquidity) ← 新增
├── Step 1d: 期权数据 (options-payoff) ← 新增
├── Step 2: 网络搜索 + 社交情绪 (search, 增强 sentiment)
│   ├── Yahoo Finance News
│   ├── Reddit 情绪
│   ├── X/Twitter 情绪
│   └── Polymarket 赔率
├── Step 3: 相关性分析 (stock-correlation) ← 新增
└── Step 4: ETF 检测 (etf-premium, 条件触发) ← 新增
```

## Wiki Section 更新

新增/增强的 wiki section:
- `## 财报预期` — 下次财报日期、共识预期、历史 beat/miss
- `## 流动性分析` — short interest、days to cover、机构持仓
- `## 期权市场` — 期权链摘要、IV、put/call ratio
- `## 社交情绪` — Reddit/X/Polymarket 情绪汇总
- `## 交叉引用` — 相关性最高的股票列表
