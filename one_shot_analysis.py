#!/usr/bin/env python3
"""
一次性获取所有分析数据的 CLI 入口

用法: python one_shot_analysis.py AAPL

这是一个简单的 CLI 包装器，实际逻辑在 data/analysis_pipeline.py 中
"""
import json
import sys

# 配置环境（必须在导入模块前）
sys.stdout.reconfigure(encoding='utf-8')

# 配置日志（重定向 loguru 到 stderr，避免污染 JSON stdout）
import logging
logging.basicConfig(level=logging.WARNING)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python one_shot_analysis.py STOCK_CODE'}))
        sys.exit(1)

    code = sys.argv[1]

    # 导入分析流水线（这里会自动加载环境变量）
    from data.analysis_pipeline import generate_analysis, decimal_default

    # 执行分析
    result = generate_analysis(code)

    # 输出 JSON
    print(json.dumps(result, ensure_ascii=False, indent=2, default=decimal_default))


if __name__ == '__main__':
    main()
