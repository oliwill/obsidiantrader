"""
财报数据模块 — earnings-preview + earnings-recap

提供:
- 下次财报日期
- 分析师 EPS/Revenue 共识预期
- 历史 beat/miss 记录
- 过往财报后股价反应
- Whisper 数字（非官方预期）

用法:
    from data.earnings import EarningsCalendar
    ec = EarningsCalendar()
    info = ec.get_earnings_info("AAPL")
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests
import yfinance as yf

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_earnings")


class EarningsInfo:
    """单只股票财报信息"""
    def __init__(self):
        self.ticker: str = ""
        self.next_earnings_date: Optional[str] = None
        self.next_eps_estimate: Optional[float] = None
        self.next_revenue_estimate: Optional[float] = None
        self.eps_consensus: Optional[float] = None
        self.revenue_consensus: Optional[float] = None
        self.history: List[Dict] = []
        self.whisper_eps: Optional[float] = None
        self.analyst_count: int = 0
        self.surprise_history: List[Dict] = []

    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "next_earnings_date": self.next_earnings_date,
            "next_eps_estimate": self.next_eps_estimate,
            "next_revenue_estimate": self.next_revenue_estimate,
            "eps_consensus": self.eps_consensus,
            "revenue_consensus": self.revenue_consensus,
            "history": self.history,
            "whisper_eps": self.whisper_eps,
            "analyst_count": self.analyst_count,
            "surprise_history": self.surprise_history,
        }


class EarningsCalendar:
    """财报日历与预期数据"""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _yf_symbol(self, symbol: str) -> str:
        """标准化为 YF 代码"""
        s = symbol.upper()
        if s.endswith(".US"):
            return s.replace(".US", "")
        if s.endswith(".HK"):
            return s
        if s.startswith("SH"):
            return s[2:] + ".SS"
        if s.startswith("SZ"):
            return s[2:] + ".SZ"
        return s

    def get_earnings_info(self, symbol: str) -> Dict:
        """
        获取股票完整财报信息

        Returns:
            EarningsInfo dict
        """
        info = EarningsInfo()
        info.ticker = symbol

        try:
            ticker = yf.Ticker(self._yf_symbol(symbol))
            info_data = ticker.info

            # 下次财报日期
            next_date = info_data.get("earningsDate")
            if next_date:
                if isinstance(next_date, list):
                    next_date = next_date[0]
                info.next_earnings_date = str(next_date)[:10] if hasattr(next_date, 'strftime') else str(next_date)

            # 分析师预期
            info.next_eps_estimate = info_data.get("epsEstimate")
            info.next_revenue_estimate = info_data.get("revenueEstimate")
            info.eps_consensus = info_data.get("epsCurrentYear") or info_data.get("trailingEPS")
            info.analyst_count = info_data.get("numberOfAnalystOpinions", 0)

            # 历史财报
            earnings_dates = ticker.earnings_dates
            if earnings_dates is not None and not earnings_dates.empty:
                info.history = self._parse_earnings_dates(earnings_dates)

            # 历史 surprise
            info.surprise_history = self._get_historical_surprises(ticker)

        except Exception as e:
            logger.warning(f"Earnings data fetch failed for {symbol}: {e}")

        return info.to_dict()

    def _parse_earnings_dates(self, df) -> List[Dict]:
        """解析 yfinance earnings_dates DataFrame"""
        results = []
        try:
            df = df.reset_index()
            for _, row in df.head(8).iterrows():
                date_val = row.iloc[0]
                if hasattr(date_val, 'strftime'):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)[:10]

                eps_est = row.get('EPS Estimate') if 'EPS Estimate' in row else None
                reported_eps = row.get('Reported EPS') if 'Reported EPS' in row else None
                surprise_pct = row.get('Surprise(%)') if 'Surprise(%)' in row else None

                entry = {
                    "date": date_str,
                    "eps_estimate": float(eps_est) if eps_est is not None and not (hasattr(eps_est, 'isna') and eps_est.isna()) else None,
                    "reported_eps": float(reported_eps) if reported_eps is not None and not (hasattr(reported_eps, 'isna') and reported_eps.isna()) else None,
                    "surprise_pct": float(surprise_pct) if surprise_pct is not None and not (hasattr(surprise_pct, 'isna') and surprise_pct.isna()) else None,
                }
                results.append(entry)
        except Exception as e:
            logger.warning(f"Parse earnings dates failed: {e}")
        return results

    def _get_historical_surprises(self, ticker) -> List[Dict]:
        """获取历史财报 surprise 记录"""
        results = []
        try:
            # yfinance earnings_trend 或 quarterly_earnings
            q_earnings = ticker.quarterly_earnings
            if q_earnings is not None and not q_earnings.empty:
                q_earnings = q_earnings.reset_index()
                for _, row in q_earnings.head(8).iterrows():
                    date_val = row.iloc[0]
                    if hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime('%Y-%m-%d')
                    else:
                        date_str = str(date_val)

                    revenue = row.get('Revenue') if 'Revenue' in row else None
                    earnings = row.get('Earnings') if 'Earnings' in row else None

                    results.append({
                        "date": date_str,
                        "revenue": float(revenue) if revenue is not None else None,
                        "earnings": float(earnings) if earnings is not None else None,
                    })
        except Exception as e:
            logger.warning(f"Historical surprises failed: {e}")
        return results

    def get_upcoming_earnings(self, days: int = 14) -> List[Dict]:
        """
        获取未来 N 天内将发布财报的股票列表

        Args:
            days: 向前看多少天

        Returns:
            [{ticker, date, eps_estimate, revenue_estimate}, ...]
        """
        # 这个需要遍历 watchlist 或 index 中的股票逐一检查
        # 暂返回空列表，由调用方传入股票列表
        return []

    def format_earnings_markdown(self, info: Dict) -> str:
        """将财报信息格式化为 Markdown"""
        lines = ["## 财报预期", ""]

        next_date = info.get("next_earnings_date")
        if next_date:
            lines.append(f"**下次财报**: {next_date}")

        eps_est = info.get("next_eps_estimate")
        rev_est = info.get("next_revenue_estimate")
        if eps_est:
            lines.append(f"**EPS 共识预期**: ${eps_est:.2f}")
        if rev_est:
            lines.append(f"**Revenue 共识预期**: ${rev_est/1e9:.2f}B" if rev_est > 1e9 else f"**Revenue 共识预期**: ${rev_est/1e6:.1f}M")

        analyst_count = info.get("analyst_count", 0)
        if analyst_count:
            lines.append(f"**覆盖分析师**: {analyst_count} 人")

        # 历史 surprise
        history = info.get("history", [])
        if history:
            lines.append("")
            lines.append("### 历史财报 Surprise")
            lines.append("| 日期 | EPS 预期 | 实际 EPS | Surprise |")
            lines.append("|------|----------|----------|----------|")
            for h in history[:6]:
                date = h.get("date", "")
                est = f"${h['eps_estimate']:.2f}" if h.get("eps_estimate") else "-"
                actual = f"${h['reported_eps']:.2f}" if h.get("reported_eps") else "-"
                surprise = f"{h['surprise_pct']:+.1f}%" if h.get("surprise_pct") else "-"
                lines.append(f"| {date} | {est} | {actual} | {surprise} |")

        lines.append("")
        return "\n".join(lines)


# ========== CLI 测试 ==========

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python earnings.py TICKER")
        sys.exit(1)

    ec = EarningsCalendar()
    info = ec.get_earnings_info(sys.argv[1])
    print(json.dumps(info, ensure_ascii=False, indent=2))
