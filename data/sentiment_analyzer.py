#!/usr/bin/env python3
"""
情绪量化分析器

基于规则的情绪评分系统：
1. 新闻情绪评分
2. 社交媒体热度
3. 恐惧/贪婪指数
"""
import re
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class SentimentResult:
    """情绪分析结果"""
    overall_score: float  # -10 到 +10
    overall_label: str
    news_score: float
    social_score: float
    fear_greed_index: int  # 0-100
    key_topics: List[str]
    summary: str


class SentimentAnalyzer:
    """情绪量化分析器"""

    # 正面关键词
    POSITIVE_WORDS = [
        "beat", "surpass", "exceed", "growth", "profit", "bullish",
        "upgrade", "outperform", "strong", "breakthrough", "milestone",
        "partnership", "expansion", "record", "surge", "rally",
        "超预期", "增长", "盈利", "突破", "合作", "扩张", "升级"
    ]

    # 负面关键词
    NEGATIVE_WORDS = [
        "miss", "loss", "decline", "bearish", "downgrade", "underperform",
        "weak", "layoff", "lawsuit", "investigation", "recall", "debt",
        "bankruptcy", "crash", "plunge", "sell", "short",
        "不及预期", "亏损", "下降", "裁员", "诉讼", "调查", "召回", "债务"
    ]

    # 恐惧关键词
    FEAR_WORDS = [
        "crash", "collapse", "crisis", "recession", "panic", "sell-off",
        "plunge", "tank", "dump", "bloodbath", "meltdown",
        "崩盘", "危机", "衰退", "恐慌", "抛售", "暴跌"
    ]

    # 贪婪关键词
    GREED_WORDS = [
        "moon", "rocket", "explode", "surge", "rally", "boom",
        "fomo", "yolo", "diamond hands", "to the moon",
        "暴涨", "火箭", "起飞", "暴富"
    ]

    def analyze(self, web_search_data: Dict[str, Any]) -> SentimentResult:
        """
        分析市场情绪

        Args:
            web_search_data: 来自网络搜索的数据

        Returns:
            情绪分析结果
        """
        # 收集所有文本
        all_texts = self._extract_texts(web_search_data)

        # 计算各维度评分
        news_score = self._analyze_news_sentiment(all_texts.get("news", []))
        social_score = self._analyze_social_sentiment(all_texts.get("social", []))
        fear_greed = self._calculate_fear_greed_index(all_texts)

        # 提取关键话题
        key_topics = self._extract_topics(all_texts)

        # 综合评分 (-10 到 +10)
        overall_score = round((news_score + social_score) / 2, 1)

        # 标签
        if overall_score >= 5:
            label = "极度乐观"
        elif overall_score >= 2:
            label = "乐观"
        elif overall_score >= -2:
            label = "中性"
        elif overall_score >= -5:
            label = "悲观"
        else:
            label = "极度悲观"

        # 生成总结
        summary = self._generate_summary(overall_score, fear_greed, key_topics)

        return SentimentResult(
            overall_score=overall_score,
            overall_label=label,
            news_score=news_score,
            social_score=social_score,
            fear_greed_index=fear_greed,
            key_topics=key_topics,
            summary=summary
        )

    def _extract_texts(self, web_search_data: Dict) -> Dict[str, List[str]]:
        """从搜索数据中提取文本"""
        texts = {"news": [], "social": [], "analyst": [], "reddit": []}

        if not web_search_data:
            return texts

        # 新闻
        for item in web_search_data.get("news", []):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            texts["news"].append(f"{title} {snippet}")

        # 社交媒体
        for item in web_search_data.get("social", []):
            texts["social"].append(item.get("content", ""))

        # 分析师
        for item in web_search_data.get("analyst", []):
            texts["analyst"].append(item.get("summary", ""))

        # Reddit
        for item in web_search_data.get("reddit", []):
            texts["reddit"].append(item.get("title", ""))

        return texts

    def _analyze_news_sentiment(self, texts: List[str]) -> float:
        """分析新闻情绪 (-10 到 +10)"""
        if not texts:
            return 0.0

        total_score = 0
        for text in texts:
            text_lower = text.lower()
            pos_count = sum(1 for w in self.POSITIVE_WORDS if w in text_lower)
            neg_count = sum(1 for w in self.NEGATIVE_WORDS if w in text_lower)

            # 计算单条情绪
            if pos_count + neg_count > 0:
                sentiment = (pos_count - neg_count) / (pos_count + neg_count) * 10
            else:
                sentiment = 0

            total_score += sentiment

        return round(total_score / len(texts), 1)

    def _analyze_social_sentiment(self, texts: List[str]) -> float:
        """分析社交媒体情绪 (-10 到 +10)"""
        if not texts:
            return 0.0

        total_score = 0
        for text in texts:
            text_lower = text.lower()
            pos_count = sum(1 for w in self.POSITIVE_WORDS if w in text_lower)
            neg_count = sum(1 for w in self.NEGATIVE_WORDS if w in text_lower)

            # 社交媒体权重更高（更情绪化）
            if pos_count + neg_count > 0:
                sentiment = (pos_count - neg_count) / (pos_count + neg_count) * 10 * 1.2
            else:
                sentiment = 0

            total_score += max(-10, min(10, sentiment))

        return round(total_score / len(texts), 1)

    def _calculate_fear_greed_index(self, all_texts: Dict[str, List[str]]) -> int:
        """
        计算恐惧/贪婪指数 (0-100)
        0 = 极度恐惧, 50 = 中性, 100 = 极度贪婪
        """
        all_text = " ".join(
            " ".join(texts)
            for texts in all_texts.values()
        ).lower()

        if not all_text:
            return 50

        fear_count = sum(1 for w in self.FEAR_WORDS if w in all_text)
        greed_count = sum(1 for w in self.GREED_WORDS if w in all_text)
        total = fear_count + greed_count

        if total == 0:
            return 50

        # 贪婪比例 -> 0-100
        greed_ratio = greed_count / total
        index = int(greed_ratio * 100)

        return max(0, min(100, index))

    def _extract_topics(self, all_texts: Dict[str, List[str]]) -> List[str]:
        """提取关键话题"""
        all_text = " ".join(
            " ".join(texts)
            for texts in all_texts.values()
        ).lower()

        # 简单的关键词频率提取
        words = re.findall(r'\b[A-Za-z]{4,}\b', all_text)
        word_freq = {}
        for w in words:
            if w not in ["this", "that", "with", "from", "have", "been", "were", "they", "their", "what", "when", "where", "which", "while", "about", "would", "could", "should"]:
                word_freq[w] = word_freq.get(w, 0) + 1

        # 返回出现频率最高的词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:5]]

    def _generate_summary(
        self,
        score: float,
        fear_greed: int,
        topics: List[str]
    ) -> str:
        """生成情绪总结"""
        if fear_greed >= 75:
            fg_desc = "市场贪婪"
        elif fear_greed >= 55:
            fg_desc = "偏向贪婪"
        elif fear_greed >= 45:
            fg_desc = "情绪中性"
        elif fear_greed >= 25:
            fg_desc = "偏向恐惧"
        else:
            fg_desc = "市场恐惧"

        topic_str = "、".join(topics[:3]) if topics else "无明显热点"

        return f"{fg_desc}，情绪得分 {score:+.1f}，市场关注: {topic_str}"

    def format_result(self, result: SentimentResult) -> str:
        """格式化为 Markdown"""
        fg_emoji = "😨" if result.fear_greed_index < 25 else "😰" if result.fear_greed_index < 45 else "😐" if result.fear_greed_index < 55 else "😏" if result.fear_greed_index < 75 else "🤑"

        lines = [
            f"**综合情绪**: {result.overall_label} ({result.overall_score:+.1f}/10)",
            f"",
            f"| 维度 | 评分 |",
            f"|------|------|",
            f"| 新闻情绪 | {result.news_score:+.1f} |",
            f"| 社交媒体 | {result.social_score:+.1f} |",
            f"| 恐惧/贪婪 | {fg_emoji} {result.fear_greed_index}/100 |",
            f"",
            f"**市场热点**: {', '.join(result.key_topics)}",
            f"",
            f"**总结**: {result.summary}",
        ]

        return "\n".join(lines)
