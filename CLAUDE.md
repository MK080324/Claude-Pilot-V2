# Claude Pilot v2 -- 项目指令

本文件是阶段 C（Agent Teams 并行开发）中 Lead 的行为指令。进入阶段 C 后，Lead 完全按本文件行事。

---

## 项目概述

Claude Pilot v2 是一个 Telegram Bot，用于远程控制和监控 Claude Code CLI 会话。核心能力包括：通过 tmux 统一管理所有 Claude 会话、JSONL 文件监听实现完整对话流推送、两层权限审批通道（Hook 层 + TUI 层）、crash_reporter 崩溃通知与 launchd 自动恢复、一键安装脚本。

技术栈：Python 3.10+, python-telegram-bot v22, aiohttp, mistune, asyncio, tmux CLI, macOS launchd。

## 核心架构

```
Telegram Cloud <-- HTTPS polling --> bot.py (入口 + 组装)
                                       |
                    +------------------+------------------+
                    |                  |                  |
              handlers/           session.py          watcher.py
              commands.py         (tmux 控制          (JSONL 监听
              messages.py          TUI 状态感知)       消息合并
              callbacks.py                             TUI 权限检测)
                    |                  |                  |
                    +--------+---------+                  |
                             |                            |
                          api.py  <--- HTTP POST --- hooks/
                       (aiohttp                     _common.py
                        127.0.0.1)                  session_start.py
                             |                      permission.py
                          config.py                 notification.py
                       (.env + .state.json)         stop.py
                             |
                        renderer.py
                     (Markdown -> TG HTML)

独立进程: crash_reporter.py (urllib 直接调 TG API, launchd 托管)
独立脚本: claude-pilot CLI (argparse, start/stop/status/enable/disable/logs)
独立脚本: install.sh (Bash, curl | bash 一键安装)
```

---

## 目录边界

开发代码全部位于 `src/` 目录下，测试代码位于 `tests/` 目录下。

| Agent | 负责的文件（src/ 下） | 负责的测试文件（tests/ 下） |
|-------|----------------------|--------------------------|
| **dev-core** | config.py, session.py, api.py, bot.py, watcher.py | test_config.py, test_session.py, test_api.py, test_watcher.py |
| **dev-ext** | renderer.py, handlers/commands.py, handlers/messages.py, handlers/callbacks.py, handlers/__init__.py, hooks/_common.py, hooks/session_start.py, hooks/permission.py, hooks/notification.py, hooks/stop.py, crash_reporter.py, claude-pilot (CLI), install.sh | test_renderer.py, test_hooks.py, test_commands.py, test_messages.py, test_callbacks.py, test_crash_reporter.py, test_cli.py, test_integration.py |

**严格规则**：
- 两个 Agent 绝不编辑同一个文件
- Agent 不得修改对方负责目录中的文件
- 根级配置文件（pyproject.toml, requirements.txt 等）由 Lead 管理
- `.agents/` 目录由 Lead 和 QA 管理，开发 Agent 仅可修改自己负责文件中 issue 对应的 status

### 按 Phase 的具体分工

Lead 在每个 Phase 开始时，按此表向 Agent 发送任务指令。

| Phase | dev-core 负责 | dev-ext 负责 | Lead 负责 |
|-------|--------------|-------------|-----------|
| 0 | -- | -- | Lead 独立完成全部脚手架 |
| 1 | config.py + test_config.py, session.py 底层 + test_session.py 底层 | renderer.py + test_renderer.py | 定义任务和接口, 生成 test-case |
| 2 | api.py + test_api.py, session.py 高层追加 + test_session.py 高层追加, bot.py | hooks/ 全部 + test_hooks.py | 定义任务和接口, 生成 test-case |
| 3 | watcher.py + test_watcher.py | -- (无任务，可协助修复 Phase 2 遗留问题) | 定义任务和接口, 生成 test-case |
| 4 | -- (无任务，可协助修复 Phase 3 遗留问题) | handlers/commands.py + handlers/messages.py + handlers/callbacks.py + 对应测试, bot.py handler 注册追加 | 定义任务和接口, 生成 test-case |
| 5 | -- | crash_reporter.py + test_crash_reporter.py, claude-pilot CLI + test_cli.py | 定义任务和接口, 生成 test-case |
| 6 | -- | install.sh + test_integration.py | 全量回归, 定义任务和接口, 生成 test-case |

注意 Phase 4 中 bot.py 的 handler 注册部分由 dev-ext 追加（因为 handlers 由 dev-ext 负责）。dev-core 在 Phase 2 完成 bot.py 的骨架后，bot.py 中 handler 注册区域的后续追加交给 dev-ext。为避免冲突，bot.py 中会有一个明确的注释标记 `# --- Handler Registration (dev-ext maintains below this line) ---`，dev-ext 只在此标记之下追加代码。

---

## 接口/通信约定

### 接口定义位置

Lead 在每个 Phase 开始前，将本 Phase 的所有接口定义写入 `.agents/interfaces/phase-N-interfaces.md`。

### 接口定义模板

```
### [接口类型]: [接口名]
- 方向: [调用方] -> [被调方]
- 参数: { field: type, ... }
- 返回值: { field: type, ... }
- 错误: 可能的错误类型及含义
- 副作用: [状态变更描述]
```

### 核心跨模块接口（全 Phase 通用）

以下接口在 structure.md 中已完整定义，各 Phase 实现时严格遵循：

1. **HTTP POST 接口**（hooks/ -> api.py）：/session_start, /session_stop, /permission, /notification, /health
2. **内部函数调用接口**：session.inject_message, session.detect_tui_state, session.launch_session, watcher.start_watcher, config.save_state, renderer.render_markdown
3. **asyncio.Event 协作**：api.py pending_permissions <-> callbacks.py 审批响应
4. **callback_data 前缀约定**：allow:, deny:, tui_allow:, tui_deny:, project:, delete_confirm:, delete_cancel:

开发 Agent 必须严格按接口定义开发。接口变更必须通过 SendMessage 通知相关 Agent 和 Lead，等待确认后才能继续。

---

## Agent Teams 工作流

### 角色

| 角色 | 模式 | 职责 |
|------|------|------|
| **Lead** | -- | 任务分解、接口定义、test-case 生成、Phase 推进、QA 调度、git 操作、Phase 0 独立开发 |
| **dev-core** | Teammate | 核心模块开发：config, session, api, bot, watcher 及其测试 |
| **dev-ext** | Teammate | 扩展模块开发：renderer, handlers, hooks, crash_reporter, CLI, install.sh 及其测试 |
| **QA** | Subagent | 按 test-case 执行验收、issue 产出（Lead 按需调用，非常驻） |

### 流程

每个 Phase 按以下步骤执行：

1. **Lead 定义任务、接口和测试用例**
   - 在 `.agents/interfaces/phase-N-interfaces.md` 写明本 Phase 的所有接口
   - 生成 `.agents/test-cases/phase-N-test-cases.md`（必须覆盖 roadmap 中该 Phase 的所有验收标准，可以增加额外用例但不能遗漏）
   - 通过 SendMessage 向各开发 Agent 发送任务指令，告知负责的具体文件和参考文档

2. **并行开发**
   - 开发 Agent 按接口并行实现各自部分
   - Agent 可参考 test-case 理解验收预期
   - Agent 完成编码后，自行运行对应的测试命令确保通过

3. **接口沟通**
   - 如需调整接口，Agent 必须通过 SendMessage 通知相关 Agent 和 Lead
   - 等待确认后才能继续

4. **完成通知**
   - 每个 Agent 完成后通过 SendMessage 向 Lead 发送完成通知
   - 通知内容包括：完成的文件列表、测试结果、遇到的问题

5. **QA 验收**
   - Lead 收到所有开发 Agent 的完成通知后，调用 QA Subagent 验收
   - QA 按 `.agents/test-cases/phase-N-test-cases.md` 逐条执行测试
   - 发现的问题写入 `.agents/issues/phase-N/` 目录

6. **问题修复**
   - QA 不通过时，Lead 通过 SendMessage 告知对应 Agent：
     "QA 验收未通过，请阅读 `.agents/issues/phase-N/` 下的 issue 文件并逐一修复。"
   - Agent 自行读取 issue 文件修复，修复后将 issue 的 status 改为 `resolved`

7. **QA 重新验收**
   - Lead 再次调用 QA，QA 重新跑全部 test-case
   - 可新增 issue 也可 reopen 旧的

8. **通过判定**
   - 不存在 Critical 或 Major 级别的 `open` issue
   - Minor 级别的 `open` issue 不阻塞通过，但记录在案
   - Lead 执行 git commit
   - Lead 更新检查点文件
   - 进入下一个 Phase

### 8 轮升级机制

连续 8 个完整的"修复 -> 验收"循环仍不通过时：
1. Lead 要求 Agent 说明无法满足的具体条件和卡点原因
2. Lead 汇总信息，向人类报告并请求介入
3. 报告内容包括：Phase 编号、未通过的验收项、Agent 的卡点说明、建议的解决方向

### Issue 生命周期

- Issue 文件路径：`.agents/issues/phase-{N}/{seq}-{brief}.md`
- Issue 文件带 status frontmatter：
  ```yaml
  ---
  status: open  # open / resolved
  severity: Critical / Major / Minor
  phase: N
  date: YYYY-MM-DD
  ---
  ```
- Agent 修复后将 status 改为 `resolved`
- QA 每轮重新跑全部 test-case，可新增 issue 也可将已 resolved 的 reopen（改回 `open`）
- 最终通过判定：不存在 Critical 或 Major 级别的 `open` issue

### 并行策略

| Phase | 并行情况 | 说明 |
|-------|---------|------|
| 0 | 不并行 | Lead 独立完成 |
| 1 | 2 路并行 | dev-core: config + session 底层; dev-ext: renderer |
| 2 | 2 路并行 | dev-core: api + session 高层 + bot; dev-ext: hooks |
| 3 | 不并行 | dev-core 独立完成 watcher |
| 4 | 不并行 | dev-ext 独立完成 handlers (commands/messages/callbacks 虽然是三个文件但都在 dev-ext 目录边界内，由 dev-ext 串行完成) |
| 5 | 2 路并行 | dev-core 无任务; dev-ext: crash_reporter + CLI (两个独立文件可由 dev-ext 串行完成) |
| 6 | 不并行 | dev-ext 独立完成 install.sh + 集成测试 |

### Git 操作约定

- **Lead 负责所有 git 操作**（commit, push, branch）
- 开发 Agent 和 QA 只写代码/测试，不做 git 操作
- 每个 Phase 验收通过后，Lead 做一次 commit
- commit 消息格式：`feat(phase-N): [Phase 目标简述]`

---

## 检查点机制

每个 Phase 验收通过后，Lead 更新 `.agents/status/phase` 文件：

```
C_PHASE_0_COMPLETED
C_PHASE_1_COMPLETED
C_PHASE_2_COMPLETED
C_PHASE_3_COMPLETED
C_PHASE_4_COMPLETED
C_PHASE_5_COMPLETED
C_PHASE_6_COMPLETED
C_COMPLETED
```

如果 session 中断，新 session 启动时 Lead 先检查此文件，从上次完成的 Phase 之后继续。

**恢复流程**：
1. 读取 `.agents/status/phase` 确定当前进度
2. 读取本文件（CLAUDE.md）恢复工作流上下文
3. 读取 `docs/roadmap.md` 确定下一个 Phase 的任务
4. 检查 `.agents/issues/` 是否有未解决的 issue
5. 从断点处继续

---

## 技术要求

### Python 编码规范
- Python 3.10+ 语法，使用 type hints
- 每个 .py 文件行数上限 200 行（硬性约束）
- 使用 dataclass 定义数据结构
- 异步代码使用 async/await，不使用回调风格
- 所有 tmux 操作通过 asyncio.create_subprocess_exec

### 测试规范
- 测试框架：pytest + pytest-asyncio
- 外部依赖（tmux, Telegram API, 文件系统）全部 mock
- 测试文件命名：test_<module>.py
- 异步测试使用 @pytest.mark.asyncio 装饰器

### 安全规范
- HTTP API 仅绑定 127.0.0.1
- session_id 白名单校验：`^[a-f0-9\-]{8,36}$`
- tmux 注入前过滤控制字符：`[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`
- 所有 ALLOWED_USERS 鉴权检查

### 项目路径
- 项目根目录：`/Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2`
- 源码目录：`src/`
- 测试目录：`tests/`
- 开发期使用 `src/` 目录结构，部署时映射到 `~/.claude-pilot/`

---

## 验收标准速查

| Phase | 自动验收（阻塞） | 延迟人工验收（不阻塞） |
|-------|----------------|---------------------|
| 0 | 依赖安装 OK, import 链完整, pytest 可发现测试, 接口签名存在, 每文件 < 200 行 | -- |
| 1 | config/renderer/session 单元测试全通过, 每文件 < 200 行 | -- |
| 2 | api/hooks/session 高层测试全通过, /health 200, /permission 超时返回 deny, bot.py 语法正确, 每文件 < 200 行 | -- |
| 3 | watcher 单元测试全通过（增量读取、UUID/source/internal 去重、消息合并、TUI 检测）, 每文件 < 200 行 | -- |
| 4 | commands/messages/callbacks 测试全通过, bot.py handler 注册完整, 每文件 < 200 行 | /setup UI 体验, /projects 按钮布局 |
| 5 | crash_reporter/CLI 测试全通过, crash_reporter 零外部依赖, CLI --help 正常, 每文件 < 200 行 | launchd 实际加载, 崩溃通知到达手机, 30 秒内恢复 |
| 6 | install.sh 语法 OK, 全量测试通过, 集成测试通过, 所有文件 < 200 行, requirements.txt 完整 | 全新 macOS 端到端, /setup 全流程, 延迟 < 3s, 并发安全, TUI 审批, 对话流/历史回显显示效果 |

---

## 参考文档

- 需求文档：docs/requirement.md
- 技术调研：docs/technical-research.md
- 技术架构：docs/structure.md（模块划分、接口签名、数据流）
- 开发路线图：docs/roadmap.md（Phase 划分、任务列表、验收标准）
