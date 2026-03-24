# Phase 4 测试用例

## 基本信息
- Phase: 4
- 生成时间: 2026-03-24
- 依据: roadmap.md Phase 4 验收标准 + interfaces/phase-4-interfaces.md

## 测试用例

### TC-4-001: commands 测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_commands.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-4-002: messages 测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_messages.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-4-003: callbacks 测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_callbacks.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-4-004: /status 命令输出格式
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_commands.py -v -k "status"`
- **通过标准**: 输出包含活跃会话信息
- **失败时严重程度**: Major

### TC-4-005: /bypass 命令切换
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_commands.py -v -k "bypass"`
- **通过标准**: True -> False -> True 切换
- **失败时严重程度**: Major

### TC-4-006: /delete 二次确认
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_commands.py -v -k "delete"`
- **通过标准**: 发送确认按钮，未确认前 session 未删除
- **失败时严重程度**: Major

### TC-4-007: messages 鉴权检查
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_messages.py -v -k "auth"`
- **通过标准**: 非 ALLOWED_USERS -> 不处理
- **失败时严重程度**: Critical

### TC-4-008: messages 无 session 提示
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_messages.py -v -k "no_session"`
- **通过标准**: 无关联 session -> 返回提示
- **失败时严重程度**: Major

### TC-4-009: messages SessionDead 处理
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_messages.py -v -k "dead"`
- **通过标准**: SessionDead -> "会话已结束"
- **失败时严重程度**: Major

### TC-4-010: callbacks Hook 层审批
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_callbacks.py -v -k "hook_allow"`
- **通过标准**: allow -> event.is_set(), decision="allow"
- **失败时严重程度**: Critical

### TC-4-011: callbacks TUI 层审批
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_callbacks.py -v -k "tui"`
- **通过标准**: tui_allow -> respond_tui_permission(pane_id, True) 被调用
- **失败时严重程度**: Critical

### TC-4-012: callbacks 目录选择
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_callbacks.py -v -k "project"`
- **通过标准**: project:{path} -> launch_session 被调用
- **失败时严重程度**: Major

### TC-4-013: bot.py handler 注册完整
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "import ast; tree=ast.parse(open('bot.py').read()); calls=[n for n in ast.walk(tree) if isinstance(n, ast.Call) and hasattr(n.func, 'attr') and n.func.attr=='add_handler']; print('OK' if len(calls)>=3 else f'FAIL: only {len(calls)} add_handler calls')"`
- **通过标准**: 输出 OK (至少 3 个 add_handler)
- **失败时严重程度**: Critical

### TC-4-014: 每个 handler 文件行数 < 200
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src/handlers && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "import os; violations=[(f,sum(1 for _ in open(f))) for f in os.listdir('.') if f.endswith('.py') and sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Major
