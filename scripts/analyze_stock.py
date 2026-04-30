#!/usr/bin/env python3
"""
股票分析脚本 - 将分析结果写入 Obsidian

用法: python scripts/analyze_stock.py INVZ

整合了 report_generator.py，统一生成格式化报告
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from run_analysis import write_analysis_to_obsidian
from data.analysis_pipeline import generate_analysis
from analyzer.report_generator import ReportGenerator
from data.manager import DataManager


def generate_wyckoff_chart(stock_code: str, df, market_data: dict) -> None:
    """
    生成威科夫图表并保存到 Obsidian Charts 目录

    Args:
        stock_code: 股票代码
        df: K线数据 DataFrame
        market_data: 市场数据字典
    """
    try:
        from analyzer.wyckoff import WyckoffAnalyzer
        from analyzer.wyckoff_chart import WyckoffChartRenderer

        # 运行威科夫分析获取完整结构
        wa = WyckoffAnalyzer()
        fund_data = market_data.get('fundamentals', {})
        wyckoff_result = wa.analyze(df.reset_index(), fund_data)

        # 获取完整结构
        structure = wyckoff_result.details.get('structure')
        if not structure or not structure.phases:
            print("威科夫结构不完整，跳过图表生成")
            return

        # 确定输出路径
        from dotenv import load_dotenv
        load_dotenv()

        wiki_base = os.getenv('WIKI_BASE_DIR')
        if not wiki_base:
            print("未设置 WIKI_BASE_DIR，跳过图表生成")
            return

        charts_dir = Path(wiki_base) / "Charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名（将 . 替换为 _）
        safe_code = stock_code.replace('.', '_')
        output_path = charts_dir / f"{safe_code}_wyckoff.png"

        # 绘制图表
        renderer = WyckoffChartRenderer()
        renderer.render(
            df=df,
            structure=structure,
            output_path=str(output_path),
            title=f"{stock_code} 威科夫分析"
        )

        print(f"威科夫图表已生成: {output_path}")

    except ImportError as e:
        print(f"威科夫图表模块不可用: {e}")
    except Exception as e:
        print(f"生成威科夫图表失败: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_stock.py <STOCK_CODE>")
        sys.exit(1)

    stock_code = sys.argv[1]

    # 获取分析数据
    market_data = generate_analysis(stock_code)

    # 运行基本面分析（补充护城河评分）
    try:
        from analyzer.fundamental import FundamentalAnalyzer
        import pandas as pd
        fa = FundamentalAnalyzer()
        fund_result = fa.analyze(
            pd.DataFrame(),
            market_data.get('fundamentals', {})
        )
        # 将护城河分析结果合并到 fundamentals
        if 'business' in fund_result.details:
            market_data['fundamentals']['moat'] = fund_result.details['business'].get('moat')
            market_data['fundamentals']['moat_indicators'] = fund_result.details['business'].get('moat_indicators', [])
    except Exception as e:
        print(f"护城河分析失败（跳过）: {e}")

    # 生成威科夫图表
    try:
        dm = DataManager()
        df = dm.get_historical_data(stock_code, period="2y")  # 获取 2 年数据用于威科夫分析
        if df is not None and len(df) > 100:  # 至少需要 100 天数据
            generate_wyckoff_chart(stock_code, df, market_data)
    except Exception as e:
        print(f"威科夫图表生成失败（跳过）: {e}")

    # 提取关键信息
    stock_info = market_data.get('stock_info', {})
    stock_name = stock_info.get('name', 'Unknown')
    price = stock_info.get('price', 0)
    fundamentals = market_data.get('fundamentals', {})
    earnings = market_data.get('earnings', {})
    liquidity = market_data.get('liquidity', {})
    options = market_data.get('options', {})
    peers = market_data.get('peers', [])
    web_search = market_data.get('web_search', {})

    # 使用统一报告生成器
    analysis_text = ReportGenerator.generate(stock_code, market_data)

    # 评分和核心观点
    score = market_data.get('wyckoff_score', 0)
    target_mean = fundamentals.get('target_mean_price', 0)
    potential = (target_mean / price - 1) * 100 if price > 0 and target_mean > 0 else 0

    core_view = f'分析师目标价 ${target_mean:.2f} vs 当前 ${price:.2f} (潜在 {potential:+.1f}%)'

    # 信号
    signals = [
        f"评分 {score}/100",
        f"潜在涨幅 {potential:+.1f}%",
        f"Put/Call {options.get('put_call_ratio', 0):.2f}"
    ]

    # 写入 Obsidian
    write_analysis_to_obsidian(
        stock_code=stock_code,
        stock_name=stock_name,
        analysis_text=analysis_text,
        score=score,
        signals=signals,
        core_view=core_view,
        price=price,
        earnings=earnings,
        liquidity=liquidity,
        options=options,
        peers=peers,
        web_search=web_search,
    )


if __name__ == '__main__':
    main()
