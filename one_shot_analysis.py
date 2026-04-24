#!/usr/bin/env python3
"""
一次性获取所有分析数据：Wiki历史 + 行情 + 基本面 + K线 + 技术指标 + 威科夫
用法: python one_shot_analysis.py 00100
"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TQDM_DISABLE'] = '1'

from dotenv import load_dotenv
load_dotenv()

from decimal import Decimal
import pandas as pd
import numpy as np

from data.manager import DataManager
from memory.manager import MemoryManager


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return str(obj)
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def compute_technicals(df):
    """从K线DataFrame计算所有技术指标"""
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)

    result = {}

    # Moving averages
    for w in [5, 10, 20, 50, 120, 200]:
        ma = close.rolling(w).mean()
        result[f'ma{w}'] = round(float(ma.iloc[-1]), 2) if not pd.isna(ma.iloc[-1]) else None

    # RSI 14
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss_s = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss_s
    rsi = 100 - (100 / (1 + rs))
    result['rsi_14'] = round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    macd_hist = macd_line - signal_line
    result['macd'] = round(float(macd_line.iloc[-1]), 2)
    result['macd_signal'] = round(float(signal_line.iloc[-1]), 2)
    result['macd_hist'] = round(float(macd_hist.iloc[-1]), 2)

    # Bollinger Bands
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    result['boll_upper'] = round(float((ma20 + 2 * std20).iloc[-1]), 2) if not pd.isna((ma20 + 2 * std20).iloc[-1]) else None
    result['boll_lower'] = round(float((ma20 - 2 * std20).iloc[-1]), 2) if not pd.isna((ma20 - 2 * std20).iloc[-1]) else None
    result['boll_mid'] = round(float(ma20.iloc[-1]), 2) if not pd.isna(ma20.iloc[-1]) else None

    # KDJ
    low9 = low.rolling(9).min()
    high9 = high.rolling(9).max()
    rsv = (close - low9) / (high9 - low9) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d
    result['kdj_k'] = round(float(k.iloc[-1]), 2) if not pd.isna(k.iloc[-1]) else None
    result['kdj_d'] = round(float(d.iloc[-1]), 2) if not pd.isna(d.iloc[-1]) else None
    result['kdj_j'] = round(float(j.iloc[-1]), 2) if not pd.isna(j.iloc[-1]) else None

    # Volume
    vol_5 = float(volume.tail(5).mean())
    vol_20 = float(volume.tail(20).mean())
    vol_all = float(volume.mean())
    result['vol_5d'] = round(vol_5, 0)
    result['vol_20d'] = round(vol_20, 0)
    result['vol_ratio'] = round(vol_5 / vol_20, 2) if vol_20 > 0 else None

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

    # Support/Resistance (20-day)
    recent20 = df.tail(20)
    result['support_20d'] = round(float(recent20['low'].astype(float).min()), 2)
    result['resistance_20d'] = round(float(recent20['high'].astype(float).max()), 2)

    # Recent 5 days
    result['recent_5d'] = []
    for i in range(-5, 0):
        result['recent_5d'].append({
            'date': str(close.index[i].date()) if hasattr(close.index[i], 'date') else str(close.index[i]),
            'close': round(float(close.iloc[i]), 2),
            'volume': int(volume.iloc[i])
        })

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python one_shot_analysis.py STOCK_CODE'}))
        sys.exit(1)

    code = sys.argv[1]
    dm = DataManager()
    mm = MemoryManager()

    output = {'code': code}

    # ===== Step 0: Wiki 历史 =====
    try:
        wiki = mm.get_stock_context(code)
        output['wiki_status'] = 'HAS_HISTORY' if wiki else 'NO_HISTORY'
        output['wiki_summary'] = wiki[:800] if wiki else None
    except Exception as e:
        output['wiki_status'] = 'ERROR'
        output['wiki_error'] = str(e)

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
    except Exception as e:
        output['stock_info_error'] = str(e)

    try:
        fund = dm.get_fundamentals(code)
        output['fundamentals'] = fund if fund else {}
    except Exception as e:
        output['fundamentals_error'] = str(e)

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
            if len(df) >= 100:
                try:
                    from analyzer.wyckoff import WyckoffAnalyzer
                    fund_data = fund if fund else {}
                    wa = WyckoffAnalyzer()
                    w = wa.analyze(df, fund_data)
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
                except Exception as e:
                    output['wyckoff_error'] = str(e)
        else:
            output['kline_rows'] = 0
    except Exception as e:
        output['technicals_error'] = str(e)

    print(json.dumps(output, ensure_ascii=False, indent=2, default=decimal_default))


if __name__ == '__main__':
    main()
