#!/usr/bin/env python3
"""
威科夫图表绘制器

基于威科夫分析结果，绘制带中文标注的专业行情图。

功能：
1. 自动检测中文字体
2. 绘制价格线和均线
3. 标注吸筹/派发区间
4. 标注阶段划分
5. 标注关键事件
"""
import os
platform_module = None
try:
    import platform as _platform
    platform_module = _platform
except ImportError:
    pass

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib import font_manager
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime

from .wyckoff import WyckoffStructure, WyckoffEvent, MarketPhase


class WyckoffChartRenderer:
    """威科夫图表绘制器"""

    # 中文字体候选列表（按优先级）
    CHINESE_FONTS = [
        "SimHei",                    # Windows 黑体
        "Microsoft YaHei",           # Windows 微软雅黑
        "PingFang SC",               # Mac 苹方
        "Heiti SC",                  # Mac 黑体
        "STHeiti",                   # Mac 华文黑体
        "WenQuanYi Micro Hei",       # Linux 文泉驿微米黑
        "Noto Sans CJK SC",          # Google Noto
        "Source Han Sans SC",        # Adobe 思源黑体
    ]

    # 颜色配置
    COLORS = {
        "price": "black",
        "ma50": "blue",
        "ma200": "red",
        "accumulation": (0, 0.8, 0, 0.15),      # 淡绿色
        "distribution": (0.8, 0, 0, 0.15),      # 淡红色
        "phase_divider": (0, 0, 0, 0.5),        # 半透明黑色
        "annotation_bg": "white",
        "annotation_border": "black",
    }

    def __init__(self, figsize: tuple = (14, 8)):
        """
        初始化绘制器

        Args:
            figsize: 图表尺寸 (宽, 高)
        """
        self.figsize = figsize
        self.chinese_font = self._detect_chinese_font()

        # 设置全局字体
        if self.chinese_font:
            plt.rcParams['font.sans-serif'] = [self.chinese_font, 'DejaVu Sans']
        else:
            print("警告: 未找到中文字体，中文显示可能异常")
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

        plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

    def render(
        self,
        df: pd.DataFrame,
        structure: WyckoffStructure,
        output_path: str,
        title: Optional[str] = None
    ) -> str:
        """
        绘制威科夫图表

        Args:
            df: 历史行情数据，需包含 date, close, ma50, ma200 列
            structure: 威科夫分析结构
            output_path: 输出图片路径
            title: 图表标题（可选）

        Returns:
            实际输出的文件路径
        """
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # 准备数据
        plot_df = self._prepare_data(df)

        # 创建图表
        fig, ax = plt.subplots(figsize=self.figsize)

        # 绘制各层
        self._plot_zones(ax, plot_df, structure)
        self._plot_price_and_ma(ax, plot_df)
        self._plot_phase_dividers(ax, plot_df, structure)
        self._plot_event_annotations(ax, plot_df, structure)
        self._plot_current_price_line(ax, plot_df)

        # 设置标题
        if title is None:
            phase_name = structure.market_phase.value
            title = f"威科夫分析 - {phase_name}"
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        # 设置格式
        self._setup_axes(ax, plot_df)

        # 添加图例
        self._add_legend(ax)

        # 保存图片
        plt.tight_layout()
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close(fig)

        return output_path

    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备绘图数据"""
        plot_df = df.copy()

        # 确保日期格式
        if 'date' in plot_df.columns:
            plot_df['date'] = pd.to_datetime(plot_df['date'])
            plot_df = plot_df.sort_values('date').reset_index(drop=True)

        # 转换数值类型
        for col in ['close', 'ma50', 'ma200']:
            if col in plot_df.columns:
                plot_df[col] = pd.to_numeric(plot_df[col], errors='coerce')

        # 只取最近 500 天数据
        if len(plot_df) > 500:
            plot_df = plot_df.tail(500).reset_index(drop=True)

        return plot_df

    def _detect_chinese_font(self) -> Optional[str]:
        """
        检测系统中可用的中文字体

        Returns:
            可用的中文字体名称，或 None
        """
        available_fonts = {f.name for f in font_manager.fontManager.ttflist}

        for font_name in self.CHINESE_FONTS:
            if font_name in available_fonts:
                print(f"使用中文字体: {font_name}")
                return font_name

        # 尝试系统特定路径
        system = platform_module.system() if platform_module else ""

        if system == "Windows":
            windows_fonts = [
                "C:\\Windows\\Fonts\\msyh.ttc",      # 微软雅黑
                "C:\\Windows\\Fonts\\simhei.ttf",    # 黑体
                "C:\\Windows\\Fonts\\simsun.ttc",    # 宋体
            ]
            for font_path in windows_fonts:
                if os.path.exists(font_path):
                    font_prop = font_manager.FontProperties(fname=font_path)
                    return font_prop.get_name()

        elif system == "Darwin":  # macOS
            mac_fonts = [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
            ]
            for font_path in mac_fonts:
                if os.path.exists(font_path):
                    font_prop = font_manager.FontProperties(fname=font_path)
                    return font_prop.get_name()

        return None

    def _plot_zones(
        self,
        ax,
        df: pd.DataFrame,
        structure: WyckoffStructure
    ) -> None:
        """绘制吸筹/派发区间阴影"""
        if len(df) < 10:
            return

        x_min = 0
        x_max = len(df) - 1
        y_min = df['close'].min()
        y_max = df['close'].max()

        # 绘制吸筹区
        if structure.accumulation_zone:
            zone_low, zone_high = structure.accumulation_zone

            # 找到区间的时间范围
            sc_events = [e for e in structure.events if e['type'] == WyckoffEvent.SC]
            sos_events = [e for e in structure.events if e['type'] == WyckoffEvent.SOS]

            if sc_events:
                # 找到SC的索引
                sc_date = pd.to_datetime(sc_events[0]['date'])
                x_start = self._find_date_index(df, sc_date)

                if sos_events:
                    sos_date = pd.to_datetime(sos_events[0]['date'])
                    x_end = self._find_date_index(df, sos_date)
                else:
                    x_end = len(df) - 1

                # 绘制阴影
                rect = Rectangle(
                    (x_start, zone_low),
                    x_end - x_start,
                    zone_high - zone_low,
                    facecolor=self.COLORS['accumulation'],
                    edgecolor='none',
                    zorder=1
                )
                ax.add_patch(rect)

                # 添加标签
                ax.text(
                    (x_start + x_end) / 2,
                    zone_high + (y_max - y_min) * 0.02,
                    "吸筹区",
                    ha='center',
                    va='bottom',
                    fontsize=10,
                    color='green',
                    fontweight='bold',
                    zorder=3
                )

        # 绘制派发区
        if structure.distribution_zone:
            zone_low, zone_high = structure.distribution_zone

            # 找到派发区的时间范围
            ut_events = [e for e in structure.events if e['type'] == WyckoffEvent.UT]
            sow_events = [e for e in structure.events if e['type'] == WyckoffEvent.SOW]

            if ut_events:
                ut_date = pd.to_datetime(ut_events[0]['date'])
                x_start = self._find_date_index(df, ut_date)

                if sow_events:
                    sow_date = pd.to_datetime(sow_events[0]['date'])
                    x_end = self._find_date_index(df, sow_date)
                else:
                    x_end = len(df) - 1

                # 绘制阴影
                rect = Rectangle(
                    (x_start, zone_low),
                    x_end - x_start,
                    zone_high - zone_low,
                    facecolor=self.COLORS['distribution'],
                    edgecolor='none',
                    zorder=1
                )
                ax.add_patch(rect)

                # 添加标签
                ax.text(
                    (x_start + x_end) / 2,
                    zone_high + (y_max - y_min) * 0.02,
                    "派发区",
                    ha='center',
                    va='bottom',
                    fontsize=10,
                    color='red',
                    fontweight='bold',
                    zorder=3
                )

    def _plot_price_and_ma(self, ax, df: pd.DataFrame) -> None:
        """绘制价格线和均线"""
        x = np.arange(len(df))

        # 收盘价
        ax.plot(
            x,
            df['close'],
            color=self.COLORS['price'],
            linewidth=1.5,
            label='收盘价',
            zorder=2
        )

        # MA50
        if 'ma50' in df.columns:
            ax.plot(
                x,
                df['ma50'],
                color=self.COLORS['ma50'],
                linewidth=1,
                linestyle='--',
                label='MA50',
                zorder=2
            )

        # MA200
        if 'ma200' in df.columns:
            ax.plot(
                x,
                df['ma200'],
                color=self.COLORS['ma200'],
                linewidth=1,
                linestyle='--',
                label='MA200',
                zorder=2
            )

    def _plot_phase_dividers(
        self,
        ax,
        df: pd.DataFrame,
        structure: WyckoffStructure
    ) -> None:
        """绘制阶段划分线"""
        if not structure.phases:
            return

        y_min = df['close'].min()
        y_max = df['close'].max()

        for phase in structure.phases:
            # 找到阶段对应的索引
            start_date = pd.to_datetime(phase.start_date)
            x_start = self._find_date_index(df, start_date)

            # 绘制竖线
            ax.axvline(
                x=x_start,
                color=self.COLORS['phase_divider'],
                linestyle=':',
                linewidth=1.5,
                zorder=1
            )

            # 添加阶段名称标注
            y_label = y_max + (y_max - y_min) * 0.05

            # 根据阶段位置调整标签位置，避免重叠
            phase_labels = {
                "Phase A": (0.02, 0.98),
                "Phase B": (0.15, 0.98),
                "Phase C": (0.28, 0.98),
                "Phase D": (0.41, 0.98),
                "Phase E": (0.54, 0.98),
            }

            x_offset, y_offset = phase_labels.get(phase.name, (0.02, 0.98))

            ax.text(
                x_start + (len(df) * x_offset),
                y_max + (y_max - y_min) * y_offset,
                phase.name,
                ha='left',
                va='bottom',
                fontsize=11,
                color='darkred',
                fontweight='bold',
                zorder=3
            )

    def _plot_event_annotations(
        self,
        ax,
        df: pd.DataFrame,
        structure: WyckoffStructure
    ) -> None:
        """标注关键事件"""
        if not structure.events:
            return

        y_min = df['close'].min()
        y_max = df['close'].max()
        y_range = y_max - y_min

        # 已标注的位置（避免重叠）
        annotated_positions = []

        # 关键事件优先级
        priority_events = [
            WyckoffEvent.SC,
            WyckoffEvent.SPRING,
            WyckoffEvent.SOS,
            WyckoffEvent.LPS,
            WyckoffEvent.UTAD,
            WyckoffEvent.BC,
            WyckoffEvent.SOW,
        ]

        # 按优先级排序事件
        sorted_events = sorted(
            structure.events,
            key=lambda e: (
                priority_events.index(e['type']) if e['type'] in priority_events else 999,
                e['index']
            )
        )

        for event in sorted_events[:15]:  # 最多标注15个事件
            event_date = pd.to_datetime(event['date'])
            x_pos = self._find_date_index(df, event_date)
            y_pos = float(event['price'])

            # 检查是否与已有标注重叠
            if self._is_overlapping(x_pos, annotated_positions, df):
                continue

            # 生成标签
            label = self._generate_event_label(event)

            # 确定标签位置（智能布局）
            label_y = self._calculate_label_y(
                y_pos, y_min, y_max, y_range, annotated_positions
            )

            # 绘制箭头和标签
            self._draw_annotation(ax, x_pos, y_pos, label_y, label)

            # 记录已标注位置
            annotated_positions.append((x_pos, label_y))

    def _generate_event_label(self, event: Dict[str, Any]) -> str:
        """生成事件标签（威科夫语气）"""
        event_type = event['type']
        price = float(event['price'])

        labels = {
            WyckoffEvent.SC: f"SC 恐慌抛售\n${price:.2f} | 大量供应涌现",
            WyckoffEvent.AR: f"AR 自动反弹\n${price:.2f} | 定义区间上沿",
            WyckoffEvent.ST: f"ST 二次测试\n${price:.2f} | 确认供应枯竭",
            WyckoffEvent.SPRING: f"Spring 弹簧\n${price:.2f} | 震出最后止损",
            WyckoffEvent.SOS: f"SOS 强势信号\n${price:.2f} | 需求主导市场",
            WyckoffEvent.LPS: f"LPS 最后支撑\n${price:.2f} | 健康回踩确认",
            WyckoffEvent.JAC: f"JAC 跨越小溪\n${price:.2f} | 突破关键阻力",
            WyckoffEvent.UT: f"UT 上冲\n${price:.2f} | 测试供给反应",
            WyckoffEvent.UTAD: f"UTAD 上冲回落\n${price:.2f} | 派发加速信号",
            WyckoffEvent.LPSY: f"LPSY 最后供应\n${price:.2f} | 弱势信号确认",
            WyckoffEvent.SOW: f"SOW 弱势信号\n${price:.2f} | 需求不足",
            WyckoffEvent.BC: f"BC 抢购高潮\n${price:.2f} | 主力开始派发",
            WyckoffEvent.TEST: f"Test 测试\n${price:.2f} | 验证支撑",
        }

        return labels.get(event_type, f"{event_type.value}\n${price:.2f}")

    def _draw_annotation(
        self,
        ax,
        x_pos: float,
        y_pos: float,
        label_y: float,
        label: str
    ) -> None:
        """绘制单个标注"""
        # 绘制箭头
        ax.annotate(
            "",
            xy=(x_pos, y_pos),
            xytext=(x_pos, label_y),
            arrowprops=dict(
                arrowstyle="->",
                color='black',
                lw=0.8,
                alpha=0.7
            ),
            zorder=4
        )

        # 绘制文本框
        bbox_props = dict(
            boxstyle="round,pad=0.4",
            facecolor=self.COLORS['annotation_bg'],
            edgecolor=self.COLORS['annotation_border'],
            linewidth=0.8,
            alpha=0.9
        )

        ax.text(
            x_pos,
            label_y,
            label,
            ha='center',
            va='bottom' if label_y > y_pos else 'top',
            fontsize=8,
            bbox=bbox_props,
            zorder=5
        )

    def _calculate_label_y(
        self,
        y_pos: float,
        y_min: float,
        y_max: float,
        y_range: float,
        annotated_positions: List[tuple]
    ) -> float:
        """计算标签位置（智能布局）"""
        # 默认在价格上方
        offset = y_range * 0.08
        label_y = y_pos + offset

        # 如果超出上限，尝试放在下方
        if label_y > y_max * 0.95:
            label_y = y_pos - offset

        # 简单避免重叠：检查与已有标签的距离
        for _, existing_y in annotated_positions:
            if abs(label_y - existing_y) < y_range * 0.05:
                # 调整位置
                if label_y > y_pos:
                    label_y = existing_y - y_range * 0.06
                else:
                    label_y = existing_y + y_range * 0.06

        return label_y

    def _is_overlapping(
        self,
        x_pos: float,
        annotated_positions: List[tuple],
        df: pd.DataFrame
    ) -> bool:
        """检查标注是否重叠"""
        threshold = len(df) * 0.03  # 3% 的数据范围作为阈值

        for existing_x, _ in annotated_positions:
            if abs(x_pos - existing_x) < threshold:
                return True
        return False

    def _plot_current_price_line(self, ax, df: pd.DataFrame) -> None:
        """绘制当前价格线"""
        current_price = df['close'].iloc[-1]
        ax.axhline(
            y=current_price,
            color='gray',
            linestyle='-',
            linewidth=0.8,
            alpha=0.5,
            zorder=1
        )

    def _setup_axes(self, ax, df: pd.DataFrame) -> None:
        """设置坐标轴格式"""
        # 设置 X 轴为日期格式
        if 'date' in df.columns:
            # 选择合适的日期间隔
            num_ticks = min(10, len(df))
            interval = max(1, len(df) // num_ticks)

            tick_indices = range(0, len(df), interval)
            tick_labels = [
                df['date'].iloc[i].strftime('%Y-%m-%d')
                for i in tick_indices
            ]

            ax.set_xticks(tick_indices)
            ax.set_xticklabels(tick_labels, rotation=30, ha='right')

        ax.set_xlabel('日期', fontsize=11)
        ax.set_ylabel('价格', fontsize=11)

        # 设置网格
        ax.grid(True, alpha=0.3, linestyle='--')

    def _add_legend(self, ax) -> None:
        """添加图例"""
        ax.legend(
            loc='upper left',
            framealpha=0.9,
            fontsize=10
        )

    def _find_date_index(self, df: pd.DataFrame, target_date) -> int:
        """查找日期在数据框中的索引"""
        try:
            target_date = pd.to_datetime(target_date)
            # 找到最接近的日期
            distances = abs(pd.to_datetime(df['date']) - target_date)
            return distances.idxmin()
        except:
            return len(df) // 2  # 默认返回中间位置
