#!/bin/bash
# run_all_tasks.sh - MacOS版本
# 汇总运行所有任务

# 设置脚本目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/auto_run.log"

cd "$SCRIPT_DIR" || exit 1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行汇总任务" >> "$LOG_FILE"

# 运行 webhtml
if [ -f "${SCRIPT_DIR}/run_webhtml.sh" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行 webhtml任务..." >> "$LOG_FILE"
    bash "${SCRIPT_DIR}/run_webhtml.sh"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] webhtml任务执行完毕" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 未找到 run_webhtml.sh" >> "$LOG_FILE"
fi

# 运行 autoProcess
if [ -f "${SCRIPT_DIR}/autoPython_bat.sh" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行 autoProcess任务..." >> "$LOG_FILE"
    bash "${SCRIPT_DIR}/autoPython_bat.sh"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] autoProcess任务执行完毕" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: 未找到 autoPython_bat.sh" >> "$LOG_FILE"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 所有任务执行完毕" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
