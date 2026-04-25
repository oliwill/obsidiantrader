"""
Backtest report generator
"""
from __future__ import annotations

from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

from backtest.core import BacktestResult


class ReportGenerator:
    """
    Generate backtest reports (markdown, CSV, charts)

    Usage:
        gen = ReportGenerator(output_dir="output")
        gen.generate_markdown_report(results, "backtest_report.md")
        gen.generate_csv(results, "backtest_signals.csv")
        gen.generate_chart(results, "backtest_chart.png")
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(
        self,
        results: Dict[str, List[BacktestResult]],
        filename: str = "backtest_report.md",
    ) -> str:
        """Generate a consolidated markdown report"""
        path = self.output_dir / filename

        lines = [
            "# Backtest Report",
            f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "\n## Summary",
            "",
            "| Ticker | Signals | Win Rate | Avg Return | Avg Holding |",
            "|--------|---------|----------|------------|-------------|",
        ]

        grand_total = 0
        grand_wins = 0
        all_returns = []

        for ticker, ticker_results in sorted(results.items()):
            total_signals = sum(r.total_signals for r in ticker_results)
            wins = sum(r.win_count for r in ticker_results)
            losses = sum(r.loss_count for r in ticker_results)
            verified = wins + losses
            win_rate = wins / verified * 100 if verified else 0
            avg_ret = sum(r.avg_return for r in ticker_results) / len(ticker_results) if ticker_results else 0
            avg_hold = sum(r.avg_holding_days for r in ticker_results) / len(ticker_results) if ticker_results else 0

            lines.append(
                f"| {ticker} | {total_signals} | {win_rate:.1f}% | {avg_ret:+.2f}% | {avg_hold:.1f}d |"
            )

            grand_total += verified
            grand_wins += wins
            all_returns.extend([
                s.return_pct for r in ticker_results for s in r.signals if s.verified
            ])

        grand_win_rate = grand_wins / grand_total * 100 if grand_total else 0
        grand_avg_ret = sum(all_returns) / len(all_returns) if all_returns else 0

        lines.extend([
            "",
            f"**Overall**: {grand_total} signals verified, win rate {grand_win_rate:.1f}%, avg return {grand_avg_ret:+.2f}%",
            "",
            "## Details",
            "",
        ])

        for ticker, ticker_results in sorted(results.items()):
            lines.append(f"### {ticker}")
            lines.append("")
            for bt in ticker_results:
                lines.append(bt.to_markdown())
                lines.append("")

        content = "\n".join(lines)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def generate_csv(
        self,
        results: Dict[str, List[BacktestResult]],
        filename: str = "backtest_signals.csv",
    ) -> str:
        """Export all signal performances to CSV"""
        path = self.output_dir / filename
        rows = []
        for ticker, ticker_results in results.items():
            for bt in ticker_results:
                for s in bt.signals:
                    rows.append({
                        "ticker": ticker,
                        "analysis_date": bt.analysis_date,
                        "signal": s.signal,
                        "action": s.action,
                        "entry_date": s.entry_date,
                        "entry_price": s.entry_price,
                        "exit_date": s.exit_date,
                        "exit_price": s.exit_price,
                        "holding_days": s.holding_days,
                        "return_pct": s.return_pct,
                        "max_return_pct": s.max_return_pct,
                        "max_drawdown_pct": s.max_drawdown_pct,
                        "correct": s.correct,
                        "verified": s.verified,
                    })
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return str(path)

    def generate_chart(
        self,
        results: Dict[str, List[BacktestResult]],
        filename: str = "backtest_chart.png",
    ) -> str:
        """Generate a performance comparison chart"""
        path = self.output_dir / filename

        # Collect per-ticker aggregated metrics
        tickers = []
        win_rates = []
        avg_returns = []
        signal_counts = []

        for ticker, ticker_results in sorted(results.items()):
            verified = sum(r.win_count + r.loss_count for r in ticker_results)
            wins = sum(r.win_count for r in ticker_results)
            returns = [s.return_pct for r in ticker_results for s in r.signals if s.verified]
            if verified > 0:
                tickers.append(ticker)
                win_rates.append(wins / verified * 100)
                avg_returns.append(sum(returns) / len(returns) if returns else 0)
                signal_counts.append(verified)

        if not tickers:
            return ""

        fig, axes = plt.subplots(1, 3, figsize=(15, 4))

        # Win rate
        ax1 = axes[0]
        colors = ["green" if r >= 50 else "red" for r in win_rates]
        ax1.barh(tickers, win_rates, color=colors, alpha=0.7)
        ax1.axvline(x=50, color="gray", linestyle="--", alpha=0.5)
        ax1.set_xlabel("Win Rate (%)")
        ax1.set_title("Win Rate by Ticker")

        # Avg return
        ax2 = axes[1]
        colors2 = ["green" if r >= 0 else "red" for r in avg_returns]
        ax2.barh(tickers, avg_returns, color=colors2, alpha=0.7)
        ax2.axvline(x=0, color="gray", linestyle="--", alpha=0.5)
        ax2.set_xlabel("Avg Return (%)")
        ax2.set_title("Average Return by Ticker")

        # Signal count
        ax3 = axes[2]
        ax3.barh(tickers, signal_counts, color="steelblue", alpha=0.7)
        ax3.set_xlabel("Verified Signals")
        ax3.set_title("Signal Count by Ticker")

        fig.suptitle("Backtest Performance Overview", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return str(path)
