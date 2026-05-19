#!/usr/bin/env bash
# start.sh - 智能教室测控系统启动脚本 (Linux/Raspberry Pi)
# 功能：使用 .venv/bin/python 直接启动 main.py

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON=".venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[错误] 未找到虚拟环境: $VENV_PYTHON"
    echo "       请先运行 ./setup.sh 初始化环境"
    exit 1
fi

echo "[启动] 使用 $VENV_PYTHON 启动 main.py ..."
exec "$VENV_PYTHON" main.py "$@"
