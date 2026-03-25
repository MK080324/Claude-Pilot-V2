# Phase 5 测试用例

## 基本信息
- Phase: 5
- 生成时间: 2026-03-24
- 依据: roadmap.md Phase 5 验收标准 + interfaces/phase-5-interfaces.md

## 测试用例

### TC-5-001: crash_reporter 测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_crash_reporter.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-5-002: CLI 测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_cli.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-5-003: crash_reporter PID 检查
- **类型**: 单元测试
- **通过标准**: mock os.kill 成功 -> True, OSError -> False
- **失败时严重程度**: Critical

### TC-5-004: crash_reporter Traceback 提取
- **类型**: 单元测试
- **通过标准**: 含 Traceback 的 log -> 提取正确错误信息
- **失败时严重程度**: Critical

### TC-5-005: crash_reporter 重启计数
- **类型**: 单元测试
- **通过标准**: 连续 5 次 PID 消失 -> 触发警告
- **失败时严重程度**: Major

### TC-5-006: crash_reporter 零外部依赖
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "import ast; tree=ast.parse(open('crash_reporter.py').read()); imports=[n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]+[n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]; third_party=[m for m in imports if m and m.split('.')[0] not in ('os','sys','json','time','urllib','signal','datetime','pathlib','re','traceback','tempfile','socket')]; print('OK' if not third_party else 'FAIL: '+str(third_party))"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Critical

### TC-5-007: CLI --help 输出
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 claude-pilot --help`
- **通过标准**: 退出码 0，输出包含 start/stop/status
- **失败时严重程度**: Critical

### TC-5-008: CLI status 子命令
- **类型**: 单元测试
- **通过标准**: mock .pid -> status 输出"运行中"或"未运行"
- **失败时严重程度**: Critical

### TC-5-009: CLI enable plist 内容
- **类型**: 单元测试
- **通过标准**: 生成 plist 含 KeepAlive, RunAtLoad, ThrottleInterval=30
- **失败时严重程度**: Critical

### TC-5-010: 每个文件行数 < 200
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "violations=[(f,sum(1 for _ in open(f))) for f in ['crash_reporter.py','claude-pilot'] if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Major
