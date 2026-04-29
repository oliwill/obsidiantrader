"""
Wyckoff 分析配置常量

集中管理 Wyckoff 分析中的所有阈值和参数
"""
from dataclasses import dataclass


@dataclass
class WyckoffConfig:
    """Wyckoff 分析配置"""

    # ========== 成交量阈值 ==========
    # 吸筹阶段最小成交量比例（相对于近期平均）
    volume_accumulation_min: float = 0.15
    # 派发阶段最小成交量比例
    volume_distribution_min: float = 0.25
    # 突破时成交量放大倍数
    volume_breakout_multiplier: float = 1.5
    # Spring 成交量比例（相对于近期平均）
    volume_spring_ratio: float = 0.8
    # 二次测试成交量比例
    volume_secondary_test_ratio: float = 0.8
    # 成交量激放检测阈值
    volume_spike_threshold: float = 1.3

    # ========== 价格阈值 ==========
    # 价格接近支撑/阻力的阈值（百分比）
    price_proximity_threshold: float = 0.03  # 3%
    # 突破确认阈值
    breakout_threshold: float = 1.02  # 2%
    # 支撑测试下界
    support_test_lower: float = 0.98
    # 支撑测试上界
    support_test_upper: float = 0.99

    # ========== 趋势强度 ==========
    # 趋势强度乘数
    trend_strength_multiplier: float = 1.2
    # AR/BR 超买阈值
    arbr_overbought: float = 150.0
    # AR/BR 超卖阈值
    arbr_oversold: float = 50.0

    # ========== 检测周期 ==========
    # 检测事件时的回溯周期
    lookback_period: int = 20
    # 最小趋势持续天数
    min_trend_days: int = 5


# 全局默认配置
DEFAULT_CONFIG = WyckoffConfig()
