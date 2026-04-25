#!/usr/bin/env python3
"""
定时任务: 更新 Dashboard

用法:
    python scripts/update_dashboard.py          # 更新 Dashboard
    python scripts/update_dashboard.py --notify # 发送通知

被 launchd/cron 调用 (建议每天 8:00):
    0 8 * * * cd /path/to/trader-obsidian && python scripts/update_dashboard.py --notify
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv()

from run_analysis import update_dashboard
from notification import notify, notify_success, notify_error


def main():
    parser = argparse.ArgumentParser(description="Update Dashboard - Scheduled Task")
    parser.add_argument("--notify", action="store_true", help="发送 macOS 通知")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    start_time = datetime.now()

    try:
        update_dashboard()
        elapsed = (datetime.now() - start_time).total_seconds()

        dashboard_path = os.getenv("OBSIDIAN_DASHBOARD_PATH", "")
        result = {
            "success": True,
            "dashboard_path": dashboard_path,
            "elapsed_seconds": elapsed,
            "timestamp": datetime.now().isoformat(),
        }

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Dashboard updated: {dashboard_path} ({elapsed:.1f}s)")

        if args.notify:
            notify_success("Dashboard 更新", f"已更新至 {dashboard_path}")

        return 0

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        result = {
            "success": False,
            "error": str(e),
            "elapsed_seconds": elapsed,
            "timestamp": datetime.now().isoformat(),
        }

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Dashboard update failed: {e}")

        if args.notify:
            notify_error("Dashboard 更新失败", str(e))

        return 1


if __name__ == "__main__":
    sys.exit(main())
