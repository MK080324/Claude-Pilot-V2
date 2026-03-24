# Phase 2 测试用例

## 基本信息
- Phase: 2
- 生成时间: 2026-03-24
- 依据: roadmap.md Phase 2 验收标准 + interfaces/phase-2-interfaces.md

## 测试用例

### TC-2-001: api 单元测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_api.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-2-002: /health 路由响应正确
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_api.py -v -k "health"`
- **通过标准**: GET /health -> 200 -> JSON {status: "running"}
- **失败时严重程度**: Critical

### TC-2-003: /permission 超时返回 deny
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_api.py -v -k "permission_timeout"`
- **通过标准**: POST /permission -> 不触发审批 -> 超时 -> {decision: "deny"}
- **失败时严重程度**: Critical

### TC-2-004: session_id 白名单校验
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_api.py -v -k "session_id"`
- **通过标准**: 非法 session_id -> 400
- **失败时严重程度**: Critical

### TC-2-005: 127.0.0.1 绑定
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_api.py -v -k "bind"`
- **通过标准**: create_api_app 配置中 host 为 127.0.0.1
- **失败时严重程度**: Critical

### TC-2-006: hooks 单元测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_hooks.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-2-007: hooks read_port 正确
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_hooks.py -v -k "read_port"`
- **通过标准**: 创建临时 .env -> read_port -> 返回正确端口号
- **失败时严重程度**: Critical

### TC-2-008: hooks post_to_bot 正确
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_hooks.py -v -k "post_to_bot"`
- **通过标准**: mock HTTP -> post_to_bot -> 验证请求正确
- **失败时严重程度**: Critical

### TC-2-009: session 高层测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_session.py -v`
- **通过标准**: 全部通过（含 Phase 1 底层 + Phase 2 高层）
- **失败时严重程度**: Critical

### TC-2-010: launch_session mock 测试
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_session.py -v -k "launch_session"`
- **通过标准**: mock tmux -> launch_session -> 返回 SessionInfo
- **失败时严重程度**: Critical

### TC-2-011: inject_message 状态感知测试
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_session.py -v -k "inject_message"`
- **通过标准**: INPUT 直接注入 / GENERATING 先 Escape 再注入 / EXITED 抛异常
- **失败时严重程度**: Critical

### TC-2-012: bot.py 语法正确
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "import ast; ast.parse(open('bot.py').read()); print('OK')"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Critical

### TC-2-013: 每个文件行数 < 200
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "import os; files=['bot.py','api.py','session.py']+[os.path.join('hooks',f) for f in os.listdir('hooks') if f.endswith('.py')]; violations=[(f,sum(1 for _ in open(f))) for f in files if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Major
