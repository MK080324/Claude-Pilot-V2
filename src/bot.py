"""启动入口与应用组装。"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from aiohttp import web
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

    api_app = create_api_app(state, tg_app.bot)
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
    await tg_app.start()
    await tg_app.updater.start_polling()
    logger.info("Bot started, polling for updates...")

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
