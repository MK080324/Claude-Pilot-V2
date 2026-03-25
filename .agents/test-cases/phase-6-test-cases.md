# Phase 6 测试用例

## 基本信息
- Phase: 6
- 生成时间: 2026-03-25
- 依据: roadmap.md Phase 6 验收标准 + interfaces/phase-6-interfaces.md

## 测试用例

### TC-6-001: install.sh 语法正确
- **类型**: 编译检查
- **验证命令**: `bash -n /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src/install.sh`
- **通过标准**: 退出码 0
- **失败时严重程度**: Critical

### TC-6-002: 全量测试套件通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/ -v --tb=short`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-6-003: 集成测试通过
- **类型**: 集成测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_integration.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-6-004: 所有 .py 文件行数 < 200
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "import os; all_py=[]; [all_py.extend([os.path.join(r,f) for f in fs if f.endswith('.py')]) for r,_,fs in os.walk('.')]; violations=[(f,sum(1 for _ in open(f))) for f in all_py if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Major

### TC-6-005: requirements.txt 完整
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pip install -r requirements.txt --dry-run 2>&1 | tail -1`
- **通过标准**: 退出码 0
- **失败时严重程度**: Major

### TC-6-006: 集成测试 - Hook -> API 链路
- **类型**: 集成测试
- **通过标准**: POST /session_start 返回正确 JSON 响应，session 状态正确
- **失败时严重程度**: Critical

### TC-6-007: 集成测试 - 消息注入链路
- **类型**: 集成测试
- **通过标准**: TG 消息 -> messages handler -> inject_message -> tmux 命令序列正确
- **失败时严重程度**: Critical

### TC-6-008: 集成测试 - 权限审批全链路
- **类型**: 集成测试
- **通过标准**: POST /permission -> pending_permissions 创建 -> callback 审批 -> 返回 allow/deny decision
- **失败时严重程度**: Critical

### TC-6-009: 集成测试 - .env 格式验证
- **类型**: 集成测试
- **通过标准**: 模拟 .env 文件 -> load_env 解析成功 -> BOT_TOKEN, ALLOWED_USERS, BOT_PORT 字段完整
- **失败时严重程度**: Critical

### TC-6-010: 集成测试 - hooks JSON 合并
- **类型**: 集成测试
- **通过标准**: 已有 settings.json 中的原有 hooks 未被覆盖，新 hooks 已添加
- **失败时严重程度**: Critical

### TC-6-011: install.sh 行数合理
- **类型**: 编译检查
- **验证命令**: `wc -l /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src/install.sh`
- **通过标准**: 行数 < 300
- **失败时严重程度**: Minor
