#!/bin/bash
# schedule_task.sh - MacOS版本
# 设置定时任务（使用 launchd）
# 每天北京时间 14:30 和 15:10 自动运行

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 设置变量
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TASK_NAME_1="com.gupiao.autoprocess.1430"
TASK_NAME_2="com.gupiao.autoprocess.1510"
LOCAL_TIME_1="14:30:00"
LOCAL_TIME_2="15:10:00"
RUN_ALL_SCRIPT="${SCRIPT_DIR}/run_all_tasks.sh"
LOG_FILE="${SCRIPT_DIR}/auto_run.log"

# LaunchAgents 目录
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"

# 显示标题
echo "========================================"
echo "MacOS 自动任务计划设置工具"
echo "========================================"
echo "将创建两个定时任务:"
echo "  - ${TASK_NAME_1} (北京时间 ${LOCAL_TIME_1})"
echo "  - ${TASK_NAME_2} (北京时间 ${LOCAL_TIME_2})"
echo ""

# 检查脚本文件是否存在
if [ ! -f "${SCRIPT_DIR}/run_webhtml.sh" ]; then
    echo -e "${RED}错误: 未找到脚本文件 ${SCRIPT_DIR}/run_webhtml.sh${NC}"
    exit 1
fi

if [ ! -f "${SCRIPT_DIR}/autoPython_bat.sh" ]; then
    echo -e "${RED}错误: 未找到脚本文件 ${SCRIPT_DIR}/autoPython_bat.sh${NC}"
    exit 1
fi

if [ ! -f "$RUN_ALL_SCRIPT" ]; then
    echo -e "${RED}错误: 未找到脚本文件 $RUN_ALL_SCRIPT${NC}"
    exit 1
fi

# 检查虚拟环境
VENV_DIR="${SCRIPT_DIR}/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}警告: 未找到虚拟环境: $VENV_DIR${NC}"
    echo -e "${YELLOW}请先运行: python3 -m venv venv${NC}"
    echo -e "${YELLOW}然后安装依赖: source venv/bin/activate && pip install -r webhtml/requirements.txt${NC}"
    read -p "是否继续? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 创建 LaunchAgents 目录（如果不存在）
if [ ! -d "$LAUNCH_AGENTS_DIR" ]; then
    echo "创建 LaunchAgents 目录..."
    mkdir -p "$LAUNCH_AGENTS_DIR"
fi

# 函数：创建 plist 文件
create_plist() {
    local task_name=$1
    local hour=$2
    local minute=$3
    local plist_file="${LAUNCH_AGENTS_DIR}/${task_name}.plist"
    
    cat > "$plist_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${task_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${RUN_ALL_SCRIPT}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${hour}</integer>
        <key>Minute</key>
        <integer>${minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/${task_name}.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/${task_name}.error.log</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>
</dict>
</plist>
EOF
    echo "$plist_file"
}

# 函数：加载任务
load_task() {
    local task_name=$1
    local plist_file="${LAUNCH_AGENTS_DIR}/${task_name}.plist"
    
    # 卸载已存在的任务
    launchctl unload "$plist_file" 2>/dev/null
    
    # 加载新任务
    if launchctl load "$plist_file" 2>/dev/null; then
        echo -e "${GREEN}✅ 任务 ${task_name} 创建成功！${NC}"
        return 0
    else
        # 尝试使用新的 launchctl 语法 (macOS 10.10+)
        if launchctl bootstrap gui/"$(id -u)" "$plist_file" 2>/dev/null; then
            echo -e "${GREEN}✅ 任务 ${task_name} 创建成功！${NC}"
            return 0
        else
            echo -e "${RED}❌ 任务 ${task_name} 创建失败！${NC}"
            return 1
        fi
    fi
}

echo "正在设置计划任务..."
echo "脚本路径: $RUN_ALL_SCRIPT"
echo "日志文件: $LOG_FILE"
echo ""

# 删除已存在的同名任务
echo "检查并删除已存在的同名任务..."
launchctl unload "${LAUNCH_AGENTS_DIR}/${TASK_NAME_1}.plist" 2>/dev/null
launchctl unload "${LAUNCH_AGENTS_DIR}/${TASK_NAME_2}.plist" 2>/dev/null
launchctl bootout gui/"$(id -u)" "${LAUNCH_AGENTS_DIR}/${TASK_NAME_1}.plist" 2>/dev/null
launchctl bootout gui/"$(id -u)" "${LAUNCH_AGENTS_DIR}/${TASK_NAME_2}.plist" 2>/dev/null

# ===== 创建第一个任务 (14:30) =====
echo ""
echo "创建任务 1: ${TASK_NAME_1} (${LOCAL_TIME_1})..."
PLIST_1=$(create_plist "$TASK_NAME_1" 14 30)
load_task "$TASK_NAME_1"

# ===== 创建第二个任务 (15:10) =====
echo ""
echo "创建任务 2: ${TASK_NAME_2} (${LOCAL_TIME_2})..."
PLIST_2=$(create_plist "$TASK_NAME_2" 15 10)
load_task "$TASK_NAME_2"

# 显示任务详情
echo ""
echo "========================================"
echo "任务创建完成！"
echo "========================================"
echo ""
echo -e "${GREEN}任务 1 详情:${NC}"
echo "  名称: ${TASK_NAME_1}"
echo "  时间: 每天 ${LOCAL_TIME_1}"
echo "  配置: ${PLIST_1}"
echo ""
echo -e "${GREEN}任务 2 详情:${NC}"
echo "  名称: ${TASK_NAME_2}"
echo "  时间: 每天 ${LOCAL_TIME_2}"
echo "  配置: ${PLIST_2}"
echo ""
echo "日志将保存到:"
echo "  - ${SCRIPT_DIR}/${TASK_NAME_1}.log"
echo "  - ${SCRIPT_DIR}/${TASK_NAME_2}.log"
echo "  - ${SCRIPT_DIR}/${TASK_NAME_1}.error.log"
echo "  - ${SCRIPT_DIR}/${TASK_NAME_2}.error.log"
echo "  - ${LOG_FILE}"
echo ""
echo "提示: 你可以通过以下命令查看任务状态:"
echo "  launchctl list | grep com.gupiao"
echo ""
echo "手动触发任务:"
echo "  launchctl start ${TASK_NAME_1}"
echo "  launchctl start ${TASK_NAME_2}"
echo ""
echo "删除任务:"
echo "  bash remove_task.sh"
echo ""
echo "按回车键退出..."
read -r
