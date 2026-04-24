#!/usr/bin/env python3
"""
Obsidian Inbox 扫描器

职责：
  - 扫描 Obsidian Inbox/ 目录中的 .md 文件
  - 解析 frontmatter，检测 analyze: true 标志
  - 从正文提取股票代码
  - 标记已处理的文件

Claude Code 调用方式：
  - `python inbox_scanner.py` — 打印所有带股票代码的文件
  - `python inbox_scanner.py --pending` — 只打印 analyze: true 的文件
  - `python inbox_scanner.py --mark <filepath>` — 标记文件为已处理
"""
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

# ========== 路径配置 ==========

INBOX_DIR = Path(os.getenv("OBSIDIAN_INBOX_DIR", ""))
DATA_MANAGER_IMPORT = "from data.manager import DataManager"


# ========== 数据结构 ==========


@dataclass
class InboxItem:
    """收件箱中的单个材料"""
    path: Path                              # 绝对路径
    filename: str                           # 文件名
    frontmatter: Dict[str, str]             # 解析后的 frontmatter
    body: str                               # 正文内容（frontmatter 以下）
    stock_codes: List[str] = field(default_factory=list)  # 检测到的股票代码
    analyze_flag: bool = False              # frontmatter 中 analyze: true
    source_type: str = "note"               # twitter | substack | wechat | zhishixingqiu | pdf | note
    title: str = ""                         # 标题
    processed: bool = False                 # 是否已处理


# ========== 股票代码提取 ==========


# 股票代码提取模式（按优先级）
STOCK_PATTERNS = [
    # Twitter cashtag: $AAPL
    (r'\$([A-Z]{1,5})\b', lambda m: f"{m.group(1)}.US"),
    # 显式 US 格式: AAPL.US
    (r'\b([A-Z]{1,5})\.US\b', lambda m: f"{m.group(1)}.US"),
    # 显式 HK 格式: 00700.HK
    (r'\b(\d{5})\.HK\b', lambda m: f"{m.group(1)}.HK"),
    # A 股前缀: SH603906, SZ000001
    (r'\b(SH|SZ)(\d{6})\b', lambda m: f"{m.group(1)}{m.group(2)}"),
    # 纯数字 5 位 → HK: 00700
    (r'\b(\d{5})\b(?!\.HK)', lambda m: f"{m.group(1)}.HK"),
    # 纯数字 6 位 → A股: 检测前缀
    (r'\b(6\d{5})\b', lambda m: f"SH{m.group(1)}"),
    (r'\b(0\d{5})\b', lambda m: f"SZ{m.group(1)}"),
    (r'\b(3\d{5})\b', lambda m: f"SZ{m.group(1)}"),
    # 大写字母序列（可能是美股代码）
    (r'\b([A-Z]{2,5})\b(?!\.US)', None),  # 需要过滤常见词
]

# 停止词：常见大写缩写，不作为股票代码
STOPWORDS = {
    "I", "A", "THE", "IN", "OF", "AND", "OR", "IS", "AT", "TO", "BY", "MY", "PM", "AM",
    "US", "UK", "AI", "CEO", "CFO", "CTO", "COO", "ETF", "IPO", "USD", "HKD", "CNY",
    "YTD", "EPS", "PE", "PB", "ROE", "ROI", "KPI", "Q1", "Q2", "Q3", "Q4", "FY", "BPS",
    "TL", "DR", "NOTE", "EDIT", "TODO", "FAQ", "PDF", "URL", "HTTP", "HTTPS",
}


def extract_stock_codes(text: str) -> List[str]:
    """
    从文本中提取股票代码

    Returns:
        规范化后的股票代码列表
    """
    if not text:
        return []

    codes = set()
    text_upper = text.upper()

    # 1. 先用显式模式提取
    for pattern in STOCK_PATTERNS[:6]:  # 前 6 个是显式格式
        regex = pattern[0]
        if pattern[1]:
            for match in re.finditer(regex, text_upper):
                code = pattern[1](match)
                codes.add(code)

    # 2. 再用大写字母模式，过滤停止词
    for match in re.finditer(STOCK_PATTERNS[-1][0], text):
        word = match.group(1)
        if word not in STOPWORDS:
            # 简单判断：可能是美股
            codes.add(f"{word}.US")

    # 3. 规范化（如果可以的话，这里直接返回）
    return sorted(list(codes))


# ========== Frontmatter 解析 ==========


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """
    解析 YAML frontmatter

    Returns:
        (frontmatter_dict, body_text)
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    frontmatter = {}
    for line in text[3:end].strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()
            # 处理布尔值
            if val.lower() in ("true", "yes"):
                val = True
            elif val.lower() in ("false", "no"):
                val = False
            frontmatter[key] = val

    body = text[end + 3:].lstrip()
    return frontmatter, body


# ========== 核心功能 ==========


def scan_inbox() -> List[InboxItem]:
    """
    扫描 Inbox 目录，返回所有相关材料

    Returns:
        InboxItem 列表（有 stock_codes 或 analyze_flag 的文件）
    """
    if not INBOX_DIR.exists():
        return []

    results = []
    for md_file in INBOX_DIR.glob("*.md"):
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = parse_frontmatter(text)

        # 检测 analyze 标志
        analyze_flag = frontmatter.get("analyze", False)

        # 提取股票代码
        codes = []

        # 优先从 frontmatter 的 ticker 字段获取
        if "ticker" in frontmatter:
            ticker = frontmatter["ticker"]
            if isinstance(ticker, str) and ticker:
                codes = [ticker.upper()]

        # 如果没有 ticker，从正文提取
        if not codes:
            # 从标题提取
            title = frontmatter.get("title", "")
            codes.extend(extract_stock_codes(title))
            # 从正文提取
            codes.extend(extract_stock_codes(body))
            # 从 tags 提取
            tags = frontmatter.get("tags", "")
            if isinstance(tags, str):
                codes.extend(extract_stock_codes(tags))

        # 去重
        codes = list(dict.fromkeys(codes))

        # 只返回有股票代码或需要分析的文件
        if codes or analyze_flag:
            results.append(InboxItem(
                path=md_file,
                filename=md_file.name,
                frontmatter=frontmatter,
                body=body,
                stock_codes=codes,
                analyze_flag=analyze_flag,
                source_type=frontmatter.get("source", "note"),
                title=frontmatter.get("title", md_file.stem),
                processed=frontmatter.get("processed", False) is True,
            ))

    return results


def get_pending_analysis() -> List[InboxItem]:
    """
    返回所有待处理的文件（analyze: true 且未标记 processed）

    Returns:
        InboxItem 列表
    """
    all_items = scan_inbox()
    return [item for item in all_items if item.analyze_flag and not item.processed]


def get_related_materials(stock_code: str) -> List[InboxItem]:
    """
    返回与某股票相关的所有 Inbox 材料

    Args:
        stock_code: 股票代码（支持部分匹配，如 "AAPL" 能匹配 "AAPL.US"）

    Returns:
        InboxItem 列表，按时间倒序
    """
    all_items = scan_inbox()
    code_upper = stock_code.upper().replace(".", "").replace("_", "")

    related = []
    for item in all_items:
        for code in item.stock_codes:
            item_code_upper = code.upper().replace(".", "").replace("_", "")
            if code_upper in item_code_upper or item_code_upper in code_upper:
                related.append(item)
                break

    # 按文件名排序（文件名通常包含日期）
    related.sort(key=lambda x: x.filename, reverse=True)
    return related


def mark_processed(item: InboxItem):
    """
    标记文件为已处理（在 frontmatter 中添加 processed: true 和 processed_at）

    Args:
        item: InboxItem 对象
    """
    text = item.path.read_text(encoding="utf-8")

    # 解析现有的 frontmatter
    frontmatter, body = parse_frontmatter(text)

    # 更新 frontmatter
    frontmatter["processed"] = True
    frontmatter["processed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 重建文件
    new_frontmatter = "---\n"
    for key, val in frontmatter.items():
        if isinstance(val, bool):
            val = "true" if val else "false"
        elif isinstance(val, str) and val:
            pass  # 保持原样
        else:
            val = str(val)
        new_frontmatter += f"{key}: {val}\n"

    new_content = new_frontmatter + "---\n\n" + body
    item.path.write_text(new_content, encoding="utf-8")

    print(f"Marked as processed: {item.filename}")


# ========== CLI 入口 ==========


def print_items(items: List[InboxItem], verbose: bool = False):
    """打印 InboxItem 列表"""
    if not items:
        print("No items found.")
        return

    print(f"Found {len(items)} item(s):\n")

    for i, item in enumerate(items, 1):
        status = "✓" if item.processed else "○"
        analyze_tag = " [ANALYZE]" if item.analyze_flag else ""

        print(f"{i}. [{status}] {item.filename}{analyze_tag}")
        print(f"   Title: {item.title or '(no title)'}")
        print(f"   Source: {item.source_type}")
        print(f"   Codes: {', '.join(item.stock_codes) if item.stock_codes else '(none)'}")

        if verbose:
            print(f"   Path: {item.path}")
            print(f"   Frontmatter: {item.frontmatter}")
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Obsidian Inbox Scanner")
    parser.add_argument("--pending", action="store_true", help="只显示待处理文件")
    parser.add_argument("--related", metavar="CODE", help="显示与股票代码相关的材料")
    parser.add_argument("--mark", metavar="FILEPATH", help="标记文件为已处理")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    if args.mark:
        # 标记模式
        item_path = Path(args.mark)
        if not item_path.exists():
            print(f"Error: File not found: {args.mark}")
            sys.exit(1)

        # 读取文件构造 InboxItem
        text = item_path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        codes = []
        if "ticker" in frontmatter:
            codes = [frontmatter["ticker"]]
        if not codes:
            codes = extract_stock_codes(frontmatter.get("title", "") + body)

        item = InboxItem(
            path=item_path,
            filename=item_path.name,
            frontmatter=frontmatter,
            body=body,
            stock_codes=codes,
            analyze_flag=frontmatter.get("analyze", False),
            source_type=frontmatter.get("source", "note"),
            title=frontmatter.get("title", ""),
        )
        mark_processed(item)

    elif args.related:
        # 关联材料模式
        items = get_related_materials(args.related)
        print_items(items, verbose=args.verbose)

    elif args.pending:
        # 待处理模式
        items = get_pending_analysis()
        print_items(items, verbose=args.verbose)

    else:
        # 默认：显示所有
        items = scan_inbox()
        print_items(items, verbose=args.verbose)


if __name__ == "__main__":
    main()
