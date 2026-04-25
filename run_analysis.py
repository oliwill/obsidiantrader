#!/usr/bin/env python3
"""
主分析入口 - Claude Code 调用

用法:
  python run_analysis.py AAPL          # 分析单只股票
  python run_analysis.py 00700         # 分析港股
  python run_analysis.py --scan        # 处理 Inbox 中所有待处理文件
  python run_analysis.py --dashboard   # 只更新 Dashboard
  python run_analysis.py --inbox      # 扫描 Inbox 并显示待处理

输出:
  打印结构化数据到 stdout，Claude Code 读取后进行推理分析
  然后调用 write_* 辅助函数将结果写回 Obsidian
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# 导入本地模块
from memory.manager import MemoryManager
from inbox_scanner import (
    scan_inbox,
    get_pending_analysis,
    get_related_materials,
    mark_processed,
    InboxItem,
)

# ========== 路径配置 ==========

TASKS_DIR = Path(os.getenv("OBSIDIAN_TASKS_DIR", ""))
DASHBOARD_PATH = Path(os.getenv("OBSIDIAN_DASHBOARD_PATH", ""))
ANALYSIS_TIMEOUT = int(os.getenv("ANALYSIS_TIMEOUT", "30"))


# ========== 数据获取（子进程，带 timeout） ==========


def fetch_market_data(stock_code: str, timeout: int = ANALYSIS_TIMEOUT) -> dict:
    """
    获取市场数据（在子进程中运行，带 timeout 保护）

    Args:
        stock_code: 股票代码
        timeout: 超时秒数

    Returns:
        dict: 解析后的 JSON 数据，或错误信息
    """
    script_dir = Path(__file__).parent
    cmd = [sys.executable, "one_shot_analysis.py", stock_code]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            cwd=script_dir,
        )

        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                data["_source"] = "market_data"
                return data
            except json.JSONDecodeError as e:
                return {
                    "_source": "market_data",
                    "error": "json_parse",
                    "detail": str(e),
                    "stdout": result.stdout[:500],
                }
        else:
            return {
                "_source": "market_data",
                "error": "subprocess_error",
                "returncode": result.returncode,
                "stderr": result.stderr[:500] if result.stderr else "",
            }

    except subprocess.TimeoutExpired:
        return {
            "_source": "market_data",
            "error": "timeout",
            "stock_code": stock_code,
            "timeout_used": timeout,
            "message": f"Market data fetch timed out after {timeout}s. May have partial data from Yahoo Finance fallback.",
        }


# ========== 上下文收集 ==========


def load_wiki_context(stock_code: str) -> dict:
    """
    加载 Wiki 上下文

    Args:
        stock_code: 股票代码

    Returns:
        dict: 包含 wiki_status, wiki_summary 等
    """
    mm = MemoryManager()

    try:
        wiki = mm.get_stock_context(stock_code)
        if wiki:
            # 只取前 1000 字符作为摘要
            return {
                "_source": "wiki_context",
                "wiki_status": "HAS_HISTORY",
                "wiki_summary": wiki[:1000] if len(wiki) > 1000 else wiki,
                "wiki_length": len(wiki),
            }
        return {
            "_source": "wiki_context",
            "wiki_status": "NO_HISTORY",
            "wiki_summary": "",
        }
    except Exception as e:
        return {
            "_source": "wiki_context",
            "error": str(e),
        }


def load_inbox_materials(stock_code: str) -> List[dict]:
    """
    加载 Inbox 中与股票相关的材料

    Args:
        stock_code: 股票代码

    Returns:
        材料列表，每个包含 {filename, title, source_type, body_snippet}
    """
    items = get_related_materials(stock_code)

    materials = []
    for item in items[:20]:  # 最多返回 20 个
        # 正文取前 500 字符作为摘要
        snippet = item.body[:500] if item.body else ""
        materials.append({
            "filename": item.filename,
            "title": item.title,
            "source_type": item.source_type,
            "body_snippet": snippet,
            "stock_codes": item.stock_codes,
            "analyze_flag": item.analyze_flag,
        })

    return materials


# ========== 写回 Obsidian ==========


def write_analysis_to_obsidian(
    stock_code: str,
    stock_name: str,
    analysis_text: str,
    score: float = 0.0,
    signals: List[str] = None,
    core_view: str = "",
    price: float = 0.0,
):
    """
    将分析结果写入 Obsidian

    Args:
        stock_code: 股票代码（已规范化）
        stock_name: 股票名称
        analysis_text: 分析文本（将追加到研究笔记）
        score: 综合评分 0-100
        signals: 交易信号列表
        core_view: 核心观点（用于时间线）
    """
    mm = MemoryManager()

    # 确保 Wiki 存在
    mm.init_stock_wiki(stock_code, stock_name)

    # 更新评估表
    mm.update_evaluation_table(
        stock_code=stock_code,
        stock_name=stock_name,
        dimension="综合",
        current_judgment=f"评分 {score}/100 - {core_view or '分析完成'}",
    )

    # 追加到时间线
    mm.append_to_timeline(
        stock_code=stock_code,
        price=price,
        score=score,
        core_view=core_view,
        analysis_type="Claude Code 分析",
    )

    # 追加到研究笔记
    entry = f"\n\n### [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Claude Code 分析\n\n{analysis_text}\n"
    mm.append_to_section(stock_code, "研究笔记", entry)

    # 更新 index
    mm.update_index(stock_code, stock_name, score)

    print(f"Analysis written to Obsidian: {stock_code}")


def write_task(
    title: str,
    ticker: str,
    task_type: str = "research",
    description: str = "",
    priority: str = "medium",
    due_date: str = "",
) -> Optional[Path]:
    """
    写入任务文件到 Tasks/

    Args:
        title: 任务标题
        ticker: 股票代码
        task_type: trade | research | review | backtest
        description: 任务描述
        priority: high | medium | low
        due_date: 到期日期 YYYY-MM-DD

    Returns:
        任务文件路径，失败返回 None
    """
    if not TASKS_DIR.exists():
        TASKS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{timestamp}_{ticker}_{task_type}.md"
    filepath = TASKS_DIR / filename

    frontmatter = f"""---
ticker: {ticker}
type: {task_type}
priority: {priority}
status: pending
created: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    if due_date:
        frontmatter += f"due: {due_date}\n"

    content = f"""{frontmatter}
---

# {title}

{description}

## Checklist
- [ ] 待办事项 1
- [ ] 待办事项 2
"""

    try:
        filepath.write_text(content, encoding="utf-8")
        print(f"Task created: {filepath}")
        return filepath
    except Exception as e:
        print(f"Error creating task: {e}")
        return None


def update_dashboard():
    """
    更新 Dashboard.md

    读取：
    - Analysis/index.md（股票总览）
    - Tasks/*.md（任务统计）
    - Analysis/log.md（最近活动）

    写入：
    - Dashboard.md（汇总面板）
    """
    mm = MemoryManager()

    # 读取 index
    index = mm.get_index()

    # 统计任务
    pending_tasks = 0
    if TASKS_DIR.exists():
        for task_file in TASKS_DIR.glob("*.md"):
            text = task_file.read_text(encoding="utf-8")
            if "status: pending" in text:
                pending_tasks += 1

    # 读取最近日志
    recent_logs = mm.get_recent_log(n=5)

    # 构建 Dashboard
    dashboard = f"""# 投资分析 Dashboard

> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 概览

- **跟踪股票**: {index.count('|') if '|' in index else 0}
- **待处理任务**: {pending_tasks}

## 最近活动

"""
    for log in recent_logs:
        dashboard += f"- **{log['timestamp']}** {log['action']}\n"
        if log.get("detail"):
            dashboard += f"  - {log['detail'][:100]}...\n"

    dashboard += f"\n## 股票总览\n\n{index}\n"

    try:
        DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
        DASHBOARD_PATH.write_text(dashboard, encoding="utf-8")
        print(f"Dashboard updated: {DASHBOARD_PATH}")
    except Exception as e:
        print(f"Error updating dashboard: {e}")


# ========== 扫描模式 ==========


def scan_and_process():
    """处理 Inbox 中所有待分析的材料"""
    pending = get_pending_analysis()

    if not pending:
        print("No pending items in Inbox.")
        return

    print(f"Found {len(pending)} pending item(s) to process.\n")

    for item in pending:
        print(f"\n--- Processing: {item.filename} ---")

        # 收集股票代码
        codes = item.stock_codes
        if not codes:
            print("  No stock codes detected, skipping.")
            continue

        # 对每个代码进行分析
        for code in codes:
            print(f"\n  Analyzing {code}...")

            # 获取市场数据
            market_data = fetch_market_data(code)
            print(f"    Market data: {market_data.get('error', 'OK')}")
            if "error" in market_data:
                print(f"    Warning: {market_data.get('error', 'Unknown error')}")

            # 加载 Wiki 上下文
            wiki_context = load_wiki_context(code)
            print(f"    Wiki: {wiki_context.get('wiki_status', 'error')}")

            # 加载 Inbox 材料
            inbox_materials = load_inbox_materials(code)
            print(f"    Inbox materials: {len(inbox_materials)}")

            # 打印结构化数据供 Claude Code 使用
            print("\n    --- Data for Claude Code ---")
            print(json.dumps({
                "stock_code": code,
                "market_data": market_data,
                "wiki_context": wiki_context,
                "inbox_materials": inbox_materials,
            }, ensure_ascii=False, indent=2))

            # 这里 Claude Code 应该介入进行分析
            # 分析完成后，调用 write_analysis_to_obsidian() 写回结果
            print("\n    [Claude Code: Please perform analysis and call write_analysis_to_obsidian()]")

        # 标记为已处理
        mark_processed(item)


# ========== CLI 入口 ==========


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_analysis.py <STOCK_CODE> | --scan | --dashboard | --inbox")
        sys.exit(1)

    command = sys.argv[1]

    if command == "--scan":
        scan_and_process()

    elif command == "--dashboard":
        update_dashboard()

    elif command == "--inbox":
        # 扫描并显示 Inbox
        items = scan_inbox()
        pending = get_pending_analysis()

        print(f"\n=== Inbox Summary ===")
        print(f"Total items: {len(items)}")
        print(f"Pending analysis: {len(pending)}\n")

        if pending:
            print("Pending items:")
            for item in pending:
                codes = ", ".join(item.stock_codes) if item.stock_codes else "(none)"
                print(f"  - {item.filename}: {item.title} ({codes})")

    else:
        # 分析单只股票
        stock_code = command

        # 获取市场数据
        market_data = fetch_market_data(stock_code)
        wiki_context = load_wiki_context(stock_code)
        inbox_materials = load_inbox_materials(stock_code)

        # 打印完整上下文供 Claude Code 使用
        output = {
            "stock_code": stock_code,
            "timestamp": datetime.now().isoformat(),
            "market_data": market_data,
            "wiki_context": wiki_context,
            "inbox_materials": inbox_materials,
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
