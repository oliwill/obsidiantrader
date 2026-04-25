# /review - 定期复盘

## 何时使用
- 用户主动发起复盘（说"复盘"、"review"、"看看之前分析的准不准"）
- 积累了多条分析记录后，需要系统性评估预测能力

## 目标
- 对所有跟踪股票的历史分析信号进行批量回测
- 将验证结果写回各股票 wiki「预测验证」section
- 生成复盘摘要，给出诊断建议

## 执行步骤

### Step 1: 确认范围
- 默认回看 90 天内、持有 30 天后验证
- 如果用户指定了某只股票，只回测那只
- 如果距离上次回测不到 7 天且没有新增分析，可以提醒"上次复盘刚做过"

### Step 2: 运行回测

```python
from backtest.review import ReviewScheduler

scheduler = ReviewScheduler()

# 全量复盘
summary = scheduler.run_review(days_after=30, lookback_days=90)

# 或指定股票
summary = scheduler.run_review(days_after=30, tickers=["AAPL.US", "OKLO.US"])
```

### Step 3: 输出结果给用户
- 直接把 `summary` 文本贴给用户
- 告诉用户报告文件已生成在 `output/` 目录

### Step 4: 如果发现问题
- 胜率低于 45% → 建议用 `/hunt` 排查信号质量
- 收益持续为负 → 建议检查分析模型的评分权重
- 样本不足 → 提醒继续积累

## 闭环流程

```
/review
  ↓
BacktestRunner 批量回测 wiki 时间线
  ↓
ReviewScheduler 汇总统计 + 诊断
  ↓
结果写回每只股票 wiki「预测验证」
  ↓
报告文件生成到 output/
  ↓
日志记录到 wiki/log.md
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `days_after` | 信号持有天数 | 30 |
| `lookback_days` | 回看多久的分析记录 | 90 |
| `tickers` | 指定股票列表 | None（全量） |

## 注意事项
1. 需要网络连接（拉取历史价格数据）
2. 数据不足的信号会跳过，不参与统计
3. 诊断建议基于简单规则，不代表完整评估
