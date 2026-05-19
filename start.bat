@echo off
REM start.bat - 智能教室测控系统启动脚本 (Windows)
REM 功能：使用 .venv\Scripts\python.exe 直接启动 main.py

cd /d "%~dp0"

set VENV_PYTHON=.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到虚拟环境: %VENV_PYTHON%
    echo        请先运行 setup.bat 初始化环境
    exit /b 1
)

echo [启动] 使用 %VENV_PYTHON% 启动 main.py ...
"%VENV_PYTHON%" main.py %*
