# MCP 配置说明

## 步骤 1：安装依赖

```bash
cd C:/Users/Lzw/alma/worktrees/trader/trader-obsidian
pip install mcp
```

## 步骤 2：配置 Claude Desktop

打开 Claude Desktop，进入 Settings → MCP Servers，添加新服务器：

### 方式 A：通过 UI 配置

在 Claude Desktop 中：
1. 点击 "+" 添加 MCP Server
2. 选择 "Command" 类型
3. 填写：
   - **Name**: `trader-obsidian`
   - **Command**: `python`
   - **Arguments**:
     ```
     C:/Users/Lzw/alma/worktrees/trader/trader-obsidian/trader_mcp.py
     ```
   - **Environment**:
     ```
     PYTHONPATH=C:/Users/Lzw/alma/worksects/trader/trader-obsidian
     ```

### 方式 B：直接编辑配置文件

在 Claude Desktop 的配置目录中找到 MCP 配置文件（通常在 `C:/Users/<用户>/AppData/Roaming/Claude/claude_desktop_config.json`），添加：

```json
{
  "mcpServers": {
    "trader-obsidian": {
      "command": "python",
      "args": [
        "C:\\Users\\Lzw\\alma\\worktrees\\trader\\trader-obsidian\\trader_mcp.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\Lzw\\alma\\worktrees\\trader\\trader-obsidian"
      }
    }
  }
}
```

**注意路径分隔符**：
- Windows 配置文件中使用 `\\` 双反斜杠
- 或使用 `/` 单斜杠（JSON 中也支持）

## 步骤 3：验证配置

重启 Claude Desktop 后，在聊天界面中测试：

```
请列出 Inbox 中的所有材料
```

```
获取 AAPL 的分析上下文
```

```
扫描待处理的材料
```

如果 Claude 能正确返回结果，说明 MCP 配置成功。

---

## 可用工具列表

配置成功后，在 Claude Desktop 或 claudian 中可以使用这些工具：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `scan_inbox_tool` | 扫描 Inbox | 无 |
| `get_pending_analysis_tool` | 获取待处理材料 | 无 |
| `get_related_materials_tool` | 获取相关材料 | stock_code |
| `get_stock_context_tool` | 获取 Wiki 上下文 | stock_code |
| `get_stock_index_tool` | 获取股票总览 | 无 |
| `get_recent_log_tool` | 获取最近日志 | n (可选，默认5) |
| `analyze_stock_tool` | 触发分析（获取数据） | stock_code |
| `write_analysis_tool` | 写入分析结果 | stock_code, stock_name, analysis_text, score, core_view |
| `create_task_tool` | 创建任务 | title, ticker, task_type, description, priority, due_date |
| `update_dashboard_tool` | 更新 Dashboard | 无 |

## 资源列表

- `mcp://trader/inbox` — Inbox 概览
- `mcp://trader/stocks` — 股票总览
