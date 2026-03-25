#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HOME}/.claude-pilot"
REPO_URL="https://github.com/MK080324/Claude-Pilot-V2.git"

check_deps() {
    local missing=()
    for cmd in git claude tmux python3; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "错误: 缺少以下依赖: ${missing[*]}" >&2
        echo "请先安装后再运行安装脚本。" >&2
        return 1
    fi
    echo "依赖检测通过: git, claude, tmux, python3"
}

setup_venv() {
    if [[ -d "${INSTALL_DIR}/.git" ]]; then
        echo "正在更新 ${INSTALL_DIR} ..."
        git -C "${INSTALL_DIR}" pull --ff-only
    else
        echo "正在克隆项目到 ${INSTALL_DIR} ..."
        git clone --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
    fi

    echo "正在创建 Python 虚拟环境 ..."
    python3 -m venv "${INSTALL_DIR}/.venv"

    echo "正在安装 Python 依赖 ..."
    "${INSTALL_DIR}/.venv/bin/pip" install -q --upgrade pip
    "${INSTALL_DIR}/.venv/bin/pip" install -q -r "${INSTALL_DIR}/requirements.txt"
    echo "Python 依赖安装完成"
}

collect_config() {
    echo ""
    echo "=== 配置 Claude Pilot ==="

    while [[ -z "${BOT_TOKEN:-}" ]]; do
        read -r -p "请输入 Telegram Bot Token: " BOT_TOKEN </dev/tty
        if [[ -z "$BOT_TOKEN" ]]; then
            echo "Bot Token 不能为空，请重新输入。"
        fi
    done

    while [[ -z "${ALLOWED_USERS:-}" ]]; do
        read -r -p "请输入允许的 Telegram User ID（多个用逗号分隔）: " ALLOWED_USERS </dev/tty
        if [[ -z "$ALLOWED_USERS" ]]; then
            echo "User ID 不能为空，请重新输入。"
        fi
    done

    export BOT_TOKEN ALLOWED_USERS
}

write_env() {
    local token="$1"
    local users="$2"
    local env_file="${INSTALL_DIR}/.env"

    cat > "$env_file" <<EOF
BOT_TOKEN=${token}
ALLOWED_USERS=${users}
BOT_PORT=8266
NOTIFY_CHAT_ID=
EOF
    chmod 600 "$env_file"
    echo ".env 已写入: ${env_file}"
}

merge_hooks() {
    local settings_file="${HOME}/.claude/settings.json"
    mkdir -p "${HOME}/.claude"

    echo "正在合并 Claude Code hooks 配置 ..."
    python3 -c "
import json, os, sys

settings_file = os.path.expanduser('~/.claude/settings.json')
install_dir = os.path.expanduser('~/.claude-pilot')
src_dir = os.path.join(install_dir, 'src')

new_hooks = {
    'session_start': [{'command': f'python3 {src_dir}/hooks/session_start.py'}],
    'stop': [{'command': f'python3 {src_dir}/hooks/stop.py'}],
    'notification': [{'command': f'python3 {src_dir}/hooks/notification.py'}],
    'permission': [{'command': f'python3 {src_dir}/hooks/permission.py', 'timeout': 120}],
}

if os.path.exists(settings_file):
    with open(settings_file, 'r', encoding='utf-8') as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}
else:
    settings = {}

existing_hooks = settings.get('hooks', {})

# 合并：仅添加不存在的 hook 条目，不覆盖已有
for hook_name, hook_entries in new_hooks.items():
    if hook_name not in existing_hooks:
        existing_hooks[hook_name] = hook_entries
    else:
        existing_cmds = {
            (e.get('command', '') if isinstance(e, dict) else e)
            for e in existing_hooks[hook_name]
        }
        for entry in hook_entries:
            cmd = entry.get('command', '') if isinstance(entry, dict) else entry
            if cmd not in existing_cmds:
                existing_hooks[hook_name].append(entry)

settings['hooks'] = existing_hooks

with open(settings_file, 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

print('hooks 合并完成')
"
}

install_cli() {
    local cli_src="${INSTALL_DIR}/src/claude-pilot"
    chmod +x "$cli_src"

    # 优先安装到 /usr/local/bin，否则安装到 ~/.local/bin
    if [[ -w "/usr/local/bin" ]]; then
        cp "$cli_src" "/usr/local/bin/claude-pilot"
        echo "CLI 已安装到 /usr/local/bin/claude-pilot"
    else
        mkdir -p "${HOME}/.local/bin"
        cp "$cli_src" "${HOME}/.local/bin/claude-pilot"
        echo "CLI 已安装到 ${HOME}/.local/bin/claude-pilot"
        echo "提示: 请确保 ~/.local/bin 在您的 PATH 中"
    fi
}

main() {
    echo "=== Claude Pilot v2 安装程序 ==="
    echo ""

    check_deps
    setup_venv
    collect_config
    write_env "$BOT_TOKEN" "$ALLOWED_USERS"
    merge_hooks
    install_cli

    echo ""
    echo "=== 安装完成 ==="
    echo "正在启动 Claude Pilot ..."
    claude-pilot start || true
    echo ""
    echo "使用 'claude-pilot status' 查看运行状态"
    echo "使用 'claude-pilot logs' 查看日志"
}

main "$@"
