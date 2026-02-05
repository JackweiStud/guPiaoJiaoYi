@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置变量  手动触发 schtasks /run /tn "AutoProcessDaily_1430"
:: PC 已设置为北京时间，无需时区转换
set "TASK_NAME_1=AutoProcessDaily_1430"
set "TASK_NAME_2=AutoProcessDaily_1510"
set "LOCAL_TIME_1=14:30:00"
set "LOCAL_TIME_2=15:10:00"
set "TASK_DESCRIPTION=每天北京时间 14:30 和 15:10 自动运行行情报告和交易脚本"
set "BAT_FILE=%~dp0run_all_tasks.bat"
set "WEBHTML_BAT=%~dp0run_webhtml.bat"
set "AUTOPYTHON_BAT=%~dp0autoPython_bat.bat"
set "LOG_FILE=%~dp0auto_run.log"

echo ========================================
echo 自动任务计划设置工具
echo ========================================
echo 将创建两个定时任务:
echo   - %TASK_NAME_1% (北京时间 %LOCAL_TIME_1%)
echo   - %TASK_NAME_2% (北京时间 %LOCAL_TIME_2%)
echo.

:: 检查批处理文件是否存在
if not exist "%WEBHTML_BAT%" (
    echo 错误: 未找到批处理文件 %WEBHTML_BAT%
    pause
    exit /b 1
)
if not exist "%AUTOPYTHON_BAT%" (
    echo 错误: 未找到批处理文件 %AUTOPYTHON_BAT%
    pause
    exit /b 1
)

:: 创建一个汇总运行的批处理文件
set "SCRIPT_DIR=%~dp0"
echo @echo off > "%BAT_FILE%"
echo chcp 65001 ^>nul >> "%BAT_FILE%"
echo cd /d "%SCRIPT_DIR:~0,-1%" >> "%BAT_FILE%"
echo echo [%%DATE%% %%TIME%%] 开始执行汇总任务 ^>^> "%LOG_FILE%" >> "%BAT_FILE%"
echo call "%WEBHTML_BAT%" >> "%BAT_FILE%"
echo echo [%%DATE%% %%TIME%%] webhtml任务执行完毕 ^>^> "%LOG_FILE%" >> "%BAT_FILE%"
echo call "%AUTOPYTHON_BAT%" >> "%BAT_FILE%"
echo echo [%%DATE%% %%TIME%%] 所有任务执行完毕 ^>^> "%LOG_FILE%" >> "%BAT_FILE%"


:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: 此脚本需要管理员权限才能设置计划任务
    echo 请右键点击此脚本，选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

echo 正在设置计划任务...
echo 批处理文件: %BAT_FILE%
echo 日志文件: %LOG_FILE%
echo.

:: 删除已存在的同名任务（如果存在）
echo 检查并删除已存在的同名任务...
schtasks /delete /tn "%TASK_NAME_1%" /f >nul 2>&1
schtasks /delete /tn "%TASK_NAME_2%" /f >nul 2>&1
:: 同时删除旧的单任务（如果存在）
schtasks /delete /tn "AutoProcessDaily" /f >nul 2>&1

:: ===== 创建第一个任务 (14:30) =====
echo.
echo 创建任务 1: %TASK_NAME_1% (%LOCAL_TIME_1%)...
schtasks /create /tn "%TASK_NAME_1%" /tr "%BAT_FILE%" /sc daily /st %LOCAL_TIME_1% /f

if %errorlevel% equ 0 (
    echo ✅ 任务 %TASK_NAME_1% 创建成功！
) else (
    echo ❌ 任务 %TASK_NAME_1% 创建失败！
)

:: ===== 创建第二个任务 (15:10) =====
echo.
echo 创建任务 2: %TASK_NAME_2% (%LOCAL_TIME_2%)...
schtasks /create /tn "%TASK_NAME_2%" /tr "%BAT_FILE%" /sc daily /st %LOCAL_TIME_2% /f

if %errorlevel% equ 0 (
    echo ✅ 任务 %TASK_NAME_2% 创建成功！
) else (
    echo ❌ 任务 %TASK_NAME_2% 创建失败！
)

:: 显示任务详情
echo.
echo ========================================
echo 任务创建完成！
echo ========================================
echo.
echo 任务 1 详情:
schtasks /query /tn "%TASK_NAME_1%" /fo list 2>nul | findstr /i "TaskName Next"
echo.
echo 任务 2 详情:
schtasks /query /tn "%TASK_NAME_2%" /fo list 2>nul | findstr /i "TaskName Next"
echo.
echo 日志将保存到: %LOG_FILE%
echo.
echo 提示: 你可以通过以下命令查看任务状态:
echo   schtasks /query /tn "%TASK_NAME_1%"
echo   schtasks /query /tn "%TASK_NAME_2%"
echo.
echo 手动触发任务:
echo   schtasks /run /tn "%TASK_NAME_1%"
echo   schtasks /run /tn "%TASK_NAME_2%"
echo.

echo 按任意键退出...
pause >nul
