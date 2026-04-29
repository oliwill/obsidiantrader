#!/usr/bin/env python3
"""
定时任务: 扫描 Inbox 并处理待分析材料

用法:
    python scripts/scan_inbox.py              # 扫描并处理
    python scripts/scan_inbox.py --dry-run    # 只扫描，不处理
    python scripts/scan_inbox.py --notify     # 处理完成后发送通知

被 launchd/cron 调用:
    * * * * * cd /path/to/trader-obsidian && python scripts/scan_inbox.py --notify
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# 导入统一配置（config.py 会自动加载 .env）
from config import Config

from inbox_scanner import scan_inbox, get_pending_analysis, mark_processed
from run_analysis import load_wiki_context, load_inbox_materials
from data.analysis_pipeline import generate_analysis
from notification import notify, notify_success, notify_error


def process_pending_items(dry_run: bool = False) -> dict:
    """
    处理 Inbox 中所有待分析的材料

    Returns:
        {"processed": int, "skipped": int, "errors": int, "details": [...]}
    """
    pending = get_pending_analysis()

    if not pending:
        return {"processed": 0, "skipped": 0, "errors": 0, "details": []}

    results = {"processed": 0, "skipped": 0, "errors": 0, "details": []}

    for item in pending:
        detail = {
            "filename": item.filename,
            "title": item.title,
            "codes": item.stock_codes,
            "status": "pending",
        }

        if not item.stock_codes:
            detail["status"] = "skipped_no_codes"
            results["skipped"] += 1
            results["details"].append(detail)
            continue

        if dry_run:
            detail["status"] = "dry_run"
            results["details"].append(detail)
            continue

        # 对每个股票代码获取数据
        for code in item.stock_codes:
            try:
                market_data = generate_analysis(code)
                wiki_ctx = load_wiki_context(code)
                materials = load_inbox_materials(code)

                detail["status"] = "data_fetched"
                detail["market_data_ok"] = "error" not in market_data

                # 注意: 这里只是获取数据，真正的分析需要 Claude Code 来做
                # 自动化模式下，可以调用 analyzer 模块做基础分析
                # 但为了保持灵活性，这里只收集数据并标记为已处理
                # 复杂分析留给 Claude Code 手动触发

            except Exception as e:
                detail["status"] = "error"
                detail["error"] = str(e)
                results["errors"] += 1

        if detail["status"] != "error":
            # 标记为已处理
            try:
                mark_processed(item)
                results["processed"] += 1
            except Exception as e:
                detail["status"] = "error"
                detail["error"] = str(e)
                results["errors"] += 1

        results["details"].append(detail)

    return results


def main():
    parser = argparse.ArgumentParser(description="Inbox Scanner - Scheduled Task")
    parser.add_argument("--dry-run", action="store_true", help="只扫描，不处理")
    parser.add_argument("--notify", action="store_true", help="发送 macOS 通知")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    start_time = datetime.now()
    results = process_pending_items(dry_run=args.dry_run)
    elapsed = (datetime.now() - start_time).total_seconds()

    # 输出结果
    summary = (
        f"Inbox 扫描完成 | "
        f"处理: {results['processed']} | "
        f"跳过: {results['skipped']} | "
        f"错误: {results['errors']} | "
        f"耗时: {elapsed:.1f}s"
    )

    if args.json:
        results["elapsed_seconds"] = elapsed
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(summary)

    # 通知
    if args.notify:
        if results["errors"] > 0:
            notify_error("Inbox 扫描", summary)
        elif results["processed"] > 0:
            notify_success("Inbox 扫描", summary)
        else:
            notify("Inbox 扫描", "无待处理材料")

    # 返回码: 有错误返回 1
    return 1 if results["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
