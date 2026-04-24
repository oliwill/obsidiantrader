"""
综合分析器 - 结合基本面和威科夫技术分析

提供完整的股票分析报告，包含：
1. 基本面深度分析
2. 威科夫技术分析
3. 综合评分与建议
"""
from typing import Dict, List
import pandas as pd

from .base import BaseAnalyzer, AnalysisResult
from .fundamental import FundamentalAnalyzer
from .wyckoff import WyckoffAnalyzer


class ComprehensiveAnalyzer(BaseAnalyzer):
    """
    综合分析器
    
    结合基本面分析师和威科夫技术分析师的视角，
    提供全面的投资决策支持。
    """
    
    def __init__(self):
        self.fundamental = FundamentalAnalyzer()
        self.wyckoff = WyckoffAnalyzer()
    
    @property
    def name(self) -> str:
        return "综合分析"
    
    @property
    def description(self) -> str:
        return "基本面 + 威科夫技术面综合分析"
    
    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        """
        执行综合分析
        
        Args:
            data: 历史行情数据
            fundamentals: 基本面数据
        
        Returns:
            综合分析结果
        """
        # 执行子分析
        fundamental_result = self.fundamental.analyze(data, fundamentals)
        wyckoff_result = self.wyckoff.analyze(data, fundamentals)
        
        # 综合评分（基本面60% + 技术面40%）
        combined_score = (
            fundamental_result.score * 0.6 +
            wyckoff_result.score * 0.4
        )
        
        # 整合信号
        all_signals = []
        all_signals.extend(fundamental_result.signals)
        all_signals.extend(wyckoff_result.signals)
        
        # 整合风险
        all_risks = []
        all_risks.extend(fundamental_result.risks)
        all_risks.extend(wyckoff_result.risks)
        
        # 生成综合摘要
        summary = self._generate_summary(
            combined_score,
            fundamental_result,
            wyckoff_result
        )
        
        return AnalysisResult(
            score=round(combined_score, 1),
            summary=summary,
            details={
                "fundamental": fundamental_result.details,
                "wyckoff": wyckoff_result.details,
                "structure": wyckoff_result.details.get("structure"),
                "indicators": wyckoff_result.details.get("indicators"),
                "support_resistance": wyckoff_result.details.get("support_resistance")
            },
            signals=all_signals,
            risks=all_risks
        )
    
    def _generate_summary(
        self,
        score: float,
        fundamental: AnalysisResult,
        wyckoff: AnalysisResult
    ) -> str:
        """生成综合分析摘要"""
        # 基本面观点
        fund_view = "中性"  # simplified
        
        # 技术面观点
        structure = wyckoff.details.get("structure")
        tech_phase = structure.market_phase.value if structure else "未知"
        
        # 综合判断
        if score >= 80:
            overall = "强烈推荐"
        elif score >= 65:
            overall = "推荐"
        elif score >= 50:
            overall = "中性"
        else:
            overall = "回避"
        
        return f"综合评级：{overall} | 基本面：{fund_view} | 技术阶段：{tech_phase}"
