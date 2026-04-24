"""
Backtest runner - batch execution and memory integration
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from loguru import logger

from data.manager import DataManager
from memory.manager import MemoryManager
from analyzer.base import AnalysisResult
from backtest.core import BacktestEngine, BacktestResult, SignalPerformance


class BacktestRunner:
    """
    Batch backtest runner with memory integration

    Usage:
        runner = BacktestRunner(data_manager, memory_manager)
        # Backtest a single analysis
        result = runner.backtest_analysis("AAPL.US", analysis_result, "2024-01-15")
        # Backtest from wiki timeline records
        results = runner.backtest_wiki_timeline("AAPL.US", days_after=30)
        # Batch backtest all tracked stocks
        all_results = runner.run_all(days_after=30)
    """

    def __init__(
        self,
        data_manager: Optional[DataManager] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.dm = data_manager or DataManager()
        self.mm = memory_manager or MemoryManager()
        self.engine = BacktestEngine(self.dm)

    def backtest_analysis(
        self,
        ticker: str,
        result: AnalysisResult,
        analysis_date: str,
        days_after: int = 30,
    ) -> BacktestResult:
        """Backtest an AnalysisResult and write result to wiki"""
        bt = self.engine.backtest_analysis(ticker, result, analysis_date, days_after)
        self._write_backtest_to_wiki(ticker, bt)
        return bt

    def backtest_signal(
        self,
        ticker: str,
        signal_text: str,
        signal_date: str,
        days_after: int = 30,
    ) -> SignalPerformance:
        """Backtest a single signal"""
        return self.engine.backtest_signal(ticker, signal_text, signal_date, days_after)

    def backtest_wiki_timeline(
        self,
        ticker: str,
        days_after: int = 30,
        lookback_days: int = 90,
    ) -> List[BacktestResult]:
        """
        Parse analysis timeline from stock wiki and backtest each entry

        Expects timeline entries like:
        - **2024-01-15 14:30** | 价格: 150 | 评分: 85/100 | 类型: 综合分析
          - 核心观点: BUY signal, bullish on earnings
        """
        results = []
        wiki = self.mm.get_stock_wiki(ticker)
        if not wiki:
            logger.warning(f"No wiki found for {ticker}")
            return results

        # Extract timeline entries
        timeline_pattern = re.compile(
            r'- \*\*(\d{4}-\d{2}-\d{2}[^*]*)\*\*\s*\|\s*价格:\s*([\d.]+)\s*\|\s*评分:\s*([\d.]+)/100\s*\|\s*类型:\s*([^\n]*)\n\s+- 核心观点:\s*([^\n]*)',
            re.MULTILINE
        )

        cutoff = datetime.now() - timedelta(days=lookback_days)

        for m in timeline_pattern.finditer(wiki):
            date_str = m.group(1).strip()[:10]  # YYYY-MM-DD
            try:
                entry_dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if entry_dt < cutoff:
                continue
            # Must be at least days_after in the past to verify
            if datetime.now() - entry_dt < timedelta(days=days_after):
                continue

            price = float(m.group(2))
            score = float(m.group(3))
            analysis_type = m.group(4).strip()
            core_view = m.group(5).strip()

            # Build a synthetic AnalysisResult
            signals = self._extract_signals_from_text(core_view)
            if not signals:
                signals = ["HOLD"]  # Default if no explicit signal

            result = AnalysisResult(
                score=score,
                summary=core_view,
                signals=signals,
                risks=[],
                details={"price": price, "type": analysis_type}
            )

            bt = self.engine.backtest_analysis(ticker, result, date_str, days_after)
            results.append(bt)
            self._write_backtest_to_wiki(ticker, bt)

        logger.info(f"Backtested {len(results)} timeline entries for {ticker}")
        return results

    def run_all(
        self,
        days_after: int = 30,
        lookback_days: int = 90,
    ) -> Dict[str, List[BacktestResult]]:
        """
        Run backtest for all stocks in the wiki index

        Returns:
            {ticker: [BacktestResult, ...]}
        """
        all_results: Dict[str, List[BacktestResult]] = {}
        index = self.mm.get_index()

        # Parse tickers from index markdown table
        tickers = []
        for line in index.split("\n"):
            if line.startswith("|") and "---" not in line and "代码" not in line:
                parts = [p.strip() for p in line.split("|")]
                parts = [p for p in parts if p]
                if parts:
                    tickers.append(parts[0])

        for ticker in tickers:
            try:
                results = self.backtest_wiki_timeline(ticker, days_after, lookback_days)
                if results:
                    all_results[ticker] = results
            except Exception as e:
                logger.error(f"Backtest failed for {ticker}: {e}")

        return all_results

    def _extract_signals_from_text(self, text: str) -> List[str]:
        """Extract BUY/SELL/HOLD signals from text"""
        signals = []
        upper = text.upper()
        if any(w in upper for w in ["BUY", "LONG", "BULLISH", "ADD", "加仓", "买入", "做多"]):
            signals.append("BUY")
        if any(w in upper for w in ["SELL", "SHORT", "BEARISH", "EXIT", "减仓", "卖出", "做空"]):
            signals.append("SELL")
        if any(w in upper for w in ["HOLD", "NEUTRAL", "WAIT", "观望", "持有"]):
            signals.append("HOLD")
        return signals

    def _write_backtest_to_wiki(self, ticker: str, bt: BacktestResult):

        """Append backtest result to stock wiki"""

        if not bt.signals:

            return

        wiki = self.mm.get_stock_wiki(ticker)

        if "预测验证" not in wiki:

            return

        entry = bt.to_markdown()

        self.mm.append_to_section(ticker, "预测验证", entry)
