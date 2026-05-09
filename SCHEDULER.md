# 定时任务调度

两种运行方式：

## 方式 A：macOS launchd（推荐，更稳定）

```bash
# 1. 复制 plist 到 ~/Library/LaunchAgents/
cp launchd/*.plist ~/Library/LaunchAgents/

# 2. 加载并启动
launchctl load ~/Library/LaunchAgents/com.trader-obsidian.inbox.plist
launchctl load ~/Library/LaunchAgents/com.trader-obsidian.review.plist
launchctl load ~/Library/LaunchAgents/com.trader-obsidian.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.trader-obsidian.weekly-review.plist

# 3. 查看状态
launchctl list | grep trader-obsidian

# 4. 停止
launchctl unload ~/Library/LaunchAgents/com.trader-obsidian.inbox.plist
```

| 任务 | 频率 | plist 文件 |
|------|------|-----------|
| Inbox 扫描 | 每 30 分钟 | `com.trader-obsidian.inbox.plist` |
| 日常回测复盘 | 每天 9:00 | `com.trader-obsidian.review.plist` |
| Dashboard 更新 | 每天 8:00 | `com.trader-obsidian.dashboard.plist` |
| **周复盘 + 框架优化建议** | **每周六 10:00** | `com.trader-obsidian.weekly-review.plist` |

日志文件：
- `/tmp/trader-inbox.log`
- `/tmp/trader-review.log`
- `/tmp/trader-dashboard.log`
- `/tmp/trader-weekly-review.log`

## 方式 B：Python 守护进程

```bash
# 安装依赖（可选，标准库 + croniter）
pip install croniter

# 启动守护进程
python scheduler.py --daemon

# 查看状态
python scheduler.py --status

# 停止
python scheduler.py --stop

# 立即运行所有任务一次（测试用）
python scheduler.py --run-once
```

配置通过 `.env`：
```
SCHEDULE_SCAN_INBOX=*/30 * * * *
SCHEDULE_REVIEW=0 9 * * *
SCHEDULE_DASHBOARD=0 8 * * *
SCHEDULE_NOTIFY=true
```

## 通知

两种方式的 `--notify` 都会触发 macOS 桌面通知（需 macOS）。
