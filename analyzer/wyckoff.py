"""
威科夫技术分析器 - 基于理查德·D·威科夫方法

核心概念：
- 威科夫价格周期：吸筹(Accumulation) → 上涨(Markup) → 派发(Distribution) → 下跌(Markdown)
- 威科夫三大定律：因果定律、努力结果定律、相对强弱定律
- 五个阶段：Phase A-E
- 关键事件：SC(恐慌抛售), ST(二次测试), Spring(弹簧), LPS(最后支撑), SOS(强势信号), UTAD(上冲回落)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from .base import BaseAnalyzer, AnalysisResult


class MarketPhase(Enum):
    """市场阶段"""
    ACCUMULATION = "吸筹区"
    DISTRIBUTION = "派发区"
    MARKUP = "上涨趋势"
    MARKDOWN = "下跌趋势"
    REBALANCING = "再吸筹/再派发"
    UNKNOWN = "无法识别"


class WyckoffEvent(Enum):
    """威科夫关键事件"""
    SC = "SC - 恐慌抛售"
    AR = "AR - 自动反弹"
    ST = "ST - 二次测试"
    SPRING = "Spring - 弹簧"
    TEST = "Test - 测试"
    SOS = "SOS - 强势信号"
    LPS = "LPS - 最后支撑点"
    JAC = "JAC - 跳跃小溪"
    BU = "BU - 回踩"
    UT = "UT - 上冲"
    UTAD = "UTAD - 上冲回落"
    LPSY = "LPSY - 最后供应点"
    SOW = "SOW - 弱势信号"
    BC = "BC - 抢购高潮"


@dataclass
class WyckoffPhase:
    """威科夫阶段"""
    name: str  # Phase A, B, C, D, E
    start_idx: int
    end_idx: int
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    description: str


@dataclass
class WyckoffStructure:
    """威科夫结构识别结果"""
    market_phase: MarketPhase
    phases: List[WyckoffPhase]
    events: List[Dict[str, Any]]
    support_level: float
    resistance_level: float
    accumulation_zone: Optional[Tuple[float, float]] = None  # (low, high)
    distribution_zone: Optional[Tuple[float, float]] = None
    confidence: float = 0.0  # 置信度 0-1


class WyckoffAnalyzer(BaseAnalyzer):
    """
    威科夫技术分析器
    
    角色：以理查德·D·威科夫的语气和方法进行专业读图
    """
    
    @property
    def name(self) -> str:
        return "威科夫技术分析"
    
    @property
    def description(self) -> str:
        return "基于威科夫方法的深度技术分析"
    
    def analyze(self, data: pd.DataFrame, fundamentals: Dict) -> AnalysisResult:
        """
        执行威科夫技术分析
        
        Args:
            data: 历史行情数据（至少500天）
            fundamentals: 基本面数据（可选）
        """
        # 数据预处理
        df = self._prepare_data(data)
        
        if len(df) < 100:
            return AnalysisResult(
                score=50,
                summary="数据不足，无法进行威科夫分析",
                details={},
                signals=["需要更多历史数据"],
                risks=["分析可靠性低"]
            )
        
        # 识别市场结构和阶段
        structure = self._identify_structure(df)
        
        # 计算技术指标
        indicators = self._calculate_indicators(df)
        
        # 生成交易信号
        signals = self._generate_wyckoff_signals(df, structure, indicators)
        
        # 评估风险和支撑阻力
        risks = self._assess_risks(df, structure)
        
        # 综合评分
        score = self._calculate_wyckoff_score(structure, signals)
        
        # 生成威科夫风格的分析摘要
        summary = self._generate_wyckoff_summary(structure, signals)
        
        return AnalysisResult(
            score=score,
            summary=summary,
            details={
                "structure": structure,
                "indicators": indicators,
                "events": structure.events,
                "phases": structure.phases,
                "support_resistance": {
                    "support": structure.support_level,
                    "resistance": structure.resistance_level
                }
            },
            signals=signals,
            risks=risks
        )
    
    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """预处理数据"""
        df = data.copy()
        
        # 确保列名统一
        column_mapping = {
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume',
            'Date': 'date', 'Datetime': 'date'
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # 确保日期格式
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
        # 将所有数值列转为 float（兼容长桥SDK返回的 Decimal 类型）
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        # 计算移动平均线
        df['ma50'] = df['close'].rolling(window=50).mean()
        df['ma200'] = df['close'].rolling(window=200).mean()
        
        # 计算波动率
        df['range'] = df['high'] - df['low']
        df['atr'] = df['range'].rolling(window=14).mean()
        
        # 计算成交量移动平均
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        
        return df
    
    def _identify_structure(self, df: pd.DataFrame) -> WyckoffStructure:
        """识别威科夫结构"""
        recent_data = df.tail(500).reset_index(drop=True)
        
        # 识别趋势
        trend = self._identify_trend(recent_data)
        
        # 识别交易区间
        trading_range = self._identify_trading_range(recent_data)
        
        # 判断是吸筹还是派发
        if trading_range:
            phase = self._determine_phase(recent_data, trading_range, trend)
        else:
            phase = MarketPhase.MARKUP if trend == "UP" else MarketPhase.MARKDOWN
            trading_range = None
        
        # 识别关键事件
        events = self._identify_events(recent_data, trading_range, phase)
        
        # 识别阶段 (Phase A-E)
        phases = self._identify_phases(recent_data, events, phase, trading_range)
        
        # 计算支撑阻力位
        support, resistance = self._calculate_support_resistance(
            recent_data, trading_range, events
        )
        
        # 确定吸筹/派发区间
        accumulation_zone = None
        distribution_zone = None
        
        if phase == MarketPhase.ACCUMULATION and trading_range:
            accumulation_zone = self._refine_zone(recent_data, trading_range, events)
        elif phase == MarketPhase.DISTRIBUTION and trading_range:
            distribution_zone = self._refine_zone(recent_data, trading_range, events)
        
        # 计算置信度
        confidence = self._calculate_confidence(events, phases, trend)
        
        return WyckoffStructure(
            market_phase=phase,
            phases=phases,
            events=events,
            support_level=support,
            resistance_level=resistance,
            accumulation_zone=accumulation_zone,
            distribution_zone=distribution_zone,
            confidence=confidence
        )
    
    def _identify_trend(self, df: pd.DataFrame) -> str:
        """识别当前趋势"""
        # 使用50日和200日均线
        if len(df) < 200:
            # 短期趋势
            price_change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]
            if price_change > 0.2:
                return "UP"
            elif price_change < -0.2:
                return "DOWN"
            return "SIDEWAYS"
        
        # 长期趋势
        ma50_current = df['ma50'].iloc[-1]
        ma200_current = df['ma200'].iloc[-1]
        ma50_prev = df['ma50'].iloc[-50]
        
        if ma50_current > ma200_current and ma50_current > ma50_prev:
            return "UP"
        elif ma50_current < ma200_current and ma50_current < ma50_prev:
            return "DOWN"
        return "SIDEWAYS"
    
    def _identify_trading_range(self, df: pd.DataFrame) -> Optional[Tuple[float, float]]:
        """识别交易区间（盘整区域）"""
        if len(df) < 50:
            return None
        
        # 计算近期价格区间
        recent = df.tail(100)
        price_range = recent['high'].max() - recent['low'].min()
        avg_price = recent['close'].mean()
        
        # 如果波动小于平均价格的15%，认为是盘整
        if price_range / avg_price < 0.25:
            return (recent['low'].min(), recent['high'].max())
        
        # 查找明显的支撑阻力区间
        # 使用价格聚类方法
        highs = recent['high'].values
        lows = recent['low'].values
        
        # 寻找频繁测试的价格水平
        resistance = self._find_cluster_level(highs, avg_price * 0.05)
        support = self._find_cluster_level(lows, avg_price * 0.05)
        
        if resistance and support and (resistance - support) / avg_price < 0.3:
            return (support, resistance)
        
        return None
    
    def _find_cluster_level(self, prices: np.ndarray, tolerance: float) -> Optional[float]:
        """找到价格聚类水平"""
        if len(prices) == 0:
            return None
        
        # 使用直方图找到最密集的价格区间
        hist, bins = np.histogram(prices, bins=20)
        max_bin_idx = np.argmax(hist)
        
        if hist[max_bin_idx] < len(prices) * 0.1:  # 至少需要10%的数据点
            return None
        
        # 返回该bin的中点
        return (bins[max_bin_idx] + bins[max_bin_idx + 1]) / 2
    
    def _determine_phase(
        self,
        df: pd.DataFrame,
        trading_range: Tuple[float, float],
        trend: str
    ) -> MarketPhase:
        """判断当前阶段"""
        recent = df.tail(50)
        avg_volume = df['volume'].tail(100).mean()
        current_volume = recent['volume'].mean()
        
        support, resistance = trading_range
        price = recent['close'].iloc[-1]
        
        # 判断之前的趋势
        prev_trend = self._identify_trend(df.head(len(df) // 2))
        
        # 如果在下跌后的盘整区 → 吸筹
        if prev_trend == "DOWN" or prev_trend == "SIDEWAYS":
            # 检查是否在区间下半部分有放量
            in_lower_half = price < (support + resistance) / 2
            high_volume = current_volume > avg_volume * 1.2
            
            if in_lower_half or high_volume:
                return MarketPhase.ACCUMULATION
        
        # 如果在上涨后的盘整区 → 派发
        if prev_trend == "UP":
            # 检查是否在区间上半部分有放量
            in_upper_half = price > (support + resistance) / 2
            distribution_volume = current_volume > avg_volume * 1.3
            
            if in_upper_half or distribution_volume:
                return MarketPhase.DISTRIBUTION
        
        # 默认根据当前位置判断
        if price > resistance:
            return MarketPhase.MARKUP
        elif price < support:
            return MarketPhase.MARKDOWN
        
        return MarketPhase.REBALANCING
    
    def _identify_events(
        self,
        df: pd.DataFrame,
        trading_range: Optional[Tuple[float, float]],
        phase: MarketPhase
    ) -> List[Dict[str, Any]]:
        """识别威科夫关键事件"""
        events = []
        
        if not trading_range:
            return events
        
        support, resistance = trading_range
        avg_volume = df['volume'].mean()
        
        # 遍历数据寻找关键事件
        for i in range(10, len(df) - 10):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # 恐慌抛售 (SC) - 放量大跌，长下影线
            if self._is_selling_climax(row, prev_row, support, avg_volume):
                events.append({
                    "type": WyckoffEvent.SC,
                    "index": i,
                    "date": row['date'],
                    "price": row['low'],
                    "volume": row['volume'],
                    "description": "恐慌性抛售，大量供应出现"
                })
            
            # 自动反弹 (AR) - SC后的自然反弹
            elif events and events[-1]["type"] == WyckoffEvent.SC:
                if row['close'] > prev_row['close'] * 1.02:
                    events.append({
                        "type": WyckoffEvent.AR,
                        "index": i,
                        "date": row['date'],
                        "price": row['high'],
                        "volume": row['volume'],
                        "description": "自动反弹，定义交易区间上沿"
                    })
            
            # 二次测试 (ST) - 回到SC区域测试
            elif self._is_secondary_test(row, prev_row, events, avg_volume):
                events.append({
                    "type": WyckoffEvent.ST,
                    "index": i,
                    "date": row['date'],
                    "price": row['low'],
                    "volume": row['volume'],
                    "description": "二次测试，确认供应枯竭"
                })
            
            # 弹簧 (Spring) - 短暂跌破支撑后迅速收回
            elif self._is_spring(row, prev_row, support, avg_volume):
                events.append({
                    "type": WyckoffEvent.SPRING,
                    "index": i,
                    "date": row['date'],
                    "price": row['low'],
                    "volume": row['volume'],
                    "description": "弹簧效应，震出最后的多头止损"
                })
            
            # 强势信号 (SOS) - 放量突破区间
            elif self._is_sign_of_strength(row, prev_row, resistance, avg_volume):
                events.append({
                    "type": WyckoffEvent.SOS,
                    "index": i,
                    "date": row['date'],
                    "price": row['close'],
                    "volume": row['volume'],
                    "description": "强势信号，需求主导市场"
                })
            
            # 最后支撑点 (LPS) - 突破后的回踩
            elif self._is_last_point_of_support(row, events, support):
                events.append({
                    "type": WyckoffEvent.LPS,
                    "index": i,
                    "date": row['date'],
                    "price": row['low'],
                    "volume": row['volume'],
                    "description": "最后支撑点，突破后的健康回踩"
                })
            
            # 抢购高潮 (BC) - 派发阶段的顶部
            elif phase == MarketPhase.DISTRIBUTION:
                if self._is_buying_climax(row, prev_row, resistance, avg_volume):
                    events.append({
                        "type": WyckoffEvent.BC,
                        "index": i,
                        "date": row['date'],
                        "price": row['high'],
                        "volume": row['volume'],
                        "description": "抢购高潮，主力开始派发"
                    })
        
        return events
    
    def _is_selling_climax(
        self,
        row: pd.Series,
        prev_row: pd.Series,
        support: float,
        avg_volume: float
    ) -> bool:
        """识别恐慌抛售"""
        # 放量
        if row['volume'] < avg_volume * 1.5:
            return False
        
        # 大跌
        price_drop = (prev_row['close'] - row['close']) / prev_row['close']
        if price_drop < 0.03:
            return False
        
        # 长下影线或接近支撑
        lower_shadow = min(row['close'], row['open']) - row['low']
        body = abs(row['close'] - row['open'])
        has_long_shadow = lower_shadow > body * 1.5
        near_support = row['low'] <= support * 1.02
        
        return has_long_shadow or near_support
    
    def _is_secondary_test(
        self,
        row: pd.Series,
        prev_row: pd.Series,
        events: List[Dict],
        avg_volume: float
    ) -> bool:
        """识别二次测试"""
        if not events:
            return False
        
        # 找到最近的SC
        sc_events = [e for e in events if e["type"] == WyckoffEvent.SC]
        if not sc_events:
            return False
        
        last_sc = sc_events[-1]
        
        # 价格在SC区域附近
        near_sc = abs(row['low'] - last_sc['price']) / last_sc['price'] < 0.02
        
        # 成交量萎缩（供应减少的信号）
        low_volume = row['volume'] < avg_volume * 0.8
        
        return near_sc and low_volume
    
    def _is_spring(
        self,
        row: pd.Series,
        prev_row: pd.Series,
        support: float,
        avg_volume: float
    ) -> bool:
        """识别弹簧效应"""
        # 短暂跌破支撑
        if row['low'] > support * 0.98:
            return False
        
        # 但收盘收回到支撑之上
        if row['close'] < support * 0.99:
            return False
        
        # 可能伴随放量（震仓效果）
        return True
    
    def _is_sign_of_strength(
        self,
        row: pd.Series,
        prev_row: pd.Series,
        resistance: float,
        avg_volume: float
    ) -> bool:
        """识别强势信号"""
        # 突破阻力
        if row['close'] <= resistance * 1.01:
            return False
        
        # 放量
        if row['volume'] < avg_volume * 1.3:
            return False
        
        # 大阳线
        price_gain = (row['close'] - prev_row['close']) / prev_row['close']
        return price_gain > 0.02
    
    def _is_last_point_of_support(
        self,
        row: pd.Series,
        events: List[Dict],
        support: float
    ) -> bool:
        """识别最后支撑点"""
        # 之前有SOS
        sos_events = [e for e in events if e["type"] == WyckoffEvent.SOS]
        if not sos_events:
            return False
        
        # 回踩到原阻力位附近（现在应该是支撑）
        near_old_resistance = abs(row['low'] - support) / support < 0.03
        
        return near_old_resistance
    
    def _is_buying_climax(
        self,
        row: pd.Series,
        prev_row: pd.Series,
        resistance: float,
        avg_volume: float
    ) -> bool:
        """识别抢购高潮"""
        # 放量
        if row['volume'] < avg_volume * 2:
            return False
        
        # 大涨
        price_gain = (row['high'] - prev_row['close']) / prev_row['close']
        if price_gain < 0.05:
            return False
        
        # 长上影线
        upper_shadow = row['high'] - max(row['close'], row['open'])
        body = abs(row['close'] - row['open'])
        return upper_shadow > body
    
    def _identify_phases(
        self,
        df: pd.DataFrame,
        events: List[Dict],
        phase: MarketPhase,
        trading_range: Optional[Tuple[float, float]]
    ) -> List[WyckoffPhase]:
        """识别威科夫阶段 A-E"""
        phases = []
        
        if not events or not trading_range:
            return phases
        
        support, resistance = trading_range
        
        # 找到关键事件索引
        sc_events = [e for e in events if e["type"] == WyckoffEvent.SC]
        ar_events = [e for e in events if e["type"] == WyckoffEvent.AR]
        spring_events = [e for e in events if e["type"] == WyckoffEvent.SPRING]
        sos_events = [e for e in events if e["type"] == WyckoffEvent.SOS]
        
        # Phase A: SC → AR
        if sc_events and ar_events:
            sc = sc_events[0]
            ar = ar_events[0]
            phases.append(WyckoffPhase(
                name="Phase A",
                start_idx=sc['index'],
                end_idx=ar['index'],
                start_date=sc['date'],
                end_date=ar['date'],
                description="停止原趋势，确定交易区间。恐慌抛售(SC)后自动反弹(AR)"
            ))
        
        # Phase B: 构建原因（横盘整理）
        if phases and spring_events:
            phases.append(WyckoffPhase(
                name="Phase B",
                start_idx=phases[-1].end_idx,
                end_idx=spring_events[0]['index'],
                start_date=phases[-1].end_date,
                end_date=spring_events[0]['date'],
                description="构建新趋势的原因，主力在此区域吸筹/派发。可能多次测试"
            ))
        elif phases:
            # 如果没有Spring，用数据的中点
            mid_idx = len(df) // 2
            phases.append(WyckoffPhase(
                name="Phase B",
                start_idx=phases[-1].end_idx,
                end_idx=mid_idx,
                start_date=phases[-1].end_date,
                end_date=df.iloc[mid_idx]['date'],
                description="构建原因阶段，筹码在此换手"
            ))
        
        # Phase C: Spring/Test
        if spring_events and phases:
            spring = spring_events[0]
            phases.append(WyckoffPhase(
                name="Phase C",
                start_idx=phases[-1].end_idx,
                end_idx=spring['index'],
                start_date=phases[-1].end_date,
                end_date=spring['date'],
                description="决定性测试。弹簧(Spring)震出最后弱势持仓者"
            ))
        
        # Phase D: 确认阶段
        if sos_events and phases:
            sos = sos_events[0]
            phases.append(WyckoffPhase(
                name="Phase D",
                start_idx=phases[-1].end_idx,
                end_idx=sos['index'],
                start_date=phases[-1].end_date,
                end_date=sos['date'],
                description="强势信号(SOS)确认需求主导，可能伴随回踩(LPS)"
            ))
        
        # Phase E: 跨越小溪
        if phases and len(phases) >= 4:
            phases.append(WyckoffPhase(
                name="Phase E",
                start_idx=phases[-1].end_idx,
                end_idx=len(df) - 1,
                start_date=phases[-1].end_date,
                end_date=df.iloc[-1]['date'],
                description="跨越小溪，进入新的上涨趋势"
            ))
        
        return phases
    
    def _calculate_support_resistance(
        self,
        df: pd.DataFrame,
        trading_range: Optional[Tuple[float, float]],
        events: List[Dict]
    ) -> Tuple[float, float]:
        """计算支撑阻力位"""
        if trading_range:
            support, resistance = trading_range
        else:
            # 使用近期高低点
            recent = df.tail(60)
            support = recent['low'].min()
            resistance = recent['high'].max()
        
        # 根据事件微调
        sc_prices = [e['price'] for e in events if e['type'] == WyckoffEvent.SC]
        if sc_prices:
            support = min(support, min(sc_prices))
        
        ar_prices = [e['price'] for e in events if e['type'] == WyckoffEvent.AR]
        if ar_prices:
            resistance = max(resistance, max(ar_prices))
        
        return support, resistance
    
    def _refine_zone(
        self,
        df: pd.DataFrame,
        trading_range: Tuple[float, float],
        events: List[Dict]
    ) -> Tuple[float, float]:
        """精修吸筹/派发区间（剔除影线干扰）"""
        support, resistance = trading_range
        
        # 找到Phase B的数据范围
        phase_b_start = None
        phase_b_end = None
        
        for i, event in enumerate(events):
            if event['type'] == WyckoffEvent.AR:
                phase_b_start = event['index']
            elif event['type'] in [WyckoffEvent.SPRING, WyckoffEvent.SOS]:
                phase_b_end = event['index']
                break
        
        if phase_b_start and phase_b_end:
            # 取Phase B中收盘价最密集的区域
            phase_b_data = df.iloc[phase_b_start:phase_b_end]
            if len(phase_b_data) > 10:
                closes = phase_b_data['close'].values
                # 使用百分位确定核心区间
                zone_low = np.percentile(closes, 20)
                zone_high = np.percentile(closes, 80)
                return (zone_low, zone_high)
        
        # 默认使用原始区间的80%
        range_size = resistance - support
        return (support + range_size * 0.1, resistance - range_size * 0.1)
    
    def _calculate_confidence(
        self,
        events: List[Dict],
        phases: List[WyckoffPhase],
        trend: str
    ) -> float:
        """计算结构识别置信度"""
        confidence = 0.3  # 基础置信度
        
        # 事件越多，置信度越高
        if len(events) >= 3:
            confidence += 0.2
        if len(events) >= 5:
            confidence += 0.1
        
        # 阶段越完整，置信度越高
        if len(phases) >= 3:
            confidence += 0.2
        if len(phases) >= 4:
            confidence += 0.1
        
        # 趋势明确增加置信度
        if trend != "SIDEWAYS":
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        recent = df.tail(60)
        
        return {
            "ma50": df['ma50'].iloc[-1],
            "ma200": df['ma200'].iloc[-1],
            "ma_trend": "UP" if df['ma50'].iloc[-1] > df['ma50'].iloc[-20] else "DOWN",
            "rsi": self._calculate_rsi(df['close']),
            "macd": self._calculate_macd(df['close']),
            "volume_trend": "UP" if recent['volume'].mean() > df['volume'].tail(100).mean() else "DOWN",
            "atr": df['atr'].iloc[-1]
        }
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """计算RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    
    def _calculate_macd(self, prices: pd.Series) -> Dict:
        """计算MACD"""
        ema12 = prices.ewm(span=12).mean()
        ema26 = prices.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line.iloc[-1],
            "signal": signal_line.iloc[-1],
            "histogram": histogram.iloc[-1],
            "crossover": "BULLISH" if macd_line.iloc[-1] > signal_line.iloc[-1] else "BEARISH"
        }
    
    def _generate_wyckoff_signals(
        self,
        df: pd.DataFrame,
        structure: WyckoffStructure,
        indicators: Dict
    ) -> List[str]:
        """
        生成威科夫观测信号（只输出事实性描述，不做交易建议）

        原则：算法负责识别模式，LLM 负责综合判断
        """
        signals = []
        current_price = float(df['close'].iloc[-1])

        # ── 阶段事实 ──
        phase = structure.market_phase
        phase_label = phase.value

        if phase == MarketPhase.ACCUMULATION:
            phase_progress = structure.phases[-1].name if structure.phases else "Phase A"
            signals.append(f"当前阶段: {phase_label}，进度: {phase_progress}")
            if structure.accumulation_zone:
                low, high = structure.accumulation_zone
                signals.append(f"吸筹区间: {low:.2f} ~ {high:.2f}")

        elif phase == MarketPhase.DISTRIBUTION:
            phase_progress = structure.phases[-1].name if structure.phases else "Phase A"
            signals.append(f"当前阶段: {phase_label}，进度: {phase_progress}")
            if structure.distribution_zone:
                low, high = structure.distribution_zone
                signals.append(f"派发区间: {low:.2f} ~ {high:.2f}")

        elif phase == MarketPhase.MARKUP:
            signals.append(f"当前阶段: {phase_label}（趋势上行中）")

        elif phase == MarketPhase.MARKDOWN:
            signals.append(f"当前阶段: {phase_label}（趋势下行中）")

        # ── 关键事件事实（最近 20 个交易日） ──
        recent_events = [e for e in structure.events if e['index'] > len(df) - 20]
        for event in recent_events:
            date_str = event['date'].strftime('%m-%d')
            price = float(event['price'])
            event_name = event['type'].value

            if event['type'] == WyckoffEvent.SOS:
                signals.append(f"近期事件: SOS 于{date_str}出现，价格 {price:.2f}")
            elif event['type'] == WyckoffEvent.LPS:
                signals.append(f"近期事件: LPS 于{date_str}出现，价格 {price:.2f}")
            elif event['type'] == WyckoffEvent.SPRING:
                signals.append(f"近期事件: Spring 于{date_str}出现，价格 {price:.2f}")
            elif event['type'] == WyckoffEvent.UTAD:
                signals.append(f"近期事件: UTAD(上冲回落) 于{date_str}出现，价格 {price:.2f}")
            elif event['type'] == WyckoffEvent.SOW:
                signals.append(f"近期事件: SOW(弱势信号) 于{date_str}出现，价格 {price:.2f}")
            elif event['type'] == WyckoffEvent.LPSY:
                signals.append(f"近期事件: LPSY(最后供应点) 于{date_str}出现，价格 {price:.2f}")
            elif event['type'] == WyckoffEvent.BC:
                signals.append(f"近期事件: BC(抢购高潮) 于{date_str}出现，价格 {price:.2f}")
            elif event['type'] == WyckoffEvent.SC:
                signals.append(f"近期事件: SC(恐慌抛售) 于{date_str}出现，价格 {price:.2f}")
            else:
                signals.append(f"近期事件: {event_name} 于{date_str}出现，价格 {price:.2f}")

        # ── 技术指标事实 ──
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', {})
        crossover = macd.get('crossover', '')

        if crossover == "BULLISH":
            signals.append(f"MACD金叉，当前 RSI={rsi:.1f}")
        elif crossover == "BEARISH":
            signals.append(f"MACD死叉，当前 RSI={rsi:.1f}")

        if rsi < 30:
            signals.append(f"RSI={rsi:.1f}，处于超卖区")
        elif rsi > 70:
            signals.append(f"RSI={rsi:.1f}，处于超买区")

        # ── 支撑阻力位置 ──
        support_dist = (current_price - structure.support_level) / current_price * 100
        resistance_dist = (structure.resistance_level - current_price) / current_price * 100
        signals.append(f"当前价 {current_price:.2f}，距支撑 {support_dist:.1f}%，距阻力 {resistance_dist:.1f}%")

        return signals
    
    def _assess_risks(
        self,
        df: pd.DataFrame,
        structure: WyckoffStructure
    ) -> List[str]:
        """
        评估技术面风险因素（事实性描述，不做交易建议）
        """
        risks = []
        current_price = float(df['close'].iloc[-1])

        # ── 置信度 ──
        if structure.confidence < 0.3:
            risks.append(f"结构识别置信度低 ({structure.confidence*100:.0f}%)，结论可靠性有限")
        elif structure.confidence < 0.6:
            risks.append(f"结构识别置信度一般 ({structure.confidence*100:.0f}%)，需结合其他维度判断")

        # ── 阶段相关风险 ──
        if structure.market_phase == MarketPhase.ACCUMULATION:
            if not any(e['type'] == WyckoffEvent.SPRING for e in structure.events):
                risks.append("吸筹区尚未出现 Spring 测试，可能继续横盘震荡")

        elif structure.market_phase == MarketPhase.DISTRIBUTION:
            recent_events = [e for e in structure.events if e['index'] > len(df) - 20]
            has_sow = any(e['type'] == WyckoffEvent.SOW for e in recent_events)
            has_utad = any(e['type'] == WyckoffEvent.UTAD for e in recent_events)
            if has_sow:
                risks.append("近期出现 SOW(弱势信号)，派发进程可能在加速")
            if has_utad:
                risks.append("近期出现 UTAD(上冲回落)，典型派发末期特征")
            if not has_sow and not has_utad:
                risks.append("处于派发阶段，需关注是否出现 SOW 或 UTAD 信号")

        elif structure.market_phase == MarketPhase.MARKDOWN:
            risks.append("处于下跌趋势中")

        # ── 价格与关键位关系 ──
        if current_price < structure.support_level * 0.95:
            risks.append(f"价格 ({current_price:.2f}) 已跌破支撑位 ({structure.support_level:.2f}) 5% 以上")

        if current_price > structure.resistance_level * 1.05:
            risks.append(f"价格 ({current_price:.2f}) 已突破阻力位 ({structure.resistance_level:.2f}) 5% 以上，需确认是否有效突破")

        # ── 量价背离检测 ──
        if len(df) >= 20:
            recent_5 = df.tail(5)
            recent_20 = df.tail(20)
            price_trend_up = float(recent_5['close'].iloc[-1]) > float(recent_20['close'].iloc[0])
            vol_declining = float(recent_5['volume'].mean()) < float(recent_20['volume'].mean()) * 0.7
            if price_trend_up and vol_declining:
                risks.append("近期价格上涨但成交量萎缩（量价背离），上涨动能可能不足")

        return risks
    
    def _calculate_wyckoff_score(
        self,
        structure: WyckoffStructure,
        signals: List[str]
    ) -> float:
        """
        计算威科夫综合评分（对多头的有利程度）

        设计原则：
        - 评分反映"当前技术面对多头有利程度"，0=极度看空，100=极度看多
        - 阶段权重最大，events 有递减上限，避免被大量事件拉偏
        """
        score = 50.0

        # ── 阶段基础分（权重最大，±20） ──
        phase_weights = {
            MarketPhase.ACCUMULATION: 12,
            MarketPhase.MARKUP: 20,
            MarketPhase.DISTRIBUTION: -20,
            MarketPhase.MARKDOWN: -25,
            MarketPhase.REBALANCING: 0,
            MarketPhase.UNKNOWN: 0,
        }
        score += phase_weights.get(structure.market_phase, 0)

        # ── 阶段完整性（递减，上限 +10） ──
        phase_bonus = min(10, len(structure.phases) * 2)
        score += phase_bonus

        # ── 关键事件（递减，上限 +15） ──
        positive_events = {WyckoffEvent.SPRING, WyckoffEvent.SOS, WyckoffEvent.LPS, WyckoffEvent.JAC}
        negative_events = {WyckoffEvent.UTAD, WyckoffEvent.SOW, WyckoffEvent.LPSY, WyckoffEvent.BC}

        pos_count = sum(1 for e in structure.events if e['type'] in positive_events)
        neg_count = sum(1 for e in structure.events if e['type'] in negative_events)

        # 递减：前几个事件权重大，后面的递减
        pos_bonus = sum(max(0, 3 - 0.5 * i) for i in range(pos_count))
        neg_penalty = sum(max(0, 3 - 0.5 * i) for i in range(neg_count))
        score += min(15, pos_bonus) - min(15, neg_penalty)

        # ── 置信度缩放 ──
        # 高置信度 → 评分更极端；低置信度 → 拉向 50
        score = 50 + (score - 50) * structure.confidence

        return max(0, min(100, round(score, 1)))
    
    def _generate_wyckoff_summary(
        self,
        structure: WyckoffStructure,
        signals: List[str]
    ) -> str:
        """生成威科夫风格分析摘要"""
        phase_str = structure.market_phase.value
        
        if structure.phases:
            current_phase = structure.phases[-1].name if structure.phases else "未确定"
            phase_detail = f"当前处于{current_phase}"
        else:
            phase_detail = "阶段识别中"
        
        event_summary = ""
        if structure.events:
            key_events = [e['type'].value for e in structure.events[-3:]]
            event_summary = f"关键事件: {', '.join(key_events)}"
        
        confidence_str = f"(置信度: {structure.confidence*100:.0f}%)"
        
        return f"{phase_str} | {phase_detail} {confidence_str}. {event_summary}"