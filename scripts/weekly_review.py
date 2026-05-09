#!/usr/bin/env python3
"""
每周六复盘任务 - 回测验证 + 框架优化建议

用法:
    python scripts/weekly_review.py             # 执行全量复盘
    python scripts/weekly_review.py AAPL.US     # 指定股票
    python scripts/weekly_review.py --notify    # 执行 + macOS 通知
    python scripts/weekly_review.py --json      # JSON 格式输出

被 launchd 每周六 10:00 自动调用:
    launchd/com.trader-obsidian.weekly-review.plist
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from config import Config
from backtest.review import ReviewScheduler
from backtest.runner import BacktestRunner
from backtest.framework_analyzer import FrameworkAnalyzer, FrameworkReport
from memory.manager import MemoryManager
from run_analysis import write_task
from notification import notify_success, notify_error

WIKI_DIR = Config.get_wiki_dir()
LOOKBACK_DAYS = 90
DAYS_AFTER = 30


def run_weekly_review(tickers: list = None) -> dict:
    """
    执行完整周复盘流水线。

    Returns:
        {success, summary_path, signal_count, suggestion_count,
         win_rate, avg_return, error}
    """
    mm = MemoryManager()
    runner = BacktestRunner()
    scheduler = ReviewScheduler()
    analyzer = FrameworkAnalyzer()

    try:
        # 1. 回测 + 写入每只股票的「预测验证」section
        scheduler.run_review(
            days_after=DAYS_AFTER,
            lookback_days=LOOKBACK_DAYS,
            tickers=tickers,
        )

        # 2. 获取结构化结果供框架分析
        if tickers:
            results = {}
            for t in tickers:
                bt = runner.backtest_wiki_timeline(
                    t, days_after=DAYS_AFTER, lookback_days=LOOKBACK_DAYS
                )
                if bt:
                    results[t] = bt
        else:
            results = runner.run_all(
                days_after=DAYS_AFTER, lookback_days=LOOKBACK_DAYS
            )

        # 3. 框架级分析 → 优化建议
        report = analyzer.analyze(results, lookback_days=LOOKBACK_DAYS)

        # 4. 写复盘报告到 Obsidian
        summary_path = _write_weekly_report(report, results)

        # 5. 创建 Task 提醒文件
        _write_review_task(report, summary_path)

        return {
            "success": True,
            "summary_path": str(summary_path),
            "signal_count": report.total_signals,
            "suggestion_count": len(report.suggestions),
            "win_rate": report.win_rate,
            "avg_return": report.avg_return,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary_path": "",
            "signal_count": 0,
            "suggestion_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
        }


# ── 报告写入 ─────────────────────────────────────────────────────

def _write_weekly_report(report: FrameworkReport, results: dict) -> Path:
    """生成并写入 Analysis/复盘_YYYYMMDD.md"""
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = WIKI_DIR / f"复盘_{datetime.now().strftime('%Y%m%d')}.md"

    lines = [
        "---",
        f'title: "周复盘 {today}"',
        "type: weekly-review",
        f"created: {today}",
        "status: pending-review",
        f"signals_verified: {report.total_signals}",
        f"win_rate: {report.win_rate:.1f}%",
        f"avg_return: {report.avg_return:+.2f}%",
        "---",
        "",
        "## 本期概况",
        "",
        f"覆盖期间：{report.period}  ",
        f"共验证 **{report.total_signals}** 条信号，"
        f"整体胜率 **{report.win_rate:.1f}%**，"
        f"平均收益 **{report.avg_return:+.2f}%**",
        "",
    ]

    # 各标的汇总表
    if results:
        lines += [
            "| 标的 | 信号数 | 胜率 | 均收益 | |",
            "|------|--------|------|--------|---|",
        ]
        for ticker, bt_list in sorted(results.items()):
            verified = [s for bt in bt_list for s in bt.signals if s.verified]
            if not verified:
                continue
            wins = sum(1 for s in verified if s.correct)
            wr = wins / len(verified) * 100
            avg_ret = sum(s.return_pct for s in verified) / len(verified)
            icon = "✅" if wr >= 55 else ("⚠️" if wr >= 40 else "❌")
            lines.append(
                f"| {ticker} | {len(verified)} | {wr:.1f}% | {avg_ret:+.2f}% | {icon} |"
            )
        lines.append("")

    # 信号类型分布
    if report.by_action:
        lines += [
            "## 信号类型分布",
            "",
            "| 类型 | 数量 | 胜率 | 均收益 | 中位最高涨幅 | 中位最大回撤 |",
            "|------|------|------|--------|-------------|-------------|",
        ]
        for action, st in sorted(report.by_action.items()):
            lines.append(
                f"| {action} | {st['count']} | {st['win_rate']:.1f}% "
                f"| {st['avg_return']:+.2f}% "
                f"| {st['median_max_return']:+.1f}% "
                f"| {st['median_drawdown']:+.1f}% |"
            )
        lines.append("")

    # 规律与教训
    lines += [
        "## 规律与教训",
        "",
        f"> {report.raw_diagnosis}",
        "",
    ]

    # 框架优化建议（带 checkbox）
    lines += [
        "## 框架优化建议",
        "",
        "> 请在 Obsidian 中勾选认可的建议，采纳后可告知 Claude Code 更新分析框架。",
        "",
    ]

    if report.suggestions:
        for s in report.suggestions:
            lines += [
                f"- [ ] **#{s.id} [{s.category}]** 置信度：{s.confidence}",
                f"  - 发现：{s.finding}",
                f"  - 建议：{s.suggestion}",
                "",
            ]
    elif report.total_signals < 3:
        lines.append(
            "_信号样本不足（<3 条），无法生成统计建议。继续积累分析记录后重新复盘。_"
        )
        lines.append("")
    else:
        lines.append(
            "_当前回测结果未触发改进规则，分析框架运行良好。_"
        )
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def _write_review_task(report: FrameworkReport, summary_path: Path):
    """在 Tasks/ 目录创建待确认提醒"""
    n = len(report.suggestions)
    desc = (
        f"本周复盘完成。验证 {report.total_signals} 条信号，"
        f"胜率 {report.win_rate:.1f}%，均收益 {report.avg_return:+.2f}%。\n\n"
        f"共生成 **{n}** 条框架优化建议，请打开复盘报告确认采纳情况：\n\n"
        f"路径：`{summary_path}`"
    )
    write_task(
        title=f"周复盘确认 — {n} 条框架建议待审阅",
        ticker="REVIEW",
        task_type="review",
        description=desc,
        priority="high" if n > 0 else "low",
        due_date=datetime.now().strftime("%Y-%m-%d"),
    )


# ── CLI 入口 ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="每周复盘 + 框架优化建议")
    parser.add_argument("tickers", nargs="*", help="指定股票代码，如 AAPL.US NVDA.US")
    parser.add_argument("--notify", action="store_true", help="发送 macOS 通知")
    parser.add_argument("--json", action="store_true", dest="json_output", help="输出 JSON")
    args = parser.parse_args()

    start = datetime.now()
    result = run_weekly_review(tickers=args.tickers if args.tickers else None)
    elapsed = (datetime.now() - start).total_seconds()

    if args.json_output:
        result["elapsed_seconds"] = elapsed
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["success"]:
            print(f"✅ 复盘完成（{elapsed:.1f}s）")
            print(f"   验证信号：{result['signal_count']} 条")
            print(f"   胜率：{result['win_rate']:.1f}%  均收益：{result['avg_return']:+.2f}%")
            print(f"   框架建议：{result['suggestion_count']} 条")
            print(f"   报告路径：{result['summary_path']}")
        else:
            print(f"❌ 复盘失败：{result.get('error')}")

    if args.notify:
        if result["success"]:
            n = result["suggestion_count"]
            notify_success(
                "📊 周复盘完成",
                f"验证 {result['signal_count']} 条信号 · {n} 条框架建议待确认",
            )
        else:
            notify_error("周复盘失败", result.get("error", "未知错误"))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
