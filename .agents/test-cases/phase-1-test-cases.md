# Phase 1 测试用例

## 基本信息
- Phase: 1
- 生成时间: 2026-03-24
- 依据: roadmap.md Phase 1 验收标准 + interfaces/phase-1-interfaces.md

## 测试用例

### TC-1-001: config load_env 解析正确
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_config.py -v -k "load_env"`
- **通过标准**: 创建临时 .env 文件 -> load_env -> 验证 Config 字段值，assert 全部通过
- **失败时严重程度**: Critical

### TC-1-002: config save_state 原子性
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_config.py -v -k "save_state"`
- **通过标准**: save_state 写入 -> 验证文件存在且 JSON 可解析 -> 验证不存在 .tmp 残留文件
- **失败时严重程度**: Critical

### TC-1-003: config load_state 空文件处理
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_config.py -v -k "load_state"`
- **通过标准**: 对不存在的文件调用 load_state -> 返回空 State 对象
- **失败时严重程度**: Critical

### TC-1-004: config 全套单元测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_config.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-1-005: renderer Markdown 转换正确
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_renderer.py -v -k "render_markdown"`
- **通过标准**: **bold**->b, `code`->code, 代码块->pre, 链接->a
- **失败时严重程度**: Critical

### TC-1-006: renderer split_message 边界正确
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_renderer.py -v -k "split_message"`
- **通过标准**: 4096+ 字符文本 -> 每段 <= 4096 字符 -> 不在 HTML 标签中间切分
- **失败时严重程度**: Critical

### TC-1-007: renderer format_tool_use 正确
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_renderer.py -v -k "format_tool_use"`
- **通过标准**: Bash/Edit/Write 工具调用格式化输出验证
- **失败时严重程度**: Major

### TC-1-008: renderer 全套单元测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_renderer.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-1-009: session detect_tui_state 四种状态
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_session.py -v -k "detect_tui_state"`
- **通过标准**: mock capture-pane 返回值 -> 验证 INPUT/GENERATING/EXITED/PERMISSION_PROMPT 四种状态
- **失败时严重程度**: Critical

### TC-1-010: session 控制字符过滤
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_session.py -v -k "control_char"`
- **通过标准**: 含控制字符和 ANSI 序列的文本 -> 过滤后不含控制字符
- **失败时严重程度**: Critical

### TC-1-011: session 全套单元测试通过
- **类型**: 单元测试
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2 && .venv/bin/python3 -m pytest tests/test_session.py -v`
- **通过标准**: 全部通过，退出码 0
- **失败时严重程度**: Critical

### TC-1-012: 每个文件行数 < 200
- **类型**: 编译检查
- **验证命令**: `cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src && /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/.venv/bin/python3 -c "violations=[(f,sum(1 for _ in open(f))) for f in ['config.py','renderer.py','session.py'] if sum(1 for _ in open(f))>200]; print('OK' if not violations else 'FAIL: '+str(violations))"`
- **通过标准**: 输出 OK
- **失败时严重程度**: Major
