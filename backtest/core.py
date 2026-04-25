"""
Backtest engine core
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from data.manager import DataManager
from analyzer.base import AnalysisResult


@dataclass
class SignalPerformance:
    """Performance of a single signal"""
    signal: str
    action: str
    ticker: str
    entry_date: str
    entry_price: float
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    holding_days: int = 0
    return_pct: float = 0.0
    max_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    verified: bool = False
    correct: bool = False


@dataclass
class BacktestResult:
    """Backtest result for a single stock"""
    ticker: str
    analysis_date: str
    signals: List[SignalPerformance] = field(default_factory=list)
    summary: str = ""
    total_signals: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    avg_holding_days: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            f"### {self.ticker} Backtest ({self.analysis_date})",
            "",
            f"- Total signals: {self.total_signals}",
            f"- Win rate: {self.win_rate:.1f}% ({self.win_count}/{self.loss_count + self.win_count})",
            f"- Avg return: {self.avg_return:.2f}%",
            f"- Avg holding: {self.avg_holding_days:.1f} days",
            "",
            "| Signal | Action | Entry | Exit | Return | Max DD | Correct |",
            "|--------|--------|-------|------|--------|--------|---------|",
        ]
        for s in self.signals:
            exit_p = f"{s.exit_price:.2f}" if s.exit_price else "-"
            ret = f"{s.return_pct:+.2f}%" if s.verified else "Pending"
            dd = f"{s.max_drawdown_pct:.2f}%" if s.verified else "-"
            ok = "OK" if s.correct else "NG" if s.verified else "PENDING"
            lines.append(
                f"| {s.signal[:20]} | {s.action} | {s.entry_price:.2f} | {exit_p} | {ret} | {dd} | {ok} |"
            )
        lines.append("")
        if self.summary:
            lines.append(f"> {self.summary}")
        return "\n".join(lines)


class BacktestEngine:
    def __init__(self, data_manager: Optional[DataManager] = None):
        self.dm = data_manager or DataManager()

    @staticmethod
    def parse_signal(signal_text: str) -> Tuple[str, str]:
        text = signal_text.upper()
        m = re.search(r'\$([A-Z]{1,5})', signal_text)
        if m:
            ticker = m.group(1)
        else:
            words = re.findall(r'\b[A-Z]{2,5}\b', text)
            ticker = words[0] if words else ""
        if any(w in text for w in ["BUY", "LONG", "ADD", "BULLISH", "买入", "做多", "加仓", "买进"]):
            action = "BUY"
        elif any(w in text for w in ["SELL", "SHORT", "EXIT", "BEARISH", "卖出", "做空", "减仓", "抛售"]):
            action = "SELL"
        elif any(w in text for w in ["HOLD", "WAIT", "NEUTRAL", "持有", "观望", "不动"]):
            action = "HOLD"
        else:
            action = "UNKNOWN"
        return action, ticker

    def backtest_signal(
        self,
        ticker: str,
        signal_text: str,
        signal_date: str,
        days_after: int = 30,
    ) -> SignalPerformance:
        perf = SignalPerformance(
            signal=signal_text,
            action="UNKNOWN",
            ticker=ticker,
            entry_date=signal_date,
            entry_price=0.0,
        )
        action, _ = self.parse_signal(signal_text)
        perf.action = action
        if action == "UNKNOWN":
            logger.warning(f"Cannot parse signal action: {signal_text}")
            return perf
        try:
            period = f"{(datetime.now() - datetime.strptime(signal_date, '%Y-%m-%d')).days + 20}d"
            df = self.dm.get_historical_data(ticker, period)
        except Exception as e:
            logger.error(f"Failed to get {ticker} history: {e}")
            return perf
        if df is None or df.empty:
            logger.warning(f"{ticker} no historical data")
            return perf
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        s = pd.to_datetime(df["date"])
        if s.dt.tz is not None:
            df["date"] = s.dt.tz_convert(None)
        else:
            df["date"] = s.dt.tz_localize(None)
        signal_dt = pd.to_datetime(signal_date)
        future = df[df["date"] >= signal_dt]
        if future.empty:
            logger.warning(f"{ticker} {signal_date} no data after signal date")
            return perf
        entry_row = future.iloc[0]
        perf.entry_price = float(entry_row["close"])
        perf.entry_date = entry_row["date"].strftime("%Y-%m-%d")
        hold_end = min(len(future), days_after + 1)
        hold_df = future.iloc[:hold_end]
        if len(hold_df) < 2:
            logger.warning(f"{ticker} insufficient holding period data")
            return perf
        prices = hold_df["close"].values
        perf.holding_days = len(hold_df) - 1
        if action == "BUY":
            perf.return_pct = (prices[-1] / perf.entry_price - 1) * 100
            perf.max_return_pct = (np.max(prices) / perf.entry_price - 1) * 100
            perf.max_drawdown_pct = (np.min(prices) / perf.entry_price - 1) * 100
            perf.correct = perf.return_pct > 0
        elif action == "SELL":
            perf.return_pct = (1 - prices[-1] / perf.entry_price) * 100
            perf.max_return_pct = (1 - np.min(prices) / perf.entry_price) * 100
            perf.max_drawdown_pct = (1 - np.max(prices) / perf.entry_price) * 100
            perf.correct = perf.return_pct > 0
        else:
            perf.return_pct = abs(prices[-1] / perf.entry_price - 1) * 100
            perf.max_return_pct = perf.return_pct
            perf.max_drawdown_pct = 0.0
            perf.correct = True
        perf.exit_price = float(prices[-1])
        perf.exit_date = hold_df.iloc[-1]["date"].strftime("%Y-%m-%d")
        perf.verified = True
        return perf

    def backtest_analysis(
        self,
        ticker: str,
        result: AnalysisResult,
        analysis_date: str,
        days_after: int = 30,
    ) -> BacktestResult:
        bt = BacktestResult(ticker=ticker, analysis_date=analysis_date)
        if not result.signals:
            bt.summary = "No trading signals"
            return bt
        for sig_text in result.signals:
            perf = self.backtest_signal(ticker, sig_text, analysis_date, days_after)
            bt.signals.append(perf)
        verified = [s for s in bt.signals if s.verified]
        bt.total_signals = len(bt.signals)
        if verified:
            bt.win_count = sum(1 for s in verified if s.correct)
            bt.loss_count = len(verified) - bt.win_count
            bt.win_rate = bt.win_count / len(verified) * 100
            bt.avg_return = np.mean([s.return_pct for s in verified])
            bt.avg_holding_days = np.mean([s.holding_days for s in verified])
            bt.summary = (
                f"{ticker} {analysis_date}: {bt.total_signals} signals, "
                f"verified {len(verified)}, win rate {bt.win_rate:.1f}%, "
                f"avg return {bt.avg_return:+.2f}%"
            )
        else:
            bt.summary = "Signals not verifiable (insufficient data)"
        return bt
