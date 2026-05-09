# trader-obsidian

[English](README.md) | 简体中文

一套以 Claude Code 为执行引擎、Obsidian 作为知识库的股票分析系统。把研究素材丢进 Inbox 文件夹，运行分析命令，结构化的深度报告会直接写入你的 Obsidian vault。

## 工作原理

```
Inbox/（你丢素材进来）
    ↓
Claude Code（编排分析流程）
    ↓
Obsidian vault（Analysis 知识库 + Materials 原文档案 + Dashboard）
```

1. 把 Substack 文章、Twitter 长推、研究笔记丢进 `Inbox/`
2. 运行 `python run_analysis.py --scan` 或 `python run_analysis.py AAPL`
3. Claude Code 自动获取行情数据、运行分析框架，并把结果直接写入 Obsidian 的 `.md` 文件

无需安装 Obsidian 插件，纯 Markdown 文件，可通过 Dropbox / iCloud / remotely-save 同步。

## 分析框架

每次分析都会输出一份包含以下章节的结构化报告：

| 章节 | 内容 |
|---|---|
| A. 公司与催化剂 | 业务概述 + 近期催化剂 + 供应链定位 |
| B. 技术面 | RSI / MACD / 布林带 + **SEPA Stage 判断**（趋势模板 + VCP 形态） |
| B2. 护城河 | 逐维度护城河评级 + 与竞对的差距量化 |
| C. 基本面 | 财务数字 + 增长轨迹 + **增长质量**（客户集中度、地理暴露、SBC 稀释） |
| D. 估值 | P/S + PSG + 同行对比表 + **反向估值** + 非对称赔率原型 |
| E. 市场结构 | 空头比例 + IV + **GEX** + 期权异常流 + 结构化情绪 |
| F. 风险量化 | 3–5 个风险，每条标注收入/估值影响 + 概率 |
| G. 三情景目标价 | Bull / Base / Bear 概率加权的 12 个月目标价 |
| H. 操作格网 | 按价位的入场格网 + 仓位规模 |
| I. 警戒线 / 加仓信号 | 只用可观测的布尔条件 |
| J. 催化剂日历 | 日期 × 事件 × 上行/下行情景 |

### 评分 — 五维框架

| 维度 | 权重 | 主要数据源 |
|---|---|---|
| 行业 / TAM | 20% | `stock-correlation` + `finance-sentiment` |
| 护城河 | 20% | `funda-data` 供应链 + `stock-correlation` 同行 |
| 增长质量 | 20% | `yfinance-data` + `funda-data` SEC 文件 |
| 估值 | 25% | `funda-data` 分析师预期 + 同行倍数 |
| 团队 | 15% | `funda-data` 内部人交易 + 国会交易 |

建仓门槛：≥75 高信心 / 60–75 标准 / 45–60 观察 / <45 Pass

### PSG 框架

`PSG = P/S ÷ 营收增速%`

- PSG < 1 → 合理
- PSG 1–2 → 偏高
- PSG > 2 → 极度高估

## 快速上手

```bash
git clone https://github.com/oliwill/obsidiantrader.git
cd obsidiantrader
pip install -r requirements.txt
cp .env.example .env   # 填入你的路径和可选的 API key
```

配置 `.env`：

```env
WIKI_BASE_DIR=/你的 Obsidian vault 根目录
WIKI_SUBDIR=Trader/Analysis
MATERIALS_SUBDIR=Trader/Materials
OBSIDIAN_INBOX_DIR=/你的 Obsidian vault 根目录/Inbox
OBSIDIAN_TASKS_DIR=/你的 Obsidian vault 根目录/Tasks
OBSIDIAN_DASHBOARD_PATH=/你的 Obsidian vault 根目录/Dashboard.md
ANALYSIS_TIMEOUT=30

# 可选 — 不填则自动 fallback 到 Yahoo Finance
LONGBRIDGE_APP_KEY=
LONGBRIDGE_APP_SECRET=
LONGBRIDGE_ACCESS_TOKEN=
```

## 命令

```bash
# 快捷分析（推荐）— 生成格式化报告并写入 Obsidian
python scripts/analyze_stock.py AAPL        # 美股
python scripts/analyze_stock.py 00700       # 港股（自动归一化为 00700.HK）
python scripts/analyze_stock.py 603906      # A 股（自动归一化为 SH603906）

# 完整分析流程（Claude Code 编排）
python run_analysis.py AAPL        # 输出 JSON 供 Claude Code 分析
python run_analysis.py --scan     # 处理 Inbox 中所有待分析文件
python run_analysis.py --dashboard  # 仅重建 Dashboard
python run_analysis.py --inbox     # 查看 Inbox 状态
```

## Obsidian Vault 结构

```
vault/
├── Inbox/              ← 把素材丢这里
│   └── NVDA_note.md
├── Trader/
│   ├── Analysis/       ← 自动管理的股票知识库
│   │   ├── AAPL_US.md
│   │   └── TSLA_US.md
│   ├── Materials/      ← 按股票归档的原文
│   │   └── TSLA_US/
│   ├── Charts/         ← 自动生成的 Wyckoff 图表
│   │   └── INVZ_wyckoff.png
│   └── Tasks/          ← 自动创建的交易/研究任务
└── Dashboard.md        ← 持仓总览，自动更新
```

> **文件命名规则**：股票代码中的 `.` 和 `/` 都会替换为 `_`，例如 `TEM.US` → `TEM_US.md`、`600487.SH` → `600487_SH.md`。

## Inbox 素材格式

在 `Inbox/` 中创建一个带 YAML frontmatter 的 `.md` 文件：

```yaml
---
title: NVDA Q1 财报超预期
source: twitter          # twitter | substack | wechat | pdf | note
ticker: NVDA
analyze: true
tags: AI, semiconductors, datacenter
---

把内容贴这里……
```

处理完成后会自动追加 `processed: true` 和 `processed_at` 字段。

## 项目结构

```
trader-obsidian/
├── run_analysis.py       # 主入口（Claude Code 编排）
├── scripts/
│   └── analyze_stock.py  # 一键分析 + 格式化报告
├── analyzer/
│   ├── report_generator.py  # 统一报告格式化（表格 + emoji）
│   ├── fundamental.py    # 基本面分析 + 6 维护城河打分
│   ├── trading_grid.py   # 斐波那契、ATR 止损、风报比
│   ├── wyckoff.py        # Wyckoff 阶段识别
│   ├── wyckoff_chart.py  # Wyckoff 图表（价格、MA、区域、阶段）
│   └── comprehensive.py  # 综合打分
├── data/
│   ├── analysis_pipeline.py  # 完整数据流水线
│   ├── manager.py        # DataManager：长桥 API + Yahoo Finance fallback
│   ├── sentiment_analyzer.py  # 情绪打分：新闻、社交、恐惧贪婪指数
│   ├── earnings.py       # 财报日历 + 超预期历史
│   ├── options.py        # 期权链：IV、GEX、异常活动
│   ├── liquidity.py      # 空头比例、ADTV、冲击成本
│   └── correlation.py    # 同行相关性矩阵
├── memory/
│   ├── manager.py        # MemoryManager：wiki 读写、时间线、素材
│   ├── utils.py          # 路径、时间、文件 I/O
│   └── section_parser.py # Markdown section 解析
├── input/
│   └── ingest.py         # 素材摄入 + 标签索引
├── inbox_scanner.py      # 扫描 Inbox/ 中的待分析文件
├── skills/               # Agent 工作流清单（think / check / hunt / learn）
└── backtest/             # 信号回测：与历史价格对照
```

## 数据源

| 数据源 | 用途 | 依赖 |
|---|---|---|
| Yahoo Finance | 基本面、历史价、期权、财报 | 无（默认） |
| 长桥 API | 实时报价、港股/A 股、K 线 | 需要在 `.env` 配置 API 凭据 |

如果长桥凭据缺失或 API 超时，系统会静默 fallback 到 Yahoo Finance。

## Skills（Agent 工作流）

`skills/` 目录提供结构化清单，引导 Claude Code 走完每个工作流阶段：

| Skill | 用途 |
|---|---|
| `think/` | 分析前：目标设定、方法选择、五维评分指南 |
| `check/` | 分析后：逻辑验证、异常检测、完整性清单 |
| `hunt/` | 调试：系统化定位问题 |
| `learn/` | 从积累的分析中提炼模式 |
| `backtest/` | 信号回测：入场 / 出场 vs 历史价格 |

## 股票代码归一化

| 输入 | 归一化后 | 市场 |
|---|---|---|
| `AAPL` | `AAPL.US` | 美股 |
| `00700` | `00700.HK` | 港股 |
| `603906` | `SH603906` | 沪市 A 股 |
| `000001` | `SZ000001` | 深市 A 股 |

由 `DataManager.normalize_symbol()` 自动处理。

## 运行环境

- Python 3.9+
- 带同步方案的 Obsidian vault（Dropbox、iCloud、remotely-save 等）
- Claude Code CLI（用于运行分析 agent）

可选：[长桥（Longbridge）](https://open.longportapp.com/) 账号，获取实时港股/A 股数据。

## License

MIT
