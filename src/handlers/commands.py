"""Telegram 命令处理。"""
from __future__ import annotations
import json, os, time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config import Config, State, save_state

_start_time = time.time()
_CTX = ContextTypes.DEFAULT_TYPE

def _ctx(context: _CTX) -> tuple[Config, State, str]:
    cfg, st = context.bot_data["config"], context.bot_data["state"]
    return cfg, st, os.path.join(context.bot_data.get("base_dir", ""), ".state.json")

def _auth(update: Update, config: Config) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    return uid in config.allowed_users

def _topic_session(state: State, update: Update) -> tuple[int | None, dict | None]:
    tid = update.message.message_thread_id
    if not tid:
        return None, None
    for sid, t in state.session_topics.items():
        if t == tid:
            return tid, state.sessions.get(sid)
    return tid, None

def _read_jsonl_summary(path: str, n: int = 5) -> str:
    if not path or not os.path.exists(path): return "(无对话记录)"
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.readlines()
    except Exception: return "(读取失败)"
    out: list[str] = []
    for line in reversed(raw):
        if not (line := line.strip()): continue
        try: ev = json.loads(line)
        except json.JSONDecodeError: continue
        role = ev.get("role", "")
        if role == "assistant":
            for b in (ev.get("message", {}).get("content", []) or []):
                if isinstance(b, dict) and b.get("type") == "text":
                    out.append(f"A: {b['text'][:80]}"); break
        elif role == "user":
            msg = ev.get("message", "")
            txt = msg if isinstance(msg, str) else (msg.get("content", "") if isinstance(msg, dict) else "")
            if txt: out.append(f"U: {txt[:80]}")
        if len(out) >= n: break
    out.reverse()
    return "\n".join(out) or "(无对话记录)"

async def cmd_setup(update: Update, context: _CTX) -> None:
    config, state, sp = _ctx(context)
    if not _auth(update, config): return
    ct = update.effective_chat.type if update.effective_chat else ""
    if "group" not in ct and "supergroup" not in ct:
        await update.message.reply_text("请在超级群组中使用此命令"); return
    state.group_chat_id = update.effective_chat.id
    save_state(state, sp)
    await update.message.reply_text(
        "✅ <b>群组已配置</b>\n确认: Bot 为管理员 + 已开启话题\n"
        "/projects 启动会话 | /status 状态 | /bypass 审批", parse_mode="HTML")

async def cmd_start(update: Update, context: _CTX) -> None:
    config, state, sp = _ctx(context)
    if not _auth(update, config): return
    state.notify_chat_id = update.effective_chat.id
    save_state(state, sp)
    await update.message.reply_text(
        "👋 <b>Claude Pilot</b>\n1. @BotFather: Group Privacy → Off\n"
        "2. 建群 → 开话题 → Bot 管理员\n3. 群内 /setup\n/help 查看命令", parse_mode="HTML")

async def cmd_projects(update: Update, context: _CTX) -> None:
    config, state, _ = _ctx(context)
    if not _auth(update, config): return
    proj_dir = state.project_dir or config.project_dir
    if not proj_dir or not os.path.isdir(proj_dir):
        await update.message.reply_text("项目目录未配置，用 /setdir 设置"); return
    try:
        entries = sorted(e for e in os.listdir(proj_dir)
                         if os.path.isdir(os.path.join(proj_dir, e)) and not e.startswith("."))
    except OSError:
        await update.message.reply_text("无法读取项目目录"); return
    if not entries:
        await update.message.reply_text("项目目录为空"); return
    buttons = [[InlineKeyboardButton(e, callback_data=f"project:{e}")] for e in entries]
    await update.message.reply_text("选择项目：", reply_markup=InlineKeyboardMarkup(buttons))

async def cmd_resume(update: Update, context: _CTX) -> None:
    config, state, _ = _ctx(context)
    if not _auth(update, config): return
    if not state.sessions:
        await update.message.reply_text("无历史会话"); return
    parts = [f"<b>{sid}</b> ({info.get('cwd', '?')})\n"
             f"{_read_jsonl_summary(info.get('transcript_path', ''))}"
             for sid, info in state.sessions.items()]
    await update.message.reply_text("\n\n".join(parts), parse_mode="HTML")

async def cmd_rename(update: Update, context: _CTX) -> None:
    config, _, _ = _ctx(context)
    if not _auth(update, config): return
    parts = (update.message.text or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("用法: /rename <新名称>"); return
    tid = update.message.message_thread_id
    if not tid:
        await update.message.reply_text("请在话题中使用"); return
    try:
        await context.bot.edit_forum_topic(update.effective_chat.id, tid, name=parts[1].strip())
        await update.message.reply_text(f"已重命名为: {parts[1].strip()}")
    except Exception:
        await update.message.reply_text("重命名失败")

async def cmd_interrupt(update: Update, context: _CTX) -> None:
    config, state, _ = _ctx(context)
    if not _auth(update, config): return
    tid, sess = _topic_session(state, update)
    if not tid:
        await update.message.reply_text("请在话题中使用"); return
    if not sess or not sess.get("pane_id"):
        await update.message.reply_text("未找到关联会话"); return
    from session import interrupt_session
    await interrupt_session(sess["pane_id"])
    await update.message.reply_text("已发送中断信号")

async def cmd_quit(update: Update, context: _CTX) -> None:
    config, _, _ = _ctx(context)
    if not _auth(update, config): return
    tid = update.message.message_thread_id
    if not tid:
        await update.message.reply_text("请在话题中使用"); return
    from watcher import stop_watcher
    stop_watcher(tid)
    await update.message.reply_text("已暂停监听")

async def cmd_delete(update: Update, context: _CTX) -> None:
    config, _, _ = _ctx(context)
    if not _auth(update, config): return
    tid = update.message.message_thread_id
    if not tid:
        await update.message.reply_text("请在话题中使用"); return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("确认删除", callback_data=f"delete_confirm:{tid}"),
        InlineKeyboardButton("取消", callback_data=f"delete_cancel:{tid}"),
    ]])
    await update.message.reply_text("确认删除此会话？", reply_markup=kb)

async def cmd_bypass(update: Update, context: _CTX) -> None:
    config, state, sp = _ctx(context)
    if not _auth(update, config): return
    state.bypass_enabled = not state.bypass_enabled
    save_state(state, sp)
    await update.message.reply_text(f"审批绕过已{'开启' if state.bypass_enabled else '关闭'}")

async def cmd_status(update: Update, context: _CTX) -> None:
    config, state, _ = _ctx(context)
    if not _auth(update, config): return
    up = int(time.time() - _start_time)
    lines = [f"运行: {up}s | 会话: {len(state.sessions)}"]
    lines += [f"  {sid}: {i.get('cwd', '?')}" for sid, i in state.sessions.items()]
    await update.message.reply_text("\n".join(lines))

async def cmd_info(update: Update, context: _CTX) -> None:
    config, state, _ = _ctx(context)
    if not _auth(update, config): return
    tid, sess = _topic_session(state, update)
    if not tid:
        await update.message.reply_text("请在话题中使用"); return
    if not sess:
        await update.message.reply_text("未找到关联会话"); return
    await update.message.reply_text("\n".join(f"{k}: {v}" for k, v in sess.items()))

async def cmd_retry(update: Update, context: _CTX) -> None:
    config, _, _ = _ctx(context)
    if not _auth(update, config): return
    await update.message.reply_text("retry 功能暂未实现")

async def cmd_setdir(update: Update, context: _CTX) -> None:
    config, state, sp = _ctx(context)
    if not _auth(update, config): return
    parts = (update.message.text or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("用法: /setdir <目录路径>"); return
    state.project_dir = parts[1].strip()
    save_state(state, sp)
    warn = "" if os.path.isdir(state.project_dir) else "\n⚠️ 该目录当前不存在"
    await update.message.reply_text(f"目录: {state.project_dir}{warn}")

async def cmd_help(update: Update, context: _CTX) -> None:
    config, _, _ = _ctx(context)
    if not _auth(update, config): return
    await update.message.reply_text(
        "<b>命令</b>\n/start 引导 | /setup 配群 | /setdir 目录\n"
        "/projects 启动 | /resume 历史 | /status 状态\n"
        "/interrupt 中断 | /rename 改名 | /info 详情\n"
        "/quit 停监听 | /delete 删除 | /bypass 审批", parse_mode="HTML")

async def cmd_unknown(update: Update, context: _CTX) -> None:
    await update.message.reply_text("未知命令，/help 查看可用命令")
