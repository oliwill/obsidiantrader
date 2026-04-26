"""
流动性分析模块 — stock-liquidity

提供:
- Short Interest（做空比例）
- Days to Cover
- 机构持仓变化
- 买卖价差/成交量深度
- 换手率分析

用法:
    from data.liquidity import LiquidityAnalyzer
    la = LiquidityAnalyzer()
    data = la.analyze("AAPL")
"""
import json
from typing import Dict, Optional

import yfinance as yf

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_liquidity")


class LiquidityAnalyzer:
    """股票流动性分析器"""

    def __init__(self):
        pass

    def _yf_symbol(self, symbol: str) -> str:
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

    def analyze(self, symbol: str) -> Dict:
        """
        获取股票流动性指标

        Returns:
            {
                "short_interest": float,
                "short_percent_float": float,
                "days_to_cover": float,
                "institutional_ownership": float,
                "insider_ownership": float,
                "float_shares": float,
                "avg_volume_10d": float,
                "avg_volume_3m": float,
                "turnover_ratio": float,
                "bid_ask_spread_pct": float,
            }
        """
        result = {"ticker": symbol}

        try:
            ticker = yf.Ticker(self._yf_symbol(symbol))
            info = ticker.info

            # Short Interest
            result["short_interest"] = info.get("sharesShort")
            result["short_percent_float"] = info.get("shortPercentOfFloat")
            result["days_to_cover"] = info.get("shortRatio")

            # Ownership
            result["institutional_ownership"] = info.get("heldPercentInstitutions")
            result["insider_ownership"] = info.get("heldPercentInsiders")

            # Float
            result["float_shares"] = info.get("floatShares")
            result["shares_outstanding"] = info.get("sharesOutstanding")

            # Volume
            result["avg_volume_10d"] = info.get("averageVolume10days")
            result["avg_volume_3m"] = info.get("averageVolume")

            # Turnover (if we have price and volume)
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            if price and result.get("avg_volume_3m") and result.get("float_shares"):
                daily_dollar_volume = price * result["avg_volume_3m"]
                market_cap_float = price * result["float_shares"]
                result["turnover_ratio"] = daily_dollar_volume / market_cap_float if market_cap_float > 0 else None
                result["daily_dollar_volume"] = daily_dollar_volume
            else:
                result["turnover_ratio"] = None
                result["daily_dollar_volume"] = None

            # 风险评估
            result["risk_flags"] = self._assess_liquidity_risk(result)

        except Exception as e:
            logger.warning(f"Liquidity analysis failed for {symbol}: {e}")
            result["error"] = str(e)

        return result

    def _assess_liquidity_risk(self, data: Dict) -> list:
        """评估流动性风险标志"""
        flags = []

        short_pct = data.get("short_percent_float")
        if short_pct and short_pct > 0.15:
            flags.append(f"做空比例高 ({short_pct*100:.1f}%)，存在 squeeze 风险")
        if short_pct and short_pct > 0.20:
            flags.append("做空比例极高，squeeze 燃料充足")

        days_cover = data.get("days_to_cover")
        if days_cover and days_cover > 5:
            flags.append(f"Days to Cover 高 ({days_cover:.1f}天)，流动性差")

        turnover = data.get("turnover_ratio")
        if turnover and turnover < 0.005:
            flags.append("换手率极低，流动性风险")

        dollar_vol = data.get("daily_dollar_volume")
        if dollar_vol and dollar_vol < 10_000_000:
            flags.append(f"日均成交额低 (${dollar_vol/1e6:.1f}M)，大单冲击风险")

        inst_pct = data.get("institutional_ownership")
        if inst_pct and inst_pct < 0.05:
            flags.append("机构持仓极低 (<5%)，缺乏机构背书")

        return flags

    def to_markdown(self, data: Dict) -> str:
        """格式化为 Markdown"""
        lines = ["## 流动性分析", ""]

        short_pct = data.get("short_percent_float")
        if short_pct is not None:
            lines.append(f"- **做空比例**: {short_pct*100:.1f}% of float")
        days_cover = data.get("days_to_cover")
        if days_cover is not None:
            lines.append(f"- **Days to Cover**: {days_cover:.1f} 天")

        inst = data.get("institutional_ownership")
        insider = data.get("insider_ownership")
        if inst is not None:
            lines.append(f"- **机构持仓**: {inst*100:.1f}%")
        if insider is not None:
            lines.append(f"- **内部人持仓**: {insider*100:.1f}%")

        vol_3m = data.get("avg_volume_3m")
        if vol_3m:
            lines.append(f"- **3月均量**: {vol_3m/1e6:.1f}M 股/天")

        dollar_vol = data.get("daily_dollar_volume")
        if dollar_vol:
            lines.append(f"- **日均成交额**: ${dollar_vol/1e6:.1f}M")

        flags = data.get("risk_flags", [])
        if flags:
            lines.append("")
            lines.append("### ⚠️ 流动性风险")
            for f in flags:
                lines.append(f"- {f}")

        lines.append("")
        return "\n".join(lines)


# ========== CLI 测试 ==========

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python liquidity.py TICKER")
        sys.exit(1)

    la = LiquidityAnalyzer()
    data = la.analyze(sys.argv[1])
    print(json.dumps(data, ensure_ascii=False, indent=2))
