"""Notification hook 处理。"""
from __future__ import annotations

import json
import sys

from hooks._common import post_to_bot


def main() -> None:
    """从 stdin 读取 JSON，转发给 Bot。"""
    raise NotImplementedError


if __name__ == "__main__":
    main()
