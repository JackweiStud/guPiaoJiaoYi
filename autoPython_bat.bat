@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置日志文件路径
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%auto_run.log"
set "PYTHON_SCRIPT=%SCRIPT_DIR%autoProcess.py"

:: 创建日志目录（如果不存在）
if not exist "%SCRIPT_DIR%" mkdir "%SCRIPT_DIR%" 2>nul

:: 获取当前时间并记录开始时间
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "CURRENT_DATE=%%a %%b %%c"
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "CURRENT_TIME=%%a:%%b"
echo [%CURRENT_DATE% %CURRENT_TIME%] 开始执行自动任务 > "%LOG_FILE%"

:: 检查Python环境
echo [%CURRENT_DATE% %CURRENT_TIME%] 检查Python环境... >> "%LOG_FILE%"

:: 尝试多种Python命令，包括特定路径
set "PYTHON_CMD="

:: 首先尝试特定安装路径
if exist "D:\Programs\python\python.exe" (
    set "PYTHON_CMD=D:\Programs\python\python.exe"
    echo [%CURRENT_DATE% %CURRENT_TIME%] 找到Python: %PYTHON_CMD% >> "%LOG_FILE%"
    goto :found_python
)

if exist "D:\Programs\Python\Python310\python.exe" (
    set "PYTHON_CMD=D:\Programs\Python\Python310\python.exe"
    echo [%CURRENT_DATE% %CURRENT_TIME%] 找到Python: %PYTHON_CMD% >> "%LOG_FILE%"
    goto :found_python
)

:: 然后尝试标准命令
for %%i in (python python3 py) do (
    %%i --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=%%i"
        echo [%CURRENT_DATE% %CURRENT_TIME%] 找到Python: %%i >> "%LOG_FILE%"
        goto :found_python
    )
)

:: 如果没找到Python，记录错误并退出
echo [%CURRENT_DATE% %CURRENT_TIME%] 错误: 未找到Python环境 >> "%LOG_FILE%"
echo [%CURRENT_DATE% %CURRENT_TIME%] 请确保Python已安装并添加到PATH环境变量 >> "%LOG_FILE%"
echo [%CURRENT_DATE% %CURRENT_TIME%] 或者检查路径: D:\Programs\Python\Python310\python.exe >> "%LOG_FILE%"
exit /b 1

:found_python
:: 检查Python脚本是否存在
if not exist "%PYTHON_SCRIPT%" (
    echo [%CURRENT_DATE% %CURRENT_TIME%] 错误: 未找到脚本文件 %PYTHON_SCRIPT% >> "%LOG_FILE%"
    exit /b 1
)

:: 检查Python脚本是否可读
type "%PYTHON_SCRIPT%" >nul 2>&1
if !errorlevel! neq 0 (
    echo [%CURRENT_DATE% %CURRENT_TIME%] 错误: 无法读取脚本文件 %PYTHON_SCRIPT% >> "%LOG_FILE%"
    exit /b 1
)

:: 记录开始执行Python脚本
echo [%CURRENT_DATE% %CURRENT_TIME%] 开始执行Python脚本: %PYTHON_SCRIPT% >> "%LOG_FILE%"

:: 切换到脚本目录
cd /d "%SCRIPT_DIR%"

:: 执行Python脚本并捕获输出，设置编码
echo [%CURRENT_DATE% %CURRENT_TIME%] 执行命令: %PYTHON_CMD% "%PYTHON_SCRIPT%" >> "%LOG_FILE%"
echo [%CURRENT_DATE% %CURRENT_TIME%] Python脚本输出开始 ========================================== >> "%LOG_FILE%"

:: 设置Python环境变量并执行
set "PYTHONIOENCODING=utf-8"
set "PYTHONLEGACYWINDOWSSTDIO=utf-8"

:: 使用PowerShell来执行Python脚本，避免编码问题
powershell -Command "& '%PYTHON_CMD%' '%PYTHON_SCRIPT%' 2>&1 | Out-File -FilePath '%LOG_FILE%' -Append -Encoding UTF8"

echo [%CURRENT_DATE% %CURRENT_TIME%] Python脚本输出结束 ========================================== >> "%LOG_FILE%"

:: 检查执行结果
if !errorlevel! equ 0 (
    echo [%CURRENT_DATE% %CURRENT_TIME%] Python脚本执行成功 >> "%LOG_FILE%"
    echo [%CURRENT_DATE% %CURRENT_TIME%] 任务完成 >> "%LOG_FILE%"
) else (
    echo [%CURRENT_DATE% %CURRENT_TIME%] 错误: Python脚本执行失败，错误代码: !errorlevel! >> "%LOG_FILE%"
    echo [%CURRENT_DATE% %CURRENT_TIME%] 请检查脚本内容和Python环境 >> "%LOG_FILE%"
)

:: 记录结束时间
echo [%CURRENT_DATE% %CURRENT_TIME%] 自动任务结束 ========================================== >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

endlocal
exit /b 0
