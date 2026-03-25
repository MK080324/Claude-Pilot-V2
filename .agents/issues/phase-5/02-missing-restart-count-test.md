---
status: resolved
severity: Major
phase: 5
date: 2026-03-24
---

# Phase 5 Issue #02: TC-5-005 重启计数警告缺少测试用例

## 问题描述

TC-5-005 要求验证"连续 5 次 PID 消失 -> 触发警告"，但 `tests/test_crash_reporter.py` 中没有对应的测试用例覆盖 `main()` 中的 `restart_count >= MAX_RESTARTS_WARN` 分支。

虽然 `crash_reporter.py` 中已正确实现该逻辑（第 106-108 行），但缺乏测试覆盖。

## 复现步骤

检查 `tests/test_crash_reporter.py`：仅有 8 个测试用例（`test_check_pid_alive_*`、`test_extract_traceback_*`、`test_send_telegram_message_*`），无任何测试 `restart_count` 警告逻辑。

## 预期行为 vs 实际行为

- **预期**: 测试套件中有覆盖重启计数警告的测试（如 mock `_check_pid_alive` 连续返回 False 5 次，验证 `_send_telegram_message` 被额外调用一次发警告）
- **实际**: 无此类测试

## 修复建议

在 `tests/test_crash_reporter.py` 中添加针对 `main()` 函数中重启计数逻辑的测试，或将警告逻辑提取为独立函数（如 `_maybe_warn_restarts(restart_count, token, chat_id)`）并对其单独测试。

示例测试：mock `_check_pid_alive` 以模拟 PID 消失场景，验证第 5 次及以上崩溃时 `_send_telegram_message` 额外触发警告消息。
