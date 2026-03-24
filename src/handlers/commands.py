"""Telegram 命令处理。"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """引导配置群组。"""
    raise NotImplementedError


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """初始化。"""
    raise NotImplementedError


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """选择项目目录。"""
    raise NotImplementedError


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """恢复历史会话（含历史回显）。"""
    raise NotImplementedError


async def cmd_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """重命名会话。"""
    raise NotImplementedError


async def cmd_interrupt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """中断 Claude 生成。"""
    raise NotImplementedError


async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """暂停会话。"""
    raise NotImplementedError


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """删除会话。"""
    raise NotImplementedError


async def cmd_bypass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """开关 Hook 层权限审批。"""
    raise NotImplementedError


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看运行状态。"""
    raise NotImplementedError


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看当前会话信息。"""
    raise NotImplementedError


async def cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """重发最后一条回复。"""
    raise NotImplementedError


async def cmd_setdir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """手动设置项目目录。"""
    raise NotImplementedError
