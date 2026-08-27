#!/bin/bash
# schedule_task.sh - MacOS版本
# 设置定时任务（使用 launchd）
# 自动识别系统本地时区并精准换算对齐【北京时间】A股交易时段：
# - 任务 1: 北京时间 09:35:00 (开盘信号与分析)
# - 任务 2: 北京时间 14:20:00 (尾盘信号与总结)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 设置变量
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TASK_NAME_1="com.gupiao.autoprocess.0935"
TASK_NAME_2="com.gupiao.autoprocess.1420"
RUN_ALL_SCRIPT="${SCRIPT_DIR}/run_all_tasks.sh"
LOG_FILE="${PROJECT_ROOT}/logs/auto_run.log"
VENV_PYTHON="${PROJECT_ROOT}/venv/bin/python"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"

export PROJECT_ROOT
export LAUNCH_AGENTS_DIR
export RUN_ALL_SCRIPT

# 确保日志目录存在
mkdir -p "${PROJECT_ROOT}/logs"
mkdir -p "$LAUNCH_AGENTS_DIR"

# 确定 Python 解释器
PYTHON_CMD="python3"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
fi

# 显示标题
echo "========================================"
echo "MacOS 自动任务计划设置工具 (时区自适应)"
echo "========================================"
echo "目标 A 股交易时段 (北京时间 CST, UTC+8):"
echo "  - 开盘任务: 周一至周五 09:35"
echo "  - 尾盘任务: 周一至周五 14:20"
echo ""

# 检查脚本文件是否存在
for s in "${SCRIPT_DIR}/run_webhtml.sh" "${SCRIPT_DIR}/autoPython_bat.sh" "$RUN_ALL_SCRIPT"; do
    if [ ! -f "$s" ]; then
        echo -e "${RED}错误: 未找到脚本文件 $s${NC}"
        exit 1
    fi
    chmod +x "$s"
done
echo -e "${GREEN}✅ 所有脚本执行权限已就绪${NC}"

# 使用 Python 自动计算本地时区换算并生成 plist
echo ""
echo -e "${CYAN}正在计算本地时区转换并生成任务配置...${NC}"

$PYTHON_CMD - << 'EOF'
import os
import plistlib
from datetime import datetime
import zoneinfo

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "../..") if "__file__" in locals() else os.getcwd()))
LAUNCH_AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
RUN_ALL_SCRIPT = os.path.join(PROJECT_ROOT, "scripts/macos/run_all_tasks.sh")

tz_cst = zoneinfo.ZoneInfo("Asia/Shanghai")
now_local = datetime.now().astimezone()
tz_local = now_local.tzinfo
tz_name = now_local.strftime("%Z")
utc_offset = now_local.strftime("%z")

tasks = [
    ("com.gupiao.autoprocess.0935", 9, 35, "开盘任务 (北京时间 09:35)"),
    ("com.gupiao.autoprocess.1420", 14, 20, "尾盘任务 (北京时间 14:20)")
]

weekday_names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]

print(f"本地系统时区: {tz_name} (UTC{utc_offset[:3]}:{utc_offset[3:]})")
print("-" * 50)

for task_name, bj_h, bj_m, desc in tasks:
    calendar_intervals = []
    local_days_list = []
    local_time_str = ""
    
    # 模拟北京时间周一至周五
    for d in range(5):
        dt_bj = datetime(2026, 8, 24 + d, bj_h, bj_m, tzinfo=tz_cst)
        dt_local = dt_bj.astimezone(tz_local)
        w = int(dt_local.strftime("%w"))
        h = dt_local.hour
        m = dt_local.minute
        calendar_intervals.append({
            "Weekday": w,
            "Hour": h,
            "Minute": m
        })
        w_name = weekday_names[w]
        if w_name not in local_days_list:
            local_days_list.append(w_name)
        local_time_str = f"{h:02d}:{m:02d}"
        
    plist_data = {
        "Label": task_name,
        "ProgramArguments": ["/bin/bash", RUN_ALL_SCRIPT],
        "StartCalendarInterval": calendar_intervals,
        "StandardOutPath": f"{PROJECT_ROOT}/logs/{task_name}.log",
        "StandardErrorPath": f"{PROJECT_ROOT}/logs/{task_name}.error.log",
        "WorkingDirectory": PROJECT_ROOT,
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": os.path.expanduser("~"),
            "PYTHONPATH": PROJECT_ROOT
        }
    }
    
    plist_path = os.path.join(LAUNCH_AGENTS_DIR, f"{task_name}.plist")
    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)
        
    print(f"【{desc}】")
    print(f"  对齐北京时间: 周一至周五 {bj_h:02d}:{bj_m:02d}")
    print(f"  换算本地时间: {'、'.join(local_days_list)} {local_time_str} ({tz_name})")
    print(f"  配置已写入: {plist_path}")
    print("-" * 50)
EOF

# 函数：重新加载 launchd 任务
load_launchd_task() {
    local task_name=$1
    local plist_file="${LAUNCH_AGENTS_DIR}/${task_name}.plist"
    
    # 先卸载旧任务
    launchctl unload "$plist_file" 2>/dev/null
    launchctl bootout gui/"$(id -u)" "$plist_file" 2>/dev/null
    
    # 尝试加载新任务
    if launchctl load "$plist_file" 2>/dev/null || launchctl bootstrap gui/"$(id -u)" "$plist_file" 2>/dev/null; then
        echo -e "${GREEN}✅ 任务 ${task_name} 已成功注册到系统！${NC}"
    else
        echo -e "${RED}❌ 任务 ${task_name} 注册失败，请检查权限。${NC}"
    fi
}

echo ""
echo "正在重新注册 launchd 定时任务..."
load_launchd_task "$TASK_NAME_1"
load_launchd_task "$TASK_NAME_2"

echo ""
echo "========================================"
echo -e "${GREEN}🎉 定时任务设置完成！${NC}"
echo "========================================"
echo "当前托管中的任务列表："
launchctl list | grep "com.gupiao"
echo ""
echo "查看运行日志："
echo "  tail -f ${LOG_FILE}"
echo ""
