"""
网络搜索模块 - 股票信息搜索

多源策略（按优先级）：
1. Yahoo Finance News（主）— 通过 yfinance，稳定可靠
2. DuckDuckGo HTML（备选）— 免 API Key
3. NewsAPI（可选）— 配置 NEWSAPI_KEY 后启用

搜索类别：
- 新闻 (news) — 最新动态、公告
- 社交媒体 (social) — Twitter/X, Reddit 讨论
- 研报 (analyst) — 分析师评级、目标价
- 综合 (all) — 以上全部

用法:
    from data.search import StockSearchEngine
    se = StockSearchEngine()
    results = se.search_all("AAPL.US")
"""
import re
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
import yfinance as yf

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_search")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())


class SearchResult:
    """单条搜索结果"""
    def __init__(self, title: str, link: str, snippet: str, source: str = ""):
        self.title = title
        self.link = link
        self.snippet = snippet
        self.source = source

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "link": self.link,
            "snippet": self.snippet,
            "source": self.source,
        }


class StockSearchEngine:
    """
    股票信息搜索引擎

    多源回退策略：
    - Yahoo Finance News（优先，最稳定）
    - DuckDuckGo HTML（备选，免 API Key）
    - NewsAPI（可选，需配置 NEWSAPI_KEY）
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.newsapi_key = os.getenv("NEWSAPI_KEY", "")
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    # ---------- 符号转换 ----------

    @staticmethod
    def _normalize_for_search(stock_code: str) -> str:
        """
        将内部股票代码转换为搜索友好的格式
        AAPL.US → AAPL
        00700.HK → 00700
        SH603906 → 603906
        """
        code = stock_code.upper()
        if code.endswith(".US"):
            return code.replace(".US", "")
        if code.endswith(".HK"):
            return code
        if code.startswith("SH") or code.startswith("SZ"):
            return code[2:]
        return code

    @staticmethod
    def _yf_symbol(symbol: str) -> str:
        """长桥代码转 YF 代码"""
        if symbol.endswith(".US"):
            return symbol.replace(".US", "")
        if symbol.endswith(".HK"):
            return symbol
        if symbol.startswith("SH"):
            return symbol[2:] + ".SS"
        if symbol.startswith("SZ"):
            return symbol[2:] + ".SZ"
        return symbol

    # ========== 源1: Yahoo Finance News ==========

    def _search_yf_news(self, stock_code: str, max_results: int = 10) -> List[SearchResult]:
        """通过 yfinance 获取股票新闻"""
        try:
            ticker = yf.Ticker(self._yf_symbol(stock_code))
            news = ticker.news
            if not news:
                return []

            results = []
            for item in news[:max_results]:
                content = item.get("content", item)  # yfinance >= 0.2 结构
                if isinstance(content, dict):
                    title = content.get("title", "")
                    # 取 canonicalUrl 或 clickThroughUrl
                    url_info = content.get("canonicalUrl", {}) or content.get("clickThroughUrl", {})
                    link = url_info.get("url", "")
                    # snippet 从 summary 或 description 取
                    summary = content.get("summary", "")
                    if not summary:
                        # 有些版本用 different keys
                        summary = content.get("description", "")
                    provider = content.get("provider", {})
                    source_name = provider.get("displayName", "Yahoo Finance") if isinstance(provider, dict) else "Yahoo Finance"
                else:
                    # 旧版 yfinance 结构
                    title = item.get("title", "")
                    link = item.get("link", "")
                    summary = item.get("summary", "")
                    source_name = "Yahoo Finance"

                if title:
                    results.append(SearchResult(
                        title=title,
                        link=link,
                        snippet=summary[:300],
                        source=source_name,
                    ))
            return results
        except Exception as e:
            logger.warning(f"YF news search failed for {stock_code}: {e}")
            return []

    # ========== 源2: DuckDuckGo HTML ==========

    def _search_ddg(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """通过 DuckDuckGo HTML 搜索"""
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"DDG search request failed: {e}")
            return []

        return self._parse_ddg_html(resp.text, max_results)

    @staticmethod
    def _parse_ddg_html(html: str, max_results: int) -> List[SearchResult]:
        """解析 DuckDuckGo HTML 结果 — 支持多种页面结构"""
        results = []

        # 模式 A: 经典 result__a / result__snippet
        blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html, re.DOTALL | re.IGNORECASE,
        )
        for link, title_html, snippet_html in blocks[:max_results]:
            title = _strip_html(title_html)
            snippet = _strip_html(snippet_html)
            if title and link:
                results.append(SearchResult(title=title, link=link, snippet=snippet))

        if results:
            return results

        # 模式 B: result-title / result__url / result__snippet
        blocks = re.findall(
            r'<a[^>]+class="result-title"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html, re.DOTALL | re.IGNORECASE,
        )
        for link, title_html, snippet_html in blocks[:max_results]:
            title = _strip_html(title_html)
            snippet = _strip_html(snippet_html)
            if title and link:
                results.append(SearchResult(title=title, link=link, snippet=snippet))

        if results:
            return results

        # 模式 C: 更宽松的匹配（class 中包含 result）
        blocks = re.findall(
            r'<a[^>]+href="([^"]+)"[^>]*>([^<]{10,200})</a>.*?<[^>]*>([^<]{20,500})</',
            html, re.DOTALL | re.IGNORECASE,
        )
        for link, title_raw, snippet_raw in blocks[:max_results]:
            title = _strip_html(title_raw).strip()
            snippet = _strip_html(snippet_raw).strip()
            # 过滤掉导航链接
            if title and link and not any(x in link.lower() for x in ["duckduckgo", "/lite", "/html"]):
                results.append(SearchResult(title=title, link=link, snippet=snippet))

        return results

    # ========== 源3: NewsAPI ==========

    def _search_newsapi(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """通过 NewsAPI 搜索（需要 NEWSAPI_KEY）"""
        if not self.newsapi_key:
            return []

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "apiKey": self.newsapi_key,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": max_results,
        }

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            data = resp.json()
            results = []
            for item in data.get("articles", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    link=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source=item.get("source", {}).get("name", "NewsAPI"),
                ))
            return results
        except Exception as e:
            logger.warning(f"NewsAPI search failed: {e}")
            return []

    # ========== 统一搜索接口 ==========

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        统一搜索接口 — 多源回退
        1. NewsAPI（如有配置）
        2. DuckDuckGo
        """
        # 优先 NewsAPI
        if self.newsapi_key:
            results = self._search_newsapi(query, max_results)
            if results:
                return results

        # 回退 DDG
        return self._search_ddg(query, max_results)

    # ========== 股票专用搜索 ==========

    def search_news(self, stock_code: str, max_results: int = 8) -> List[SearchResult]:
        """
        搜索股票最新新闻

        优先使用 Yahoo Finance News，失败时回退到 web search
        """
        ticker = self._normalize_for_search(stock_code)

        # 1. 优先 YF News
        yf_results = self._search_yf_news(stock_code, max_results=max_results)
        if yf_results:
            for r in yf_results:
                r.source = "news"
            return yf_results

        # 2. 回退 web search
        queries = [
            f"{ticker} stock news 2026",
            f"{ticker} 股票 最新",
        ]
        all_results = []
        for query in queries:
            results = self.search(query, max_results=max_results)
            for r in results:
                r.source = "news"
                if not any(existing.link == r.link for existing in all_results):
                    all_results.append(r)
            if len(all_results) >= max_results:
                break

        return all_results[:max_results]

    def search_sentiment(self, stock_code: str, max_results: int = 6) -> List[SearchResult]:
        """搜索社交媒体讨论和情绪"""
        ticker = self._normalize_for_search(stock_code)

        queries = [
            f"${ticker} twitter sentiment",
            f"{ticker} reddit stock discussion",
            f"{ticker} 股民讨论",
        ]

        all_results = []
        for query in queries:
            results = self.search(query, max_results=max_results)
            for r in results:
                r.source = "social"
                if not any(existing.link == r.link for existing in all_results):
                    all_results.append(r)
            if len(all_results) >= max_results:
                break

        return all_results[:max_results]

    def search_analyst(self, stock_code: str, max_results: int = 6) -> List[SearchResult]:
        """搜索分析师评级和目标价"""
        ticker = self._normalize_for_search(stock_code)

        queries = [
            f"{ticker} analyst rating price target 2026",
            f"{ticker} 分析师评级 目标价",
        ]

        all_results = []
        for query in queries:
            results = self.search(query, max_results=max_results)
            for r in results:
                r.source = "analyst"
                if not any(existing.link == r.link for existing in all_results):
                    all_results.append(r)
            if len(all_results) >= max_results:
                break

        return all_results[:max_results]

    def search_all(self, stock_code: str) -> Dict:
        """
        综合搜索：新闻 + 社交 + 研报

        Returns:
            {
                "stock_code": str,
                "searched_at": str,
                "news": [SearchResult, ...],
                "social": [SearchResult, ...],
                "analyst": [SearchResult, ...],
            }
        """
        logger.info(f"Searching web info for {stock_code}")

        news = self.search_news(stock_code)
        social = self.search_sentiment(stock_code)
        analyst = self.search_analyst(stock_code)

        return {
            "stock_code": stock_code,
            "searched_at": datetime.now().isoformat(),
            "news": [r.to_dict() for r in news],
            "social": [r.to_dict() for r in social],
            "analyst": [r.to_dict() for r in analyst],
        }

    def to_markdown(self, results: Dict) -> str:
        """将搜索结果格式化为 Markdown"""
        lines = ["## 网络搜索摘要", ""]

        if results.get("news"):
            lines.append("### 最新动态")
            for item in results["news"]:
                lines.append(f"- **{item['title']}**  ")
                lines.append(f"  {item['snippet'][:120]}... [(link)]({item['link']})")
            lines.append("")

        if results.get("social"):
            lines.append("### 市场讨论")
            for item in results["social"]:
                lines.append(f"- **{item['title']}**  ")
                lines.append(f"  {item['snippet'][:120]}...")
            lines.append("")

        if results.get("analyst"):
            lines.append("### 分析师观点")
            for item in results["analyst"]:
                lines.append(f"- **{item['title']}**  ")
                lines.append(f"  {item['snippet'][:120]}...")
            lines.append("")

        return "\n".join(lines)


# ---------- 工具函数 ----------

def _strip_html(html: str) -> str:
    """去除 HTML 标签并解码实体"""
    text = re.sub(r"<[^>]+>", "", html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
    return text.strip()


# ========== CLI 测试 ==========

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python search.py STOCK_CODE")
        sys.exit(1)

    code = sys.argv[1]
    se = StockSearchEngine()
    results = se.search_all(code)

    print(json.dumps(results, ensure_ascii=False, indent=2))
