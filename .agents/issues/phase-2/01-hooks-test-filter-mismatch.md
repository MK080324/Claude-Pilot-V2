---
status: open
severity: Minor
phase: 2
date: 2026-03-24
---

# Phase 2 Issue #01: test_hooks.py 测试名不匹配 TC 验证命令中的 -k 过滤器

## 问题描述

TC-2-007 和 TC-2-008 使用 `-k "read_port"` 和 `-k "post_to_bot"` 作为过滤条件，但实际测试命名不匹配：
- `read_port` 的测试方法名为 `test_reads_port_from_env`（位于 `TestReadPort` 类中），不包含子串 `read_port`
- `post_to_bot` 的测试方法名为 `test_successful_post` / `test_returns_none_on_error`（位于 `TestPostToBot` 类中），不包含子串 `post_to_bot`

执行这两条验证命令时，pytest 返回退出码 5（0 个测试被选中）。

## 复现步骤

```bash
cd /Users/mserver/workspace/Development-Workflow/projects/Claude-Remote-Control-V2
.venv/bin/python3 -m pytest tests/test_hooks.py -v -k "read_port"
# 退出码 5，0 selected
.venv/bin/python3 -m pytest tests/test_hooks.py -v -k "post_to_bot"
# 退出码 5，0 selected
```

## 预期行为 vs 实际行为

- **预期**：过滤器匹配对应测试，退出码 0
- **实际**：0 tests selected，退出码 5

## 功能影响

功能本身正常，`read_port` 和 `post_to_bot` 的逻辑均有完整测试覆盖（16/16 通过），仅 TC 验证命令中的 -k 过滤器无法选中对应测试。

## 修复建议

将测试方法名调整为包含对应功能关键字，使 -k 过滤器能正确匹配：
- `test_reads_port_from_env` → `test_read_port_from_env`（去掉 's'）
- 或在 TestReadPort 类名中调整，或保持方法名、改用 `-k "reads_port"` 等方式

推荐修改测试方法名（最小改动）：
- `TestReadPort::test_reads_port_from_env` → `test_read_port_from_env`
- `TestPostToBot` 中增加包含 `post_to_bot` 的测试名，或重命名 `test_successful_post` 为含 `post_to_bot` 的名字
