@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置脚本目录和目标文件
set "SCRIPT_DIR=%~dp0"
set "PYTHON_SCRIPT=%SCRIPT_DIR%webhtml\main.py"
set "LOG_FILE=%SCRIPT_DIR%webhtml_run.log"

:: 记录开始时间
echo [%DATE% %TIME%] 开始执行 webhtml/main.py > "%LOG_FILE%"

:: 切换到项目根目录
cd /d "%SCRIPT_DIR%"

:: 检查 Python 环境
set "PYTHON_CMD="
if exist "D:\Programs\python\python.exe" (
    set "PYTHON_CMD=D:\Programs\python\python.exe"
) else if exist "D:\Programs\Python\Python310\python.exe" (
    set "PYTHON_CMD=D:\Programs\Python\Python310\python.exe"
) else (
    for %%i in (python python3 py) do (
        %%i --version >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=%%i"
            goto :found_python
        )
    )
)

:found_python
if "%PYTHON_CMD%"=="" (
    echo [错误] 未找到 Python 环境 >> "%LOG_FILE%"
    echo 请确保 Python 已安装并添加到 PATH 环境变量。
    pause
    exit /b 1
)

echo 使用 Python: %PYTHON_CMD% >> "%LOG_FILE%"

:: 执行脚本
set "PYTHONIOENCODING=utf-8"
echo 正在执行 %PYTHON_SCRIPT% ...
"%PYTHON_CMD%" "%PYTHON_SCRIPT%" >> "%LOG_FILE%" 2>&1

if !errorlevel! equ 0 (
    echo [%DATE% %TIME%] 执行成功 >> "%LOG_FILE%"
    echo 执行成功！详情请查看 %LOG_FILE%
) else (
    echo [%DATE% %TIME%] 执行失败，错误代码: !errorlevel! >> "%LOG_FILE%"
    echo 执行失败，请检查 %LOG_FILE%
    pause
)

endlocal
exit /b 0
