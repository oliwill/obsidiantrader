"""
分析流水线模块 - 一次性获取所有分析数据

包含：Wiki历史 + 行情 + 基本面 + K线 + 技术指标 + 威科夫 + 财报 + 流动性 + 期权 + 相关性 + ETF

用法:
    from data.analysis_pipeline import generate_analysis
    result = generate_analysis("AAPL")
"""
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import pandas as pd
import numpy as np

from data.constants import (
    MA_PERIODS,
    RSI_PERIOD,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    BB_PERIOD,
    BB_STD_DEV,
    KDJ_PERIOD,
    KDJ_K_SMOOTH,
    KDJ_D_SMOOTH,
    VOLUME_SHORT_PERIOD,
    VOLUME_MID_PERIOD,
    SUPPORT_RESISTANCE_PERIOD,
    RECENT_TRADING_DAYS,
    WYCKOFF_MIN_ROWS,
)
from data.manager import DataManager
from memory.manager import MemoryManager


# 环境变量配置（避免重复加载）
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TQDM_DISABLE'] = '1'


def decimal_default(obj: Any) -> Any:
    """JSON 序列化辅助函数，处理 Decimal 和 Timestamp 类型"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def compute_technicals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    从K线DataFrame计算所有技术指标

    Args:
        df: 价格数据 DataFrame，必须包含 close, high, low, volume 列，
            且已按日期排序并设置为索引

    Returns:
        包含所有技术指标的字典
    """
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)

    result = {}

    # Moving averages
    for w in MA_PERIODS:
        ma = close.rolling(w).mean()
        result[f'ma{w}'] = round(float(ma.iloc[-1]), 2) if not pd.isna(ma.iloc[-1]) else None

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(RSI_PERIOD).mean()
    loss_s = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss_s
    rsi = 100 - (100 / (1 + rs))
    result['rsi_14'] = round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None

    # MACD
    ema_fast = close.ewm(span=MACD_FAST).mean()
    ema_slow = close.ewm(span=MACD_SLOW).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL).mean()
    macd_hist = macd_line - signal_line
    result['macd'] = round(float(macd_line.iloc[-1]), 2) if not pd.isna(macd_line.iloc[-1]) else None
    result['macd_signal'] = round(float(signal_line.iloc[-1]), 2) if not pd.isna(signal_line.iloc[-1]) else None
    result['macd_hist'] = round(float(macd_hist.iloc[-1]), 2) if not pd.isna(macd_hist.iloc[-1]) else None

    # Bollinger Bands
    ma_bb = close.rolling(BB_PERIOD).mean()
    std_bb = close.rolling(BB_PERIOD).std()
    result['boll_upper'] = round(float((ma_bb + BB_STD_DEV * std_bb).iloc[-1]), 2) if not pd.isna((ma_bb + BB_STD_DEV * std_bb).iloc[-1]) else None
    result['boll_lower'] = round(float((ma_bb - BB_STD_DEV * std_bb).iloc[-1]), 2) if not pd.isna((ma_bb - BB_STD_DEV * std_bb).iloc[-1]) else None
    result['boll_mid'] = round(float(ma_bb.iloc[-1]), 2) if not pd.isna(ma_bb.iloc[-1]) else None

    # KDJ
    low_kdj = low.rolling(KDJ_PERIOD).min()
    high_kdj = high.rolling(KDJ_PERIOD).max()
    rsv = (close - low_kdj) / (high_kdj - low_kdj) * 100
    k = rsv.ewm(com=KDJ_K_SMOOTH).mean()
    d = k.ewm(com=KDJ_D_SMOOTH).mean()
    j = 3 * k - 2 * d
    result['kdj_k'] = round(float(k.iloc[-1]), 2) if not pd.isna(k.iloc[-1]) else None
    result['kdj_d'] = round(float(d.iloc[-1]), 2) if not pd.isna(d.iloc[-1]) else None
    result['kdj_j'] = round(float(j.iloc[-1]), 2) if not pd.isna(j.iloc[-1]) else None

    # Volume
    vol_short = float(volume.tail(VOLUME_SHORT_PERIOD).mean())
    vol_mid = float(volume.tail(VOLUME_MID_PERIOD).mean())
    vol_all = float(volume.mean())
    result['vol_5d'] = round(vol_short, 0)
    result['vol_20d'] = round(vol_mid, 0)
    result['vol_ratio'] = round(vol_short / vol_mid, 2) if vol_mid > 0 else None

    # Price position
    period_high = float(high.max())
    period_low = float(low.min())
    latest = float(close.iloc[-1])
    result['period_high'] = round(period_high, 2)
    result['period_low'] = round(period_low, 2)
    result['pct_from_high'] = round((latest - period_high) / period_high * 100, 2)
    result['pct_from_low'] = round((latest - period_low) / period_low * 100, 2)

    # Trend
    ma5 = result.get('ma5')
    ma20_val = result.get('ma20')
    ma50_val = result.get('ma50')
    if ma5 and ma20_val:
        result['trend_short'] = 'BULLISH' if ma5 > ma20_val else 'BEARISH'
    if ma20_val and ma50_val:
        result['trend_mid'] = 'BULLISH' if ma20_val > ma50_val else 'BEARISH'

    # Support/Resistance
    recent_period = df.tail(SUPPORT_RESISTANCE_PERIOD)
    result['support_20d'] = round(float(recent_period['low'].astype(float).min()), 2)
    result['resistance_20d'] = round(float(recent_period['high'].astype(float).max()), 2)

    # Recent trading days
    result['recent_5d'] = []
    for i in range(-RECENT_TRADING_DAYS, 0):
        result['recent_5d'].append({
            'date': str(close.index[i].date()) if hasattr(close.index[i], 'date') else str(close.index[i]),
            'close': round(float(close.iloc[i]), 2),
            'volume': int(volume.iloc[i])
        })

    return result


def generate_analysis(code: str) -> Dict[str, Any]:
    """
    执行完整的股票分析流水线

    Args:
        code: 股票代码（如 "AAPL", "00700.HK"）

    Returns:
        包含所有分析结果的字典，结构如下：
        {
            'code': str,
            'wiki_status': str,
            'wiki_summary': str | None,
            'stock_info': dict,
            'fundamentals': dict,
            'earnings': dict,
            'kline_rows': int,
            'technicals': dict,
            'wyckoff': dict,
            'liquidity': dict,
            'options': dict,
            'web_search': dict,
            'peers': list,
            'etf': dict | None,
            # 各模块可能包含的 *_error 字段
        }
    """
    dm = DataManager()
    mm = MemoryManager()

    output: Dict[str, Any] = {'code': code, '_generated_at': datetime.now().isoformat()}

    fund = None  # 用于后续 Wyckoff 分析

    # ===== Step 0: Wiki 历史 =====
    try:
        wiki = mm.get_stock_context(code)
        output['wiki_status'] = 'HAS_HISTORY' if wiki else 'NO_HISTORY'
        output['wiki_summary'] = wiki[:800] if wiki else None
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['wiki_status'] = 'ERROR'
        output['wiki_error'] = str(e)
    except Exception as e:
        # 记录但不中断其他步骤
        output['wiki_status'] = 'ERROR'
        output['wiki_error'] = f"Unexpected: {str(e)}"

    # ===== Step 1: 行情 + 基本面 =====
    try:
        info = dm.get_stock_info(code)
        if info:
            output['stock_info'] = {
                'code': info.code,
                'name': info.name,
                'market': info.market,
                'price': float(info.price) if info.price else None,
                'change_pct': float(info.change_pct) if info.change_pct else None,
                'currency': info.currency,
                'sector': info.sector,
                'industry': info.industry,
            }
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['stock_info_error'] = str(e)
    except Exception as e:
        output['stock_info_error'] = f"Unexpected: {str(e)}"

    try:
        fund = dm.get_fundamentals(code)
        output['fundamentals'] = fund if fund else {}
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['fundamentals_error'] = str(e)
    except Exception as e:
        output['fundamentals_error'] = f"Unexpected: {str(e)}"

    # ===== Step 1.5: 财报预期 (earnings-preview) =====
    try:
        from data.earnings import EarningsCalendar
        ec = EarningsCalendar()
        output['earnings'] = ec.get_earnings_info(code)
    except ImportError:
        output['earnings_error'] = 'EarningsCalendar module not available'
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['earnings_error'] = str(e)
    except Exception as e:
        output['earnings_error'] = f"Unexpected: {str(e)}"

    # ===== Step 1b: K线 + 技术指标 =====
    try:
        df = dm.get_historical_data(code, period='1y')
        if df is not None and len(df) > 0:
            df = df.sort_values('date').reset_index(drop=True)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            output['kline_rows'] = len(df)
            output['technicals'] = compute_technicals(df)

            # Wyckoff analysis (if enough data)
            if len(df) >= WYCKOFF_MIN_ROWS:
                try:
                    from analyzer.wyckoff import WyckoffAnalyzer
                    fund_data = fund if fund else {}
                    wa = WyckoffAnalyzer()
                    # reset index so 'date' is accessible as a column
                    w = wa.analyze(df.reset_index(), fund_data)
                    struct = w.details.get('structure')
                    if struct:
                        output['wyckoff'] = {
                            'phase': struct.market_phase.value,
                            'support': round(float(struct.support_level), 2),
                            'resistance': round(float(struct.resistance_level), 2),
                            'confidence': round(struct.confidence * 100),
                        }
                    output['wyckoff_score'] = w.score
                    output['wyckoff_signals'] = w.signals[:5] if w.signals else []
                    output['wyckoff_risks'] = w.risks[:5] if w.risks else []
                except (ImportError, AttributeError, TypeError, ValueError) as e:
                    output['wyckoff_error'] = str(e)
                except Exception as e:
                    output['wyckoff_error'] = f"Unexpected: {str(e)}"
        else:
            output['kline_rows'] = 0
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['technicals_error'] = str(e)
    except Exception as e:
        output['technicals_error'] = f"Unexpected: {str(e)}"

    # ===== Step 1c: 流动性分析 (stock-liquidity) =====
    try:
        from data.liquidity import LiquidityAnalyzer
        la = LiquidityAnalyzer()
        output['liquidity'] = la.analyze(code)
    except ImportError:
        output['liquidity_error'] = 'LiquidityAnalyzer module not available'
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['liquidity_error'] = str(e)
    except Exception as e:
        output['liquidity_error'] = f"Unexpected: {str(e)}"

    # ===== Step 1d: 期权数据 (options-payoff) =====
    try:
        from data.options import OptionsAnalyzer
        oa = OptionsAnalyzer()
        output['options'] = oa.analyze(code)
    except ImportError:
        output['options_error'] = 'OptionsAnalyzer module not available'
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['options_error'] = str(e)
    except Exception as e:
        output['options_error'] = f"Unexpected: {str(e)}"

    # ===== Step 2: 网络搜索（新闻 + 社交 + 研报 + Reddit + Polymarket）=====
    try:
        from data.search import StockSearchEngine
        se = StockSearchEngine()
        search_results = se.search_all(code)
        # 增加 Reddit 和 Polymarket
        try:
            reddit_results = se.search_reddit(code)
            search_results['reddit'] = [r.to_dict() for r in reddit_results]
        except Exception:
            pass  # Reddit 搜索失败不影响其他结果
        try:
            poly_results = se.search_polymarket(code)
            search_results['polymarket'] = [r.to_dict() for r in poly_results]
        except Exception:
            pass  # Polymarket 搜索失败不影响其他结果
        output['web_search'] = search_results
    except ImportError:
        output['web_search_error'] = 'StockSearchEngine module not available'
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['web_search_error'] = str(e)
    except Exception as e:
        output['web_search_error'] = f"Unexpected: {str(e)}"

    # ===== Step 3: 相关性分析 (stock-correlation) =====
    try:
        from data.correlation import CorrelationAnalyzer
        ca = CorrelationAnalyzer()
        output['peers'] = ca.find_peers(code, top_n=5)
    except ImportError:
        output['peers_error'] = 'CorrelationAnalyzer module not available'
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['peers_error'] = str(e)
    except Exception as e:
        output['peers_error'] = f"Unexpected: {str(e)}"

    # ===== Step 4: ETF 检测 (etf-premium) =====
    try:
        from data.etf import ETFAnalyzer
        ea = ETFAnalyzer()
        etf_data = ea.analyze(code)
        if etf_data.get('is_etf'):
            output['etf'] = etf_data
    except ImportError:
        output['etf_error'] = 'ETFAnalyzer module not available'
    except (FileNotFoundError, KeyError, ValueError, OSError) as e:
        output['etf_error'] = str(e)
    except Exception as e:
        output['etf_error'] = f"Unexpected: {str(e)}"

    return output
