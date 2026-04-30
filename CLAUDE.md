# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**trader-obsidian** is a stock analysis system that integrates with Obsidian as the user workbench. Claude Code is the execution engine.

- **Analysis Output**: Written directly to Obsidian `.md` files (no plugins needed)
- **Input**: User drops materials in the Obsidian `Inbox/` folder (path set via `OBSIDIAN_INBOX_DIR` in `.env`)
- **Execution**: Claude Code orchestrates analysis via Python scripts

## Quick Commands

All commands run from the project root:

```bash
# Quick analysis (recommended) - generates formatted report and writes to Obsidian
python scripts/analyze_stock.py AAPL

# Full analysis workflow (Claude Code orchestration)
python run_analysis.py AAPL        # Outputs JSON for Claude Code analysis
python run_analysis.py --scan     # Process all pending Inbox items
python run_analysis.py --dashboard  # Update Dashboard only
python run_analysis.py --inbox     # Scan Inbox status
```

## Obsidian Vault Structure

```
Lzw/
├── Inbox/          # User drops materials here (Twitter, Substack, WeChat, etc.)
├── Analysis/       # Stock wiki pages (auto-managed by MemoryManager)
├── Materials/      # Raw material archives (auto-managed)
├── Tasks/          # Trading and research tasks (auto-created)
└── Dashboard.md    # Portfolio overview (auto-updated)
```

## Standard Analysis Workflow

When user asks to analyze a stock (e.g., "分析 AAPL"):

1. **Run data fetch**:
   ```bash
   python run_analysis.py AAPL
   ```
   This prints JSON with: `market_data`, `wiki_context`, `inbox_materials`

2. **Read the output** - Look for:
   - `stock_info` (price, market cap, sector)
   - `fundamentals` (PE, PB, margins, growth)
   - `technicals` (MA, RSI, MACD, Bollinger)
   - `wyckoff` (phase, support, resistance)
   - `wiki_summary` (historical context)

3. **Gather supplementary data** using structured skill calls (replaces ad-hoc web search):

   | Skill | 用途 | 何时调用 |
   |---|---|---|
   | `funda-data` | 期权 flow/GEX、内部人交易、国会交易、分析师预期、供应链图谱 | 每次必做 |
   | `stock-correlation` | 同行 P/S 基准（自动输出 3–5 家，替代手动搜索） | 每次必做 |
   | `finance-sentiment` | Reddit / X / Polymarket 结构化情绪 | 每次必做 |
   | `earnings-preview` | 财报前共识、beat/miss 历史、各项 beat 临界值 | 财报前 30 天内 |
   | `earnings-recap` | 实际 vs 预期、股价反应、电话会要点 | 财报后 |
   | `stock-liquidity` | ADTV、bid-ask 价差、大单冲击估算 | 小市值 / 低流动性标的必做 |
   | `sepa-strategy` | Stage 判断 + VCP / 趋势模板技术形态 | 每次必做 |
   | `twitter-reader` | 读取关键 KOL（如 Serenity）最新推文 | 有 KOL 持仓信号时 |

4. **Write comprehensive analysis** — mandatory sections in order:

   **A. 公司与催化剂**
   - 一句话业务描述 + 近期触发此次分析的事件
   - 供应链定位：上游供应商（3个）/ 核心客户 / 主要竞争对手（来自 `funda-data` 供应链图谱）

   **B. 技术面**
   - RSI / KDJ / MACD / 布林带 / 成交量比 — 表格呈现，每项附信号判断
   - **SEPA Stage 判断（必做）**：检查趋势模板（价格 > MA50 > MA150 > MA200 = Stage 2 买入区）；识别 VCP / 突破形态；结论："当前处于 Stage X，是否有效买入形态"

   **B2. 护城河分析（必做）**
   - 逐项评级（★1–5）：技术/IP 壁垒、客户锁定程度、规模优势、品牌壁垒
   - **劣势不回避**：竞争对手最大威胁 + 规模差距量化（来自 `stock-correlation` 竞对对比）
   - 结论：护城河有效窗口期估计（年数）

   **C. 基本面**
   - 关键财务数字表格（营收、毛利、净亏损/净利、现金、关键比率）
   - 增长轨迹（过去4季度 QoQ/YoY，未来1-2年分析师预期）
   - **增长质量维度（必做）**：
     - 经常性收入 vs 一次性收入占比
     - 客户集中度（前3大客户占比）
     - 地理分布与地缘政治暴露
     - 有机增长 vs 收购贡献
     - SBC/Revenue 比率（股权稀释压力）

   **D. 估值锚点（必做）**
   - 当前 TTM P/S = 市值 ÷ 年化营收
   - 同行 P/S 对比表（来自 `stock-correlation`，3–5家，含 NVDA/AMD 等参照系）
   - PSG = P/S ÷ 预期收入增速%（PSG<1合理，1–2偏高，>2极度高估）
   - **当前价格假设了什么（反向推导，必做）**：在当前市值下，需要几年/多高增速才能达到合理估值？明确说出"定价透支了哪一年的收入"
   - **非对称赔率原型判断**：标注属于哪种类型 — 高确定性增长型 / 催化剂驱动型 / 困境反转型 / 周期底部型；判断当前赔率是否正向
   - 结论：安全边际判断（充足 / 偏紧 / 无安全边际）

   **E. 市场结构分析（必做）**
   - 空头比例（Short Float %）+ Days to Cover
   - 期权 IV（与历史均值对比）+ **GEX（Gamma Exposure）方向**（来自 `funda-data`）
   - **期权异常流**（来自 `funda-data`）：vol/OI 异常倍数、方向判断
   - **结构化情绪数据**（来自 `finance-sentiment`）：Reddit 热度、X 情绪、Polymarket 赔率
   - 近期涨幅拆解：基本面新信息贡献 vs 技术性因素（情绪/空头回补/期权gamma）
   - 内部人增减持（过去6个月，买入次数 vs 卖出次数 vs 金额）；与其他持仓的内部人信号横向对比

   **F. 风险量化（必做）**
   - 列出 3–5 个主要风险，每条格式：
     `风险名称 → 如果发生：收入影响 ±X%，估值影响 ±Y%，概率判断（高/中/低）`

   **G. 三情景目标价（必做）**
   - 🟢 Bull Case（概率X%）：核心假设 + 12个月目标价 $Z
   - 🟡 Base Case（概率X%）：核心假设 + 12个月目标价 $Z
   - 🔴 Bear Case（概率X%）：核心假设 + 12个月目标价 $Z
   - **概率加权目标价** = Bull×P + Base×P + Bear×P
   - 当前价 vs 加权目标价 → 隐含12个月回报%

   **H. 操作格网（必做）**
   - 表格格式，每行：价位区间 | 动作 | 仓位 | 触发条件
   - 至少覆盖：当前价（追/不追）、第一回调位、核心建仓位、深度加仓位
   - 注明最大仓位上限

   **I. 警戒线 / 加仓信号（必做）**
   - 🔴 警戒线（3–6条）：格式"如果 A → 减仓/清仓，原因"
   - 🟢 加仓信号（3–6条）：格式"如果 B → 可加仓，原因"
   - 每条必须是可观测的布尔条件（避免"如果市场好转"这类模糊表达）

   **J. 关键催化剂日历**
   - 按时间排序，每条：日期 | 事件 | 若超预期→股价反应 | 若不及预期→股价反应
   - 财报前30天内：追加"**财报情景预判**"子节（来自 `earnings-preview`）：共识 EPS/Revenue、有意义 beat 临界值、财报后 3 情景概率 × 股价预判

**报告开头必须包含 Obsidian Front Matter**：

```yaml
---
title: "{TICKER} {评分}/100 — {核心观点简述}"
source: claude-code
author: "Claude Code"
published: {YYYY-MM-DD}
created: {YYYY-MM-DD HH:MM}
description: "{一句话总结：如 PSG XX，12 个月目标价 $X，建仓价位 $Y}"
tags:
  - stock-analysis
  - {sector}
  - {sub-sector}
  - 12m-target-{目标价}
  - psg-{PSG值}
stock_code: {TICKER.US}
score: {评分}
psg: {PSG值}
target_price: {加权目标价}
current_price: {当前价格}
stage: "{Stage 1 底部整理 / Stage 2 主升浪 / Stage 3 顶部 / Stage 4 下跌}"
moat_score: {护城河综合评分 /10}
insider_signal: "{positive / neutral / negative}"
liquidity: "{liquid / normal / thin}"
earnings_date: "{YYYY-MM-DD}"
---
```

字段说明：
- `title`：格式为 "POET 42/100 — PSG 199，12 个月目标价 $11.30（-25%）"
- `description`：一句话精华，如 "P/S 2145x，PSG 199，无安全边际；等待 $9–10 回调"
- `tags`：必须包含 `stock-analysis`，行业标签如 `semiconductors`，子领域如 `photonics`
- `12m-target-{目标价}`：便于 Obsidian 搜索按目标价过滤
- `psg-{PSG值}`：便于按估值水平过滤（如 `psg-199` 为极度高估）
- `target_price` / `current_price`：便于 Obsidian Dataview 插件计算潜在收益
- `stage`：来自 SEPA 分析，便于按技术形态筛选标的
- `moat_score`：护城河评分，便于 Dataview 筛选高护城河标的
- `insider_signal`：内部人信号方向，positive = 净买入，negative = 净卖出
- `liquidity`：thin 表示小市值/低流动性，需要 `stock-liquidity` 分析
- `earnings_date`：下次财报日，便于 Dataview 按财报日排序

## 五维评分框架

每次分析使用五维打分，加权合计为总分（100分制）：

| 维度 | 权重 | 评分要点 | 主要数据来源 |
|---|---|---|---|
| 行业/TAM | 20% | 赛道方向、市场规模、资金流入热度 | `stock-correlation` + `finance-sentiment` |
| 护城河 | 20% | 技术/IP、客户锁定、规模、品牌 | `funda-data` 供应链 + `stock-correlation` |
| 增长质量 | 20% | 增速、经常性收入、客户集中度、毛利趋势 | `yfinance-data` + `funda-data` SEC 细节 |
| 估值 | 25% | P/S、PSG、同行倍数、安全边际 | `funda-data` 分析师预期 + `stock-correlation` |
| 团队 | 15% | CEO 质量、内部人信号、Skin in the game | `funda-data` 内部人/国会交易 |

**建仓门槛参考**：≥75 高信心建仓 / 60–75 标准建仓 / 45–60 观察/小仓位 / <45 Pass

5. **Write to Obsidian** using Python helper:
   ```python
   from memory.manager import MemoryManager
   mm = MemoryManager()
   mm.append_to_timeline("AAPL.US", price=185.5, score=72, core_view="技术面整固", analysis_type="综合分析")
   mm.update_evaluation_table("AAPL.US", "Apple Inc", "综合", "评分72/100 持有观望")
   ```

6. **Write task file** if actionable signal:
   ```bash
   python -c "from run_analysis import write_task; write_task('Review AAPL entry', 'AAPL.US', 'trade', 'Price broke MA50', 'high', '2026-04-30')"
   ```

7. **Update dashboard**:
   ```bash
   python run_analysis.py --dashboard
   ```

## Inbox Material Format

Users create `.md` files in `Inbox/` with YAML frontmatter:

```yaml
---
title: NVDA earnings beat expectations
source: twitter          # twitter|substack|wechat|zhishixingqiu|pdf|note
ticker: NVDA             # Optional; scanner also auto-detects
analyze: true            # Set true to queue for processing
tags: AI, semiconductors, datacenter
---

Content here...
```

After processing, `processed: true` and `processed_at: YYYY-MM-DD HH:MM` are added to frontmatter.

## Timeout Protection

All Longbridge API calls run in `one_shot_analysis.py` via subprocess with `ANALYSIS_TIMEOUT` (default 30s).

If you see `"error": "timeout"` in output:
- Longbridge API hung (network/credential issue)
- Yahoo Finance fallback may have partial data
- Proceed with available data, note the limitation

## Symbol Normalization

Always use normalized formats when calling Python helpers:

| Input | Normalized | Market |
|-------|------------|--------|
| `AAPL` | `AAPL.US` | US |
| `00700` | `00700.HK` | HK |
| `603906` | `SH603906` | CN (Shanghai) |
| `000001` | `SZ000001` | CN (Shenzhen) |

The `DataManager.normalize_symbol()` function handles this automatically.

## Module Reference

| Module | Class/Function | Purpose |
|--------|----------------|---------|
| `scripts.analyze_stock` | `main()` | One-click analysis entry point |
| `analyzer.report_generator.ReportGenerator` | `generate()` | Unified report formatting (tables + emojis) |
| `analyzer.wyckoff_chart.WyckoffChartRenderer` | `render()` | Wyckoff chart visualization (price, MA, zones, phases, events) |
| `analyzer.trading_grid.TradingGridGenerator` | `generate()` | Trading grid with Fibonacci levels, ATR stops, R/R ratios |
| `data.sentiment_analyzer.SentimentAnalyzer` | `analyze()` | Sentiment scoring: news, social, fear/greed index |
| `data.analysis_pipeline` | `generate_analysis()` | Complete data pipeline (all modules) |
| `data.manager.DataManager` | `normalize_symbol()`, `get_historical_data()`, `get_fundamentals()`, `get_stock_info()` | Market data |
| `memory.manager.MemoryManager` | `init_stock_wiki()`, `append_to_timeline()`, `update_evaluation_table()`, `get_stock_context()`, `save_material()` | Wiki persistence |
| `inbox_scanner` | `scan_inbox()`, `get_pending_analysis()`, `get_related_materials()`, `mark_processed()` | Inbox management |
| `input.ingest` | `ingest()` | Material intake with tag indexing (`tags_index.json`) |
| `run_analysis` | `write_analysis_to_obsidian()`, `write_task()`, `update_dashboard()` | Main orchestration |

## Analysis Output Sections

Each stock in `Analysis/{CODE}.md` has these sections:

- `## 综合评估` - Evaluation table (fundamental/valuation/technical/news/aggregate)
- `## 分析时间线` - Analysis history (timestamp, price, score, type, core view)
- `## 预测验证` - Backtest results
- `## 关键事件` - Important events affecting price
- `## KOL观点汇总` - Social media sentiment
- `## 研究笔记` - Detailed analysis (append here)
- `## 交叉引用` - Related stocks
- `## 资料索引` - Material index

## Common Tasks

### Create a stock wiki page
```python
from memory.manager import MemoryManager
mm = MemoryManager()
mm.init_stock_wiki("AAPL.US", "Apple Inc")
# Creates Analysis/AAPL_US.md with all sections
```

### Add a material to wiki
```python
from memory.manager import MemoryManager
mm = MemoryManager()
mm.save_material(
    stock_code="AAPL.US",
    source_type="twitter",
    content="Thread content...",
    title="AAPL bullish thread",
    summary="Key points...",
    tags="AI, iPhone",
)
# Writes to Materials/AAPL_US/ and updates index
```

### Query stock context
```python
from memory.manager import MemoryManager
mm = MemoryManager()
context = mm.get_stock_context("AAPL.US")
print(context)  # Full wiki + materials summary
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: longbridge` | SDK not installed | Normal - falls back to Yahoo Finance |
| `WIKI_BASE_DIR not set` | .env not loaded | Run `load_dotenv()` before imports |
| `TimeoutExpired` | Longbridge API hung | Increase `ANALYSIS_TIMEOUT` in .env |
| Empty wiki context | First-time analysis | Call `init_stock_wiki()` first |

## Environment Configuration

Required in `.env`:
- `WIKI_BASE_DIR` - Obsidian vault root
- `WIKI_SUBDIR` - Wiki subdirectory (default: Analysis)
- `MATERIALS_SUBDIR` - Materials subdirectory (default: Materials)
- `OBSIDIAN_INBOX_DIR` - Inbox folder path
- `OBSIDIAN_TASKS_DIR` - Tasks folder path
- `OBSIDIAN_DASHBOARD_PATH` - Dashboard.md path
- `ANALYSIS_TIMEOUT` - Subprocess timeout in seconds

Optional (defaults to Yahoo Finance if missing):
- `LONGBRIDGE_APP_KEY`
- `LONGBRIDGE_APP_SECRET`
- `LONGBRIDGE_ACCESS_TOKEN`
