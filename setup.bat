@echo off
REM setup.bat - 智能教室测控系统环境初始化脚本 (Windows)
REM 功能：创建 .venv 虚拟环境、安装依赖、清理旧 venv/ 目录

setlocal enabledelayedexpansion

cd /d "%~dp0"

set VENV_DIR=.venv
set OLD_VENV_DIR=venv
set REQUIREMENTS=requirements.txt

echo ==========================================
echo   智能教室测控系统 - 环境初始化
echo ==========================================
echo.

REM 1. 清理旧的 venv/ 目录
if exist "%OLD_VENV_DIR%\" (
    echo [清理] 检测到旧的 %OLD_VENV_DIR%\ 目录，正在删除...
    rmdir /s /q "%OLD_VENV_DIR%"
    echo [清理] 旧 %OLD_VENV_DIR%\ 目录已删除
) else (
    echo [清理] 未检测到旧的 %OLD_VENV_DIR%\ 目录，跳过
)

echo.

REM 2. 创建 .venv 虚拟环境
if exist "%VENV_DIR%\" (
    echo [环境] %VENV_DIR%\ 已存在，跳过创建
) else (
    echo [环境] 正在创建 %VENV_DIR%\ 虚拟环境...
    python -m venv "%VENV_DIR%"
    echo [环境] %VENV_DIR%\ 创建完成
)

echo.

REM 3. 安装依赖
if not exist "%REQUIREMENTS%" (
    echo [错误] 未找到 %REQUIREMENTS% 文件
    exit /b 1
)

echo [依赖] 正在安装 %REQUIREMENTS% 中的依赖包...
"%VENV_DIR%\Scripts\pip.exe" install --upgrade pip
"%VENV_DIR%\Scripts\pip.exe" install -r "%REQUIREMENTS%"

echo.
echo ==========================================
echo   初始化完成！
echo ==========================================
echo.
echo   虚拟环境路径: %cd%\%VENV_DIR%\
echo   Python 路径:  %cd%\%VENV_DIR%\Scripts\python.exe
echo.
echo   使用 start.bat 启动系统
echo ==========================================

endlocal
