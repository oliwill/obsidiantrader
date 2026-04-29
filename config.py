"""
统一配置管理模块

集中管理所有环境变量，提供默认值和类型转换。
在应用启动时加载一次，各模块直接导入使用。
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 只在首次导入时加载环境变量
load_dotenv()


class Config:
    """应用配置类，集中管理所有环境变量"""

    # ========== 长桥 API（可选）==========
    LONGBRIDGE_APP_KEY: Optional[str] = os.getenv("LONGBRIDGE_APP_KEY")
    LONGBRIDGE_APP_SECRET: Optional[str] = os.getenv("LONGBRIDGE_APP_SECRET")
    LONGBRIDGE_ACCESS_TOKEN: Optional[str] = os.getenv("LONGBRIDGE_ACCESS_TOKEN")

    # ========== 搜索 API（可选）==========
    SERPAPI_KEY: Optional[str] = os.getenv("SERPAPI_KEY")

    # ========== Obsidian Vault 路径 ==========
    WIKI_BASE_DIR: Path = Path(os.getenv("WIKI_BASE_DIR", ""))
    WIKI_SUBDIR: str = os.getenv("WIKI_SUBDIR", "Analysis")
    MATERIALS_SUBDIR: str = os.getenv("MATERIALS_SUBDIR", "Materials")

    # ========== Obsidian 通用目录 ==========
    OBSIDIAN_INBOX_DIR: Path = Path(os.getenv("OBSIDIAN_INBOX_DIR", ""))
    OBSIDIAN_TASKS_DIR: Path = Path(os.getenv("OBSIDIAN_TASKS_DIR", ""))
    OBSIDIAN_DASHBOARD_PATH: Path = Path(os.getenv("OBSIDIAN_DASHBOARD_PATH", ""))

    # ========== 超时配置 ==========
    ANALYSIS_TIMEOUT: int = int(os.getenv("ANALYSIS_TIMEOUT", "30"))

    # ========== 定时任务配置（可选）==========
    SCHEDULE_SCAN_INBOX: Optional[str] = os.getenv("SCHEDULE_SCAN_INBOX")
    SCHEDULE_REVIEW: Optional[str] = os.getenv("SCHEDULE_REVIEW")
    SCHEDULE_DASHBOARD: Optional[str] = os.getenv("SCHEDULE_DASHBOARD")
    SCHEDULE_NOTIFY: Optional[str] = os.getenv("SCHEDULE_NOTIFY")

    @classmethod
    def validate(cls) -> list[str]:
        """
        验证必需的配置项

        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []

        if not cls.WIKI_BASE_DIR:
            errors.append("WIKI_BASE_DIR is required")

        if not cls.OBSIDIAN_INBOX_DIR:
            errors.append("OBSIDIAN_INBOX_DIR is required")

        if not cls.OBSIDIAN_TASKS_DIR:
            errors.append("OBSIDIAN_TASKS_DIR is required")

        if not cls.OBSIDIAN_DASHBOARD_PATH:
            errors.append("OBSIDIAN_DASHBOARD_PATH is required")

        return errors

    @classmethod
    def get_wiki_dir(cls) -> Path:
        """获取 Wiki 目录完整路径"""
        return cls.WIKI_BASE_DIR / cls.WIKI_SUBDIR

    @classmethod
    def get_materials_dir(cls) -> Path:
        """获取 Materials 目录完整路径"""
        return cls.WIKI_BASE_DIR / cls.MATERIALS_SUBDIR


# 验证配置（可选，在需要时调用）
def ensure_config() -> None:
    """确保配置有效，否则抛出异常"""
    errors = Config.validate()
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")


# 导出便捷访问
config = Config
