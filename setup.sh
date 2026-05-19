#!/usr/bin/env bash
# setup.sh - 智能教室测控系统环境初始化脚本 (Linux/Raspberry Pi)
# 功能：创建 .venv 虚拟环境、安装依赖、清理旧 venv/ 目录
#
# 用法: bash setup.sh  (不要用 sudo!)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
OLD_VENV_DIR="venv"
REQUIREMENTS="requirements.txt"

echo "=========================================="
echo "  智能教室测控系统 - 环境初始化"
echo "=========================================="
echo ""

# 0. 检查是否以 root 运行（不建议）
if [ "$(id -u)" -eq 0 ]; then
    echo "[警告] 请勿使用 sudo 运行此脚本！"
    echo "       直接运行: bash setup.sh"
    echo ""
    exit 1
fi

# 1. 清理旧的 venv/ 目录
if [ -d "$OLD_VENV_DIR" ]; then
    echo "[清理] 检测到旧的 $OLD_VENV_DIR/ 目录，正在删除..."
    rm -rf "$OLD_VENV_DIR"
    echo "[清理] 旧 $OLD_VENV_DIR/ 目录已删除"
else
    echo "[清理] 未检测到旧的 $OLD_VENV_DIR/ 目录，跳过"
fi

echo ""

# 2. 创建 .venv 虚拟环境
# 如果 .venv 存在但 pip 不可用，则删除重建
if [ -d "$VENV_DIR" ]; then
    if [ ! -x "$VENV_DIR/bin/pip" ]; then
        echo "[环境] $VENV_DIR/ 已损坏（pip 不可执行），正在重建..."
        rm -rf "$VENV_DIR"
    else
        # 检查是否有 --system-site-packages（树莓派需要访问系统 picamera2）
        if ! "$VENV_DIR/bin/python" -c "import sys; exit(0 if any('site-packages' in p and '.venv' not in p for p in sys.path) else 1)" 2>/dev/null; then
            echo "[环境] $VENV_DIR/ 缺少 --system-site-packages，正在重建..."
            rm -rf "$VENV_DIR"
        else
            echo "[环境] $VENV_DIR/ 已存在且正常，跳过创建"
        fi
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[环境] 正在创建 $VENV_DIR/ 虚拟环境..."
    # --system-site-packages 允许访问系统预装的 picamera2、lgpio 等树莓派专用库
    python3 -m venv "$VENV_DIR" --system-site-packages
    echo "[环境] $VENV_DIR/ 创建完成"
fi

echo ""

# 3. 安装依赖
if [ ! -f "$REQUIREMENTS" ]; then
    echo "[错误] 未找到 $REQUIREMENTS 文件"
    exit 1
fi

echo "[依赖] 正在升级 pip..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "[依赖] 正在安装 $REQUIREMENTS 中的依赖包..."
"$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS"

echo ""
echo "=========================================="
echo "  初始化完成！"
echo "=========================================="
echo ""
echo "  虚拟环境路径: $SCRIPT_DIR/$VENV_DIR/"
echo "  Python 路径:  $SCRIPT_DIR/$VENV_DIR/bin/python"
echo ""
echo "  启动方式:"
echo "    ./start.sh"
echo "  或:"
echo "    source .venv/bin/activate"
echo "    python main.py"
echo "=========================================="
