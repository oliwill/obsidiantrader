#!/usr/bin/env python3
"""
股票分析脚本 - 将分析结果写入 Obsidian

用法: python scripts/analyze_stock.py INVZ

整合了 report_generator.py，统一生成格式化报告
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from run_analysis import write_analysis_to_obsidian
from data.analysis_pipeline import generate_analysis
from analyzer.report_generator import ReportGenerator


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_stock.py <STOCK_CODE>")
        sys.exit(1)

    stock_code = sys.argv[1]

    # 获取分析数据
    market_data = generate_analysis(stock_code)

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
