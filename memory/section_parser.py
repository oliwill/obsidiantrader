"""
Markdown Section 解析器

提供在 Wiki 文件中查找、获取、替换、追加 section 的功能
"""
import re
from typing import Tuple


# ========== Section 解析 ==========

def _find_section(wiki_text: str, section_name: str) -> Tuple[int, int]:
    """
    在 Wiki 文本中定位指定 section 的位置

    Args:
        wiki_text: Wiki 文本内容
        section_name: section 名称（不含 ## 符号）

    Returns:
        (start, end) 元组，表示 section 的起始和结束位置（字符索引）
        如果找不到返回 (-1, -1)
    """
    pattern = rf'^##\s+{re.escape(section_name)}\s*$'
    match = re.search(pattern, wiki_text, flags=re.MULTILINE)

    if not match:
        return -1, -1

    start = match.start()

    # 查找下一个同级或更高级标题
    next_pattern = r'^##[^\n#]'
    next_match = re.search(next_pattern, wiki_text[start + 1:], flags=re.MULTILINE)

    if next_match:
        end = start + 1 + next_match.start()
    else:
        end = len(wiki_text)

    return start, end


def _get_section_content(wiki_text: str, section_name: str) -> str:
    """
    获取指定 section 的内容（不含标题行）

    Args:
        wiki_text: Wiki 文本内容
        section_name: section 名称

    Returns:
        section 内容，如果找不到返回空字符串
    """
    start, end = _find_section(wiki_text, section_name)

    if start == -1:
        return ""

    # 跳过标题行
    content_start = wiki_text.find('\n', start) + 1
    if content_start >= end:
        return ""

    return wiki_text[content_start:end].strip()


def _replace_section(wiki_text: str, section_name: str, new_content: str) -> str:
    """
    替换指定 section 的内容

    Args:
        wiki_text: Wiki 文本内容
        section_name: section 名称
        new_content: 新内容（不含标题行）

    Returns:
        替换后的完整 Wiki 文本
    """
    start, end = _find_section(wiki_text, section_name)

    if start == -1:
        # Section 不存在，追加到末尾
        return _append_section(wiki_text, section_name, new_content)

    # 找到标题行结束位置
    header_end = wiki_text.find('\n', start) + 1

    # 构建新文本
    prefix = wiki_text[:header_end]
    suffix = wiki_text[end:] if end < len(wiki_text) else ""

    return prefix + new_content + "\n\n" + suffix


def _append_section(wiki_text: str, section_name: str, entry: str) -> str:
    """
    追加内容到指定 section（如果 section 不存在则创建）

    Args:
        wiki_text: Wiki 文本内容
        section_name: section 名称
        entry: 要追加的内容

    Returns:
        追加后的完整 Wiki 文本
    """
    start, end = _find_section(wiki_text, section_name)

    if start == -1:
        # Section 不存在，创建新的
        return wiki_text.rstrip() + f"\n\n## {section_name}\n\n{entry}\n"

    # 找到 section 内容结束位置
    header_end = wiki_text.find('\n', start) + 1

    # 检查 section 是否为空
    section_content = wiki_text[header_end:end].strip()

    if not section_content:
        # Section 为空，直接写入
        prefix = wiki_text[:header_end]
        suffix = wiki_text[end:] if end < len(wiki_text) else ""
        return prefix + entry + "\n\n" + suffix

    # Section 有内容，追加到末尾
    prefix = wiki_text[:end]
    suffix = wiki_text[end:] if end < len(wiki_text) else ""

    return prefix.rstrip() + "\n\n" + entry + "\n\n" + suffix


def _append_to_section(wiki_text: str, section_name: str, entry: str) -> str:
    """
    向指定 section 追加一条记录（在现有内容后追加）

    Args:
        wiki_text: Wiki 文本内容
        section_name: section 名称
        entry: 要追加的条目

    Returns:
        追加后的完整 Wiki 文本
    """
    return _append_section(wiki_text, section_name, entry)
