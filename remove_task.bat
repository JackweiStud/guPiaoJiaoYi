@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置变量
set "TASK_NAME=AutoProcessDaily"

echo ========================================
echo 自动任务删除工具
echo ========================================
echo.

:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: 此脚本需要管理员权限才能删除计划任务
    echo 请右键点击此脚本，选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

:: 检查任务是否存在
echo 检查计划任务是否存在...
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo 任务 "%TASK_NAME%" 不存在，无需删除
    echo.
    pause
    exit /b 0
)

:: 显示任务信息
echo 找到计划任务: %TASK_NAME%
echo.
echo 当前任务状态:
schtasks /query /tn "%TASK_NAME%" /fo list | findstr /i "任务名\|下次运行时间\|状态"
echo.

:: 确认删除
set /p "CONFIRM=确定要删除此计划任务吗？(y/N): "
if /i not "%CONFIRM%"=="y" (
    echo 操作已取消
    pause
    exit /b 0
)

:: 删除任务
echo 正在删除计划任务...
schtasks /delete /tn "%TASK_NAME%" /f

:: 检查删除结果
if %errorlevel% equ 0 (
    echo.
    echo ✅ 计划任务删除成功！
    echo 任务 "%TASK_NAME%" 已被完全移除
    echo.
) else (
    echo.
    echo ❌ 计划任务删除失败！
    echo 错误代码: %errorlevel%
    echo 请检查是否有足够的权限
    echo.
)

echo 按任意键退出...
pause >nul 