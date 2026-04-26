"""
股票相关性分析模块 — stock-correlation

提供:
- 与指定股票相关性最高的股票列表
- 行业/板块内相关性矩阵
- 配对交易候选

用法:
    from data.correlation import CorrelationAnalyzer
    ca = CorrelationAnalyzer()
    peers = ca.find_peers("NVDA", top_n=5)
"""
import json
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_correlation")


class CorrelationAnalyzer:
    """股票相关性分析器"""

    # 行业映射表（常见股票）
    SECTOR_PEERS = {
        "NVDA": ["AMD", "INTC", "AVGO", "MRVL", "QCOM"],
        "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
        "TSLA": ["RIVN", "LCID", "NIO", "XPEV"],
        "AMD": ["NVDA", "INTC", "AVGO", "MRVL"],
        "MRVL": ["NVDA", "AMD", "AVGO", "QCOM"],
        "POET": ["NVTS", "MRVL", "LITE", "AAOI"],
        "NVTS": ["POET", "MRVL", "IFNNY", "POWI"],
        "GOOGL": ["META", "MSFT", "AMZN", "AAPL"],
        "META": ["GOOGL", "MSFT", "SNAP", "PINS"],
        "AMZN": ["WMT", "TGT", "COST", "EBAY"],
        "MSFT": ["AAPL", "GOOGL", "META", "ORCL"],
        "MU": ["WDC", "SNDK", "INTC", "NVDA"],
        "INTC": ["AMD", "NVDA", "QCOM", "AVGO"],
    }

    def __init__(self, period: str = "6mo"):
        self.period = period

    def _yf_symbol(self, symbol: str) -> str:
        s = symbol.upper()
        if s.endswith(".US"):
            return s.replace(".US", "")
        return s

    def find_peers(self, symbol: str, top_n: int = 5, use_calculated: bool = True) -> List[Dict]:
        """
        找到与指定股票相关性最高的 peer

        Args:
            symbol: 股票代码
            top_n: 返回前 N 个
            use_calculated: 是否用历史价格计算真实相关性

        Returns:
            [{ticker, correlation, sector}, ...]
        """
        peers = self.SECTOR_PEERS.get(symbol.upper().replace(".US", ""), [])
        if not peers:
            return []

        if use_calculated:
            return self._calculate_correlations(symbol, peers, top_n)
        else:
            # 返回预设 peers，correlation 为 None
            return [{"ticker": p, "correlation": None, "sector": "preset"} for p in peers[:top_n]]

    def _calculate_correlations(self, symbol: str, peers: List[str], top_n: int) -> List[Dict]:
        """计算实际价格相关性"""
        try:
            # 获取价格数据
            all_symbols = [self._yf_symbol(symbol)] + [self._yf_symbol(p) for p in peers]
            data = yf.download(all_symbols, period=self.period, progress=False)["Close"]

            if data is None or data.empty:
                return [{"ticker": p, "correlation": None, "sector": "data_unavailable"} for p in peers[:top_n]]

            # 单只股票时 data 是 Series
            if len(all_symbols) == 2:
                data = data.to_frame()
                data.columns = all_symbols

            # 计算日收益率
            returns = data.pct_change().dropna()

            target_col = self._yf_symbol(symbol)
            if target_col not in returns.columns:
                return [{"ticker": p, "correlation": None, "sector": "column_missing"} for p in peers[:top_n]]

            correlations = []
            for peer in peers:
                peer_col = self._yf_symbol(peer)
                if peer_col in returns.columns:
                    corr = returns[target_col].corr(returns[peer_col])
                    if not pd.isna(corr):
                        correlations.append({"ticker": peer, "correlation": round(float(corr), 3), "sector": "calculated"})

            # 按相关性排序
            correlations.sort(key=lambda x: abs(x["correlation"]) if x["correlation"] is not None else 0, reverse=True)
            return correlations[:top_n]

        except Exception as e:
            logger.warning(f"Correlation calculation failed: {e}")
            return [{"ticker": p, "correlation": None, "sector": "error"} for p in peers[:top_n]]

    def to_markdown(self, peers: List[Dict], symbol: str) -> str:
        """格式化为 Markdown"""
        lines = ["## 交叉引用", ""]
        lines.append(f"**与 {symbol} 相关性最高的股票:**")
        lines.append("")

        for p in peers:
            ticker = p["ticker"]
            corr = p.get("correlation")
            if corr is not None:
                emoji = "🔴" if abs(corr) > 0.7 else "🟡" if abs(corr) > 0.4 else "🟢"
                lines.append(f"- {emoji} [[{ticker}_US]] — 相关性 {corr:+.2f}")
            else:
                lines.append(f"- [[{ticker}_US]] — 行业 peer")

        lines.append("")
        return "\n".join(lines)


# ========== CLI 测试 ==========

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python correlation.py TICKER")
        sys.exit(1)

    ca = CorrelationAnalyzer()
    peers = ca.find_peers(sys.argv[1])
    print(json.dumps(peers, ensure_ascii=False, indent=2))
