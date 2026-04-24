"""
材料摄入模块 — 负责摄入、tag 索引、查询

职责：
  - 接收各种来源的学习材料
  - 维护 tag 索引（tags_index.json）
  - 支持按 tag / 股票 / 关键词 查询

和 memory 的关系：
  - ingest() 内部调用 MemoryManager.save_material() 写材料和更新 Wiki
  - 额外维护一份 tag 索引，提供按 tag 查询能力
"""
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


# ========== 路径 ==========

BASE_DIR = Path(os.getenv("WIKI_BASE_DIR", "./data"))
MATERIALS_DIR = BASE_DIR / os.getenv("MATERIALS_SUBDIR", "materials")
TAGS_INDEX_PATH = BASE_DIR / "tags_index.json"

# 非个股材料的默认目录
CATEGORY_MAP = {
    "industry": "行业",
    "macro": "宏观",
    "strategy": "策略",
    "general": "通用",
}


# ========== 工具函数 ==========

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today_compact() -> str:
    return datetime.now().strftime("%Y%m%d")


def _short_id() -> str:
    return str(uuid.uuid4())[:8]


def _write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _parse_tags(raw) -> List[str]:
    """把各种格式的 tag 输入统一成 list"""
    if isinstance(raw, list):
        return [t.strip() for t in raw if t.strip()]
    if isinstance(raw, str):
        # 支持逗号、中文逗号、空格分隔
        return [t.strip() for t in re.split(r"[,\s，、]+", raw) if t.strip()]
    return []


def _resolve_material_dir(stock_code: Optional[str], category: Optional[str]) -> Path:
    """决定材料存到哪个目录"""
    if stock_code:
        safe = stock_code.replace(".", "_")
        return MATERIALS_DIR / safe
    cat = category or "general"
    return MATERIALS_DIR / cat


def _relative_path(filepath: str) -> str:
    """把绝对路径转成相对于 materials/ 的相对路径"""
    p = Path(filepath)
    try:
        return str(p.relative_to(MATERIALS_DIR)).replace("\\", "/")
    except ValueError:
        return p.name


# ========== Tag 索引 ==========

class TagsIndex:
    """维护 tag → [文件路径列表] 的映射"""

    def __init__(self):
        self._data: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        TAGS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        if TAGS_INDEX_PATH.exists():
            try:
                self._data = json.loads(TAGS_INDEX_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                self._data = {}

    def _save(self):
        TAGS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        TAGS_INDEX_PATH.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, rel_path: str, tags: List[str]):
        """给一个文件添加 tags"""
        changed = False
        for tag in tags:
            tag = tag.strip()
            if not tag:
                continue
            if tag not in self._data:
                self._data[tag] = []
            if rel_path not in self._data[tag]:
                self._data[tag].append(rel_path)
                changed = True
        if changed:
            self._save()

    def remove_file(self, rel_path: str):
        """从索引中移除某个文件"""
        changed = False
        for tag in list(self._data.keys()):
            if rel_path in self._data[tag]:
                self._data[tag].remove(rel_path)
                changed = True
                # 清理空 tag
                if not self._data[tag]:
                    del self._data[tag]
        if changed:
            self._save()

    def query(self, tags: List[str], match: str = "all") -> List[str]:
        """
        按 tag 查询文件路径列表

        match="all" → AND（文件必须包含所有 tag）
        match="any" → OR（包含任一 tag 即可）
        """
        if not tags:
            return []

        sets = []
        for tag in tags:
            paths = set(self._data.get(tag, []))
            sets.append(paths)

        if match == "any":
            result = set.union(*sets)
        else:  # all / AND
            result = set.intersection(*sets)

        return sorted(result)

    def list_tags(self) -> Dict[str, int]:
        """返回所有 tag 及其文件数量"""
        return {tag: len(paths) for tag, paths in sorted(self._data.items())}

    def rebuild(self):
        """从磁盘材料文件重建整个索引"""
        self._data = {}
        if not MATERIALS_DIR.exists():
            self._save()
            return

        for md_file in MATERIALS_DIR.rglob("*.md"):
            text = _read_file(md_file)
            if not text.startswith("---"):
                continue
            end = text.find("---", 3)
            if end == -1:
                continue

            # 解析 tags 字段
            tags_raw = ""
            for line in text[3:end].strip().split("\n"):
                if line.startswith("tags:"):
                    tags_raw = line.split(":", 1)[1].strip()
                    break

            tags = _parse_tags(tags_raw)
            if tags:
                rel = str(md_file.relative_to(MATERIALS_DIR)).replace("\\", "/")
                for tag in tags:
                    if tag not in self._data:
                        self._data[tag] = []
                    self._data[tag].append(rel)

        self._save()


# ========== 主类 ==========

class MaterialInput:
    """材料摄入入口"""

    def __init__(self, memory_manager=None):
        """
        Args:
            memory_manager: MemoryManager 实例（可选）
                传入时会同步更新 Wiki，不传则只写材料文件 + tag 索引
        """
        self.mm = memory_manager
        self.tags = TagsIndex()

    # ==================== 摄入 ====================

    def ingest(
        self,
        content: str,
        title: str = "",
        *,
        stock_code: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_type: str = "user_input",
        source_url: str = "",
        summary: str = "",
        category: Optional[str] = None,
    ) -> str:
        """
        摄入一条材料

        Args:
            content: 原始内容
            title: 标题
            stock_code: 关联股票代码（可选）
            tags: 标签列表，如 ["核能", "SMR"]
            source_type: 来源类型 (user_input / web_search / twitter / article / kol)
            source_url: 来源链接
            summary: 摘要
            category: 非个股材料分类 (industry / macro / strategy / general)

        Returns:
            材料文件路径
        """
        mid = _short_id()
        ts = _now()
        tag_list = _parse_tags(tags) if tags else []
        tags_str = ", ".join(tag_list)

        # 决定存储目录
        mat_dir = _resolve_material_dir(stock_code, category)
        filename = f"{_today_compact()}_{source_type}_{mid}.md"
        filepath = mat_dir / filename

        # stock_code 用于 frontmatter（没有则为空）
        code_for_meta = stock_code or ""

        md_content = f"""---
id: {mid}
timestamp: {ts}
stock_code: {code_for_meta}
source_type: {source_type}
source_url: {source_url}
title: {title or '(无标题)'}
tags: {tags_str}
---

# {title or '(无标题)'}

> 来源: {source_type} | 时间: {ts}
{f'> 链接: {source_url}' if source_url else ''}

## 摘要

{summary or '（无摘要）'}

## 原文

{content}
"""
        _write_file(filepath, md_content)

        # 更新 tag 索引
        rel_path = _relative_path(str(filepath))
        self.tags.add(rel_path, tag_list)

        # 如果有 memory_manager 且有 stock_code，同步更新 Wiki
        if self.mm and stock_code:
            self.mm.save_material(
                stock_code=stock_code,
                source_type=source_type,
                content=content,
                title=title,
                source_url=source_url,
                summary=summary,
                tags=tags_str,
            )

        return str(filepath)

    def ingest_batch(self, items: List[Dict]) -> List[str]:
        """
        批量摄入

        每个 item 是一个 dict，字段和 ingest() 参数一致
        返回每个材料的文件路径列表
        """
        paths = []
        for item in items:
            path = self.ingest(
                content=item.get("content", ""),
                title=item.get("title", ""),
                stock_code=item.get("stock_code"),
                tags=item.get("tags"),
                source_type=item.get("source_type", "user_input"),
                source_url=item.get("source_url", ""),
                summary=item.get("summary", ""),
                category=item.get("category"),
            )
            paths.append(path)
        return paths

    # ==================== 查询 ====================

    def query_by_tags(self, tags: List[str], match: str = "all") -> List[Dict]:
        """
        按 tag 查询材料

        Args:
            tags: 标签列表
            match: "all" = AND, "any" = OR

        Returns:
            材料元数据列表 [{id, title, stock_code, source_type, tags, path}]
        """
        rel_paths = self.tags.query(tags, match)
        results = []
        for rel in rel_paths:
            filepath = MATERIALS_DIR / rel
            meta = self._read_meta(filepath)
            if meta:
                results.append(meta)
        return results

    def query_by_stock(self, stock_code: str) -> List[Dict]:
        """
        查询某只股票的所有材料

        Args:
            stock_code: 股票代码

        Returns:
            材料元数据列表（按时间倒序）
        """
        safe = stock_code.replace(".", "_")
        stock_dir = MATERIALS_DIR / safe
        if not stock_dir.exists():
            return []

        results = []
        for md_file in sorted(stock_dir.glob("*.md"), reverse=True):
            meta = self._read_meta(md_file)
            if meta:
                results.append(meta)
        return results

    def query_by_keyword(self, keyword: str, limit: int = 20) -> List[Dict]:
        """
        全文关键词搜索（遍历材料文件内容）

        Args:
            keyword: 搜索关键词
            limit: 最多返回条数

        Returns:
            材料元数据列表
        """
        if not MATERIALS_DIR.exists():
            return []

        keyword_lower = keyword.lower()
        results = []
        for md_file in MATERIALS_DIR.rglob("*.md"):
            text = _read_file(md_file)
            if keyword_lower in text.lower():
                meta = self._read_meta(md_file)
                if meta:
                    results.append(meta)
            if len(results) >= limit:
                break
        return results

    def query_by_category(self, category: str) -> List[Dict]:
        """
        查询某分类的通用材料

        Args:
            category: industry / macro / strategy / general

        Returns:
            材料元数据列表（按时间倒序）
        """
        cat_dir = MATERIALS_DIR / category
        if not cat_dir.exists():
            return []

        results = []
        for md_file in sorted(cat_dir.glob("*.md"), reverse=True):
            meta = self._read_meta(md_file)
            if meta:
                results.append(meta)
        return results

    # ==================== 工具 ====================

    def _read_meta(self, filepath: Path) -> Optional[Dict]:
        """从材料文件的 frontmatter 解析元数据"""
        text = _read_file(filepath)
        if not text.startswith("---"):
            return None
        end = text.find("---", 3)
        if end == -1:
            return None

        meta = {}
        for line in text[3:end].strip().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()

        meta["path"] = str(filepath)
        meta["rel_path"] = _relative_path(str(filepath))
        return meta

    def list_all_tags(self) -> Dict[str, int]:
        """列出所有 tag 及对应材料数量"""
        return self.tags.list_tags()

    def rebuild_index(self):
        """从磁盘重建 tag 索引"""
        self.tags.rebuild()
