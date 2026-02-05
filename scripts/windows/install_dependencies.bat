@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo Python依赖包自动安装工具
echo ========================================
echo.

:: 设置日志文件路径
set "LOG_FILE=%~dp0auto_run.log"

:: 记录开始时间
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "CURRENT_DATE=%%a %%b %%c"
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "CURRENT_TIME=%%a:%%b"
echo [%CURRENT_DATE% %CURRENT_TIME%] 开始安装Python依赖包 >> "%LOG_FILE%"

:: 检查Python环境
echo 检查Python环境...
set "PYTHON_CMD="

:: 首先尝试特定安装路径
if exist "D:\Programs\Python\Python310\python.exe" (
    set "PYTHON_CMD=D:\Programs\Python\Python310\python.exe"
    echo 找到Python: %PYTHON_CMD%
    echo [%CURRENT_DATE% %CURRENT_TIME%] 找到Python: %PYTHON_CMD% >> "%LOG_FILE%"
    goto :found_python
)

:: 然后尝试标准命令
for %%i in (python python3 py) do (
    %%i --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=%%i"
        echo 找到Python: %%i
        echo [%CURRENT_DATE% %CURRENT_TIME%] 找到Python: %%i >> "%LOG_FILE%"
        goto :found_python
    )
)

if "%PYTHON_CMD%"=="" (
    echo 错误: 未找到Python环境
    echo 请确保Python已安装并添加到PATH环境变量
    echo 或者检查路径: D:\Programs\Python\Python310\python.exe
    echo [%CURRENT_DATE% %CURRENT_TIME%] 错误: 未找到Python环境 >> "%LOG_FILE%"
    pause
    exit /b 1
)

:found_python
:: 显示Python版本
echo.
echo Python版本信息:
%PYTHON_CMD% --version
echo.

:: 检查pip是否可用
echo 检查pip包管理器...
%PYTHON_CMD% -m pip --version >nul 2>&1
if !errorlevel! neq 0 (
    echo 错误: pip不可用，尝试升级pip...
    %PYTHON_CMD% -m ensurepip --upgrade
)

:: 升级pip
echo 升级pip到最新版本...
%PYTHON_CMD% -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1

:: 安装必要的包
echo.
echo 开始安装必要的Python包...
echo [%CURRENT_DATE% %CURRENT_TIME%] 开始安装Python包 >> "%LOG_FILE%"

:: 定义需要安装的包列表
set "PACKAGES=pandas numpy requests beautifulsoup4 lxml openpyxl xlrd"

for %%p in (%PACKAGES%) do (
    echo 正在安装 %%p...
    echo [%CURRENT_DATE% %CURRENT_TIME%] 安装包: %%p >> "%LOG_FILE%"
    %PYTHON_CMD% -m pip install %%p >> "%LOG_FILE%" 2>&1
    if !errorlevel! equ 0 (
        echo ✅ %%p 安装成功
        echo [%CURRENT_DATE% %CURRENT_TIME%] %%p 安装成功 >> "%LOG_FILE%"
    ) else (
        echo ❌ %%p 安装失败
        echo [%CURRENT_DATE% %CURRENT_TIME%] %%p 安装失败 >> "%LOG_FILE%"
    )
)

:: 验证安装
echo.
echo 验证安装结果...
echo [%CURRENT_DATE% %CURRENT_TIME%] 验证安装结果 >> "%LOG_FILE%"

%PYTHON_CMD% -c "import pandas; print('pandas版本:', pandas.__version__)" >> "%LOG_FILE%" 2>&1
if !errorlevel! equ 0 (
    echo ✅ pandas 验证成功
    echo [%CURRENT_DATE% %CURRENT_TIME%] pandas 验证成功 >> "%LOG_FILE%"
) else (
    echo ❌ pandas 验证失败
    echo [%CURRENT_DATE% %CURRENT_TIME%] pandas 验证失败 >> "%LOG_FILE%"
)

%PYTHON_CMD% -c "import numpy; print('numpy版本:', numpy.__version__)" >> "%LOG_FILE%" 2>&1
if !errorlevel! equ 0 (
    echo ✅ numpy 验证成功
    echo [%CURRENT_DATE% %CURRENT_TIME%] numpy 验证成功 >> "%LOG_FILE%"
) else (
    echo ❌ numpy 验证失败
    echo [%CURRENT_DATE% %CURRENT_TIME%] numpy 验证失败 >> "%LOG_FILE%"
)

echo.
echo ========================================
echo 依赖包安装完成！
echo ========================================
echo.
echo 安装日志已保存到: %LOG_FILE%
echo.
echo 现在可以运行 autoPython_bat.bat 了
echo.

echo [%CURRENT_DATE% %CURRENT_TIME%] 依赖包安装完成 >> "%LOG_FILE%"

pause 