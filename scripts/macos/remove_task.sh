#!/bin/bash
# remove_task.sh - MacOS版本
# 删除定时任务

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 设置变量
TASK_NAME_1="com.gupiao.autoprocess.1430"
TASK_NAME_2="com.gupiao.autoprocess.1510"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"

echo "========================================"
echo "MacOS 自动任务删除工具"
echo "========================================"
echo ""

# 函数：删除任务
remove_task() {
    local task_name=$1
    local plist_file="${LAUNCH_AGENTS_DIR}/${task_name}.plist"
    
    if [ -f "$plist_file" ]; then
        echo "正在删除任务: ${task_name}..."
        
        # 尝试卸载任务（旧版本 macOS）
        launchctl unload "$plist_file" 2>/dev/null
        
        # 尝试卸载任务（新版本 macOS 10.10+）
        launchctl bootout gui/"$(id -u)" "$plist_file" 2>/dev/null
        
        # 删除 plist 文件
        rm -f "$plist_file"
        
        echo -e "${GREEN}✅ 任务 ${task_name} 已删除${NC}"
    else
        echo -e "${YELLOW}任务 ${task_name} 不存在${NC}"
    fi
}

# 删除任务 1
echo "删除任务 1..."
remove_task "$TASK_NAME_1"

# 删除任务 2
echo ""
echo "删除任务 2..."
remove_task "$TASK_NAME_2"

# 显示剩余任务
echo ""
echo "========================================"
echo "当前剩余的股票相关任务:"
echo "========================================"
launchctl list | grep "com.gupiao" || echo -e "${GREEN}无${NC}"
echo ""

echo "按回车键退出..."
read -r
