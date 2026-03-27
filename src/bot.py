"""启动入口与应用组装。"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from aiohttp import web
from telegram import BotCommand
from telegram.ext import ApplicationBuilder

from api import create_api_app
from config import Config, load_env, load_state, save_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.environ.get("CLAUDE_PILOT_DIR", os.path.expanduser("~/.claude-pilot"))


async def main() -> None:
    """异步入口函数：构建 TG Application + aiohttp server，启动事件循环。"""
    env = load_env(os.path.join(BASE_DIR, ".env"))
    config = Config(
        bot_token=env.get("BOT_TOKEN", ""),
        allowed_users=[int(u) for u in env.get("ALLOWED_USERS", "").split(",") if u.strip()],
        bot_port=int(env.get("BOT_PORT", "8266")),
        project_dir=env.get("PROJECT_DIR", ""),
    )
    state = load_state(os.path.join(BASE_DIR, ".state.json"))
    app_builder = ApplicationBuilder().token(config.bot_token)
    tg_app = app_builder.build()
    tg_app.bot_data["config"] = config
    tg_app.bot_data["state"] = state
    tg_app.bot_data["base_dir"] = BASE_DIR

    # --- Handler Registration (dev-ext maintains below this line) ---
    from handlers.commands import (
        cmd_setup, cmd_start, cmd_projects, cmd_resume, cmd_rename,
        cmd_interrupt, cmd_quit, cmd_delete, cmd_bypass, cmd_status,
        cmd_info, cmd_retry, cmd_setdir, cmd_help, cmd_unknown,
    )
    from handlers.messages import handle_message
    from handlers.callbacks import handle_button
    from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters

    tg_app.add_handler(CommandHandler("setup", cmd_setup))
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("projects", cmd_projects))
    tg_app.add_handler(CommandHandler("resume", cmd_resume))
    tg_app.add_handler(CommandHandler("rename", cmd_rename))
    tg_app.add_handler(CommandHandler("interrupt", cmd_interrupt))
    tg_app.add_handler(CommandHandler("quit", cmd_quit))
    tg_app.add_handler(CommandHandler("delete", cmd_delete))
    tg_app.add_handler(CommandHandler("bypass", cmd_bypass))
    tg_app.add_handler(CommandHandler("status", cmd_status))
    tg_app.add_handler(CommandHandler("info", cmd_info))
    tg_app.add_handler(CommandHandler("retry", cmd_retry))
    tg_app.add_handler(CommandHandler("setdir", cmd_setdir))
    tg_app.add_handler(CommandHandler("help", cmd_help))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    tg_app.add_handler(CallbackQueryHandler(handle_button))
    tg_app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    api_app = create_api_app(state, tg_app.bot, base_dir=BASE_DIR)
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", config.bot_port)
    await site.start()
    logger.info("API server started on 127.0.0.1:%d", config.bot_port)

    pid_path = os.path.join(BASE_DIR, ".pid")
    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await tg_app.initialize()
    await tg_app.bot.set_my_commands([
        BotCommand("start", "初始引导"),
        BotCommand("help", "查看所有命令"),
        BotCommand("setup", "配置群组"),
        BotCommand("projects", "选择项目启动会话"),
        BotCommand("status", "查看运行状态"),
        BotCommand("resume", "查看历史会话"),
        BotCommand("setdir", "设置项目目录"),
        BotCommand("bypass", "开关权限审批"),
        BotCommand("interrupt", "中断当前生成"),
        BotCommand("quit", "停止监听"),
        BotCommand("info", "查看会话详情"),
        BotCommand("rename", "重命名话题"),
        BotCommand("delete", "删除会话"),
    ])
    await tg_app.start()
    await tg_app.updater.start_polling()
    logger.info("Bot started, polling for updates...")

    # 恢复已有 session 的 watcher
    if state.group_chat_id:
        from watcher import start_watcher
        for sid, info in state.sessions.items():
            tp = info.get("transcript_path", "")
            tid = state.session_topics.get(sid)
            if tp and tid:
                try:
                    await start_watcher(
                        sid, tp, state.group_chat_id, tid,
                        info.get("source", "terminal"),
                        info.get("pane_id"), state, tg_app.bot,
                    )
                    logger.info("Restored watcher for session %s", sid)
                except Exception:
                    logger.warning("Failed to restore watcher for %s", sid, exc_info=True)

    await stop_event.wait()
    logger.info("Shutting down...")
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()
    await runner.cleanup()
    try:
        os.unlink(pid_path)
    except OSError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
