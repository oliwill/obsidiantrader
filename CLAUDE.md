# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**trader-obsidian** is a stock analysis system that integrates with Obsidian as the user workbench. It replaces Alma with Claude Code as the execution engine.

- **Obsidian Vault**: `C:\Users\Lzw\Downloads\Documents\obsidian\Lzw\Lzw\`
- **Analysis Output**: Written directly to Obsidian `.md` files (no plugins needed)
- **Input**: User drops materials in `Inbox/` folder
- **Execution**: Claude Code orchestrates analysis via Python scripts

## Quick Commands

All commands should be run from `C:\Users\Lzw\alma\worktrees\trader\trader-obsidian\`:

```bash
# Analyze a stock
python run_analysis.py AAPL

# Process all pending Inbox items
python run_analysis.py --scan

# Update Dashboard only
python run_analysis.py --dashboard

# Scan Inbox status
python run_analysis.py --inbox
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

3. **Do web search** for recent news if needed

4. **Write comprehensive analysis** covering:
   - Current price and technical position
   - Fundamental assessment
   - Wyckoff phase interpretation
   - KOL/social sentiment (from inbox materials)
   - Key risks and catalysts
   - Concrete signals (BUY/HOLD/SELL with targets)

5. **Write to Obsidian** using Python helper:
   ```python
   from memory.manager import MemoryManager
   mm = MemoryManager()
   mm.append_to_timeline("AAPL.US", price=185.5, score=72, core_view="技术面整固", analysis_type="综合分析")
   mm.update_evaluation_table("AAPL.US", "Apple Inc", "综合", "评分72/100 持有观望")
   ```

6. **Write task file** if actionable signal:
   ```bash
   python -c "
   import os, sys
   sys.path.insert(0, 'C:/Users/Lzw/alma/worktrees/trader/trader-obsidian')
   from run_analysis import write_task
   write_task('Review AAPL entry', 'AAPL.US', 'trade', 'Price broke MA50', 'high', '2026-04-30')
   "
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
| `data.manager.DataManager` | `normalize_symbol()`, `get_historical_data()`, `get_fundamentals()`, `get_stock_info()` | Market data |
| `memory.manager.MemoryManager` | `init_stock_wiki()`, `append_to_timeline()`, `update_evaluation_table()`, `get_stock_context()`, `save_material()` | Wiki persistence |
| `inbox_scanner` | `scan_inbox()`, `get_pending_analysis()`, `get_related_materials()`, `mark_processed()` | Inbox management |
| `run_analysis` | `fetch_market_data()`, `write_analysis_to_obsidian()`, `write_task()`, `update_dashboard()` | Main orchestration |

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
