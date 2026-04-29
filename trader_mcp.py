#!/usr/bin/env python3
"""
MCP Server for trader-obsidian

提供工具给 MCP 客户端（Claude Desktop, claudian 等）调用

运行方式：
  python trader_mcp.py

配置 Claude Desktop：
  在 Claude Desktop 设置中添加此 server 的配置
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 导入统一配置（config.py 会自动加载 .env）
from config import Config

# 添加项目路径到 sys.path
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

# 导入项目模块
from memory.manager import MemoryManager
from inbox_scanner import (
    scan_inbox,
    get_pending_analysis,
    get_related_materials,
    InboxItem,
)

# ========== MCP Server ==========

server = Server("trader-obsidian")


# ========== 工具函数 ==========


@server.tool()
async def scan_inbox_tool() -> str:
    """
    扫描 Obsidian Inbox，返回所有材料列表

    Returns:
        JSON 字符串，包含所有扫描到的材料
    """
    items = scan_inbox()

    result = {
        "count": len(items),
        "items": [
            {
                "filename": item.filename,
                "title": item.title,
                "source_type": item.source_type,
                "stock_codes": item.stock_codes,
                "analyze_flag": item.analyze_flag,
                "processed": item.processed,
                "path": str(item.path),
            }
            for item in items
        ],
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@server.tool()
async def get_pending_analysis_tool() -> str:
    """
    获取所有待处理的材料（analyze: true 且未标记 processed）

    Returns:
        JSON 字符串，包含待处理材料列表
    """
    items = get_pending_analysis()

    result = {
        "count": len(items),
        "items": [
            {
                "filename": item.filename,
                "title": item.title,
                "source_type": item.source_type,
                "stock_codes": item.stock_codes,
                "path": str(item.path),
            }
            for item in items
        ],
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@server.tool()
async def get_related_materials_tool(stock_code: str) -> str:
    """
    获取与某股票相关的所有 Inbox 材料

    Args:
        stock_code: 股票代码（如 "AAPL", "00700"）

    Returns:
        JSON 字符串，包含相关材料列表
    """
    items = get_related_materials(stock_code)

    result = {
        "stock_code": stock_code,
        "count": len(items),
        "items": [
            {
                "filename": item.filename,
                "title": item.title,
                "source_type": item.source_type,
                "body_snippet": item.body[:200] if item.body else "",
                "stock_codes": item.stock_codes,
            }
            for item in items
        ],
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@server.tool()
async def get_stock_context_tool(stock_code: str) -> str:
    """
    获取某股票的 Wiki 上下文（历史分析记录）

    Args:
        stock_code: 股票代码（如 "AAPL.US"）

    Returns:
        股票 Wiki 的完整内容
    """
    mm = MemoryManager()
    context = mm.get_stock_context(stock_code)

    if context:
        return context
    else:
        return f"No context found for {stock_code}"


@server.tool()
async def get_stock_index_tool() -> str:
    """
    获取所有跟踪股票的总览（index.md）

    Returns:
        index.md 的内容
    """
    mm = MemoryManager()
    index = mm.get_index()
    return index if index else "# Stock Index\n\nNo stocks tracked yet."


@server.tool()
async def get_recent_log_tool(n: int = 5) -> str:
    """
    获取最近 N 条操作日志

    Args:
        n: 日志条数

    Returns:
        JSON 字符串，包含最近日志
    """
    mm = MemoryManager()
    logs = mm.get_recent_log(n=n)

    result = {
        "count": len(logs),
        "logs": logs,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@server.tool()
async def analyze_stock_tool(stock_code: str) -> str:
    """
    触发股票分析（获取市场数据）

    注意：此工具只获取数据，不生成分析报告。
    分析报告需要 Claude Code 读取数据后自己生成。

    Args:
        stock_code: 股票代码

    Returns:
        JSON 字符串，包含市场数据、Wiki 上下文、Inbox 材料
    """
    from data.analysis_pipeline import generate_analysis
    from inbox_scanner import get_related_materials
    from memory.manager import MemoryManager

    try:
        # 直接调用分析流水线（不再通过 subprocess）
        market_data = generate_analysis(stock_code)
        market_data["_source"] = "mcp_analysis_pipeline"

        # 加载 Wiki 上下文
        mm = MemoryManager()
        wiki = mm.get_stock_context(stock_code)
        wiki_context = {
            "_source": "wiki_context",
            "wiki_status": "HAS_HISTORY" if wiki else "NO_HISTORY",
            "wiki_summary": wiki[:1000] if wiki else "",
            "wiki_length": len(wiki) if wiki else 0,
        }

        # 加载 Inbox 材料
        items = get_related_materials(stock_code)
        inbox_materials = [
            {
                "filename": item.filename,
                "title": item.title,
                "source_type": item.source_type,
                "body_snippet": item.body[:500] if item.body else "",
                "stock_codes": item.stock_codes,
            }
            for item in items[:20]
        ]

        result = {
            "stock_code": stock_code,
            "timestamp": datetime.now().isoformat(),
            "market_data": market_data,
            "wiki_context": wiki_context,
            "inbox_materials": inbox_materials,
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_info = {
            "error": "analysis_failed",
            "stock_code": stock_code,
            "message": str(e),
        }
        return json.dumps(error_info, ensure_ascii=False)


@server.tool()
async def write_analysis_tool(
    stock_code: str,
    stock_name: str,
    analysis_text: str,
    score: float = 0.0,
    core_view: str = "",
) -> str:
    """
    将分析结果写入 Obsidian

    Args:
        stock_code: 股票代码（已规范化，如 "AAPL.US"）
        stock_name: 股票名称
        analysis_text: 分析文本（将追加到研究笔记）
        score: 综合评分 0-100
        core_view: 核心观点（用于时间线）

    Returns:
        操作结果消息
    """
    from run_analysis import write_analysis_to_obsidian

    write_analysis_to_obsidian(
        stock_code=stock_code,
        stock_name=stock_name,
        analysis_text=analysis_text,
        score=score,
        signals=[],
        core_view=core_view,
    )

    return f"Analysis written to Obsidian for {stock_code}"


@server.tool()
async def create_task_tool(
    title: str,
    ticker: str,
    task_type: str = "research",
    description: str = "",
    priority: str = "medium",
    due_date: str = "",
) -> str:
    """
    在 Obsidian Tasks/ 中创建任务文件

    Args:
        title: 任务标题
        ticker: 股票代码
        task_type: trade | research | review | backtest
        description: 任务描述
        priority: high | medium | low
        due_date: 到期日期 YYYY-MM-DD

    Returns:
        任务文件路径或错误信息
    """
    from run_analysis import write_task

    filepath = write_task(
        title=title,
        ticker=ticker,
        task_type=task_type,
        description=description,
        priority=priority,
        due_date=due_date,
    )

    if filepath:
        return f"Task created: {filepath}"
    else:
        return "Failed to create task"


@server.tool()
async def update_dashboard_tool() -> str:
    """
    更新 Obsidian Dashboard.md

    Returns:
        操作结果消息
    """
    from run_analysis import update_dashboard

    update_dashboard()
    return f"Dashboard updated: {Config.OBSIDIAN_DASHBOARD_PATH}"


@server.tool()
async def search_stock_news_tool(stock_code: str, max_results: int = 8) -> str:
    """
    搜索股票最新新闻和动态

    Args:
        stock_code: 股票代码（如 "AAPL.US", "00700.HK"）
        max_results: 最大返回条数

    Returns:
        JSON 字符串，包含新闻列表
    """
    from data.search import StockSearchEngine

    se = StockSearchEngine()
    results = se.search_news(stock_code, max_results=max_results)

    return json.dumps(
        {
            "stock_code": stock_code,
            "category": "news",
            "count": len(results),
            "items": [r.to_dict() for r in results],
        },
        ensure_ascii=False,
        indent=2,
    )


@server.tool()
async def search_stock_sentiment_tool(stock_code: str, max_results: int = 6) -> str:
    """
    搜索股票社交媒体讨论和市场情绪

    Args:
        stock_code: 股票代码
        max_results: 最大返回条数

    Returns:
        JSON 字符串，包含讨论列表
    """
    from data.search import StockSearchEngine

    se = StockSearchEngine()
    results = se.search_sentiment(stock_code, max_results=max_results)

    return json.dumps(
        {
            "stock_code": stock_code,
            "category": "sentiment",
            "count": len(results),
            "items": [r.to_dict() for r in results],
        },
        ensure_ascii=False,
        indent=2,
    )


@server.tool()
async def search_stock_all_tool(stock_code: str) -> str:
    """
    综合搜索：新闻 + 社交 + 研报

    Args:
        stock_code: 股票代码

    Returns:
        JSON 字符串，包含三类搜索结果
    """
    from data.search import StockSearchEngine

    se = StockSearchEngine()
    results = se.search_all(stock_code)

    return json.dumps(results, ensure_ascii=False, indent=2)


# ========== 资源 ==========


@server.resource("mcp://trader/inbox")
async def inbox_resource() -> str:
    """返回 Inbox 概览"""
    items = scan_inbox()
    pending = get_pending_analysis()

    return f"""# Inbox Overview

Total items: {len(items)}
Pending analysis: {len(pending)}

## All Items
{chr(10).join(f"- {item.filename}: {item.title} ({', '.join(item.stock_codes)})" for item in items)}
"""


@server.resource("mcp://trader/stocks")
async def stocks_resource() -> str:
    """返回股票总览"""
    mm = MemoryManager()
    index = mm.get_index()

    if not index:
        return "# Stocks\n\nNo stocks tracked yet."

    return f"""# Stocks Overview

{index}
"""


# ========== Main ==========


async def main():
    """启动 MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
