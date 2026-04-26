"""
Memory Manager - Karpathy LLM Wiki 模式

三层架构：
  Raw Sources (data/materials/) → Wiki (data/wiki/) → Schema (本文件)

核心原则：
  - 知识是增量编译的，不是每次重新推导
  - 每次摄入资料后更新 Wiki 页面，而非只追加
  - 小规模用 index.md 导航，不需要向量数据库
"""

import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ========== 路径常量 ==========

BASE_DIR = Path(os.getenv("WIKI_BASE_DIR", "./data"))
WIKI_DIR = BASE_DIR / os.getenv("WIKI_SUBDIR", "wiki")
MATERIALS_DIR = BASE_DIR / os.getenv("MATERIALS_SUBDIR", "materials")
INDEX_PATH = WIKI_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"

# Wiki 模板中的标准 section 顺序

WIKI_SECTIONS = [

    "综合评估",

    "分析时间线",

    "预测验证",

    "关键事件",

    "财报预期",

    "流动性分析",

    "期权市场",

    "KOL 观点汇总",

    "社交情绪",

    "研究笔记",

    "交叉引用",

    "资料索引",

]

# 评估维度
EVAL_DIMENSIONS = ["基本面", "估值面", "技术面", "消息面", "综合"]


# ========== 数据类 ==========

@dataclass
class AnalysisRecord:
    """分析记录（兼容旧接口）"""
    id: str = ""
    timestamp: str = ""
    stock_code: str = ""
    stock_name: str = ""
    analysis_type: str = ""
    input_data: Dict = field(default_factory=dict)
    result: str = ""
    score: float = 0.0
    feedback: Optional[str] = None


@dataclass
class LintIssue:
    """Lint 问题"""
    stock_code: str
    severity: str  # "error" | "warning" | "info"
    section: str
    message: str


# ========== 工具函数 ==========

def _ensure_dirs():
    """确保目录存在"""
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    MATERIALS_DIR.mkdir(parents=True, exist_ok=True)


def _stock_wiki_path(stock_code: str) -> Path:
    """股票 Wiki 页面路径（OKLO.US → OKLO_US.md）"""
    safe_name = stock_code.replace(".", "_")
    return WIKI_DIR / f"{safe_name}.md"


def _stock_materials_dir(stock_code: str) -> Path:
    """股票原始资料目录"""
    safe_name = stock_code.replace(".", "_")
    d = MATERIALS_DIR / safe_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _today_compact() -> str:
    return datetime.now().strftime("%Y%m%d")


def _short_id() -> str:
    return str(uuid.uuid4())[:8]


def _read_file(path: Path) -> str:
    """安全读取文件"""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _write_file(path: Path, content: str):
    """安全写入文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_file(path: Path, content: str):
    """安全追加文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


# ========== Markdown Section 解析器 ==========

def _find_section(wiki_text: str, section_name: str) -> Tuple[int, int]:
    """
    找到 ## section_name 在 wiki_text 中的范围。
    返回 (start, end) 字符索引，包含 section header。
    找不到返回 (-1, -1)。
    """
    pattern = rf"^## {re.escape(section_name)}\s*$"
    match = re.search(pattern, wiki_text, re.MULTILINE)
    if not match:
        return -1, -1

    start = match.start()
    # 找下一个 ## section 或文件末尾
    rest = wiki_text[match.end():]
    next_match = re.search(r"^## ", rest, re.MULTILINE)
    if next_match:
        end = match.end() + next_match.start()
    else:
        end = len(wiki_text)

    return start, end


def _get_section_content(wiki_text: str, section_name: str) -> str:
    """获取某个 section 的内容（不含 header）"""
    start, end = _find_section(wiki_text, section_name)
    if start == -1:
        return ""
    # 跳过 header 行
    header_end = wiki_text.index("\n", start) + 1
    return wiki_text[header_end:end].strip()


def _replace_section(wiki_text: str, section_name: str, new_content: str) -> str:
    """替换某个 section 的内容（保留 header）"""
    start, end = _find_section(wiki_text, section_name)
    if start == -1:
        # section 不存在，追加到文件末尾
        return wiki_text.rstrip() + f"\n\n## {section_name}\n\n{new_content}\n"

    header_line_end = wiki_text.index("\n", start) + 1
    return wiki_text[:header_line_end] + f"\n{new_content}\n" + wiki_text[end:]


def _append_to_section(wiki_text: str, section_name: str, entry: str) -> str:
    """在某个 section 末尾追加内容"""
    content = _get_section_content(wiki_text, section_name)
    # 去掉占位文字（匹配「（暂无...）」任意位置）
    content = re.sub(r'（暂无[^）]*）', '', content).strip()
    if content:
        new_content = content.rstrip() + "\n" + entry
    else:
        new_content = entry
    return _replace_section(wiki_text, section_name, new_content)


def _parse_frontmatter(text: str) -> Dict[str, str]:
    """解析 YAML frontmatter"""
    meta = {}
    if not text.startswith("---"):
        return meta
    end = text.find("---", 3)
    if end == -1:
        return meta
    for line in text[3:end].strip().split("\n"):
        if ": " in line:
            k, v = line.split(": ", 1)
            meta[k.strip()] = v.strip()
    return meta


# ====================================================================
# MemoryManager 主类
# ====================================================================

class MemoryManager:
    """
    基于 Markdown Wiki 的记忆管理器

    设计参考 Karpathy 的 LLM Wiki 模式：
    - 每只股票一个 Wiki 页面
    - 摄入资料时更新 Wiki（而非只追加）
    - index.md 作为总目录
    - log.md 作为操作日志
    """

    def __init__(self):
        _ensure_dirs()
        self._init_index()
        self._init_log()

    # ==================== Index ====================

    def _init_index(self):
        """初始化 index.md"""
        if not INDEX_PATH.exists():
            _write_file(INDEX_PATH,
                "# Stock Wiki Index\n\n"
                "> 每次分析或摄入资料后自动更新\n\n"
                "| 代码 | 名称 | 最近分析 | 评分 | 资料数 |\n"
                "|------|------|----------|------|--------|\n"
            )

    def get_index(self) -> str:
        """读取 index.md"""
        return _read_file(INDEX_PATH)

    def update_index(self, stock_code: str, stock_name: str, score: float = 0, material_count: int = -1):
        """更新 index.md 中某只股票的条目"""
        content = self.get_index()
        lines = content.split("\n")
        new_row = f"| {stock_code} | {stock_name} | {_now()} | {score} | {material_count if material_count >= 0 else '-'} |"

        # 查找已有条目并替换
        found = False
        for i, line in enumerate(lines):
            if line.startswith("|") and stock_code in line and "---" not in line and "代码" not in line:
                lines[i] = new_row
                found = True
                break

        if not found:
            # 插入到表格末尾（跳过 header 和分隔线）
            insert_at = len(lines)
            for i, line in enumerate(lines):
                if i > 4 and not line.startswith("|") and line.strip():
                    insert_at = i
                    break
            # 如果所有行都是表格行，追加到末尾
            if insert_at == len(lines) or all(l.startswith("|") for l in lines[insert_at:]):
                insert_at = len(lines)
            lines.insert(insert_at, new_row)

        _write_file(INDEX_PATH, "\n".join(lines))

    # ==================== Log ====================

    def _init_log(self):
        """初始化 log.md"""
        if not LOG_PATH.exists():
            _write_file(LOG_PATH,
                "# Operation Log\n\n> Append-only 操作日志\n\n"
            )

    def append_log(self, action: str, detail: str):
        """追加操作日志"""
        entry = f"\n## [{_now()}] {action}\n\n{detail}\n"
        _append_file(LOG_PATH, entry)

    def get_recent_log(self, n: int = 10) -> List[Dict]:
        """
        读取最近 n 条日志，返回结构化列表。
        每条: {"timestamp": ..., "action": ..., "detail": ...}
        """
        content = _read_file(LOG_PATH)
        if not content:
            return []

        entries = re.split(r"^## \[", content, flags=re.MULTILINE)
        results = []
        for entry in entries[-n:]:
            entry = entry.strip()
            if not entry:
                continue
            # 格式: 2026-04-15 14:30] action\n\ndetail
            m = re.match(r"([^\]]+)\]\s+(.+)", entry, re.DOTALL)
            if m:
                ts_action = m.group(2)
                parts = ts_action.split("\n", 1)
                results.append({
                    "timestamp": m.group(1).strip(),
                    "action": parts[0].strip(),
                    "detail": parts[1].strip() if len(parts) > 1 else "",
                })
        return results

    # ==================== Stock Wiki ====================

    def get_stock_wiki(self, stock_code: str) -> str:
        """读取某只股票的 Wiki 页面"""
        return _read_file(_stock_wiki_path(stock_code))

    def init_stock_wiki(self, stock_code: str, stock_name: str) -> str:
        """初始化某只股票的 Wiki 页面，已存在则直接返回"""
        path = _stock_wiki_path(stock_code)
        if path.exists():
            return _read_file(path)

        # 评估表行
        eval_rows = "\n".join(
            f"| {d} | - | - | - | - |" for d in EVAL_DIMENSIONS
        )

        # 占位 section
        placeholder = "（暂无）"
        tl_placeholder = "（暂无分析记录）"

        content = f"""# {stock_name} ({stock_code})

> 股票知识库 - 每次分析和资料摄入后自动更新

## 综合评估

| 维度 | 当前判断 | 上次判断 | 变化 | 更新时间 |
|------|----------|----------|------|----------|
{eval_rows}

## 分析时间线

> 每次分析后追加，记录当时的价格、评分、核心观点

{tl_placeholder}

## 预测验证

> 记录历次预测及实际结果，追踪准确率

{placeholder}

## 关键事件

> 影响股价的重要事件，按时间倒序

{placeholder}

## 财报预期

> 下次财报日期、分析师共识预期、历史 beat/miss 记录

{placeholder}

## 流动性分析

> 做空比例、机构持仓、Days to Cover、换手率

{placeholder}

## 期权市场

> Put/Call Ratio、Max Pain、ATM IV、异常活动

{placeholder}

## KOL 观点汇总

> 来自 Twitter KOL 的观点，标注来源和时间

{placeholder}

## 社交情绪

> Reddit、X/Twitter、Polymarket 情绪汇总

{placeholder}

## 研究笔记

> 分析过程中的深度问答，知识沉淀

{placeholder}

## 交叉引用

> 相关股票、竞品、同行业公司

{placeholder}

## 资料索引

> 已摄入的原始资料列表

{placeholder}
"""
        _write_file(path, content)
        return content

    def _ensure_wiki(self, stock_code: str, stock_name: str = "") -> str:
        """确保 wiki 存在，返回内容"""
        wiki = self.get_stock_wiki(stock_code)
        if not wiki:
            wiki = self.init_stock_wiki(stock_code, stock_name or stock_code)
        return wiki

    # ==================== 评估表 ====================

    def update_evaluation_table(
        self,
        stock_code: str,
        stock_name: str,
        dimension: str,
        current_judgment: str,
    ):
        """
        更新评估表的某个维度。
        旧的「当前判断」→「上次判断」，新的写入「当前判断」。
        """
        if dimension not in EVAL_DIMENSIONS:
            return

        wiki = self._ensure_wiki(stock_code, stock_name)
        content = _get_section_content(wiki, "综合评估")

        # 解析表格
        lines = content.split("\n")
        new_lines = []
        updated = False

        for line in lines:
            if not line.startswith("|") or "---" in line or "维度" in line:
                new_lines.append(line)
                continue

            parts = [p.strip() for p in line.split("|")]
            # parts: ['', dim, cur, prev, change, time, '']
            parts = [p for p in parts if p != ""]  # 去掉首尾空串
            if len(parts) < 5:
                new_lines.append(line)
                continue

            row_dim = parts[0]
            if row_dim == dimension:
                old_judgment = parts[1] if parts[1] != "-" else ""
                change = "新增" if not old_judgment else "已更新"
                new_line = (
                    f"| {dimension} | {current_judgment} | "
                    f"{old_judgment or '-'} | {change} | {_now()} |"
                )
                new_lines.append(new_line)
                updated = True
            else:
                new_lines.append(line)

        if updated:
            wiki = _replace_section(wiki, "综合评估", "\n".join(new_lines))
        else:
            # 维度行不存在，追加
            new_lines.append(
                f"| {dimension} | {current_judgment} | - | 新增 | {_now()} |"
            )
            wiki = _replace_section(wiki, "综合评估", "\n".join(new_lines))

        _write_file(_stock_wiki_path(stock_code), wiki)
        self.append_log("eval_update", f"{stock_code} 评估表更新: {dimension} → {current_judgment}")

    # ==================== 时间线 ====================

    def append_to_timeline(
        self,
        stock_code: str,
        price: float = 0,
        score: float = 0,
        core_view: str = "",
        analysis_type: str = "综合分析",
    ):
        """追加分析记录到时间线"""
        wiki = self.get_stock_wiki(stock_code)
        if not wiki:
            return

        entry = (
            f"- **{_now()}** | 价格: {price} | 评分: {score}/100 | "
            f"类型: {analysis_type}\n"
            f"  - 核心观点: {core_view}"
        )

        wiki = _append_to_section(wiki, "分析时间线", entry)
        _write_file(_stock_wiki_path(stock_code), wiki)

    # ==================== 预测验证 ====================

    def add_prediction(self, stock_code: str, prediction: str, target_date: str = ""):
        """
        添加一条预测到「预测验证」section。
        target_date: 预计验证的日期，留空表示不限
        """
        wiki = self._ensure_wiki(stock_code)
        entry = (
            f"- **[{_now()}]** {prediction}\n"
            f"  - 状态: ⏳ 待验证"
            f"{f'  | 目标日期: {target_date}' if target_date else ''}"
        )
        wiki = _append_to_section(wiki, "预测验证", entry)
        _write_file(_stock_wiki_path(stock_code), wiki)
        

        self.append_log("prediction", f"添加预测: {stock_code} - {prediction[:50]}")

    # ==================== Materials 管理 ====================

    def save_material(
        self,
        stock_code: str,
        source_type: str,
        content: str,
        title: str = "",
        source_url: str = "",
        summary: str = "",
        tags: str = "",
    ) -> str:
        """
        保存原始资料文件

        Args:
            stock_code: 股票代码
            source_type: 来源类型 (user_input / web_search / twitter / article / kol)
            content: 原始内容
            title: 标题
            source_url: 来源链接
            summary: 摘要
            tags: 标签（逗号分隔）

        Returns:
            文件路径
        """
        mid = _short_id()
        ts = _now()

        mat_dir = _stock_materials_dir(stock_code)
        filename = f"{_today_compact()}_{source_type}_{mid}.md"
        filepath = mat_dir / filename

        md_content = f"""---
id: {mid}
timestamp: {ts}
stock_code: {stock_code}
source_type: {source_type}
source_url: {source_url}
title: {title}
tags: {tags}
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

        # 更新 Wiki 的资料索引
        self._update_material_index(stock_code, ts, source_type, title or "(无标题)", str(filepath), summary)

        # 更新 index.md 的资料数
        materials = self.get_materials(stock_code)
        wiki = _read_file(_stock_wiki_path(stock_code))
        # 从第一行提取 stock_name
        stock_name = ""
        if wiki:
            m = re.match(r"^# (.+?) \(", wiki)
            if m:
                stock_name = m.group(1)
        self.update_index(stock_code, stock_name, material_count=len(materials))

        # 追加日志
        self.append_log("ingest", f"保存资料: {stock_code} / {source_type} / {title}")

        return str(filepath)

    def _update_material_index(
        self, stock_code: str, ts: str, source_type: str, title: str, filepath: str, summary: str
    ):
        """更新 Wiki 页面的资料索引 section"""
        wiki = _read_file(_stock_wiki_path(stock_code))
        if not wiki:
            return

        entry = f"- [{ts}] [{source_type}] {title}"
        if summary:
            entry += f" — {summary[:80]}"

        wiki = _append_to_section(wiki, "资料索引", entry)
        _write_file(_stock_wiki_path(stock_code), wiki)

    def get_materials(
        self,
        stock_code: str,
        source_type: str = None,
        limit: int = 20,
    ) -> List[Dict]:
        """获取某只股票的历史资料"""
        mat_dir = _stock_materials_dir(stock_code)
        results = []

        files = sorted(mat_dir.glob("*.md"), reverse=True)
        for f in files:
            if len(results) >= limit:
                break
            text = _read_file(f)
            meta = _parse_frontmatter(text)

            if source_type and meta.get("source_type") != source_type:
                continue

            results.append({
                "id": meta.get("id", ""),
                "timestamp": meta.get("timestamp", ""),
                "stock_code": meta.get("stock_code", stock_code),
                "source_type": meta.get("source_type", ""),
                "source_url": meta.get("source_url", ""),
                "title": meta.get("title", ""),
                "tags": meta.get("tags", ""),
                "filepath": str(f),
            })

        return results

    def get_materials_summary(self, stock_code: str) -> str:
        """获取某只股票的资料摘要（用于分析 prompt）"""
        materials = self.get_materials(stock_code)
        if not materials:
            return ""

        lines = [f"### 历史资料库 ({len(materials)} 条)\n"]
        for m in materials:
            lines.append(f"- [{m['timestamp']}] [{m['source_type']}] {m['title']}")
        return "\n".join(lines)

    # ==================== 查询 + 上下文 + 回写 ====================

    def search_materials(self, keyword: str, limit: int = 10) -> List[Dict]:
        """按关键词搜索所有资料"""
        results = []
        keyword_lower = keyword.lower()
        for mat_file in MATERIALS_DIR.rglob("*.md"):
            if len(results) >= limit:
                break
            text = _read_file(mat_file)
            if keyword_lower in text.lower():
                meta = _parse_frontmatter(text)
                results.append({
                    "id": meta.get("id", ""),
                    "timestamp": meta.get("timestamp", ""),
                    "stock_code": meta.get("stock_code", ""),
                    "source_type": meta.get("source_type", ""),
                    "title": meta.get("title", ""),
                    "filepath": str(mat_file),
                })
        return results

    def get_stock_context(self, stock_code: str, include_materials: bool = True) -> str:
        """
        获取某只股票的完整上下文（用于注入 LLM 分析 prompt）

        包含：Wiki 全文 + 最近资料摘要 + 交叉引用的股票摘要
        """
        wiki = _read_file(_stock_wiki_path(stock_code))
        if not wiki:
            return ""

        parts = [wiki]

        # 附加最近资料摘要
        if include_materials:
            summary = self.get_materials_summary(stock_code)
            if summary:
                parts.append(f"\n---\n{summary}")

        # 解析交叉引用，附加相关股票的简要信息
        xref_content = _get_section_content(wiki, "交叉引用")
        if xref_content and not xref_content.startswith("（暂无"):
            for line in xref_content.split("\n"):
                m = re.match(r"^- .*\[([A-Z0-9]+\.[A-Z]{2})\]", line)
                if m:
                    ref_code = m.group(1)
                    ref_wiki = _read_file(_stock_wiki_path(ref_code))
                    if ref_wiki:
                        # 只取综合评估 section
                        eval_content = _get_section_content(ref_wiki, "综合评估")
                        if eval_content and not eval_content.startswith("| 维度"):
                            # 取表格最后一行（综合）
                            for row in eval_content.split("\n"):
                                if "综合" in row and "|" in row:
                                    parts.append(f"\n> 关联 {ref_code}: {row.strip()}")
                                    break

        return "\n".join(parts)

    def save_query_result(
        self, stock_code: str, question: str, answer: str
    ):
        """
        将好的问答存回 Wiki 的「研究笔记」section
        知识沉淀，避免重复推导
        """
        wiki = self._ensure_wiki(stock_code)

        entry = (
            f"### [{_now()}] {question}\n\n"
            f"{answer}\n"
        )
        wiki = _append_to_section(wiki, "研究笔记", entry)
        _write_file(_stock_wiki_path(stock_code), wiki)

        self.append_log("query_save", f"研究笔记: {stock_code} - {question[:50]}")

    def append_to_section(self, stock_code: str, section_name: str, entry: str):
        """追加内容到 Wiki 的指定章节"""
        wiki = _read_file(_stock_wiki_path(stock_code))
        if not wiki:
            return
        wiki = _append_to_section(wiki, section_name, entry)
        _write_file(_stock_wiki_path(stock_code), wiki)

    def find_similar_analyses(
        self, stock_name: str, analysis_type: str = "", top_k: int = 5
    ) -> List[Dict]:
        """从 Wiki 中搜索相关分析"""
        results = []
        for wiki_file in WIKI_DIR.glob("*.md"):
            if wiki_file.name in ("index.md", "log.md"):
                continue
            text = _read_file(wiki_file)
            if not text:
                continue

            score = 0
            if stock_name.lower() in text.lower():
                score += 1
            if analysis_type and analysis_type.lower() in text.lower():
                score += 1
            # 检查交叉引用里是否提到
            xref = _get_section_content(text, "交叉引用")
            if xref and stock_name.lower() in xref.lower():
                score += 2

            if score > 0:
                code = wiki_file.stem.replace("_", ".", 1)
                results.append({
                    "id": wiki_file.stem,
                    "stock_code": code,
                    "metadata": {"path": str(wiki_file)},
                    "distance": score,
                })

        results.sort(key=lambda x: x["distance"], reverse=True)
        return results[:top_k]

    # ==================== Lint + 学习 + 建议 ====================

    def lint_wiki(self) -> List[LintIssue]:
        """
        Wiki 健康检查
        检查：矛盾、过时、孤儿页面、缺失 section
        """
        issues = []

        for wiki_file in WIKI_DIR.glob("*.md"):
            if wiki_file.name in ("index.md", "log.md"):
                continue

            stock_code = wiki_file.stem.replace("_", ".", 1)
            wiki = _read_file(wiki_file)
            if not wiki:
                issues.append(LintIssue(stock_code, "error", "", "Wiki 文件为空"))
                continue

            # 检查缺失 section
            for section in WIKI_SECTIONS:
                if f"## {section}" not in wiki:
                    issues.append(LintIssue(
                        stock_code, "warning", section,
                        f"缺失 section: {section}"
                    ))

            # 检查过时：时间线最近一条超过 30 天
            timeline = _get_section_content(wiki, "分析时间线")
            if timeline and not timeline.startswith("（暂无"):
                dates = re.findall(r"\*\*(\d{4}-\d{2}-\d{2})", timeline)
                if dates:
                    last_date = max(dates)
                    last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                    if (datetime.now() - last_dt).days > 30:
                        issues.append(LintIssue(
                            stock_code, "info", "分析时间线",
                            f"超过 30 天未分析（上次: {last_date}）"
                        ))

            # 检查预测验证：有待验证超过 14 天的预测
            predictions = _get_section_content(wiki, "预测验证")
            if predictions and not predictions.startswith("（暂无"):
                pending = re.findall(r"\*\*\[(\d{4}-\d{2}-\d{2}[^\]]*)\]", predictions)
                for pd_str in pending:
                    pd_clean = pd_str[:10]
                    try:
                        pd_dt = datetime.strptime(pd_clean, "%Y-%m-%d")
                        if (datetime.now() - pd_dt).days > 14:
                            issues.append(LintIssue(
                                stock_code, "warning", "预测验证",
                                f"有超过 14 天未验证的预测（{pd_clean}）"
                            ))
                    except ValueError:
                        pass

        # 检查 index.md 和实际 wiki 文件的一致性
        index_content = _read_file(INDEX_PATH)
        index_codes = set(re.findall(r"\| ([A-Z0-9]+\.[A-Z]{2}) ", index_content))
        wiki_codes = set()
        for wf in WIKI_DIR.glob("*.md"):
            if wf.name not in ("index.md", "log.md"):
                wiki_codes.add(wf.stem.replace("_", ".", 1))

        orphans = wiki_codes - index_codes
        for code in orphans:
            issues.append(LintIssue(code, "warning", "", "Wiki 存在但 index.md 未收录"))

        missing = index_codes - wiki_codes
        for code in missing:
            issues.append(LintIssue(code, "error", "", "index.md 收录但无 Wiki 文件"))

        return issues

    def learn_from_history(self) -> Dict:
        """
        从所有 Wiki 历史中学习
        分析模式：评分趋势、分析频率、准确率
        """
        all_scores = []
        stock_stats = {}

        for wiki_file in WIKI_DIR.glob("*.md"):
            if wiki_file.name in ("index.md", "log.md"):
                continue

            stock_code = wiki_file.stem.replace("_", ".", 1)
            wiki = _read_file(wiki_file)
            if not wiki:
                continue

            # 解析时间线中的评分
            timeline = _get_section_content(wiki, "分析时间线")
            if not timeline or timeline.startswith("（暂无"):
                continue

            scores = []
            for line in timeline.split("\n"):
                m = re.search(r"评分:\s*([\d.]+)", line)
                if m:
                    scores.append(float(m.group(1)))

            if scores:
                all_scores.extend(scores)
                stock_stats[stock_code] = {
                    "count": len(scores),
                    "avg_score": round(sum(scores) / len(scores), 1),
                    "latest_score": scores[-1],
                    "trend": "up" if len(scores) >= 2 and scores[-1] > scores[0] else "down" if len(scores) >= 2 else "stable",
                }

        # 解析预测验证
        predictions = _get_section_content(wiki, "预测验证")
        verified = 0
        correct = 0
        if predictions and not predictions.startswith("（暂无"):
            verified = len(re.findall(r"状态: ✅", predictions))
            correct = len(re.findall(r"结果: ✅", predictions))

        result = {
            "learned_at": _now(),
            "total_stocks": len(stock_stats),
            "total_analyses": len(all_scores),
            "avg_score_all": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
            "stock_stats": stock_stats,
            "prediction_accuracy": round(correct / verified * 100, 1) if verified > 0 else None,
            "top_patterns": [],
        }

        # 生成模式洞察
        if all_scores:
            high_scores = [s for s in all_scores if s >= 70]
            low_scores = [s for s in all_scores if s < 30]
            result["top_patterns"] = [
                f"高评分(≥70)占比: {round(len(high_scores)/len(all_scores)*100)}%",
                f"低评分(<30)占比: {round(len(low_scores)/len(all_scores)*100)}%",
                f"评分范围: {min(all_scores)}-{max(all_scores)}",
            ]

        return result

    def get_improvement_suggestions(self) -> List[str]:
        """
        基于当前 Wiki 状态给出改进建议
        """
        suggestions = []
        issues = self.lint_wiki()

        for issue in issues:
            if issue.severity == "error":
                suggestions.append(f"[严重] {issue.stock_code}: {issue.message}")
            elif issue.severity == "warning":
                suggestions.append(f"[建议] {issue.stock_code}: {issue.message}")

        # 从学习结果中生成建议
        stats = self.learn_from_history()
        for code, info in stats.get("stock_stats", {}).items():
            if info["trend"] == "down":
                suggestions.append(f"[关注] {code} 评分持续下降，建议重新分析")
            if info["count"] == 1:
                suggestions.append(f"[补充] {code} 只分析过 1 次，建议增加分析频率")

        # 检查资料但无分析的股票
        for mat_dir in MATERIALS_DIR.iterdir():
            if mat_dir.is_dir():
                code = mat_dir.name.replace("_", ".", 1)
                wiki_path = _stock_wiki_path(code)
                if not wiki_path.exists():
                    suggestions.append(f"[缺失] {code} 有资料但未建 Wiki 页面")

        return suggestions[:20]  # 最多返回 20 条

    # ==================== 预测验证 ====================

    def verify_prediction(
        self, stock_code: str, prediction_text: str, outcome: str, note: str = ""
    ):
        """验证一条预测的结果"""
        wiki = _read_file(_stock_wiki_path(stock_code))
        if not wiki:
            return

        icon = "✅ 正确" if outcome == "correct" else "❌ 错误"
        lines = wiki.splitlines()
        for i, line in enumerate(lines):
            if prediction_text[:20] in line and i + 1 < len(lines):
                if "⏳ 待验证" in lines[i + 1]:
                    lines[i + 1] = lines[i + 1].replace("状态: ⏳ 待验证", f"状态: {icon}")
                    if note:
                        lines.insert(i + 2, f"  - 验证说明: {note}")
                    break

        _write_file(_stock_wiki_path(stock_code), chr(10).join(lines))
        self.append_log("verify", f"验证预测: {stock_code} - {icon} | {prediction_text[:50]}")

    # ==================== 兼容旧接口 ====================

    def save_analysis(self, record: AnalysisRecord):
        """
        保存分析记录（兼容旧接口）
        现在会写入 Wiki：初始化页面 → 更新 index → 追加时间线 → 更新评估表
        """
        # 确保 Wiki 存在
        self.init_stock_wiki(record.stock_code, record.stock_name)

        # 更新 index
        self.update_index(record.stock_code, record.stock_name, record.score)

        # 追加时间线
        self.append_to_timeline(
            record.stock_code,
            price=record.input_data.get("price", 0),
            score=record.score,
            core_view=record.result[:100] if record.result else "",
            analysis_type=record.analysis_type,
        )

        # 更新综合评估表的"综合"维度
        self.update_evaluation_table(
            record.stock_code,
            record.stock_name,
            dimension="综合",
            current_judgment=f"评分 {record.score}/100 — {record.analysis_type}",
        )

        # 追加日志
        self.append_log(
            "analysis",
            f"分析 {record.stock_code} ({record.stock_name}): "
            f"评分 {record.score}, 类型 {record.analysis_type}"
        )

    def get_analysis_history(
        self,
        stock_code: str = None,
        analysis_type: str = None,
        limit: int = 20,
    ) -> List[Dict]:
        """获取分析历史（从 Wiki 时间线解析）"""
        if stock_code:
            wiki = self.get_stock_wiki(stock_code)
            if not wiki:
                return []

            timeline = _get_section_content(wiki, "分析时间线")
            if not timeline or timeline.startswith("（暂无"):
                return []

            results = []
            for line in timeline.split("\n"):
                if not line.startswith("- **"):
                    continue
                if "评分:" not in line:
                    continue

                # 解析时间戳
                ts_match = re.search(r"\*\*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\*\*", line)
                ts = ts_match.group(1) if ts_match else ""

                # 解析各字段
                parts = line.split("|")
                price_part = [p for p in parts if "价格:" in p]
                score_part = [p for p in parts if "评分:" in p]
                type_part = [p for p in parts if "类型:" in p]

                score = 0.0
                if score_part:
                    num = re.search(r"([\d.]+)", score_part[0])
                    score = float(num.group(1)) if num else 0.0

                atype = ""
                if type_part:
                    atype = type_part[0].replace("类型:", "").strip()

                if analysis_type and analysis_type not in atype:
                    continue

                # 获取下一行作为核心观点
                core_view = ""
                lines = timeline.split("\n")
                idx = lines.index(line) if line in lines else -1
                if idx >= 0 and idx + 1 < len(lines):
                    next_line = lines[idx + 1].strip()
                    if next_line.startswith("- 核心观点:"):
                        core_view = next_line.replace("- 核心观点:", "").strip()

                results.append({
                    "id": ts,
                    "timestamp": ts,
                    "stock_code": stock_code,
                    "stock_name": "",
                    "analysis_type": atype,
                    "score": score,
                    "result": core_view,
                    "input_data": {},
                })

            return results[:limit]

        # 无 stock_code 时从 log 解析所有分析
        return self._get_all_analysis_from_log(limit)

    def _get_all_analysis_from_log(self, limit: int = 20) -> List[Dict]:
        """从 log.md 解析所有分析记录"""
        log_content = _read_file(LOG_PATH)
        if not log_content:
            return []

        results = []
        entries = re.findall(
            r"## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] analysis\n\n(.*?)(?=\n## |\Z)",
            log_content,
            re.DOTALL,
        )
        for ts, detail in entries:
            code_match = re.search(r"分析 ([A-Z0-9]+\.[A-Z]{2})", detail)
            name_match = re.search(r"\(([^)]+)\)", detail)
            score_match = re.search(r"评分 ([\d.]+)", detail)
            type_match = re.search(r"类型 (.+)", detail)

            results.append({
                "id": ts,
                "timestamp": ts,
                "stock_code": code_match.group(1) if code_match else "",
                "stock_name": name_match.group(1) if name_match else "",
                "analysis_type": type_match.group(1).strip() if type_match else "",
                "score": float(score_match.group(1)) if score_match else 0.0,
                "result": "",
                "input_data": {},
            })

        results.reverse()  # 最新的在前
        return results[:limit]

    def add_feedback(self, analysis_id: str, feedback: str, score: float):
        """添加用户反馈"""
        self.append_log("feedback", f"反馈: {analysis_id} → 评分 {score}, {feedback}")
