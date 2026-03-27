"""崩溃检测与通知（独立守护进程，零外部依赖）。"""
import json
import os
import signal
import sys
import time
import urllib.request
from datetime import date

BASE_DIR = os.environ.get("CLAUDE_PILOT_DIR", os.path.expanduser("~/.claude-pilot"))
MAX_TRACEBACK_LEN = 500
POLL_INTERVAL = 10
MAX_RESTARTS_WARN = 5


def _parse_env(path: str) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                v = v.strip().strip("\"'")
                result[k.strip()] = v
    except FileNotFoundError:
        pass
    return result


def _read_pid(pid_path: str) -> int | None:
    try:
        with open(pid_path) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def _check_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _extract_traceback(log_path: str) -> str:
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return ""
    tail = lines[-50:] if len(lines) > 50 else lines
    tb_start = -1
    for i in range(len(tail) - 1, -1, -1):
        if tail[i].startswith("Traceback"):
            tb_start = i
            break
    if tb_start < 0:
        return ""
    block = "".join(tail[tb_start:])
    return block[:MAX_TRACEBACK_LEN]


def _send_telegram_message(token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _handle_state_change(
    was_alive: bool, alive: bool, restart_count: int,
    token: str, chat_id: int, log_path: str,
) -> int:
    """处理状态变化，返回更新后的 restart_count。"""
    if was_alive and not alive:
        restart_count += 1
        tb = _extract_traceback(log_path)
        msg = "<b>Claude Pilot 崩溃</b>\n"
        if tb:
            msg += f"<pre>{tb}</pre>\n"
        msg += f"今日重启次数: {restart_count}"
        _send_telegram_message(token, chat_id, msg)
        if restart_count >= MAX_RESTARTS_WARN:
            _send_telegram_message(token, chat_id,
                f"<b>警告</b>: 今日重启已达 {restart_count} 次，请检查")
    elif not was_alive and alive:
        _send_telegram_message(token, chat_id, "<b>Claude Pilot 已恢复</b>")
    return restart_count


def _read_state_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main() -> None:
    env = _parse_env(os.path.join(BASE_DIR, ".env"))
    token = env.get("BOT_TOKEN", "")
    chat_id_str = env.get("NOTIFY_CHAT_ID", "")
    if not chat_id_str:
        state_data = _read_state_json(os.path.join(BASE_DIR, ".state.json"))
        chat_id_str = str(state_data.get("notify_chat_id", ""))
    if not token or not chat_id_str:
        print("BOT_TOKEN or NOTIFY_CHAT_ID not configured", file=sys.stderr)
        sys.exit(1)
    try:
        chat_id = int(chat_id_str)
    except (ValueError, TypeError):
        print(f"Invalid chat_id: {chat_id_str!r}", file=sys.stderr)
        sys.exit(1)
    pid_path = os.path.join(BASE_DIR, ".pid")
    log_path = os.path.join(BASE_DIR, "bot.log")
    was_alive = True
    restart_count = 0
    today = date.today()
    while True:
        pid = _read_pid(pid_path)
        alive = _check_pid_alive(pid) if pid else False
        current_date = date.today()
        if current_date != today:
            restart_count = 0
            today = current_date
        restart_count = _handle_state_change(
            was_alive, alive, restart_count, token, chat_id, log_path)
        was_alive = alive
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
