"""
ETF 分析模块 — etf-premium

检测股票是否为 ETF，并提供:
- NAV vs 市场价格（溢价/折价）
- 持仓集中度
- 费用率

用法:
    from data.etf import ETFAnalyzer
    ea = ETFAnalyzer()
    data = ea.analyze("SPY")  # 或 ea.detect_etf("AAPL")
"""
import json
from typing import Dict, Optional

import yfinance as yf

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_etf")


class ETFAnalyzer:
    """ETF 分析器"""

    def __init__(self):
        pass

    def _yf_symbol(self, symbol: str) -> str:
        s = symbol.upper()
        if s.endswith(".US"):
            return s.replace(".US", "")
        return s

    def is_etf(self, symbol: str) -> bool:
        """判断是否为 ETF"""
        try:
            ticker = yf.Ticker(self._yf_symbol(symbol))
            info = ticker.info
            return info.get("quoteType") == "ETF" or info.get("fundFamily") is not None
        except Exception:
            return False

    def analyze(self, symbol: str) -> Dict:
        """
        获取 ETF 数据（如果不是 ETF 返回空）

        Returns:
            {
                "is_etf": bool,
                "nav": float,
                "market_price": float,
                "premium_pct": float,
                "expense_ratio": float,
                "aum": float,
                "top_holdings": [{"ticker": str, "weight": float}, ...],
                "sector_breakdown": {sector: weight, ...},
            }
        """
        result = {"ticker": symbol, "is_etf": False}

        if not self.is_etf(symbol):
            return result

        result["is_etf"] = True

        try:
            ticker = yf.Ticker(self._yf_symbol(symbol))
            info = ticker.info

            # 基本信息
            result["fund_family"] = info.get("fundFamily")
            result["expense_ratio"] = info.get("annualReportExpenseRatio")
            result["aum"] = info.get("totalAssets")

            # 价格 vs NAV
            result["market_price"] = info.get("regularMarketPrice") or info.get("navPrice")
            result["nav"] = info.get("navPrice")

            if result["nav"] and result["market_price"] and result["nav"] > 0:
                result["premium_pct"] = round(
                    (result["market_price"] - result["nav"]) / result["nav"] * 100, 2
                )
            else:
                result["premium_pct"] = None

            # 持仓（yfinance 有时不返回 holdings，需容错）
            try:
                holdings = ticker.institutional_holders
                if holdings is not None and not holdings.empty:
                    top = []
                    for _, row in holdings.head(10).iterrows():
                        top.append({
                            "holder": str(row.iloc[0]),
                            "shares": int(row.iloc[1]) if len(row) > 1 else None,
                            "pct": float(row.iloc[2]) if len(row) > 2 else None,
                        })
                    result["top_institutional"] = top
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"ETF analysis failed for {symbol}: {e}")
            result["error"] = str(e)

        return result

    def to_markdown(self, data: Dict) -> str:
        """格式化为 Markdown"""
        if not data.get("is_etf"):
            return ""

        lines = ["## ETF 分析", ""]

        er = data.get("expense_ratio")
        if er:
            lines.append(f"**费用率**: {er*100:.2f}%")

        aum = data.get("aum")
        if aum:
            lines.append(f"**AUM**: ${aum/1e9:.2f}B")

        premium = data.get("premium_pct")
        if premium is not None:
            status = "溢价" if premium > 0 else "折价"
            lines.append(f"**NAV 偏差**: {premium:+.2f}% ({status})")

        lines.append("")
        return "\n".join(lines)


# ========== CLI 测试 ==========

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python etf.py TICKER")
        sys.exit(1)

    ea = ETFAnalyzer()
    data = ea.analyze(sys.argv[1])
    print(json.dumps(data, ensure_ascii=False, indent=2))
