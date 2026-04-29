#!/usr/bin/env python3
"""
定时任务: 回测复盘 - 验证历史分析信号的准确率

用法:
    python scripts/run_review.py                    # 全量复盘
    python scripts/run_review.py AAPL.US NVDA.US    # 指定股票
    python scripts/run_review.py --notify           # 发送通知

被 launchd/cron 调用 (建议每天 9:00):
    0 9 * * * cd /path/to/trader-obsidian && python scripts/run_review.py --notify
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# 导入统一配置（config.py 会自动加载 .env）
from config import Config

from backtest.review import ReviewScheduler
from notification import notify, notify_success, notify_error


def run_review(tickers: list = None, days_after: int = 30, lookback_days: int = 90) -> dict:
    """
    执行回测复盘

    Args:
        tickers: 指定股票列表，None = 全量
        days_after: 信号持有天数
        lookback_days: 回看多久的历史分析记录

    Returns:
        {"success": bool, "summary": str, "tickers": int, "signals": int}
    """
    scheduler = ReviewScheduler()

    try:
        summary = scheduler.run_review(
            days_after=days_after,
            lookback_days=lookback_days,
            tickers=tickers,
        )

        # 从 summary 中提取统计
        # summary 是 markdown 格式，我们简单解析
        ticker_count = summary.count("|") // 4  # 粗略估计
        signal_count = 0
        if "验证" in summary:
            # 尝试提取 "验证 N 条信号"
            import re
            m = re.search(r"验证\s*(\d+)\s*条信号", summary)
            if m:
                signal_count = int(m.group(1))

        return {
            "success": True,
            "summary": summary,
            "tickers": ticker_count,
            "signals": signal_count,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": f"复盘失败: {e}",
            "tickers": 0,
            "signals": 0,
        }


def main():
    parser = argparse.ArgumentParser(description="Backtest Review - Scheduled Task")
    parser.add_argument("tickers", nargs="*", help="指定股票代码 (如 AAPL.US)")
    parser.add_argument("--days-after", type=int, default=30, help="信号持有天数")
    parser.add_argument("--lookback", type=int, default=90, help="回看天数")
    parser.add_argument("--notify", action="store_true", help="发送 macOS 通知")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    start_time = datetime.now()
    result = run_review(
        tickers=args.tickers if args.tickers else None,
        days_after=args.days_after,
        lookback_days=args.lookback,
    )
    elapsed = (datetime.now() - start_time).total_seconds()

    # 输出
    if args.json:
        result["elapsed_seconds"] = elapsed
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["summary"])
        print(f"\n耗时: {elapsed:.1f}s")

    # 通知
    if args.notify:
        if result["success"]:
            title = "📊 回测复盘完成"
            msg = f"{result['tickers']} 只股票, {result['signals']} 条信号验证 | 耗时 {elapsed:.0f}s"
            notify_success(title, msg)
        else:
            notify_error("回测复盘失败", result.get("error", "未知错误"))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
