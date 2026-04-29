#!/usr/bin/env python3
"""
统一分析报告生成器

整合所有数据模块，生成格式化的 Markdown 分析报告
"""
from typing import Dict, Any
from datetime import datetime


class ReportGenerator:
    """分析报告生成器"""

    # Emoji 映射
    EMOJI = {
        "bullish": "📈",
        "bearish": "📉",
        "neutral": "🟡",
        "positive": "🟢",
        "negative": "🔴",
        "warning": "⚠️",
        "rocket": "🚀",
        "chart": "📊",
        "target": "🎯",
        "fire": "🔥",
    }

    @classmethod
    def generate(cls, stock_code: str, market_data: Dict[str, Any]) -> str:
        """
        生成完整的分析报告

        Args:
            stock_code: 股票代码
            market_data: 来自 analysis_pipeline 的完整数据

        Returns:
            格式化的 Markdown 报告
        """
        # 提取数据
        stock_info = market_data.get('stock_info', {})
        fundamentals = market_data.get('fundamentals', {})
        technicals = market_data.get('technicals', {})
        wyckoff = market_data.get('wyckoff', {})
        liquidity = market_data.get('liquidity', {})
        options = market_data.get('options', {})
        earnings = market_data.get('earnings', {})
        web_search = market_data.get('web_search', {})

        # 生成各章节
        sections = []

        sections.append(cls._section_1_overview(stock_code, stock_info, technicals, fundamentals, liquidity, options, wyckoff, earnings))
        sections.append(cls._section_2_technical(technicals, wyckoff))
        sections.append(cls._section_3_fundamental(fundamentals))
        sections.append(cls._section_4_market_structure(liquidity, options))
        sections.append(cls._section_5_catalysts(fundamentals, earnings, web_search))
        sections.append(cls._section_6_trading_plan(stock_info, technicals, fundamentals, wyckoff))

        return "\n\n".join(sections)

    @classmethod
    def _section_1_overview(cls, stock_code: str, stock_info: Dict, technicals: Dict, fundamentals: Dict, liquidity: Dict, options: Dict, wyckoff: Dict, earnings: Dict) -> str:
        """第一部分：核心观点"""
        name = stock_info.get('name', 'Unknown')
        sector = stock_info.get('sector', '-')
        industry = stock_info.get('industry', '-')
        price = stock_info.get('price', 0)
        change_pct = stock_info.get('change_pct', 0)

        # 评分
        wyckoff_score = fundamentals.get('wyckoff_score', 50)  # 默认中性
        score_emoji = cls._get_score_emoji(wyckoff_score)

        # 估值信号
        target_mean = fundamentals.get('target_mean_price', 0)
        potential = (target_mean / price - 1) * 100 if price > 0 and target_mean > 0 else 0

        # 趋势信号
        trend_short = technicals.get('trend_short', 'NEUTRAL')
        rsi = technicals.get('rsi_14', 50)

        return f"""## 一、核心观点

**综合评分**：{wyckoff_score}/100 {score_emoji}

**股票信息**：{name} ({stock_code}) | {sector} / {industry}
**当前价格**：${price:,.2f} ({change_pct:+.2f}%)

### {cls.EMOJI['chart']} 快速评估

| 维度 | 数值 | 评级 |
|------|------|------|
| 估值 | PE(Forward) {fundamentals.get('pe_forward', 0):.2f} | {cls._get_valuation_signal(potential)} |
| 潜在涨幅 | {potential:+.1f}% | {cls._get_potential_emoji(potential)} |
| 趋势 | {trend_short} | {cls._get_trend_emoji(trend_short)} |
| RSI | {rsi:.1f} | {cls._get_rsi_signal(rsi)} |
| 做空比例 | {liquidity.get('short_percent_float', 0) * 100:.1f}% | {cls._get_short_signal(liquidity.get('short_percent_float', 0) * 100)} |

### {cls.EMOJI['target']} 分析师预期
- **目标价均值**：${target_mean:.2f} ({potential:+.1f}%)
- **目标价区间**：${fundamentals.get('target_low_price', 0):.2f} - ${fundamentals.get('target_high_price', 0):.2f}
- **评级**：{fundamentals.get('recommendation_key', '-').upper()} ({fundamentals.get('analyst_count', 0)} 位分析师)

---

## 二、技术分析

### 价格位置
- **当前价格**：${price:.2f}
- **52周区间**：${technicals.get('period_low', 0):.2f} - ${technicals.get('period_high', 0):.2f}
- **距高点**：{technicals.get('pct_from_high', 0):+.1f}% | **距低点**：{technicals.get('pct_from_low', 0):+.1f}%

### 趋势分析
- **短期**：{trend_short} (MA5: ${technicals.get('ma5', 0):.2f} vs MA20: ${technicals.get('ma20', 0):.2f}) {cls._get_trend_emoji(trend_short)}
- **中期**：{technicals.get('trend_mid', 'NEUTRAL')} (MA20 vs MA50: ${technicals.get('ma50', 0):.2f})

### 技术指标
| 指标 | 数值 | 信号 |
|------|------|------|
| RSI(14) | {rsi:.2f} | {cls._get_rsi_signal(rsi)} |
| MACD | {technicals.get('macd', 0):.3f} | {cls._get_macd_signal(technicals.get('macd_hist', 0))} |
| KDJ_K | {technicals.get('kdj_k', 0):.2f} | {cls._get_kdj_signal(technicals.get('kdj_k', 0), technicals.get('kdj_d', 0))} |

### 支撑/阻力
- **阻力**：${technicals.get('resistance_20d', 0):.2f} (20日)
- **支撑**：${technicals.get('support_20d', 0):.2f} (20日)

### Wyckoff 分析
- **阶段**：{wyckoff.get('phase', 'N/A')}
- **区间**：${{wyckoff.get('support', 0):.2f}} - ${{wyckoff.get('resistance', 0):.2f}}
- **置信度**：{wyckoff.get('confidence', 0)}%

### Wyckoff 图表
![Wyckoff分析](../Charts/{stock_code.replace('.', '_')}_wyckoff.png)

---

## 三、基本面分析

### 估值水平
| 指标 | 数值 | 评价 |
|------|------|------|
| PE (Forward) | {fundamentals.get('pe_forward', 0):.2f} | {cls._get_pe_signal(fundamentals.get('pe_forward', 0))} |
| PB | {fundamentals.get('pb', 0):.2f} | {cls._get_pb_signal(fundamentals.get('pb', 0))} |
| PS | {fundamentals.get('ps', 0):.2f} | {cls._get_ps_signal(fundamentals.get('ps', 0))} |

### 盈利能力
| 指标 | 数值 | 评价 |
|------|------|------|
| ROE | {fundamentals.get('roe', 0) * 100:.2f}% | {cls._get_roe_signal(fundamentals.get('roe', 0) * 100)} |
| ROA | {fundamentals.get('roa', 0) * 100:.2f}% | {cls._get_roa_signal(fundamentals.get('roa', 0) * 100)} |
| 毛利率 | {fundamentals.get('gross_margin', 0) * 100:.2f}% | {cls._get_margin_signal(fundamentals.get('gross_margin', 0) * 100)} |
| 净利率 | {fundamentals.get('profit_margin', 0) * 100:.2f}% | {cls._get_margin_signal(fundamentals.get('profit_margin', 0) * 100)} |

### 成长性
- **营收增长**：{fundamentals.get('revenue_growth', 0) * 100:+.1f}% YoY {cls._get_growth_emoji(fundamentals.get('revenue_growth', 0) * 100)}

### 财务健康
- **流动比率**：{fundamentals.get('current_ratio', 0):.2f} {cls._get_current_ratio_signal(fundamentals.get('current_ratio', 0))}
- **债务权益比**：{fundamentals.get('debt_equity', 0):.1f}
- **现金**：${fundamentals.get('total_cash', 0) / 1_000_000:.1f}M | **债务**：${fundamentals.get('total_debt', 0) / 1_000_000:.1f}M
- **自由现金流**：${fundamentals.get('free_cashflow', 0) / 1_000_000:.1f}M {cls._get_fcf_signal(fundamentals.get('free_cashflow', 0))}

---

## 四、市场结构

### 流动性分析
| 指标 | 数值 | 评价 |
|------|------|------|
| 做空比例 | {liquidity.get('short_percent_float', 0) * 100:.1f}% | {cls._get_short_signal(liquidity.get('short_percent_float', 0) * 100)} |
| Days to Cover | {liquidity.get('days_to_cover', 0):.1f}天 | {cls._get_days_to_cover_signal(liquidity.get('days_to_cover', 0))} |
| 机构持仓 | {liquidity.get('institutional_ownership', 0) * 100:.1f}% | - |
| 日均成交额 | ${liquidity.get('daily_dollar_volume', 0) / 1_000_000:.1f}M | {cls._get_volume_signal(liquidity.get('daily_dollar_volume', 0) / 1_000_000)} |

### 期权市场
- **Put/Call Ratio**：{options.get('put_call_ratio', 0):.2f} {cls._get_putcall_signal(options.get('put_call_ratio', 0))}
- **Max Pain**：${options.get('max_pain', 0):.2f}

---

## 五、催化因素

### {cls.EMOJI['positive']} 向上催化
{cls._get_positive_catalysts(fundamentals, earnings, price)}

### {cls.EMOJI['negative']} 下行风险
{cls._get_negative_risks(fundamentals, liquidity)}

---

## 六、操作建议

### 当前状态
{cls._get_action_emoji(wyckoff_score)} | 综合评分 {wyckoff_score}/100

### 价格网格
| 类型 | 价格 | 理由 |
|------|------|------|
| 强支撑 | ${technicals.get('support_20d', 0):.2f} | 20日低点 |
| 第一买点 | ${wyckoff.get('support', 0):.2f} | Wyckoff 支撑 |
| 当前价格 | ${price:.2f} | - |
| 第一阻力 | ${technicals.get('resistance_20d', 0):.2f} | 20日高点 |
| 目标价 | ${target_mean:.2f} | 分析师均值 |

### 仓位管理
- **建议仓位**：{cls._get_position_size(wyckoff_score)}
- **止损位**：${technicals.get('support_20d', 0):.2f}

---

**免责声明**：本分析仅供参考，不构成投资建议。
"""

    @classmethod
    def _section_2_technical(cls, technicals: Dict, wyckoff: Dict) -> str:
        """第二部分：技术分析（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_3_fundamental(cls, fundamentals: Dict) -> str:
        """第三部分：基本面分析（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_4_market_structure(cls, liquidity: Dict, options: Dict) -> str:
        """第四部分：市场结构（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_5_catalysts(cls, fundamentals: Dict, earnings: Dict, web_search: Dict) -> str:
        """第五部分：催化因素（已合并到第一部分）"""
        return ""

    @classmethod
    def _section_6_trading_plan(cls, stock_info: Dict, technicals: Dict, fundamentals: Dict, wyckoff: Dict) -> str:
        """第六部分：操作建议（已合并到第一部分）"""
        return ""

    # ========== 辅助方法：信号判定 ==========

    @classmethod
    def _get_score_emoji(cls, score: float) -> str:
        return cls.EMOJI['positive'] if score >= 70 else cls.EMOJI['neutral'] if score >= 50 else cls.EMOJI['negative']

    @classmethod
    def _get_valuation_signal(cls, potential: float) -> str:
        return f"{cls.EMOJI['positive']} 低估" if potential > 50 else f"{cls.EMOJI['neutral']} 合理" if potential > 0 else f"{cls.EMOJI['negative']} 高估"

    @classmethod
    def _get_potential_emoji(cls, potential: float) -> str:
        return f"{cls.EMOJI['rocket']}" if potential > 50 else f"➡️" if potential > 0 else f"{cls.EMOJI['warning']}"

    @classmethod
    def _get_trend_emoji(cls, trend: str) -> str:
        return f"{cls.EMOJI['bullish']} 看多" if trend == "BULLISH" else f"{cls.EMOJI['bearish']} 看空"

    @classmethod
    def _get_rsi_signal(cls, rsi: float) -> str:
        return f"{cls.EMOJI['positive']} 超卖" if rsi < 30 else f"{cls.EMOJI['negative']} 超买" if rsi > 70 else f"{cls.EMOJI['neutral']} 中性"

    @classmethod
    def _get_short_signal(cls, short_pct: float) -> str:
        return f"{cls.EMOJI['warning']} 高" if short_pct > 10 else f"{cls.EMOJI['positive']} 正常"

    @classmethod
    def _get_macd_signal(cls, macd_hist: float) -> str:
        return f"{cls.EMOJI['positive']} 金叉" if macd_hist > 0 else f"{cls.EMOJI['negative']} 死叉"

    @classmethod
    def _get_kdj_signal(cls, k: float, d: float) -> str:
        return f"{cls.EMOJI['positive']}" if k > d else f"{cls.EMOJI['negative']}"

    @classmethod
    def _get_pe_signal(cls, pe: float) -> str:
        return f"{cls.EMOJI['warning']} 亏损" if pe < 0 else f"{cls.EMOJI['positive']} 合理" if pe < 20 else f"{cls.EMOJI['neutral']} 偏高"

    @classmethod
    def _get_pb_signal(cls, pb: float) -> str:
        return f"{cls.EMOJI['positive']} 低" if pb < 1 else f"{cls.EMOJI['neutral']} 中等" if pb < 3 else f"{cls.EMOJI['negative']} 高"

    @classmethod
    def _get_ps_signal(cls, ps: float) -> str:
        return f"{cls.EMOJI['positive']} 低" if ps < 1 else f"{cls.EMOJI['neutral']} 中等" if ps < 3 else f"{cls.EMOJI['negative']} 高"

    @classmethod
    def _get_roe_signal(cls, roe: float) -> str:
        return f"{cls.EMOJI['positive']} 优秀" if roe > 15 else f"{cls.EMOJI['neutral']} 一般" if roe > 0 else f"{cls.EMOJI['negative']} 亏损"

    @classmethod
    def _get_roa_signal(cls, roa: float) -> str:
        return f"{cls.EMOJI['positive']} 优秀" if roa > 10 else f"{cls.EMOJI['neutral']} 一般" if roa > 0 else f"{cls.EMOJI['negative']} 亏损"

    @classmethod
    def _get_margin_signal(cls, margin: float) -> str:
        return f"{cls.EMOJI['positive']} 高" if margin > 40 else f"{cls.EMOJI['neutral']} 中等" if margin > 20 else f"{cls.EMOJI['negative']} 低"

    @classmethod
    def _get_growth_emoji(cls, growth: float) -> str:
        return f"{cls.EMOJI['rocket']}" if growth > 20 else f"➡️" if growth > 0 else f"{cls.EMOJI['warning']}"

    @classmethod
    def _get_current_ratio_signal(cls, ratio: float) -> str:
        return f"{cls.EMOJI['positive']} 健康" if ratio > 1.5 else f"{cls.EMOJI['neutral']} 一般" if ratio > 1 else f"{cls.EMOJI['negative']} 紧张"

    @classmethod
    def _get_fcf_signal(cls, fcf: float) -> str:
        return f"{cls.EMOJI['positive']} 正向" if fcf > 0 else f"{cls.EMOJI['negative']} 烧钱"

    @classmethod
    def _get_days_to_cover_signal(cls, days: float) -> str:
        return f"{cls.EMOJI['warning']} 流动性差" if days > 5 else f"{cls.EMOJI['positive']} 正常"

    @classmethod
    def _get_volume_signal(cls, volume: float) -> str:
        return f"{cls.EMOJI['warning']} 低" if volume < 2 else f"{cls.EMOJI['positive']} 正常"

    @classmethod
    def _get_putcall_signal(cls, ratio: float) -> str:
        return f"{cls.EMOJI['negative']} 极度看空" if ratio > 10 else f"{cls.EMOJI['neutral']} 看空" if ratio > 1 else f"{cls.EMOJI['positive']} 看多"

    @classmethod
    def _get_positive_catalysts(cls, fundamentals: Dict, earnings: Dict, price: float = 0) -> str:
        """生成向上催化因素"""
        catalysts = []

        # 财报
        history = earnings.get('history', [])
        if history:
            catalysts.append(f"1. **财报超预期**：下次财报 {history[0].get('date', 'N/A')}")

        # 分析师目标价
        target_mean = fundamentals.get('target_mean_price', 0)
        if target_mean > 0 and price > 0:
            potential = (target_mean / price - 1) * 100
            catalysts.append(f"2. **分析师上调**：目标价均值 ${target_mean:.2f} 暗示 {potential:+.1f}% 空间")

        return "\n".join(catalysts) if catalysts else "暂无"

    @classmethod
    def _get_negative_risks(cls, fundamentals: Dict, liquidity: Dict) -> str:
        """生成下行风险"""
        risks = []

        # 流动性
        daily_volume = liquidity.get('daily_dollar_volume', 0) / 1_000_000
        if daily_volume < 2:
            risks.append(f"1. **流动性风险**：日均成交额 ${daily_volume:.1f}M 较低")

        # 做空
        short_pct = liquidity.get('short_percent_float', 0) * 100
        if short_pct > 5:
            risks.append(f"2. **做空挤压风险**")

        # 现金流
        fcf = fundamentals.get('free_cashflow', 0) / 1_000_000
        if fcf < 0:
            risks.append(f"3. **现金流压力**：自由现金流 ${fcf:.1f}M")

        return "\n".join(risks) if risks else "暂无"

    @classmethod
    def _get_action_emoji(cls, score: float) -> str:
        return f"{cls.EMOJI['positive']} 建仓" if score >= 60 else f"{cls.EMOJI['neutral']} 观望" if score >= 40 else f"{cls.EMOJI['negative']} 回避"

    @classmethod
    def _get_action_text(cls, score: float) -> str:
        return "建仓" if score >= 60 else "观望" if score >= 40 else "回避"

    @classmethod
    def _get_position_size(cls, score: float) -> str:
        return "2-3%" if score >= 60 else "1-2%" if score >= 40 else "0%"
