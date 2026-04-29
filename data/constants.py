"""
技术指标常量配置

集中管理所有技术指标的参数，避免 magic numbers 散落在代码中
"""
from typing import List


# ========== 移动平均线周期 ==========
MA_PERIODS: List[int] = [5, 10, 20, 50, 120, 200]

# ========== RSI 参数 ==========
RSI_PERIOD: int = 14

# ========== MACD 参数 ==========
MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9

# ========== 布林带参数 ==========
BB_PERIOD: int = 20
BB_STD_DEV: float = 2.0

# ========== KDJ 参数 ==========
KDJ_PERIOD: int = 9
KDJ_K_SMOOTH: int = 2  # ewm com 参数
KDJ_D_SMOOTH: int = 2  # ewm com 参数

# ========== 成交量参数 ==========
VOLUME_SHORT_PERIOD: int = 5   # 短期成交量周期
VOLUME_MID_PERIOD: int = 20    # 中期成交量周期

# ========== 支撑/阻力参数 ==========
SUPPORT_RESISTANCE_PERIOD: int = 20  # 用于计算 20 日支撑/阻力

# ========== 近期交易日数 ==========
RECENT_TRADING_DAYS: int = 5

# ========== Wyckoff 分析最小数据量 ==========
WYCKOFF_MIN_ROWS: int = 100
