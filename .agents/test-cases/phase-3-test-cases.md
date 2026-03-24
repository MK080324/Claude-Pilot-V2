# Phase 3 测试用例

## 基本信息
- Phase: 3
- 生成时间: 2026-03-24
- 依据: roadmap.md Phase 3 验收标准 + interfaces/phase-3-interfaces.md

## 测试用例

### TC-3-001: watcher 全套单元测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-3-002: JSONL 增量读取
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "incremental"`
- **通过标准**: 创建临时 JSONL -> 写入 3 行 -> _read_jsonl_incremental 返回 3 个事件 -> 追加 2 行 -> 再次调用返回 2 个新事件
- **失败时严重程度**: Critical

### TC-3-003: UUID 去重
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "uuid"`
- **通过标准**: 同一 uuid 事件发送两次 -> _process_event 只处理一次
- **失败时严重程度**: Critical

### TC-3-004: source 去重（telegram）
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "source_telegram"`
- **通过标准**: source="telegram" + userType="external" user 事件 -> 不推送
- **失败时严重程度**: Critical

### TC-3-005: source 不去重（terminal）
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "source_terminal"`
- **通过标准**: source="terminal" + userType="external" user 事件 -> 正常推送
- **失败时严重程度**: Critical

### TC-3-006: internal 事件过滤
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "internal"`
- **通过标准**: userType="internal" user 事件 -> 不推送
- **失败时严重程度**: Critical

### TC-3-007: assistant 事件解析
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "assistant"`
- **通过标准**: assistant 事件含 text + tool_use -> 正确提取文本和工具摘要
- **失败时严重程度**: Critical

### TC-3-008: 消息合并机制
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "flush" or -k "merge"`
- **通过标准**: 短时间内多个事件 -> 合并为一条消息 -> send 调用次数 < 事件数
- **失败时严重程度**: Critical

### TC-3-009: 指数退避重试
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "retry"`
- **通过标准**: mock send 失败 -> 重试最多 3 次
- **失败时严重程度**: Critical

### TC-3-010: TUI 权限检测集成
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "tui"`
- **通过标准**: mock detect_tui_state 返回 PERMISSION_PROMPT -> 审批消息发送
- **失败时严重程度**: Critical

### TC-3-011: start_watcher 返回 Task
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "start_watcher"`
- **通过标准**: 返回值是 asyncio.Task -> 可取消
- **失败时严重程度**: Critical

### TC-3-012: stop_watcher 取消任务
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_watcher.py -v -k "stop_watcher"`
- **通过标准**: start -> stop -> task 已 cancel
- **失败时严重程度**: Critical

### TC-3-013: watcher.py 行数 < 200
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "lines=sum(1 for _ in open('watcher.py')); print('OK' if lines<=200 else f'FAIL: {lines} lines')"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Major
