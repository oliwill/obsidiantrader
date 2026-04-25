# /backtest - 回测验证

## 何时使用
- 完成股票分析后，想验证分析结论的预测能力
- 发现 Wiki 中有未验证的预测记录
- 定期批量回测所有跟踪股票的历史信号
- 评估某个分析模型（基本面/威科夫/综合）的真实胜率

## 目标
- 将分析发出的交易信号与市场实际走势对比
- 计算胜率、平均收益、最大回撤等核心指标
- 把验证结果写回 Wiki「预测验证」section，形成闭环

## 依赖模块

```python
from backtest.core import BacktestEngine, BacktestResult
from backtest.runner import BacktestRunner
from backtest.report import ReportGenerator
from data.manager import DataManager
from memory.manager import MemoryManager
```

## 核心用法

### 1. 单信号回测

验证某只股票在某一天的某个具体信号：

```python
from backtest.core import BacktestEngine
from data.manager import DataManager

engine = BacktestEngine(DataManager())

perf = engine.backtest_signal(
    ticker="AAPL.US",
    signal_text="BUY - bullish on earnings beat",
    signal_date="2024-01-15",
    days_after=30,  # 持有30个交易日后平仓
)

print(perf.return_pct)      # 收益率%
print(perf.correct)         # 方向是否正确
print(perf.max_drawdown_pct) # 期间最大回撤
```

### 2. 完整分析结果回测

对一次 `AnalysisResult` 的所有信号批量验证：

```python
from backtest.core import BacktestEngine
from analyzer.models import get_analyzer
from data.manager import DataManager

dm = DataManager()
engine = BacktestEngine(dm)

# 假设刚做完一次分析
df = dm.get_historical_data("NVDA.US", "1y")
fundamentals = dm.get_fundamentals("NVDA.US")
analyzer = get_analyzer("comprehensive")
result = analyzer.analyze(df, fundamentals)

# 回测
bt = engine.backtest_analysis(
    ticker="NVDA.US",
    result=result,
    analysis_date="2025-04-17",
    days_after=30,
)

print(bt.summary)
print(bt.to_markdown())
```

### 3. Wiki 时间线批量回测

自动读取某只股票的 Wiki「分析时间线」，回测每一条历史记录：

```python
from backtest.runner import BacktestRunner

runner = BacktestRunner()

# 回测 AAPL 过去90天内所有可验证的时间线记录
results = runner.backtest_wiki_timeline(
    ticker="AAPL.US",
    days_after=30,
    lookback_days=90,
)

for r in results:
    print(r.summary)
```

### 4. 全仓库批量回测

回测 index.md 中所有跟踪的股票：

```python
all_results = runner.run_all(days_after=30, lookback_days=90)

# 生成报告
gen = ReportGenerator(output_dir="output")
gen.generate_markdown_report(all_results, "report.md")
gen.generate_csv(all_results, "signals.csv")
gen.generate_chart(all_results, "chart.png")
```

## 信号解析规则

回测引擎自动从 `AnalysisResult.signals`（字符串列表）中解析：

| 文本特征 | 解析为 |
|----------|--------|
| BUY / LONG / ADD / bullish | BUY |
| SELL / SHORT / EXIT / bearish | SELL |
| HOLD / WAIT / NEUTRAL | HOLD |
| $TICKER 或纯大写单词 | ticker |

如果信号中不含明确动作，回测引擎会跳过该信号。

## 回测参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `days_after` | 持有天数（按交易日计） | 30 |
| `signal_date` | 信号发出日期 | 必填 |
| `entry_price` | 入场价 = signal_date 收盘价 | 自动获取 |
| `exit_price` | 出场价 = signal_date + days_after 收盘价 | 自动获取 |

## 输出指标

### SignalPerformance（单条信号）
- `return_pct`: 持有期收益率
- `correct`: 方向是否正确（BUY赚、SELL赚、HOLD不亏）
- `max_return_pct`: 期间最大浮盈
- `max_drawdown_pct`: 期间最大回撤
- `holding_days`: 实际持仓天数

### BacktestResult（单次分析）
- `win_rate`: 胜率%
- `avg_return`: 平均收益率
- `avg_holding_days`: 平均持仓天数
- `to_markdown()`: 生成可直接插入 Wiki 的 markdown

## 闭环流程

```
分析股票 → 信号存入 Wiki 时间线
    ↓
等待 N 天后 → 运行 /backtest
    ↓
读取 Wiki 时间线 → 拉取历史价格 → 计算收益
    ↓
结果写回 Wiki「预测验证」section
    ↓
定期汇总 → 生成报告 → 评估模型可信度
```

## 注意事项

1. **数据不足**: 新股或停牌股可能无法验证，会标记为 `verified=False`
2. **时间对齐**: 使用 signal_date 后的第一个交易日收盘价作为入场价
3. **HOLD 信号**: 判定为"不亏即对"，return_pct 记录的是价格变动幅度
4. **不要提前泄露**: 回测只应使用 signal_date 之前已知的分析结论
5. **无交易执行**: 本模块仅做验证，不连接任何券商 API

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 所有信号 return_pct = 0 | 数据获取失败 | 检查 DataManager 是否配置了长桥或 Yahoo Finance |
| verified = False | signal_date 后无数据 | 检查日期格式、股票是否停牌 |
| 胜率异常高/低 | 信号样本太少 | 增加 lookback_days 或等待更多分析记录 |
| Wiki 未更新 | 「预测验证」section 不存在 | 先用 memory manager 初始化股票 Wiki |
