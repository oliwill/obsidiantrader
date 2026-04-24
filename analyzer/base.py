"""
分析器基类 - 所有分析器的抽象基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class AnalysisResult:
    """分析结果数据类"""
    score: float  # 综合评分 0-100
    summary: str  # 分析摘要
    details: Dict[str, Any] = field(default_factory=dict)  # 详细分析数据
    signals: List[str] = field(default_factory=list)  # 交易信号
    risks: List[str] = field(default_factory=list)  # 风险提示


class BaseAnalyzer(ABC):
    """
    分析器抽象基类
    
    所有具体分析器必须继承此类并实现 analyze 方法
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """分析器名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """分析器描述"""
        pass
    
    @abstractmethod
    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        """
        执行分析
        
        Args:
            data: 历史行情数据 DataFrame，包含 OHLCV
            fundamentals: 基本面数据字典
        
        Returns:
            AnalysisResult: 分析结果
        """
        pass
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据完整性"""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        return all(col in data.columns for col in required_columns)
