#!/usr/bin/env python3
"""
交易网格生成器

基于技术面和基本面数据，生成操作价位网格：
1. 多时间框架支撑/阻力
2. Fibonacci 回撤位
3. ATR-based 止损
4. 风险/回报比计算
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class PriceLevel:
    """价格档位"""
    level_type: str      # 档位类型
    price: float         # 价格
    trigger: str         # 触发条件
    position_pct: int    # 建议仓位 (%)
    risk_reward: Optional[float] = None  # 风险回报比
    rationale: str = ""  # 理由


class TradingGridGenerator:
    """交易网格生成器"""

    # Fibonacci 回撤比例
    FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]

    def generate(
        self,
        stock_info: Dict[str, Any],
        technicals: Dict[str, Any],
        fundamentals: Dict[str, Any],
        wyckoff: Dict[str, Any]
    ) -> List[PriceLevel]:
        """
        生成交易网格

        Args:
            stock_info: 股票基本信息 (price, name, etc.)
            technicals: 技术指标 (support, resistance, ma, etc.)
            fundamentals: 基本面数据
            wyckoff: 威科夫分析结果

        Returns:
            价格档位列表（从低到高排序）
        """
        current_price = stock_info.get('price', 0)
        target_mean = fundamentals.get('target_mean_price', 0)

        # 获取支撑阻力位
        support_20d = technicals.get('support_20d', 0)
        resistance_20d = technicals.get('resistance_20d', 0)
        period_low = technicals.get('period_low', 0)
        period_high = technicals.get('period_high', 0)

        # Wyckoff 支撑/阻力
        wyckoff_support = wyckoff.get('support', 0)
        wyckoff_resistance = wyckoff.get('resistance', 0)

        # 计算 Fibonacci 回撤位
        fib_levels = self._calculate_fibonacci_levels(period_low, period_high)

        # ATR-based 止损
        atr = technicals.get('atr', current_price * 0.05)  # 默认 5%
        atr_stop = current_price - 2.5 * atr if atr > 0 else current_price * 0.9

        levels = []

        # === 深度价值区（最低档）===
        deep_value_price = min(
            fib_levels.get('0.786', period_low * 0.95),
            wyckoff_support * 0.95 if wyckoff_support > 0 else period_low * 0.95,
            atr_stop
        )
        if deep_value_price > 0 and deep_value_price < current_price * 0.85:
            rr = self._calculate_rr(deep_value_price, current_price, target_mean)
            levels.append(PriceLevel(
                level_type="🔴 深度价值",
                price=deep_value_price,
                trigger=f"跌破 {wyckoff_support:.2f} 或触及 78.6% 回撤",
                position_pct=30,
                risk_reward=rr,
                rationale=f"极端低估区，2.5x ATR 止损外，R/R {rr:.1f}" if rr else "极端低估区"
            ))

        # === 核心建仓区 ===
        core_entry = max(
            fib_levels.get('0.618', period_low * 1.05),
            wyckoff_support if wyckoff_support > 0 else support_20d
        )
        if core_entry > 0 and core_entry < current_price * 0.95:
            rr = self._calculate_rr(core_entry, current_price, target_mean)
            levels.append(PriceLevel(
                level_type="🟡 核心建仓",
                price=core_entry,
                trigger="回踩 Wyckoff 支撑或 61.8% 回撤",
                position_pct=40,
                risk_reward=rr,
                rationale=f"主要建仓区，Wyckoff 支撑确认，R/R {rr:.1f}" if rr else "主要建仓区"
            ))

        # === 第一买点（接近当前价）===
        first_buy = max(
            fib_levels.get('0.5', current_price * 0.95),
            support_20d if support_20d > 0 else current_price * 0.95
        )
        if first_buy > 0 and first_buy < current_price * 0.99:
            rr = self._calculate_rr(first_buy, current_price, target_mean)
            levels.append(PriceLevel(
                level_type="🟢 第一买点",
                price=first_buy,
                trigger="回踩 20日支撑或 50% 回撤",
                position_pct=20,
                risk_reward=rr,
                rationale=f"试探性建仓，20日支撑附近，R/R {rr:.1f}" if rr else "试探性建仓"
            ))

        # === 当前价 ===
        levels.append(PriceLevel(
            level_type="⚪ 当前价",
            price=current_price,
            trigger="-",
            position_pct=0,
            risk_reward=None,
            rationale="观望或持有"
        ))

        # === 突破加仓 ===
        breakout = min(
            fib_levels.get('0.382', current_price * 1.05),
            resistance_20d if resistance_20d > current_price else current_price * 1.05
        )
        if breakout > current_price * 1.01:
            rr = self._calculate_rr(current_price, breakout, target_mean)
            levels.append(PriceLevel(
                level_type="🟢 突破加仓",
                price=breakout,
                trigger=f"突破 20日阻力 {resistance_20d:.2f}",
                position_pct=15,
                risk_reward=rr,
                rationale=f"趋势确认加仓，R/R {rr:.1f}" if rr else "趋势确认加仓"
            ))

        # === 目标价 ===
        if target_mean > current_price * 1.05:
            levels.append(PriceLevel(
                level_type="🎯 目标价",
                price=target_mean,
                trigger="达到分析师共识目标",
                position_pct=-50,  # 减仓
                risk_reward=None,
                rationale=f"分析师均值目标，考虑减仓锁定利润"
            ))

        # 按价格排序
        levels.sort(key=lambda x: x.price)

        return levels

    def _calculate_fibonacci_levels(self, low: float, high: float) -> Dict[float, float]:
        """计算 Fibonacci 回撤位"""
        if low <= 0 or high <= low:
            return {}

        range_size = high - low
        levels = {}
        for ratio in self.FIB_LEVELS:
            levels[ratio] = high - range_size * ratio
        levels[0.0] = high
        levels[1.0] = low

        return levels

    def _calculate_rr(
        self,
        entry: float,
        stop: float,
        target: float
    ) -> Optional[float]:
        """计算风险回报比"""
        if entry <= 0 or target <= 0:
            return None

        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk <= 0:
            return None

        return round(reward / risk, 1)

    def format_grid(self, levels: List[PriceLevel]) -> str:
        """格式化为 Markdown 表格"""
        if not levels:
            return "暂无交易网格数据"

        lines = [
            "| 档位 | 价格 | 触发条件 | 仓位 | R/R | 理由 |",
            "|------|------|----------|------|-----|------|",
        ]

        for level in levels:
            rr_str = f"{level.risk_reward:.1f}" if level.risk_reward else "-"
            pos_str = f"{level.position_pct}%" if level.position_pct >= 0 else f"减仓{abs(level.position_pct)}%"
            if level.position_pct == 0:
                pos_str = "-"

            lines.append(
                f"| {level.level_type} | ${level.price:.2f} | {level.trigger} | {pos_str} | {rr_str} | {level.rationale} |"
            )

        return "\n".join(lines)
