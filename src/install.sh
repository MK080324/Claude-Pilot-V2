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
    local tmp_dir
    tmp_dir="$(mktemp -d)"

    echo "正在克隆项目 ..."
    git clone --depth 1 "${REPO_URL}" "${tmp_dir}/repo"

    echo "正在部署文件到 ${INSTALL_DIR} ..."
    mkdir -p "${INSTALL_DIR}"
    # 将 src/ 内容平铺到安装目录，保持 CLI/hooks 期望的路径结构
    cp -r "${tmp_dir}/repo/src/." "${INSTALL_DIR}/"
    cp "${tmp_dir}/repo/requirements.txt" "${INSTALL_DIR}/"
    rm -rf "${tmp_dir}"

    echo "正在创建 Python 虚拟环境 ..."
    python3 -m venv "${INSTALL_DIR}/.venv"

    echo "正在安装 Python 依赖 ..."
    "${INSTALL_DIR}/.venv/bin/pip" install -q --timeout 60 --upgrade pip 2>/dev/null || echo "提示: pip 升级跳过（不影响安装）"
    "${INSTALL_DIR}/.venv/bin/pip" install -q --timeout 60 -r "${INSTALL_DIR}/requirements.txt"
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

backup_settings() {
    local settings_file="${HOME}/.claude/settings.json"
    local backup_file="${INSTALL_DIR}/settings.json.backup"

    if [[ -f "$settings_file" ]]; then
        cp "$settings_file" "$backup_file"
        echo "已备份原 Claude Code 设置文件到: ${backup_file}"
    else
        echo "未检测到已有 Claude Code 设置文件，跳过备份。"
    fi
}

merge_hooks() {
    local settings_file="${HOME}/.claude/settings.json"
    mkdir -p "${HOME}/.claude"

    echo "正在合并 Claude Code hooks 配置 ..."
    python3 -c "
import json, os, sys

settings_file = os.path.expanduser('~/.claude/settings.json')
install_dir = os.path.expanduser('~/.claude-pilot')

def make_hook(cmd, timeout=10):
    return {'matcher': '', 'hooks': [{'type': 'command', 'command': cmd, 'timeout': timeout}]}

new_hooks = {
    'SessionStart': [make_hook(f'python3 {install_dir}/hooks/session_start.py')],
    'Stop': [make_hook(f'python3 {install_dir}/hooks/stop.py')],
    'Notification': [make_hook(f'python3 {install_dir}/hooks/notification.py')],
    'PreToolUse': [make_hook(f'python3 {install_dir}/hooks/permission.py', 130)],
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

# 合并：检查是否已有同命令的 hook，避免重复
for hook_name, hook_entries in new_hooks.items():
    if hook_name not in existing_hooks:
        existing_hooks[hook_name] = hook_entries
    else:
        existing_cmds = set()
        for rule in existing_hooks[hook_name]:
            for h in rule.get('hooks', []):
                existing_cmds.add(h.get('command', ''))
        for entry in hook_entries:
            cmd = entry['hooks'][0]['command']
            if cmd not in existing_cmds:
                existing_hooks[hook_name].append(entry)

settings['hooks'] = existing_hooks

with open(settings_file, 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

print('hooks 合并完成')
"
}

install_cli() {
    local cli_src="${INSTALL_DIR}/claude-pilot"
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
    backup_settings
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
