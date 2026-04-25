"""
基本面分析器 - 专业股票分析师框架

分析维度：
1. 业务模式与核心竞争力
2. 财务健康与盈利能力
3. 估值分析（横向+纵向对比）
4. 成长性与估值匹配度
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum

from .base import BaseAnalyzer, AnalysisResult


class Rating(Enum):
    """评级枚举"""
    EXCELLENT = "优秀"
    GOOD = "良好"
    FAIR = "一般"
    POOR = "较差"
    UNKNOWN = "未知"


@dataclass
class FinancialMetrics:
    """财务指标"""
    # 盈利能力
    gross_margin: float = 0
    operating_margin: float = 0
    profit_margin: float = 0
    roe: float = 0
    roa: float = 0
    
    # 成长性
    revenue_growth: float = 0
    earnings_growth: float = 0
    
    # 估值
    pe_ttm: float = 0
    pe_forward: float = 0
    pb: float = 0
    ps: float = 0
    ev_ebitda: float = 0
    
    # 财务健康
    current_ratio: float = 0
    debt_equity: float = 0
    free_cashflow: float = 0


@dataclass
class ValuationContext:
    """估值上下文"""
    industry_avg_pe: float = 15
    industry_avg_pb: float = 2
    historical_pe_low: float = 10
    historical_pe_high: float = 30
    historical_pb_low: float = 1
    historical_pb_high: float = 5


class FundamentalAnalyzer(BaseAnalyzer):
    """
    基本面分析器
    
    角色：经验丰富的股票分析师、研究员
    """
    
    @property
    def name(self) -> str:
        return "基本面深度分析"
    
    @property
    def description(self) -> str:
        return "多维度财务分析与估值评估"
    
    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        """
        执行基本面分析
        
        Args:
            data: 历史行情数据（用于计算历史估值区间）
            fundamentals: 基本面数据字典
        """
        # 清洗 None 值
        fundamentals = {k: (v if v is not None else 0) for k, v in fundamentals.items()}
        # 文本字段特殊处理
        for k in ["sector", "industry", "website", "business_summary"]:
            if k in fundamentals and fundamentals[k] == 0:
                fundamentals[k] = ""
        # 解析财务指标
        metrics = self._parse_metrics(fundamentals)
        
        # 获取估值上下文（行业对比和历史区间）
        context = self._get_valuation_context(data, fundamentals)
        
        # 执行各维度分析
        business_analysis = self._analyze_business_model(fundamentals)
        financial_analysis = self._analyze_financial_health(metrics)
        valuation_analysis = self._analyze_valuation(metrics, context)
        growth_analysis = self._analyze_growth(metrics)
        
        # 综合评分
        score = self._calculate_overall_score(
            business_analysis,
            financial_analysis,
            valuation_analysis,
            growth_analysis
        )
        
        # 生成投资建议
        recommendation = self._generate_recommendation(
            score, metrics, valuation_analysis
        )
        
        return AnalysisResult(
            score=score,
            summary=recommendation["summary"],
            details={
                "business": business_analysis,
                "financial": financial_analysis,
                "valuation": valuation_analysis,
                "growth": growth_analysis,
                "metrics": metrics,
                "context": context
            },
            signals=recommendation["signals"],
            risks=recommendation["risks"]
        )
    
    def _parse_metrics(self, fundamentals: Dict) -> FinancialMetrics:
        """解析财务指标"""
        return FinancialMetrics(
            gross_margin=self._safe_get(fundamentals, "gross_margin", 0) * 100,
            operating_margin=self._safe_get(fundamentals, "operating_margin", 0) * 100,
            profit_margin=self._safe_get(fundamentals, "profit_margin", 0) * 100,
            roe=self._safe_get(fundamentals, "roe", 0) * 100,
            roa=self._safe_get(fundamentals, "roa", 0) * 100,
            revenue_growth=self._safe_get(fundamentals, "revenue_growth", 0) * 100,
            earnings_growth=self._safe_get(fundamentals, "earnings_growth", 0) * 100,
            pe_ttm=self._safe_get(fundamentals, "pe_ttm", 0),
            pe_forward=self._safe_get(fundamentals, "pe_forward", 0),
            pb=self._safe_get(fundamentals, "pb", 0),
            ps=self._safe_get(fundamentals, "ps", 0),
            ev_ebitda=self._safe_get(fundamentals, "ev_ebitda", 0),
            current_ratio=self._safe_get(fundamentals, "current_ratio", 0),
            debt_equity=self._safe_get(fundamentals, "debt_equity", 0),
            free_cashflow=self._safe_get(fundamentals, "free_cashflow", 0)
        )
    
    def _safe_get(self, d: Dict, key: str, default: Any) -> Any:
        """安全获取字典值"""
        value = d.get(key, default)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        return value
    
    def _get_valuation_context(
        self,
        data: pd.DataFrame,
        fundamentals: Dict
    ) -> ValuationContext:
        """获取估值上下文"""
        context = ValuationContext()
        
        # 根据行业设置基准
        sector = (fundamentals.get("sector") or "").lower()
        industry = (fundamentals.get("industry") or "").lower()
        
        # 不同行业的典型估值区间
        sector_multiples = {
            "technology": {"pe": 25, "pb": 4},
            "healthcare": {"pe": 20, "pb": 3},
            "financial": {"pe": 12, "pb": 1.2},
            "energy": {"pe": 10, "pb": 1.5},
            "consumer": {"pe": 18, "pb": 2.5},
            "industrials": {"pe": 16, "pb": 2}
        }
        
        for key, multiples in sector_multiples.items():
            if key in sector or key in industry:
                context.industry_avg_pe = multiples["pe"]
                context.industry_avg_pb = multiples["pb"]
                break
        
        # 历史估值区间（简化处理）
        context.historical_pe_low = context.industry_avg_pe * 0.6
        context.historical_pe_high = context.industry_avg_pe * 1.8
        context.historical_pb_low = context.industry_avg_pb * 0.5
        context.historical_pb_high = context.industry_avg_pb * 2
        
        return context
    
    def _analyze_business_model(self, fundamentals: Dict) -> Dict:
        """分析业务模式与核心竞争力"""
        summary = fundamentals.get("business_summary", "")
        sector = fundamentals.get("sector", "未知")
        industry = fundamentals.get("industry", "未知")
        market_cap = fundamentals.get("market_cap", 0)
        employees = fundamentals.get("employees", 0)
        
        # 市值规模分类
        if market_cap > 200e9:
            size = "大型蓝筹"
            size_rating = Rating.EXCELLENT
        elif market_cap > 10e9:
            size = "中型成长"
            size_rating = Rating.GOOD
        elif market_cap > 2e9:
            size = "小型潜力"
            size_rating = Rating.FAIR
        else:
            size = "微型风险"
            size_rating = Rating.POOR
        
        return {
            "sector": sector,
            "industry": industry,
            "market_cap_tier": size,
            "market_cap_rating": size_rating.value,
            "employees": employees,
            "business_summary": summary[:500] if summary else "暂无",
            "moat_indicators": self._assess_moat(fundamentals)
        }
    
    def _assess_moat(self, fundamentals: Dict) -> List[str]:
        """评估护城河"""
        moats = []
        
        # 规模效应
        if fundamentals.get("market_cap", 0) > 100e9:
            moats.append("规模优势")
        
        # 盈利能力护城河
        if (fundamentals.get("gross_margin") or 0) > 0.4:
            moats.append("定价权/品牌溢价")

        # 现金创造能力
        if (fundamentals.get("free_cashflow") or 0) > 0:
            moats.append("现金创造能力")
        
        return moats if moats else ["护城河待观察"]
    
    def _analyze_financial_health(self, metrics: FinancialMetrics) -> Dict:
        """分析财务健康与盈利能力"""
        # 盈利能力评级
        profitability_score = self._rate_profitability(metrics)
        
        # 财务结构评级
        structure_score = self._rate_financial_structure(metrics)
        
        # 现金流健康度
        cashflow_rating = self._rate_cashflow(metrics)
        
        return {
            "profitability": {
                "score": profitability_score,
                "gross_margin": {"value": metrics.gross_margin, "rating": self._rate_margin(metrics.gross_margin, 30, 50)},
                "operating_margin": {"value": metrics.operating_margin, "rating": self._rate_margin(metrics.operating_margin, 10, 20)},
                "profit_margin": {"value": metrics.profit_margin, "rating": self._rate_margin(metrics.profit_margin, 8, 15)},
                "roe": {"value": metrics.roe, "rating": self._rate_roe(metrics.roe)},
                "roa": {"value": metrics.roa, "rating": self._rate_roa(metrics.roa)}
            },
            "financial_structure": {
                "score": structure_score,
                "current_ratio": {"value": metrics.current_ratio, "rating": self._rate_current_ratio(metrics.current_ratio)},
                "debt_equity": {"value": metrics.debt_equity, "rating": self._rate_debt_equity(metrics.debt_equity)}
            },
            "cashflow": cashflow_rating
        }
    
    def _rate_profitability(self, metrics: FinancialMetrics) -> int:
        """盈利能力评分"""
        score = 0
        if metrics.gross_margin > 40: score += 20
        elif metrics.gross_margin > 25: score += 15
        elif metrics.gross_margin > 15: score += 10
        
        if metrics.profit_margin > 15: score += 20
        elif metrics.profit_margin > 8: score += 15
        elif metrics.profit_margin > 3: score += 10
        
        if metrics.roe > 20: score += 20
        elif metrics.roe > 15: score += 15
        elif metrics.roe > 10: score += 10
        elif metrics.roe > 5: score += 5
        
        return min(score, 60)
    
    def _rate_margin(self, value: float, good: float, excellent: float) -> str:
        if value > excellent: return Rating.EXCELLENT.value
        elif value > good: return Rating.GOOD.value
        elif value > 0: return Rating.FAIR.value
        return Rating.POOR.value
    
    def _rate_roe(self, roe: float) -> str:
        if roe > 20: return Rating.EXCELLENT.value
        elif roe > 15: return Rating.GOOD.value
        elif roe > 10: return Rating.FAIR.value
        elif roe > 0: return Rating.POOR.value
        return Rating.UNKNOWN.value
    
    def _rate_roa(self, roa: float) -> str:
        if roa > 10: return Rating.EXCELLENT.value
        elif roa > 6: return Rating.GOOD.value
        elif roa > 3: return Rating.FAIR.value
        elif roa > 0: return Rating.POOR.value
        return Rating.UNKNOWN.value
    
    def _rate_financial_structure(self, metrics: FinancialMetrics) -> int:
        """财务结构评分"""
        score = 0
        if metrics.current_ratio > 2: score += 20
        elif metrics.current_ratio > 1.5: score += 15
        elif metrics.current_ratio > 1: score += 10
        
        if metrics.debt_equity < 50: score += 20
        elif metrics.debt_equity < 100: score += 15
        elif metrics.debt_equity < 200: score += 10
        
        return score
    
    def _rate_current_ratio(self, ratio: float) -> str:
        if ratio > 2: return Rating.EXCELLENT.value
        elif ratio > 1.5: return Rating.GOOD.value
        elif ratio > 1: return Rating.FAIR.value
        return Rating.POOR.value
    
    def _rate_debt_equity(self, de: float) -> str:
        if de < 50: return Rating.EXCELLENT.value
        elif de < 100: return Rating.GOOD.value
        elif de < 200: return Rating.FAIR.value
        return Rating.POOR.value
    
    def _rate_cashflow(self, metrics: FinancialMetrics) -> str:
        if metrics.free_cashflow > 1e9: return Rating.EXCELLENT.value
        elif metrics.free_cashflow > 0: return Rating.GOOD.value
        return Rating.POOR.value
    
    def _analyze_valuation(
        self,
        metrics: FinancialMetrics,
        context: ValuationContext
    ) -> Dict:
        """估值分析 - 横向+纵向对比"""
        # 横向对比（行业对比）
        pe_vs_industry = self._compare_pe(metrics.pe_ttm, context.industry_avg_pe)
        pb_vs_industry = self._compare_pb(metrics.pb, context.industry_avg_pb)
        
        # 纵向对比（历史区间）
        pe_percentile = self._calculate_percentile(
            metrics.pe_ttm,
            context.historical_pe_low,
            context.historical_pe_high
        )
        pb_percentile = self._calculate_percentile(
            metrics.pb,
            context.historical_pb_low,
            context.historical_pb_high
        )
        
        # 综合估值评级
        valuation_rating = self._rate_overall_valuation(
            pe_vs_industry, pb_vs_industry, pe_percentile, pb_percentile
        )
        
        return {
            "pe_analysis": {
                "current": round(metrics.pe_ttm, 2),
                "industry_avg": context.industry_avg_pe,
                "vs_industry": pe_vs_industry,
                "historical_percentile": round(pe_percentile * 100, 1)
            },
            "pb_analysis": {
                "current": round(metrics.pb, 2),
                "industry_avg": context.industry_avg_pb,
                "vs_industry": pb_vs_industry,
                "historical_percentile": round(pb_percentile * 100, 1)
            },
            "other_metrics": {
                "ps": round(metrics.ps, 2),
                "ev_ebitda": round(metrics.ev_ebitda, 2),
                "forward_pe": round(metrics.pe_forward, 2)
            },
            "overall_rating": valuation_rating,
            "margin_of_safety": self._calculate_safety_margin(
                pe_percentile, pb_percentile
            )
        }
    
    def _compare_pe(self, pe: float, industry_avg: float) -> str:
        if pe <= 0 or industry_avg <= 0:
            return "无法比较"
        ratio = pe / industry_avg
        if ratio < 0.7: return "显著低估"
        elif ratio < 0.9: return "相对低估"
        elif ratio < 1.1: return "估值合理"
        elif ratio < 1.3: return "相对高估"
        return "显著高估"
    
    def _compare_pb(self, pb: float, industry_avg: float) -> str:
        if pb <= 0 or industry_avg <= 0:
            return "无法比较"
        ratio = pb / industry_avg
        if ratio < 0.7: return "显著低估"
        elif ratio < 0.9: return "相对低估"
        elif ratio < 1.1: return "估值合理"
        elif ratio < 1.3: return "相对高估"
        return "显著高估"
    
    def _calculate_percentile(self, value: float, low: float, high: float) -> float:
        """计算在历史区间的百分位"""
        if value <= 0 or high <= low:
            return 0.5
        percentile = (value - low) / (high - low)
        return max(0, min(1, percentile))
    
    def _rate_overall_valuation(self, pe_vs: str, pb_vs: str, pe_p: float, pb_p: float) -> str:
        """综合估值评级"""
        if "低估" in pe_vs and "低估" in pb_vs:
            return "低估"
        elif "高估" in pe_vs or "高估" in pb_vs:
            if pe_p > 0.8 or pb_p > 0.8:
                return "显著高估"
            return "相对高估"
        elif pe_p < 0.3 and pb_p < 0.3:
            return "低估区间"
        elif pe_p > 0.7 and pb_p > 0.7:
            return "高估区间"
        return "估值合理"
    
    def _calculate_safety_margin(self, pe_p: float, pb_p: float) -> str:
        """计算安全边际"""
        avg_p = (pe_p + pb_p) / 2
        if avg_p < 0.25: return "高安全边际"
        elif avg_p < 0.4: return "中等安全边际"
        elif avg_p < 0.6: return "安全边际一般"
        elif avg_p < 0.75: return "安全边际较低"
        return "安全边际不足"
    
    def _analyze_growth(self, metrics: FinancialMetrics) -> Dict:
        """成长性分析"""
        # 收入增长评级
        revenue_rating = self._rate_growth(metrics.revenue_growth)
        earnings_rating = self._rate_growth(metrics.earnings_growth)
        
        # PEG 估值
        peg = self._calculate_peg(metrics.pe_ttm, metrics.earnings_growth)
        
        return {
            "revenue_growth": {
                "value": round(metrics.revenue_growth, 2),
                "rating": revenue_rating
            },
            "earnings_growth": {
                "value": round(metrics.earnings_growth, 2),
                "rating": earnings_rating
            },
            "peg_ratio": round(peg, 2) if peg else None,
            "peg_rating": self._rate_peg(peg)
        }
    
    def _rate_growth(self, growth: float) -> str:
        if growth > 30: return Rating.EXCELLENT.value
        elif growth > 15: return Rating.GOOD.value
        elif growth > 5: return Rating.FAIR.value
        elif growth > 0: return "低增长"
        return "负增长"
    
    def _calculate_peg(self, pe: float, growth: float) -> float:
        """计算PEG比率"""
        if pe <= 0 or growth <= 0:
            return None
        return pe / growth
    
    def _rate_peg(self, peg: float) -> str:
        if peg is None:
            return "无法计算"
        if peg < 1: return "显著低估"
        elif peg < 1.5: return "相对低估"
        elif peg < 2: return "估值合理"
        return "相对高估"
    
    def _calculate_overall_score(
        self,
        business: Dict,
        financial: Dict,
        valuation: Dict,
        growth: Dict
    ) -> float:
        """计算综合评分"""
        # 盈利能力权重 30%
        profitability_score = financial["profitability"]["score"]
        
        # 估值合理性权重 25%
        valuation_score = self._valuation_to_score(valuation["overall_rating"])
        
        # 成长性权重 20%
        growth_score = self._growth_to_score(growth)
        
        # 财务结构权重 15%
        structure_score = financial["financial_structure"]["score"]
        
        # 业务质量权重 10%
        business_score = 50 if business["market_cap_rating"] == "优秀" else 40
        
        total = (profitability_score * 0.3 +
                valuation_score * 0.25 +
                growth_score * 0.2 +
                structure_score * 0.15 +
                business_score * 0.1)
        
        return round(total, 1)
    
    def _valuation_to_score(self, rating: str) -> float:
        scores = {
            "低估": 90,
            "显著低估": 95,
            "相对低估": 80,
            "估值合理": 60,
            "相对高估": 40,
            "显著高估": 25,
            "高估区间": 35
        }
        return scores.get(rating, 50)
    
    def _growth_to_score(self, growth: Dict) -> float:
        earnings = growth.get("earnings_growth", {}).get("value", 0)
        revenue = growth.get("revenue_growth", {}).get("value", 0)
        avg_growth = (earnings + revenue) / 2 if earnings and revenue else max(earnings, revenue)
        
        if avg_growth > 30: return 90
        elif avg_growth > 20: return 80
        elif avg_growth > 10: return 65
        elif avg_growth > 5: return 50
        elif avg_growth > 0: return 35
        return 20
    
    def _generate_recommendation(
        self,
        score: float,
        metrics: FinancialMetrics,
        valuation: Dict
    ) -> Dict:
        """生成投资建议"""
        signals = []
        risks = []
        
        # 根据评分生成观点
        if score >= 80:
            view = "看好"
            summary = f"基本面优秀，估值{valuation['overall_rating']}，值得重点关注"
        elif score >= 65:
            view = "谨慎看好"
            summary = f"基本面良好，估值{valuation['overall_rating']}，可考虑分批建仓"
        elif score >= 50:
            view = "中性"
            summary = "基本面一般，建议观望或等待更好时机"
        else:
            view = "看空"
            summary = "基本面存在明显问题，建议规避"
        
        # 交易信号
        if valuation["overall_rating"] in ["低估", "显著低估"]:
            signals.append(f"估值处于{valuation['margin_of_safety']}区间，中长期配置价值显现")
        
        if metrics.roe > 15 and metrics.profit_margin > 10:
            signals.append("ROE与净利率双高，盈利能力强劲")
        
        if metrics.revenue_growth > 20:
            signals.append("营收高速增长，成长动能充足")
        
        # 风险警示
        if metrics.debt_equity > 150:
            risks.append("负债率偏高，财务杠杆风险需关注")
        
        if metrics.current_ratio < 1:
            risks.append("流动比率低于1，短期偿债压力较大")
        
        if valuation["overall_rating"] in ["高估", "显著高估"]:
            risks.append("当前估值偏高，存在回调风险")
        
        if metrics.earnings_growth < 0:
            risks.append("盈利负增长，基本面承压")
        
        if not risks:
            risks.append("市场整体波动风险")
        
        return {
            "view": view,
            "summary": summary,
            "signals": signals,
            "risks": risks
        }