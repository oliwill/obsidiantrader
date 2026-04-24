"""
复盘模块 - 定期回测 + 生成复盘总结 + 写回 wiki

被 /review skill 调用，不直接暴露给用户。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger

from backtest.core import BacktestEngine, BacktestResult
from backtest.runner import BacktestRunner
from backtest.report import ReportGenerator
from data.manager import DataManager
from memory.manager import MemoryManager


class ReviewScheduler:
    """
    复盘调度器

    一键跑完：回测 → 统计 → 写复盘到 wiki → 生成报告文件
    """

    def __init__(
        self,
        data_manager: Optional[DataManager] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.dm = data_manager or DataManager()
        self.mm = memory_manager or MemoryManager()
        self.runner = BacktestRunner(self.dm, self.mm)
        self.reporter = ReportGenerator(output_dir="output")

    def run_review(
        self,
        days_after: int = 30,
        lookback_days: int = 90,
        tickers: Optional[List[str]] = None,
    ) -> str:
        """
        执行一轮完整复盘，返回复盘摘要文本。

        Args:
            days_after: 回测持有天数
            lookback_days: 回看多久的分析记录
            tickers: 指定股票列表，None = 全量
        """
        logger.info(f"Starting review: days_after={days_after}, lookback={lookback_days}")

        # 1. 跑回测
        if tickers:
            results: Dict[str, List[BacktestResult]] = {}
            for ticker in tickers:
                try:
                    bt_list = self.runner.backtest_wiki_timeline(
                        ticker, days_after=days_after, lookback_days=lookback_days
                    )
                    if bt_list:
                        results[ticker] = bt_list
                except Exception as e:
                    logger.error(f"Review failed for {ticker}: {e}")
        else:
            results = self.runner.run_all(days_after=days_after, lookback_days=lookback_days)

        if not results:
            return "本轮复盘无数据（没有可验证的分析记录）。"

        # 2. 汇总统计
        summary = self._build_summary(results)

        # 3. 写复盘到每只股票的 wiki
        for ticker, bt_list in results.items():
            self._write_review_to_wiki(ticker, bt_list, summary)

        # 4. 生成报告文件
        self.reporter.generate_markdown_report(results, f"review_{datetime.now().strftime('%Y%m%d')}.md")
        self.reporter.generate_csv(results, f"review_{datetime.now().strftime('%Y%m%d')}.csv")
        self.reporter.generate_chart(results, f"review_{datetime.now().strftime('%Y%m%d')}.png")

        # 5. 写全局 log
        self.mm.append_log("review", summary["one_liner"])

        logger.info(f"Review done: {summary['one_liner']}")
        return self._format_summary(summary, results)

    def _build_summary(self, results: Dict[str, List[BacktestResult]]) -> Dict:
        """从回测结果提炼统计摘要"""
        total_verified = 0
        total_wins = 0
        all_returns = []
        ticker_stats = []

        for ticker, bt_list in sorted(results.items()):
            verified = sum(r.win_count + r.loss_count for r in bt_list)
            wins = sum(r.win_count for r in bt_list)
            returns = [s.return_pct for r in bt_list for s in r.signals if s.verified]

            total_verified += verified
            total_wins += wins
            all_returns.extend(returns)

            win_rate = wins / verified * 100 if verified else 0
            avg_ret = sum(returns) / len(returns) if returns else 0

            ticker_stats.append({
                "ticker": ticker,
                "verified": verified,
                "wins": wins,
                "win_rate": win_rate,
                "avg_return": avg_ret,
            })

        overall_win_rate = total_wins / total_verified * 100 if total_verified else 0
        overall_avg_ret = sum(all_returns) / len(all_returns) if all_returns else 0

        return {
            "total_verified": total_verified,
            "total_wins": total_wins,
            "overall_win_rate": overall_win_rate,
            "overall_avg_return": overall_avg_ret,
            "ticker_count": len(results),
            "ticker_stats": ticker_stats,
            "one_liner": (
                f"复盘完成: {len(results)}只股票, "
                f"{total_verified}条信号验证, "
                f"胜率{overall_win_rate:.1f}%, "
                f"平均收益{overall_avg_ret:+.2f}%"
            ),
        }

    def _write_review_to_wiki(
        self, ticker: str, bt_list: List[BacktestResult], summary: Dict
    ):
        """把复盘结论追加到股票 wiki 的「预测验证」section"""
        wiki = self.mm.get_stock_wiki(ticker)
        if not wiki:
            return

        # 找这只股票的统计
        ts = next((t for t in summary["ticker_stats"] if t["ticker"] == ticker), None)
        if not ts or ts["verified"] == 0:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"",
            f"### 复盘 [{now}]",
            f"",
            f"- 验证信号数: {ts['verified']}",
            f"- 胜率: {ts['win_rate']:.1f}% ({ts['wins']}/{ts['verified']})",
            f"- 平均收益: {ts['avg_return']:+.2f}%",
            f"",
        ]

        # 逐条信号明细
        for bt in bt_list:
            for s in bt.signals:
                if not s.verified:
                    continue
                mark = "OK" if s.correct else "NG"
                lines.append(
                    f"- [{mark}] {s.action} @ {s.entry_date} "
                    f"→ {s.return_pct:+.2f}% ({s.holding_days}d) "
                    f"| {s.signal[:40]}"
                )

        lines.append("")

        # 诊断建议
        lines.append(self._diagnose(ts))
        lines.append("")

        entry = "\n".join(lines)
        self.mm.append_to_section(ticker, "预测验证", entry)

    def _diagnose(self, stats: Dict) -> str:
        """根据统计数据给出简单诊断"""
        wr = stats["win_rate"]
        ar = stats["avg_return"]
        v = stats["verified"]

        if v < 3:
            return "> 诊断: 样本太少，暂不具备统计意义，继续积累分析记录。"

        parts = []
        if wr >= 60:
            parts.append("胜率良好（≥60%）")
        elif wr >= 45:
            parts.append("胜率尚可（45-60%）")
        else:
            parts.append("胜率偏低（<45%），建议检查信号质量")

        if ar > 2:
            parts.append("平均收益为正，方向判断有效")
        elif ar < -2:
            parts.append("平均收益为负，信号方向需调整")
        else:
            parts.append("收益接近零，信号区分度不足")

        return "> 诊断: " + "；".join(parts) + "。"

    def _format_summary(self, summary: Dict, results: Dict[str, List[BacktestResult]]) -> str:
        """格式化成给人看的复盘摘要"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"## 复盘报告 [{now}]",
            "",
            f"覆盖 {summary['ticker_count']} 只股票，验证 {summary['total_verified']} 条信号。",
            f"总体胜率 **{summary['overall_win_rate']:.1f}%**，平均收益 **{summary['overall_avg_return']:+.2f}%**",
            "",
            "| 股票 | 验证数 | 胜率 | 平均收益 |",
            "|------|--------|------|----------|",
        ]

        for ts in summary["ticker_stats"]:
            lines.append(
                f"| {ts['ticker']} | {ts['verified']} | {ts['win_rate']:.1f}% | {ts['avg_return']:+.2f}% |"
            )

        lines.append("")

        # 每只股票的关键诊断
        for ts in summary["ticker_stats"]:
            if ts["verified"] >= 3:
                lines.append(self._diagnose(ts))

        return "\n".join(lines)
