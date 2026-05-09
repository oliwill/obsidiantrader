"""
Memory 模块工具函数

包含路径处理、时间格式化、文件 I/O 等辅助功能
"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

# 导入统一配置
from config import Config


# ========== 路径工具 ==========

def _ensure_dirs() -> None:
    """确保必要的目录存在"""
    Config.get_wiki_dir().mkdir(parents=True, exist_ok=True)
    Config.get_materials_dir().mkdir(parents=True, exist_ok=True)


def _stock_wiki_path(stock_code: str) -> Path:
    """
    获取股票 Wiki 文件路径

    Args:
        stock_code: 股票代码（如 "AAPL.US"）

    Returns:
        Wiki 文件的完整路径

    Note:
        将 . 和 / 都替换为 _，保持与 Obsidian 现有命名一致（如 AAPL_US.md）
    """
    filename = stock_code.replace('/', '_').replace('.', '_') + ".md"
    return Config.get_wiki_dir() / filename


def _stock_materials_dir(stock_code: str) -> Path:
    """
    获取股票资料目录路径

    Args:
        stock_code: 股票代码

    Returns:
        资料目录的完整路径
    """
    dirname = stock_code.replace('/', '_').replace('.', '_')
    return Config.get_materials_dir() / dirname


# ========== 时间工具 ==========

def _now() -> str:
    """当前时间戳（完整）"""
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def _today() -> str:
    """今天的日期"""
    return datetime.now().strftime('%Y-%m-%d')


def _today_compact() -> str:
    """今天的日期（紧凑格式）"""
    return datetime.now().strftime('%Y%m%d')


def _short_id() -> str:
    """生成短 ID"""
    return str(uuid.uuid4())[:8]


# ========== 文件 I/O 工具 ==========

def _read_file(path: Path) -> str:
    """
    读取文件内容

    Args:
        path: 文件路径

    Returns:
        文件内容，如果文件不存在返回空字符串
    """
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_file(path: Path, content: str) -> None:
    """
    写入文件内容

    Args:
        path: 文件路径
        content: 文件内容
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_file(path: Path, content: str) -> None:
    """
    追加内容到文件

    Args:
        path: 文件路径
        content: 要追加的内容
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(content)


def _parse_frontmatter(text: str) -> Dict[str, str]:
    """
    解析 Markdown frontmatter

    Args:
        text: Markdown 文本

    Returns:
        frontmatter 字典
    """
    if not text.startswith('---'):
        return {}

    try:
        # 找到第二个 ---
        end = text.find('---', 3)
        if end == -1:
            return {}

        fm_text = text[3:end].strip()
        result = {}
        for line in fm_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
        return result
    except Exception:
        return {}
