"""
数据管理器 - 统一数据接入层
数据源: 长桥API (美股/港股) + Yahoo Finance (备用/基本面)
"""
import os
import sys
import io
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from contextlib import contextmanager

import yfinance as yf
from loguru import logger


@contextmanager
def suppress_stdout():
    """Context manager to suppress stdout (for Longbridge SDK debug output)"""
    old_stdout = sys.stdout
    old_stdout_fd = None
    saved_stdout_fd = None

    try:
        if hasattr(sys.stdout, 'fileno'):
            old_stdout_fd = sys.stdout.fileno()
            # Save the original file descriptor by duplicating it
            import os as os_module
            import fcntl
            saved_stdout_fd = os_module.dup(old_stdout_fd)
            # Open dev/null and redirect stdout to it
            devnull = os_module.open(os_module.devnull, os_module.O_WRONLY)
            os_module.dup2(devnull, old_stdout_fd)
            os_module.close(devnull)
        # Also redirect Python's sys.stdout
        sys.stdout = io.StringIO()
        yield
    finally:
        # Restore Python's sys.stdout first
        sys.stdout = old_stdout
        # Then restore the file descriptor
        if saved_stdout_fd is not None and old_stdout_fd is not None:
            import os as os_module
            # Flush before restoring
            try:
                sys.stdout.flush()
            except:
                pass
            # Restore the original file descriptor
            os_module.dup2(saved_stdout_fd, old_stdout_fd)
            os_module.close(saved_stdout_fd)

# 长桥SDK - lazy import to avoid debug output during module load
LONGBRIDGE_AVAILABLE = False
Config = None
QuoteContext = None
AdjustType = None
Period = None

def _import_longbridge():
    """Lazy import Longbridge SDK with stdout suppression"""
    global LONGBRIDGE_AVAILABLE, Config, QuoteContext, AdjustType, Period
    if Config is not None:  # Already imported
        return

    try:
        with suppress_stdout():
            from longbridge.openapi import Config as _Config, QuoteContext as _QuoteContext, AdjustType as _AdjustType, Period as _Period
        Config = _Config
        QuoteContext = _QuoteContext
        AdjustType = _AdjustType
        Period = _Period
        LONGBRIDGE_AVAILABLE = True
    except ImportError:
        LONGBRIDGE_AVAILABLE = False
        logger.warning("longbridge SDK not installed, falling back to Yahoo Finance")


@dataclass
class StockInfo:
    """股票信息"""
    code: str
    name: str
    market: str  # 'US' | 'HK'
    price: float = 0.0
    change_pct: float = 0.0
    currency: str = "USD"
    sector: str = ""
    industry: str = ""


class LongBridgeClient:
    """长桥API客户端"""

    def __init__(self):
        self.quote_ctx = None
        self._init_client()

    def _init_client(self):
        # Lazy import to suppress debug output
        _import_longbridge()
        if not LONGBRIDGE_AVAILABLE:
            return
        try:
            app_key = os.getenv("LONGBRIDGE_APP_KEY")
            app_secret = os.getenv("LONGBRIDGE_APP_SECRET")
            access_token = os.getenv("LONGBRIDGE_ACCESS_TOKEN")

            if all([app_key, app_secret, access_token]):
                # Suppress stdout during Longbridge SDK initialization
                # to prevent debug tables from corrupting JSON output
                with suppress_stdout():
                    config = Config.from_apikey(app_key, app_secret, access_token)
                    self.quote_ctx = QuoteContext(config)
                logger.info("Longbridge API initialized")
            else:
                logger.warning("Longbridge credentials incomplete")
        except Exception as e:
            logger.error(f"Longbridge init failed: {e}")
            self.quote_ctx = None

    def is_available(self) -> bool:
        return self.quote_ctx is not None

    # ---------- 行情 ----------

    def get_quote(self, symbol: str) -> Optional[Dict]:
        """获取实时行情"""
        if not self.is_available():
            return None
        try:
            quotes = self.quote_ctx.quote([symbol])
            if not quotes:
                return None
            q = quotes[0]
            change_pct = 0.0
            if q.prev_close and q.prev_close > 0:
                change_pct = (q.last_done - q.prev_close) / q.prev_close * 100
            return {
                "symbol": q.symbol,
                "price": q.last_done,
                "open": q.open,
                "high": q.high,
                "low": q.low,
                "prev_close": q.prev_close,
                "volume": q.volume,
                "turnover": q.turnover,
                "change_pct": round(change_pct, 2),
                "timestamp": str(q.timestamp),
            }
        except Exception as e:
            logger.error(f"Longbridge quote failed for {symbol}: {e}")
            return None

    # ---------- 历史K线 ----------

    def get_history(
        self, symbol: str, days: int = 365
    ) -> Optional[pd.DataFrame]:
        """获取历史K线（前复权）"""
        if not self.is_available():
            return None
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            candles = self.quote_ctx.history_candlesticks_by_date(
                symbol=symbol,
                period=Period.Day,
                adjust_type=AdjustType.ForwardAdjust,
                start=start,
                end=end,
            )
            if not candles:
                return None
            df = pd.DataFrame([
                {
                    "date": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in candles
            ])
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"Longbridge history failed for {symbol}: {e}")
            return None

    # ---------- 静态信息 ----------

    def get_static_info(self, symbol: str) -> Optional[Dict]:
        """获取股票静态信息（名称、行业等）"""
        if not self.is_available():
            return None
        try:
            infos = self.quote_ctx.static_info([symbol])
            if not infos:
                return None
            s = infos[0]
            return {
                "symbol": s.symbol,
                "name_cn": s.name_cn,
                "name_en": s.name_en,
                "exchange": str(s.exchange),
                "currency": s.currency,
                "lot_size": s.lot_size,
                "total_shares": s.total_shares,
                "circulating_shares": s.circulating_shares,
                "eps": s.eps,
                "bps": s.bps,
                "dividend_yield": s.dividend_yield,
            }
        except Exception as e:
            logger.error(f"Longbridge static_info failed for {symbol}: {e}")
            return None


class DataManager:
    """数据管理器 - 长桥API优先，Yahoo Finance备用"""

    def __init__(self):
        self.longbridge = LongBridgeClient()
        logger.info("DataManager initialized")

    # ---------- 符号处理 ----------

    @staticmethod
    def normalize_symbol(code: str) -> str:
        """
        标准化股票代码
        长桥格式: 美股 AAPL.US  港股 00700.HK / 02600.HK  A股 SH603906 / SZ000001
        输入兼容: 603906 / SH603906 / sh603906 / 000001 / SZ000001
        """
        code = code.strip().upper()
        # 已经是长桥格式
        if code.endswith(".US") or code.endswith(".HK"):
            return code
        # A股: SH/SZ 前缀（长桥格式）
        if code.startswith("SH") or code.startswith("SZ"):
            return code
        # 纯数字 → 判断市场
        if code.isdigit():
            num = int(code)
            # 港股5位: 00001-99999
            if 1 <= num <= 99999 and len(code) == 5:
                return f"{code}.HK"
            # A股: 沪市6开头, 深市0/3开头
            if len(code) == 6:
                if code.startswith("6"):
                    return f"SH{code}"
                else:
                    return f"SZ{code}"
            # 其他数字当港股处理
            return f"{code}.HK"
        # 纯字母 → 美股
        if code.isalpha():
            return f"{code}.US"
        return code

    @staticmethod
    def detect_market(symbol: str) -> str:
        if symbol.endswith(".HK"):
            return "HK"
        if symbol.startswith("SH") or symbol.startswith("SZ"):
            return "CN"
        return "US"

    # ---------- 对外接口 ----------

    def search_stocks(self, query: str, limit: int = 10) -> list:
        """搜索股票"""
        results = []

        # 尝试把输入当作代码直接查
        symbol = self.normalize_symbol(query)

        # 长桥: 获取静态信息
        if self.longbridge.is_available():
            static = self.longbridge.get_static_info(symbol)
            if static:
                quote = self.longbridge.get_quote(symbol)
                results.append({
                    "code": symbol,
                    "name": static.get("name_cn") or static.get("name_en") or symbol,
                    "market": "港股" if self.detect_market(symbol) == "HK" else "美股",
                    "price": quote["price"] if quote else 0,
                })

        # Yahoo Finance 备用（美股用不带 .US 的代码）
        if not results:
            try:
                import yfinance as yf
                # YF 美股不需要 .US 后缀
                yf_symbol = symbol.replace(".US", "")
                ticker = yf.Ticker(yf_symbol)
                info = ticker.info
                name = info.get("shortName") or info.get("longName") or symbol
                if name and name != symbol:
                    results.append({
                        "code": symbol,
                        "name": name,
                        "market": "港股" if self.detect_market(symbol) == "HK" else "美股",
                        "price": info.get("regularMarketPrice", 0),
                    })
            except Exception:
                pass

        return results[:limit]

    def get_stock_info(self, code: str) -> StockInfo:
        """获取股票详情"""
        symbol = self.normalize_symbol(code)
        market = self.detect_market(symbol)

        # 长桥
        if self.longbridge.is_available():
            quote = self.longbridge.get_quote(symbol)
            static = self.longbridge.get_static_info(symbol)
            if quote:
                return StockInfo(
                    code=symbol,
                    name=static.get("name_cn", "") if static else symbol,
                    market=market,
                    price=quote["price"],
                    change_pct=quote["change_pct"],
                    currency={"HK": "HKD", "CN": "CNY"}.get(market, "USD"),
                )

        # 备用 Yahoo Finance
        return self._get_yf_stock_info(symbol)

    def get_historical_data(self, code: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """获取历史行情"""
        symbol = self.normalize_symbol(code)
        days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "3y": 1095}
        days = days_map.get(period, 365)

        # 长桥
        if self.longbridge.is_available():
            df = self.longbridge.get_history(symbol, days)
            if df is not None and not df.empty:
                return df

        # 备用 Yahoo Finance
        return self._get_yf_history(symbol, period)

    def get_fundamentals(self, code: str) -> Dict:
        """获取基本面数据：长桥 static_info 优先算 PE/PB，YF 补充其余字段"""
        symbol = self.normalize_symbol(code)
        result = {}

        # ===== 1. 长桥 static_info：拿 EPS/BPS/股本，自己算 PE/PB =====
        lb_data = {}
        if self.longbridge.is_available():
            static = self.longbridge.get_static_info(symbol)
            quote = self.longbridge.get_quote(symbol)
            if static:
                lb_data["eps"] = static.get("eps")
                lb_data["bps"] = static.get("bps")
                lb_data["total_shares"] = static.get("total_shares")
                lb_data["circulating_shares"] = static.get("circulating_shares")
                lb_data["dividend_yield"] = static.get("dividend_yield")
                lb_data["lot_size"] = static.get("lot_size")
                lb_data["name_cn"] = static.get("name_cn")
                lb_data["name_en"] = static.get("name_en")

                # 用长桥数据算 PE/PB（比 YF 更可靠，覆盖港股新股）
                price = None
                if quote and quote.get("price"):
                    price = float(quote["price"])
                eps = lb_data.get("eps")
                bps = lb_data.get("bps")
                if price and eps and float(eps) != 0:
                    result["pe_ttm"] = round(price / float(eps), 2)
                if price and bps and float(bps) != 0:
                    result["pb"] = round(price / float(bps), 2)
                if lb_data.get("total_shares") and price:
                    result["market_cap"] = round(float(lb_data["total_shares"]) * price, 2)
                if lb_data.get("dividend_yield") is not None:
                    result["dividend_yield"] = lb_data["dividend_yield"]
                if lb_data.get("total_shares"):
                    result["total_shares"] = lb_data["total_shares"]
                if lb_data.get("circulating_shares"):
                    result["circulating_shares"] = lb_data["circulating_shares"]

        # ===== 2. Yahoo Finance：补充毛利率/营收增长/行业/业务描述等 =====
        try:
            yf_symbol = self._yf_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            # YF 有值且长桥没算出来的字段，用 YF 补
            yf_fields = {
                "pe_ttm": "trailingPE",
                "pe_forward": "forwardPE",
                "pb": "priceToBook",
                "ps": "priceToSalesTrailing12Months",
                "ev_ebitda": "enterpriseToEbitda",
                "roe": "returnOnEquity",
                "roa": "returnOnAssets",
                "gross_margin": "grossMargins",
                "operating_margin": "operatingMargins",
                "profit_margin": "profitMargins",
                "revenue_growth": "revenueGrowth",
                "earnings_growth": "earningsGrowth",
                "current_ratio": "currentRatio",
                "debt_equity": "debtToEquity",
                "total_cash": "totalCash",
                "total_debt": "totalDebt",
                "free_cashflow": "freeCashflow",
                "market_cap": "marketCap",
                "sector": "sector",
                "industry": "industry",
                "employees": "fullTimeEmployees",
                "business_summary": "longBusinessSummary",
            }
            for key, yf_key in yf_fields.items():
                val = info.get(yf_key)
                # 长桥已算出的 PE/PB 不覆盖，其余字段 YF 有值就补
                if key in result:
                    continue
                if val is not None:
                    result[key] = val
        except Exception as e:
            logger.warning(f"YF fundamentals fallback failed for {symbol}: {e}")

        return result

    # ---------- Yahoo Finance 备用 ----------

    @staticmethod
    def _yf_symbol(symbol: str) -> str:
        """长桥代码转 YF 代码"""
        # 美股: AAPL.US → AAPL
        if symbol.endswith(".US"):
            return symbol.replace(".US", "")
        # 港股: 00700.HK → 00700.HK (YF 同格式)
        if symbol.endswith(".HK"):
            return symbol
        # A股: SH603906 → 603906.SS, SZ000001 → 000001.SZ
        if symbol.startswith("SH"):
            return symbol[2:] + ".SS"
        if symbol.startswith("SZ"):
            return symbol[2:] + ".SZ"
        return symbol

    def _get_yf_stock_info(self, symbol: str) -> StockInfo:
        try:
            ticker = yf.Ticker(self._yf_symbol(symbol))
            info = ticker.info
            market = self.detect_market(symbol)
            return StockInfo(
                code=symbol,
                name=info.get("shortName", symbol),
                market=market,
                price=info.get("regularMarketPrice", 0),
                change_pct=info.get("regularMarketChangePercent", 0),
                currency={"HK": "HKD", "CN": "CNY"}.get(market, "USD"),
                sector=info.get("sector", ""),
                industry=info.get("industry", ""),
            )
        except Exception as e:
            logger.error(f"YF stock info failed: {e}")
            return StockInfo(code=symbol, name="Unknown", market="US")

    def _get_yf_history(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        try:
            ticker = yf.Ticker(self._yf_symbol(symbol))
            df = ticker.history(period=period)
            df = df.reset_index()
            df.columns = [c.lower().replace(" ", "_").replace(".", "_") for c in df.columns]
            return df
        except Exception as e:
            logger.error(f"YF history failed: {e}")
            return None
