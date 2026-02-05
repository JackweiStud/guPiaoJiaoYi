#!/bin/bash
# autoPython_bat.sh - MacOS版本
# 运行 autoProcess.py

# 设置项目根目录（脚本的上两级目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_SCRIPT="${PROJECT_ROOT}/autoProcess.py"
LOG_FILE="${PROJECT_ROOT}/logs/auto_run.log"
VENV_DIR="${PROJECT_ROOT}/venv"

# 确保日志目录存在
mkdir -p "${PROJECT_ROOT}/logs"

# 记录开始时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行自动任务" > "$LOG_FILE"

# 切换到项目根目录
cd "$PROJECT_ROOT" || exit 1

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 未找到虚拟环境: $VENV_DIR" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 请先运行: python3 -m venv venv" >> "$LOG_FILE"
    exit 1
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 找到Python: $(which python3)" >> "$LOG_FILE"

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 未找到脚本文件 $PYTHON_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

# 检查Python脚本是否可读
if [ ! -r "$PYTHON_SCRIPT" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 无法读取脚本文件 $PYTHON_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

# 记录开始执行Python脚本
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行Python脚本: $PYTHON_SCRIPT" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行命令: python3 $PYTHON_SCRIPT" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Python脚本输出开始 ==========================================" >> "$LOG_FILE"

# 执行Python脚本
if python3 "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1; then
    EXIT_CODE=0
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Python脚本执行成功" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 任务完成" >> "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: Python脚本执行失败，错误代码: $EXIT_CODE" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 请检查脚本内容和Python环境" >> "$LOG_FILE"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Python脚本输出结束 ==========================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 自动任务结束 ==========================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

exit $EXIT_CODE
