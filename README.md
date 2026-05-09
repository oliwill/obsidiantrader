# trader-obsidian

English | [简体中文](README.zh.md)

A stock analysis system that uses Claude Code as the execution engine and Obsidian as the knowledge base. Drop research materials into an Inbox folder, run an analysis command, and get a structured deep-dive written directly into your Obsidian vault.

## How It Works

```
Inbox/ (you drop materials)
    ↓
Claude Code (orchestrates analysis)
    ↓
Obsidian vault (Analysis wiki + Materials + Dashboard)
```

1. Drop a Substack article, Twitter thread, or research note into `Inbox/`
2. Run `python run_analysis.py --scan` or `python run_analysis.py AAPL`
3. Claude Code fetches market data, runs the analysis framework, and writes the output directly to your Obsidian `.md` files

No Obsidian plugins required. Plain markdown files, synced via Dropbox/iCloud/remotely-save.

## Analysis Framework

Each analysis produces a structured report with these sections:

| Section | Content |
|---|---|
| A. 公司与催化剂 | Business description + recent catalysts + supply chain positioning |
| B. 技术面 | RSI/MACD/Bollinger + **SEPA Stage analysis** (trend template + VCP) |
| B2. 护城河 | Moat rating per dimension + competitive gap quantification |
| C. 基本面 | Financials + growth trajectory + **growth quality** (customer concentration, geo exposure, SBC) |
| D. 估值 | P/S + PSG + peer table + **reverse valuation** + asymmetric bet archetype |
| E. 市场结构 | Short interest + IV + **GEX** + options flow + structured sentiment |
| F. 风险量化 | 3–5 risks with revenue/valuation impact + probability |
| G. 三情景目标价 | Bull/Base/Bear with probability-weighted 12m target |
| H. 操作格网 | Entry grid by price level with position sizing |
| I. 警戒线/加仓信号 | Observable boolean conditions only |
| J. 催化剂日历 | Date × event × upside/downside scenario |

### Scoring — Five-Dimension Framework

| Dimension | Weight | Key Data Source |
|---|---|---|
| 行业/TAM | 20% | `stock-correlation` + `finance-sentiment` |
| 护城河 | 20% | `funda-data` supply chain + `stock-correlation` peers |
| 增长质量 | 20% | `yfinance-data` + `funda-data` SEC filings |
| 估值 | 25% | `funda-data` analyst estimates + peer multiples |
| 团队 | 15% | `funda-data` insider trades + congressional trades |

Thresholds: ≥75 high-conviction / 60–75 standard / 45–60 watch / <45 pass

### PSG Framework

`PSG = P/S ÷ Revenue Growth%`

- PSG < 1 → reasonable
- PSG 1–2 → elevated
- PSG > 2 → extreme overvaluation

## Quick Start

```bash
git clone https://github.com/oliwill/obsidiantrader.git
cd obsidiantrader
pip install -r requirements.txt
cp .env.example .env   # fill in your paths and optional API keys
```

Configure `.env`:

```env
WIKI_BASE_DIR=/path/to/your/obsidian/vault
WIKI_SUBDIR=Trader/Analysis
MATERIALS_SUBDIR=Trader/Materials
OBSIDIAN_INBOX_DIR=/path/to/your/obsidian/vault/Inbox
OBSIDIAN_TASKS_DIR=/path/to/your/obsidian/vault/Tasks
OBSIDIAN_DASHBOARD_PATH=/path/to/your/obsidian/vault/Dashboard.md
ANALYSIS_TIMEOUT=30

# Optional — falls back to Yahoo Finance if missing
LONGBRIDGE_APP_KEY=
LONGBRIDGE_APP_SECRET=
LONGBRIDGE_ACCESS_TOKEN=
```

## Commands

```bash
# Quick analysis (recommended) - generates formatted report and writes to Obsidian
python scripts/analyze_stock.py AAPL        # US stock
python scripts/analyze_stock.py 00700       # HK stock (auto-normalized to 00700.HK)
python scripts/analyze_stock.py 603906      # A-share (auto-normalized to SH603906)

# Full analysis workflow (Claude Code orchestration)
python run_analysis.py AAPL        # Outputs JSON for Claude Code analysis
python run_analysis.py --scan     # Process all pending Inbox items
python run_analysis.py --dashboard  # Rebuild Dashboard only
python run_analysis.py --inbox     # Show Inbox status
```

## Obsidian Vault Structure

```
vault/
├── Inbox/              ← drop materials here
│   └── NVDA_note.md
├── Trader/
│   ├── Analysis/       ← auto-managed stock wikis
│   │   ├── AAPL_US.md
│   │   └── TSLA_US.md
│   ├── Materials/      ← raw material archives per stock
│   │   └── TSLA_US/
│   ├── Charts/         ← auto-generated Wyckoff charts
│   │   └── INVZ_wyckoff.png
│   └── Tasks/          ← auto-created trade/research tasks
└── Dashboard.md        ← portfolio overview, auto-updated
```

## Inbox Material Format

Create a `.md` file in `Inbox/` with YAML frontmatter:

```yaml
---
title: NVDA Q1 earnings beat
source: twitter          # twitter | substack | wechat | pdf | note
ticker: NVDA
analyze: true
tags: AI, semiconductors, datacenter
---

Paste the content here...
```

After processing, `processed: true` and `processed_at` are appended automatically.

## Project Structure

```
trader-obsidian/
├── run_analysis.py       # main entry point (Claude Code orchestration)
├── scripts/
│   └── analyze_stock.py  # one-click analysis with formatted report
├── analyzer/
│   ├── report_generator.py  # unified report formatting (tables + emojis)
│   ├── fundamental.py    # fundamental analysis + 6-dimension moat scoring
│   ├── trading_grid.py   # Fibonacci levels, ATR stops, R/R ratios
│   ├── wyckoff.py        # Wyckoff phase detection
│   ├── wyckoff_chart.py  # Wyckoff chart visualization (price, MA, zones, phases)
│   └── comprehensive.py  # combined scoring
├── data/
│   ├── analysis_pipeline.py  # complete data pipeline
│   ├── manager.py        # DataManager: Longbridge API + Yahoo Finance fallback
│   ├── sentiment_analyzer.py  # sentiment scoring: news, social, fear/greed
│   ├── earnings.py       # earnings calendar + surprise history
│   ├── options.py        # options chain: IV, GEX, unusual activity
│   ├── liquidity.py      # short interest, ADTV, market impact
│   └── correlation.py    # peer correlation matrix
├── memory/
│   └── manager.py        # MemoryManager: wiki read/write, timeline, materials
├── input/
│   └── ingest.py         # material intake with tag indexing
├── inbox_scanner.py      # scans Inbox/ for pending analysis
├── skills/               # agent workflow checklists (think/check/hunt/learn)
└── backtest/             # signal validation against historical prices
```

## Data Sources

| Source | Used For | Requires |
|---|---|---|
| Yahoo Finance | Fundamentals, history, options, earnings | Nothing (default) |
| Longbridge API | Real-time quotes, HK/CN stocks, K-lines | API credentials in `.env` |

The system silently falls back to Yahoo Finance if Longbridge credentials are absent or the API times out.

## Skills (Agent Workflows)

The `skills/` directory contains structured checklists that guide Claude Code through each workflow phase:

| Skill | Purpose |
|---|---|
| `think/` | Pre-analysis: goal setting, method selection, 5-dimension scoring guide |
| `check/` | Post-analysis: logic verification, anomaly detection, completeness checklist |
| `hunt/` | Debugging: systematic issue resolution |
| `learn/` | Pattern extraction from accumulated analyses |
| `backtest/` | Signal validation: entry/exit vs historical price |

## Symbol Normalization

| Input | Normalized | Market |
|---|---|---|
| `AAPL` | `AAPL.US` | US |
| `00700` | `00700.HK` | HK |
| `603906` | `SH603906` | CN Shanghai |
| `000001` | `SZ000001` | CN Shenzhen |

Handled automatically by `DataManager.normalize_symbol()`.

## Requirements

- Python 3.9+
- Obsidian vault with a sync solution (Dropbox, iCloud, remotely-save, etc.)
- Claude Code CLI (for running the analysis agent)

Optional: [Longbridge](https://open.longportapp.com/) account for real-time HK/CN data.

## License

MIT
