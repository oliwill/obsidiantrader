"""
通知模块 - macOS 桌面通知

用法:
    from notification import notify
    notify("分析完成", "AAPL 分析报告已写入 Obsidian")

    from notification import notify_error
    notify_error("数据获取失败", "Longbridge API 超时")
"""
import os
import subprocess
from datetime import datetime
from typing import Optional


def notify(title: str, message: str, sound: bool = True) -> bool:
    """
    发送 macOS 桌面通知

    Args:
        title: 通知标题
        message: 通知内容
        sound: 是否播放提示音

    Returns:
        是否成功发送
    """
    try:
        sound_cmd = 'sound name "Glass"' if sound else ""
        script = f'display notification "{message}" with title "{title}" {sound_cmd}'
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        # fallback: 打印到 stderr
        print(f"[NOTIFY] {title}: {message}", flush=True)
        return False


def notify_error(title: str, message: str) -> bool:
    """发送错误通知（带错误音效）"""
    try:
        script = f'display notification "{message}" with title "❌ {title}" sound name "Basso"'
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        print(f"[ERROR] {title}: {message}", flush=True)
        return False


def notify_success(title: str, message: str) -> bool:
    """发送成功通知"""
    return notify(f"✅ {title}", message, sound=True)


# ========== CLI 测试 ==========

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python notification.py <title> <message> [--error]")
        sys.exit(1)

    title = sys.argv[1]
    message = sys.argv[2]
    is_error = "--error" in sys.argv

    if is_error:
        notify_error(title, message)
    else:
        notify(title, message)
