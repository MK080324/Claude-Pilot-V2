---
status: resolved
severity: Major
phase: 5
date: 2026-03-24
---

# Phase 5 Issue #01: crash_reporter.py 零外部依赖检测因 `__future__` 失败

## 问题描述

TC-5-006 零外部依赖检测命令输出 `FAIL: ['__future__']`，因为检测白名单不包含 `__future__`，而 `crash_reporter.py` 第 2 行使用了 `from __future__ import annotations`。

`__future__` 是 Python 内置模块，非第三方依赖，但测试用例的验证命令按字面执行结果为 FAIL（Critical 降级为 Major 因为是误报，但仍需修复以通过 TC-5-006）。

## 复现步骤

```bash
cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2/src
.venv/bin/python3 -c "import ast; tree=ast.parse(open('crash_reporter.py').read()); imports=[n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]+[n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]; third_party=[m for m in imports if m and m.split('.')[0] not in ('os','sys','json','time','urllib','signal','datetime','pathlib','re','traceback','tempfile','socket')]; print('OK' if not third_party else 'FAIL: '+str(third_party))"
# 输出: FAIL: ['__future__']
```

## 预期行为 vs 实际行为

- **预期**: 输出 `OK`（crash_reporter.py 只使用标准库）
- **实际**: 输出 `FAIL: ['__future__']`

## 修复建议

在 `crash_reporter.py` 中移除 `from __future__ import annotations` 行（Python 3.10+ 默认已支持 PEP 604 类型语法，不需要此导入），或将代码改为不依赖 `from __future__ import annotations`。

移除第 2 行 `from __future__ import annotations` 后，需同时确认类型注解语法仍然正确（如 `int | None` 在 Python 3.10+ 原生支持）。
