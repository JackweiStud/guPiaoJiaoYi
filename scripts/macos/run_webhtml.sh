#!/bin/bash
# run_webhtml.sh - MacOS版本
# 运行 webhtml/main.py

# 设置项目根目录（脚本的上两级目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_SCRIPT="${PROJECT_ROOT}/run.py"
LOG_FILE="${PROJECT_ROOT}/logs/webhtml_run.log"
VENV_DIR="${PROJECT_ROOT}/venv"

# 确保日志目录存在
mkdir -p "${PROJECT_ROOT}/logs"

# 记录开始时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行 webhtml/main.py" > "$LOG_FILE"

# 切换到项目根目录
cd "$PROJECT_ROOT" || exit 1

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[错误] 未找到虚拟环境: $VENV_DIR" >> "$LOG_FILE"
    echo "请先运行: python3 -m venv venv" >> "$LOG_FILE"
    exit 1
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "[错误] 未找到脚本文件: $PYTHON_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 使用虚拟环境Python: $(which python3)" >> "$LOG_FILE"

# 执行脚本
echo "正在执行 $PYTHON_SCRIPT report ..."
if python3 "$PYTHON_SCRIPT" report >> "$LOG_FILE" 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行成功" >> "$LOG_FILE"
    echo "执行成功！详情请查看 $LOG_FILE"
else
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行失败，错误代码: $EXIT_CODE" >> "$LOG_FILE"
    echo "执行失败，请检查 $LOG_FILE"
    exit $EXIT_CODE
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] webhtml任务完成" >> "$LOG_FILE"
exit 0
