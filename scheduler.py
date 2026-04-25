"""
任务调度器 - Python 守护进程模式（可选）

如果不想用 launchd/cron，可以用这个 Python 守护进程。

用法:
    python scheduler.py              # 前台运行
    python scheduler.py --daemon     # 后台守护进程
    python scheduler.py --stop       # 停止守护进程
    python scheduler.py --status     # 查看状态

任务配置（通过 .env）:
    SCHEDULE_SCAN_INBOX=*/30 * * * *     # 每30分钟扫描Inbox
    SCHEDULE_REVIEW=0 9 * * *            # 每天9:00复盘
    SCHEDULE_DASHBOARD=0 8 * * *         # 每天8:00更新Dashboard
    SCHEDULE_NOTIFY=true                 # 是否发送通知
"""
import os
import sys
import time
import signal
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from croniter import croniter

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("trader_scheduler")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

PID_FILE = Path("/tmp/trader-obsidian-scheduler.pid")
LOG_FILE = Path("/tmp/trader-obsidian-scheduler.log")

# 默认调度配置
DEFAULT_SCHEDULE = {
    "scan_inbox": "*/30 * * * *",      # 每30分钟
    "review": "0 9 * * *",              # 每天9:00
    "dashboard": "0 8 * * *",           # 每天8:00
}


def _get_schedule(key: str) -> str:
    """从环境变量读取调度配置，使用默认值"""
    env_key = f"SCHEDULE_{key.upper()}"
    return os.getenv(env_key, DEFAULT_SCHEDULE.get(key, ""))


def _should_run(schedule_expr: str, last_run: datetime) -> bool:
    """检查是否应该执行任务"""
    if not schedule_expr:
        return False
    try:
        itr = croniter(schedule_expr, last_run)
        next_run = itr.get_next(datetime)
        return datetime.now() >= next_run
    except Exception:
        return False


def run_task(script_name: str) -> bool:
    """执行一个脚本任务"""
    script_path = PROJECT_DIR / "scripts" / script_name
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False

    try:
        notify_flag = "--notify" if os.getenv("SCHEDULE_NOTIFY", "true").lower() == "true" else ""
        cmd = [sys.executable, str(script_path)]
        if notify_flag:
            cmd.append(notify_flag)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=PROJECT_DIR,
        )

        if result.returncode == 0:
            logger.info(f"✅ {script_name}: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"❌ {script_name}: {result.stderr.strip()}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"⏱️ {script_name}: 超时")
        return False
    except Exception as e:
        logger.error(f"💥 {script_name}: {e}")
        return False


class Scheduler:
    """任务调度器"""

    def __init__(self):
        self.running = False
        self.last_runs = {
            "scan_inbox": datetime.min,
            "review": datetime.min,
            "dashboard": datetime.min,
        }
        self.sleep_interval = 60  # 每分钟检查一次

    def start(self):
        """启动调度器主循环"""
        logger.info("🚀 调度器启动")
        logger.info(f"   Inbox扫描: {_get_schedule('scan_inbox')}")
        logger.info(f"   回测复盘: {_get_schedule('review')}")
        logger.info(f"   Dashboard: {_get_schedule('dashboard')}")

        self.running = True

        # 注册信号处理
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        while self.running:
            self._tick()
            time.sleep(self.sleep_interval)

        logger.info("🛑 调度器停止")

    def _tick(self):
        """单次调度检查"""
        now = datetime.now()

        # 扫描 Inbox
        if _should_run(_get_schedule("scan_inbox"), self.last_runs["scan_inbox"]):
            if run_task("scan_inbox.py"):
                self.last_runs["scan_inbox"] = now

        # 回测复盘
        if _should_run(_get_schedule("review"), self.last_runs["review"]):
            if run_task("run_review.py"):
                self.last_runs["review"] = now

        # 更新 Dashboard
        if _should_run(_get_schedule("dashboard"), self.last_runs["dashboard"]):
            if run_task("update_dashboard.py"):
                self.last_runs["dashboard"] = now

    def _handle_signal(self, signum, frame):
        """处理终止信号"""
        logger.info(f"收到信号 {signum}，准备停止...")
        self.running = False


def start_daemon():
    """启动守护进程"""
    # 检查是否已在运行
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)  # 检查进程是否存在
            logger.error(f"调度器已在运行 (PID: {old_pid})")
            return 1
        except (OSError, ValueError):
            pass  # 进程不存在，继续

    # 创建子进程
    pid = os.fork()
    if pid > 0:
        # 父进程退出
        print(f"调度器已启动 (PID: {pid})")
        return 0

    # 子进程成为守护进程
    os.setsid()
    os.umask(0)

    # 重定向输出
    sys.stdout.flush()
    sys.stderr.flush()
    with open(LOG_FILE, "a+") as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())

    # 写 PID 文件
    PID_FILE.write_text(str(os.getpid()))

    # 启动调度器
    scheduler = Scheduler()
    try:
        scheduler.start()
    finally:
        PID_FILE.unlink(missing_ok=True)

    return 0


def stop_daemon():
    """停止守护进程"""
    if not PID_FILE.exists():
        print("调度器未在运行")
        return 0

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"已发送停止信号 (PID: {pid})")

        # 等待进程退出
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                print("调度器已停止")
                PID_FILE.unlink(missing_ok=True)
                return 0

        print("进程未响应，强制终止")
        os.kill(pid, signal.SIGKILL)
        PID_FILE.unlink(missing_ok=True)
        return 0

    except Exception as e:
        print(f"停止失败: {e}")
        return 1


def status_daemon():
    """查看守护进程状态"""
    if not PID_FILE.exists():
        print("❌ 调度器未运行")
        return 1

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        print(f"✅ 调度器运行中 (PID: {pid})")
        print(f"   日志: {LOG_FILE}")
        if LOG_FILE.exists():
            # 显示最后5行日志
            lines = LOG_FILE.read_text().strip().split("\n")[-5:]
            print("   最近日志:")
            for line in lines:
                print(f"     {line}")
        return 0
    except (OSError, ValueError):
        print("❌ PID 文件存在但进程已消失")
        PID_FILE.unlink(missing_ok=True)
        return 1


def main():
    parser = argparse.ArgumentParser(description="Trader-Obsidian Scheduler")
    parser.add_argument("--daemon", action="store_true", help="后台守护进程模式")
    parser.add_argument("--stop", action="store_true", help="停止守护进程")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--run-once", action="store_true", help="立即运行所有任务一次")
    args = parser.parse_args()

    if args.stop:
        return stop_daemon()

    if args.status:
        return status_daemon()

    if args.run_once:
        logger.info("🔄 立即运行所有任务...")
        scheduler = Scheduler()
        scheduler._tick()
        return 0

    if args.daemon:
        return start_daemon()

    # 默认: 前台运行
    scheduler = Scheduler()
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n👋 再见")
    return 0


if __name__ == "__main__":
    sys.exit(main())
