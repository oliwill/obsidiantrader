"""
回测模块 - 验证分析结论的预测能力

用法:
    from backtest import BacktestRunner, ReportGenerator

    runner = BacktestRunner(data_manager, memory_manager)

    # 回测单次分析
    bt = runner.backtest_analysis("AAPL.US", analysis_result, "2024-01-15")

    # 回测某只股票的 wiki 时间线
    results = runner.backtest_wiki_timeline("AAPL.US", days_after=30)

    # 全量回测 + 生成报告
    all_results = runner.run_all(days_after=30)
    ReportGenerator().generate_markdown_report(all_results)
"""

from .core import BacktestEngine, BacktestResult, SignalPerformance
from .runner import BacktestRunner
from .report import ReportGenerator
from .review import ReviewScheduler

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "SignalPerformance",
    "BacktestRunner",
    "ReportGenerator",
    "ReviewScheduler",
]
