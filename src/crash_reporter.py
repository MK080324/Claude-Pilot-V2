"""崩溃检测与通知（独立守护进程）。"""
from __future__ import annotations


def _check_pid_alive(pid: int) -> bool:
    """检查进程是否存活。"""
    raise NotImplementedError


def _extract_traceback(log_path: str) -> str:
    """从日志提取最近的 Traceback。"""
    raise NotImplementedError


def _send_telegram_message(token: str, chat_id: int, text: str) -> None:
    """urllib 直接调用 TG API。"""
    raise NotImplementedError


def main() -> None:
    """主循环：每 10 秒检查 PID 存活。"""
    raise NotImplementedError


if __name__ == "__main__":
    main()
