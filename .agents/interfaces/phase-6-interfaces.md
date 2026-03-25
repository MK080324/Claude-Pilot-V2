# Phase 6 接口定义

## install.sh

### 脚本行为

install.sh 是 `curl | bash` 一键安装脚本，按以下步骤执行：

1. **依赖检测**: 检查 claude, tmux, python3 是否存在于 PATH 中，缺失则报错退出
2. **项目部署**: 克隆/复制项目文件到 `~/.claude-pilot/`（开发期从 src/ 复制）
3. **Python 依赖安装**: `pip install -r requirements.txt`（使用 venv）
4. **交互收集配置**: 提示用户输入 BOT_TOKEN、ALLOWED_USERS（逗号分隔的 user ID）
5. **写入 .env**: 生成 `~/.claude-pilot/.env`
6. **合并 hooks**: 将 Claude Code hooks 配置合并到 `~/.claude/settings.json`（不覆盖已有配置）
7. **安装 CLI**: 将 claude-pilot 安装到 PATH（如 /usr/local/bin 或 ~/.local/bin）
8. **后台启动**: 调用 claude-pilot start

### .env 格式

```
BOT_TOKEN=<token>
ALLOWED_USERS=<comma-separated-ids>
BOT_PORT=8266
NOTIFY_CHAT_ID=
```

### hooks 合并逻辑

读取已有的 `~/.claude/settings.json`，在 `hooks` 字段中追加 claude-pilot 的 hook 条目。如果已存在同名 hook，不覆盖。如果文件不存在，创建新文件。

hooks 格式参考:
```json
{
  "hooks": {
    "session_start": [{"command": "python3 ~/.claude-pilot/hooks/session_start.py"}],
    "stop": [{"command": "python3 ~/.claude-pilot/hooks/stop.py"}],
    "notification": [{"command": "python3 ~/.claude-pilot/hooks/notification.py"}],
    "permission": [{"command": "python3 ~/.claude-pilot/hooks/permission.py", "timeout": 120}]
  }
}
```

### 函数列表（Shell 函数）

- `check_deps()`: 检测 claude/tmux/python3，缺失返回非零
- `setup_venv()`: 创建 venv 并 pip install
- `collect_config()`: 交互式收集 BOT_TOKEN 和 ALLOWED_USERS
- `write_env(token, users)`: 写入 .env 文件
- `merge_hooks()`: JSON 合并 hooks 到 settings.json（用 python3 内联脚本处理 JSON）
- `install_cli()`: 复制 claude-pilot 到 PATH
- `main()`: 编排以上步骤

## tests/test_integration.py

### 集成测试覆盖

1. **Hook -> API 链路**: mock HTTP POST /session_start -> api.py 处理 -> 返回正确响应
2. **消息注入链路**: 模拟 TG 消息 -> messages.py handler -> session.inject_message -> 验证 tmux 命令
3. **权限审批全链路**: mock POST /permission -> 创建 pending_permissions -> 模拟 callback 审批 -> 返回 decision
4. **.env 格式验证**: 用 config.load_env 解析模拟的 .env -> 验证字段完整
5. **hooks JSON 合并验证**: 模拟已有 settings.json -> 合并新 hooks -> 验证原有配置未被覆盖且新 hooks 已添加
