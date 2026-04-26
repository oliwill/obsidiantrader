"""
期权数据分析模块 — options-payoff

提供:
- 期权链摘要（最高成交量行权价）
- 隐含波动率 (IV)
- Put/Call Ratio
- 最大痛点 (Max Pain)
- 大单异动检测

用法:
    from data.options import OptionsAnalyzer
    oa = OptionsAnalyzer()
    data = oa.analyze("AAPL")
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

import yfinance as yf
import pandas as pd

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_options")


class OptionsAnalyzer:
    """期权数据分析器"""

    def __init__(self):
        pass

    def _yf_symbol(self, symbol: str) -> str:
        s = symbol.upper()
        if s.endswith(".US"):
            return s.replace(".US", "")
        return s

    def analyze(self, symbol: str) -> Dict:
        """
        获取股票期权数据摘要

        Returns:
            {
                "ticker": str,
                "next_expiry": str,
                "put_call_ratio": float,
                "max_pain": float,
                "highest_call_oi": {"strike": float, "oi": int},
                "highest_put_oi": {"strike": float, "oi": int},
                "atm_iv": float,
                "iv_skew": str,  # "steep" | "normal" | "flat"
                "unusual_activity": list,
            }
        """
        result = {"ticker": symbol}

        try:
            ticker = yf.Ticker(self._yf_symbol(symbol))

            # 获取期权链
            expiry_dates = ticker.options
            if not expiry_dates:
                result["error"] = "No options data available"
                return result

            # 用最近的到期日
            next_expiry = expiry_dates[0]
            result["next_expiry"] = next_expiry

            opt_chain = ticker.option_chain(next_expiry)
            calls = opt_chain.calls
            puts = opt_chain.puts

            # Put/Call Ratio (by OI)
            total_call_oi = calls["openInterest"].sum() if "openInterest" in calls.columns else 0
            total_put_oi = puts["openInterest"].sum() if "openInterest" in puts.columns else 0
            if total_call_oi > 0:
                result["put_call_ratio"] = round(total_put_oi / total_call_oi, 2)
            else:
                result["put_call_ratio"] = None

            # 最高 OI 行权价
            if not calls.empty and "openInterest" in calls.columns:
                top_call = calls.loc[calls["openInterest"].idxmax()]
                result["highest_call_oi"] = {
                    "strike": float(top_call["strike"]),
                    "oi": int(top_call["openInterest"]),
                }
            if not puts.empty and "openInterest" in puts.columns:
                top_put = puts.loc[puts["openInterest"].idxmax()]
                result["highest_put_oi"] = {
                    "strike": float(top_put["strike"]),
                    "oi": int(top_put["openInterest"]),
                }

            # ATM IV（取最接近当前价的行权价）
            current_price = ticker.info.get("regularMarketPrice") or ticker.info.get("currentPrice")
            if current_price and not calls.empty and "impliedVolatility" in calls.columns:
                atm_call = calls.iloc[(calls["strike"] - current_price).abs().argsort()[:1]]
                atm_iv = atm_call["impliedVolatility"].values[0]
                result["atm_iv"] = round(float(atm_iv), 3) if not pd.isna(atm_iv) else None

            # Max Pain 计算
            result["max_pain"] = self._calculate_max_pain(calls, puts)

            # IV Skew
            result["iv_skew"] = self._assess_iv_skew(calls, current_price)

            # 异常活动检测（高 volume/oi 比率）
            result["unusual_activity"] = self._detect_unusual(calls, puts)

        except Exception as e:
            logger.warning(f"Options analysis failed for {symbol}: {e}")
            result["error"] = str(e)

        return result

    def _calculate_max_pain(self, calls: pd.DataFrame, puts: pd.DataFrame) -> Optional[float]:
        """计算 Max Pain（卖方损失最小点）"""
        try:
            all_strikes = sorted(set(
                calls["strike"].tolist() + puts["strike"].tolist()
            ))

            pain_values = []
            for strike in all_strikes:
                # Call 卖方损失
                call_pain = 0
                for _, row in calls.iterrows():
                    if row["strike"] < strike:
                        call_pain += (strike - row["strike"]) * row.get("openInterest", 0)

                # Put 卖方损失
                put_pain = 0
                for _, row in puts.iterrows():
                    if row["strike"] > strike:
                        put_pain += (row["strike"] - strike) * row.get("openInterest", 0)

                pain_values.append((strike, call_pain + put_pain))

            if pain_values:
                pain_values.sort(key=lambda x: x[1])
                return float(pain_values[0][0])
            return None
        except Exception:
            return None

    def _assess_iv_skew(self, calls: pd.DataFrame, current_price: Optional[float]) -> str:
        """评估 IV skew"""
        try:
            if current_price is None or calls.empty or "impliedVolatility" not in calls.columns:
                return "unknown"

            # 取 ITM call（低 strike）和 OTM call（高 strike）的 IV 对比
            itm_calls = calls[calls["strike"] < current_price * 0.95]
            otm_calls = calls[calls["strike"] > current_price * 1.05]

            itm_iv = itm_calls["impliedVolatility"].mean() if not itm_calls.empty else None
            otm_iv = otm_calls["impliedVolatility"].mean() if not otm_calls.empty else None

            if itm_iv and otm_iv and not pd.isna(itm_iv) and not pd.isna(otm_iv):
                ratio = otm_iv / itm_iv
                if ratio > 1.3:
                    return "steep"
                elif ratio < 0.9:
                    return "flat"
                else:
                    return "normal"
            return "unknown"
        except Exception:
            return "unknown"

    def _detect_unusual(self, calls: pd.DataFrame, puts: pd.DataFrame) -> List[Dict]:
        """检测异常期权活动"""
        unusual = []
        try:
            for df, opt_type in [(calls, "CALL"), (puts, "PUT")]:
                if df.empty or "volume" not in df.columns or "openInterest" not in df.columns:
                    continue
                # volume / OI > 2 视为异常
                df = df.copy()
                df["vol_oi_ratio"] = df["volume"] / df["openInterest"].replace(0, 1)
                hot = df[df["vol_oi_ratio"] > 2].sort_values("volume", ascending=False).head(3)
                for _, row in hot.iterrows():
                    unusual.append({
                        "type": opt_type,
                        "strike": float(row["strike"]),
                        "volume": int(row["volume"]),
                        "oi": int(row["openInterest"]),
                        "vol_oi_ratio": round(float(row["vol_oi_ratio"]), 1),
                    })
        except Exception:
            pass
        return unusual

    def to_markdown(self, data: Dict) -> str:
        """格式化为 Markdown"""
        lines = ["## 期权市场", ""]

        expiry = data.get("next_expiry")
        if expiry:
            lines.append(f"**最近到期日**: {expiry}")

        pcr = data.get("put_call_ratio")
        if pcr is not None:
            sentiment = "看跌" if pcr > 1.2 else "看涨" if pcr < 0.8 else "中性"
            lines.append(f"**Put/Call Ratio**: {pcr} ({sentiment})")

        max_pain = data.get("max_pain")
        if max_pain:
            lines.append(f"**Max Pain**: ${max_pain:.2f}")

        atm_iv = data.get("atm_iv")
        if atm_iv:
            lines.append(f"**ATM IV**: {atm_iv*100:.1f}%")

        skew = data.get("iv_skew")
        if skew and skew != "unknown":
            lines.append(f"**IV Skew**: {skew}")

        top_call = data.get("highest_call_oi")
        top_put = data.get("highest_put_oi")
        if top_call:
            lines.append(f"- 最高 Call OI: Strike ${top_call['strike']:.2f} ({top_call['oi']:,} 张)")
        if top_put:
            lines.append(f"- 最高 Put OI: Strike ${top_put['strike']:.2f} ({top_put['oi']:,} 张)")

        unusual = data.get("unusual_activity", [])
        if unusual:
            lines.append("")
            lines.append("### 🔥 异常活动")
            for u in unusual:
                lines.append(f"- {u['type']} ${u['strike']:.2f} — Volume {u['volume']:,} / OI {u['oi']:,} (ratio {u['vol_oi_ratio']})")

        lines.append("")
        return "\n".join(lines)


# ========== CLI 测试 ==========

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python options.py TICKER")
        sys.exit(1)

    oa = OptionsAnalyzer()
    data = oa.analyze(sys.argv[1])
    print(json.dumps(data, ensure_ascii=False, indent=2))
