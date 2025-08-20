@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置变量
set "TASK_NAME=AutoProcessDaily"
set "TASK_DESCRIPTION=每天14:30:00自动运行autoProcess.py脚本"
set "BAT_FILE=%~dp0autoPython_bat.bat"
set "LOG_FILE=%~dp0auto_run.log"

echo ========================================
echo 自动任务计划设置工具
echo ========================================
echo.

:: 检查批处理文件是否存在
if not exist "%BAT_FILE%" (
    echo 错误: 未找到批处理文件 %BAT_FILE%
    echo 请确保此脚本与autoPython_bat.bat在同一目录
    pause
    exit /b 1
)

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
echo 任务名称: %TASK_NAME%
echo 任务描述: %TASK_DESCRIPTION%
echo 批处理文件: %BAT_FILE%
echo 日志文件: %LOG_FILE%
echo.

:: 删除已存在的同名任务（如果存在）
echo 检查并删除已存在的同名任务...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: 尝试方法1：使用当前用户创建任务
echo 尝试方法1：使用当前用户创建任务...
schtasks /create /tn "%TASK_NAME%" /tr "%BAT_FILE%" /sc daily /st 14:30:00 /f

:: 检查方法1是否成功
if %errorlevel% equ 0 (
    echo.
    echo ✅ 计划任务创建成功！（使用当前用户权限）
    goto :success
)

:: 如果方法1失败，尝试方法2：使用SYSTEM权限
echo 方法1失败，尝试方法2：使用SYSTEM权限...
schtasks /create /tn "%TASK_NAME%" /tr "%BAT_FILE%" /sc daily /st 14:30:00 /f /rl highest /ru "SYSTEM" /s localhost

:: 检查方法2是否成功
if %errorlevel% equ 0 (
    echo.
    echo ✅ 计划任务创建成功！（使用SYSTEM权限）
    goto :success
)

:: 如果两种方法都失败
echo.
echo ❌ 计划任务创建失败！
echo 错误代码: %errorlevel%
echo.
echo 可能的原因：
echo 1. 系统策略限制计划任务创建
echo 2. 需要更高的系统权限
echo 3. 系统组件损坏
echo.
echo 建议使用GUI方式创建任务：
echo 1. 按Win+R，输入taskschd.msc
echo 2. 手动创建基本任务
echo.
goto :end

:success
echo.
echo 任务详情:
schtasks /query /tn "%TASK_NAME%" /fo list | findstr /i "任务名\|下次运行时间\|状态"
echo.
echo 任务将在每天14:30:00自动运行
echo 日志将保存到: %LOG_FILE%
echo.
echo 提示: 你可以通过以下命令查看任务状态:
echo   schtasks /query /tn "%TASK_NAME%"
echo.

:end
echo 按任意键退出...
pause >nul 