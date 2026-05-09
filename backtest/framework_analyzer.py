"""
框架分析器 - 从回测结果中提炼框架级优化建议

接收 BacktestResult 列表，识别系统性规律（入场时机、止损纪律、
仓位管理、标的筛选、估值门槛），输出带置信度的结构化建议。
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from backtest.core import BacktestResult, SignalPerformance


@dataclass
class Suggestion:
    id: int
    category: str   # "入场时机" | "止损纪律" | "仓位管理" | "标的筛选" | "估值门槛"
    finding: str    # 客观规律陈述，附数据
    suggestion: str # 具体可操作建议
    confidence: str # "高" | "中" | "低"


@dataclass
class FrameworkReport:
    period: str
    total_signals: int
    win_rate: float
    avg_return: float
    by_action: Dict[str, dict]   # BUY/SELL/HOLD 分项统计
    suggestions: List[Suggestion]
    raw_diagnosis: str


class FrameworkAnalyzer:
    """分析回测结果，生成框架优化建议"""

    MIN_HIGH = 10   # 高置信度所需样本量
    MIN_MED = 5
    MIN_LOW = 3

    def analyze(
        self,
        results: Dict[str, List[BacktestResult]],
        lookback_days: int = 90,
    ) -> FrameworkReport:
        all_signals: List[SignalPerformance] = [
            s
            for bt_list in results.values()
            for bt in bt_list
            for s in bt.signals
            if s.verified
        ]

        if all_signals:
            dates = sorted(s.entry_date for s in all_signals)
            period = f"{dates[0]} ~ {dates[-1]}"
        else:
            period = f"过去 {lookback_days} 天（无可验证信号）"

        total = len(all_signals)
        wins = sum(1 for s in all_signals if s.correct)
        win_rate = wins / total * 100 if total else 0.0
        avg_return = statistics.mean(s.return_pct for s in all_signals) if all_signals else 0.0
        by_action = self._stats_by_action(all_signals)
        suggestions = self._generate_suggestions(all_signals, by_action, results)

        return FrameworkReport(
            period=period,
            total_signals=total,
            win_rate=win_rate,
            avg_return=avg_return,
            by_action=by_action,
            suggestions=suggestions,
            raw_diagnosis=self._raw_diagnosis(total, win_rate, avg_return),
        )

    # ── 统计工具 ──────────────────────────────────────────────────

    def _stats_by_action(self, signals: List[SignalPerformance]) -> Dict[str, dict]:
        groups: Dict[str, List[SignalPerformance]] = {}
        for s in signals:
            groups.setdefault(s.action, []).append(s)

        out = {}
        for action, sigs in groups.items():
            wins = sum(1 for s in sigs if s.correct)
            rets = [s.return_pct for s in sigs]
            out[action] = {
                "count": len(sigs),
                "win_rate": wins / len(sigs) * 100,
                "avg_return": statistics.mean(rets),
                "median_max_return": statistics.median(s.max_return_pct for s in sigs),
                "median_drawdown": statistics.median(s.max_drawdown_pct for s in sigs),
            }
        return out

    # ── 五类启发式规则 ────────────────────────────────────────────

    def _generate_suggestions(
        self,
        signals: List[SignalPerformance],
        by_action: Dict[str, dict],
        results: Dict[str, List[BacktestResult]],
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        sid = 1

        # 1. 入场时机：BUY 均收益为负但中位最高涨幅可观
        buy = by_action.get("BUY", {})
        if buy.get("count", 0) >= self.MIN_LOW:
            if buy["avg_return"] < 0 and buy["median_max_return"] > 5:
                conf = "高" if buy["count"] >= self.MIN_HIGH else "中"
                suggestions.append(Suggestion(
                    id=sid,
                    category="入场时机",
                    finding=(
                        f"BUY 信号均收益 {buy['avg_return']:+.1f}%，"
                        f"但中位最高涨幅达 {buy['median_max_return']:.1f}%（{buy['count']} 条）——"
                        f"方向大致正确，但建仓点偏早"
                    ),
                    suggestion=(
                        "等价格突破关键阻力（或收盘站稳 MA50）后再建仓，"
                        "避免在整理阶段过早入场被震出"
                    ),
                    confidence=conf,
                ))
                sid += 1

        # 2. 止损纪律：BUY 信号最大回撤超 -15% 的比例偏高
        buy_sigs = [s for s in signals if s.action == "BUY"]
        if len(buy_sigs) >= self.MIN_LOW:
            deep = [s for s in buy_sigs if s.max_drawdown_pct < -15]
            if len(deep) >= 2:
                pct = len(deep) / len(buy_sigs) * 100
                conf = "高" if len(buy_sigs) >= self.MIN_HIGH else "中"
                suggestions.append(Suggestion(
                    id=sid,
                    category="止损纪律",
                    finding=(
                        f"{pct:.0f}% 的买入信号（{len(deep)}/{len(buy_sigs)} 条）"
                        f"最大回撤超过 -15%，超出合理止损幅度"
                    ),
                    suggestion=(
                        "建立硬止损规则：买入后跌破入场价 -8% 强制离场；"
                        "或跌破 MA50 且无企稳信号则减仓至半仓"
                    ),
                    confidence=conf,
                ))
                sid += 1

        # 3. 仓位管理：HOLD 信号占比过高
        hold_n = by_action.get("HOLD", {}).get("count", 0)
        buy_n = by_action.get("BUY", {}).get("count", 0)
        sell_n = by_action.get("SELL", {}).get("count", 0)
        total_directional = hold_n + buy_n + sell_n
        if total_directional > 0 and hold_n / total_directional > 0.5:
            suggestions.append(Suggestion(
                id=sid,
                category="仓位管理",
                finding=(
                    f"HOLD 信号占比 {hold_n/total_directional*100:.0f}%（{hold_n}/{total_directional} 条），"
                    f"过于保守可能导致错过趋势"
                ),
                suggestion=(
                    "对评分 ≥70 且处于 Stage 2 的标的，"
                    "将『继续观察』改为明确的小仓位建仓价位区间（如 $X–$Y 轻仓）"
                ),
                confidence="中",
            ))
            sid += 1

        # 4. 标的筛选：某标的所有方向性信号均判断错误
        problem: list[tuple[str, int]] = []
        for ticker, bt_list in results.items():
            dir_sigs = [
                s for bt in bt_list for s in bt.signals
                if s.verified and s.action in ("BUY", "SELL")
            ]
            if len(dir_sigs) >= 2 and all(not s.correct for s in dir_sigs):
                problem.append((ticker, len(dir_sigs)))

        if problem:
            names = ", ".join(f"{t}（{n} 条）" for t, n in problem)
            conf = "高" if any(n >= 3 for _, n in problem) else "低"
            suggestions.append(Suggestion(
                id=sid,
                category="标的筛选",
                finding=f"以下标的所有方向性信号均判断错误：{names}",
                suggestion=(
                    "检查这些标的的特殊性（高波动、政策敏感、低流动性），"
                    "考虑将其移出常规框架或单独制定更保守的操作规则"
                ),
                confidence=conf,
            ))
            sid += 1

        # 5. 估值门槛：整体胜率和均收益双双低于阈值
        total = len(signals)
        if total >= self.MIN_MED:
            overall_wr = sum(1 for s in signals if s.correct) / total * 100
            overall_ret = statistics.mean(s.return_pct for s in signals)
            if overall_wr < 40 and overall_ret < -2:
                conf = "高" if total >= self.MIN_HIGH else "中"
                suggestions.append(Suggestion(
                    id=sid,
                    category="估值门槛",
                    finding=(
                        f"总体胜率 {overall_wr:.1f}%、均收益 {overall_ret:+.1f}%，"
                        f"系统性低于基准（{total} 条信号）"
                    ),
                    suggestion=(
                        "暂时将建仓评分门槛从 ≥60 提高到 ≥75，"
                        "待连续两次复盘胜率回升至 50% 以上再酌情放宽"
                    ),
                    confidence=conf,
                ))

        return suggestions

    def _raw_diagnosis(self, total: int, win_rate: float, avg_return: float) -> str:
        if total < self.MIN_LOW:
            return "样本不足（<3 条），暂无统计意义，请继续积累分析记录。"
        parts = []
        if win_rate >= 60:
            parts.append(f"胜率良好（{win_rate:.1f}%）")
        elif win_rate >= 45:
            parts.append(f"胜率尚可（{win_rate:.1f}%）")
        else:
            parts.append(f"胜率偏低（{win_rate:.1f}%）")
        if avg_return > 2:
            parts.append(f"均收益 {avg_return:+.1f}%，方向判断有效")
        elif avg_return < -2:
            parts.append(f"均收益 {avg_return:+.1f}%，方向存在系统性偏差")
        else:
            parts.append(f"均收益 {avg_return:+.1f}%，信号区分度不足")
        return "；".join(parts) + "。"
