# MacOS 自动化任务设置指南

本文档说明如何在 MacOS 上设置股票自动化任务（替代 Windows 的 .bat 脚本）。

## 📁 文件说明

### Shell 脚本（MacOS 版本）

| Windows (.bat) | MacOS (.sh) | 说明 |
|----------------|-------------|------|
| `run_webhtml.bat` | `run_webhtml.sh` | 运行 webhtml/main.py |
| `autoPython_bat.bat` | `autoPython_bat.sh` | 运行 autoProcess.py |
| `run_all_tasks.bat` | `run_all_tasks.sh` | 汇总运行所有任务 |
| `schedule_task.bat` | `schedule_task.sh` | 设置定时任务 |
| `remove_task.bat` | `remove_task.sh` | 删除定时任务 |

## 🚀 快速开始

### 1. 首次设置

确保虚拟环境已创建：

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境并安装依赖
source venv/bin/activate
pip install -r webhtml/requirements.txt
pip install tenacity matplotlib httpx pydantic
```

### 2. 手动运行任务

```bash
# 运行单个任务
./run_webhtml.sh
./autoPython_bat.sh

# 运行所有任务（先运行webhtml，再运行autoProcess）
./run_all_tasks.sh
```

### 3. 设置定时任务

MacOS 使用 `launchd` 管理定时任务（替代 Windows 的 Task Scheduler）：

```bash
# 设置每天 14:30 和 15:10 自动运行
./schedule_task.sh
```

这将在 `~/Library/LaunchAgents/` 创建两个 plist 配置文件：
- `com.gupiao.autoprocess.1430.plist` - 每天 14:30 运行
- `com.gupiao.autoprocess.1510.plist` - 每天 15:10 运行

### 4. 查看任务状态

```bash
# 查看所有任务
launchctl list | grep com.gupiao

# 手动触发任务
launchctl start com.gupiao.autoprocess.1430
launchctl start com.gupiao.autoprocess.1510
```

### 5. 删除定时任务

```bash
./remove_task.sh
```

## 📋 对比：Windows vs MacOS

| 功能 | Windows | MacOS |
|------|---------|-------|
| **脚本格式** | `.bat` | `.sh` |
| **定时任务** | Task Scheduler (`schtasks`) | `launchd` |
| **任务配置** | 命令行参数 | `plist` XML 文件 |
| **任务目录** | 系统任务计划 | `~/Library/LaunchAgents/` |
| **查看任务** | `schtasks /query` | `launchctl list` |
| **运行任务** | `schtasks /run` | `launchctl start` |

## 📄 生成的文件

运行后会生成以下日志文件：

- `webhtml_run.log` - webhtml 任务日志
- `auto_run.log` - autoProcess 任务日志
- `com.gupiao.autoprocess.1430.log` - 定时任务 1 的输出日志
- `com.gupiao.autoprocess.1430.error.log` - 定时任务 1 的错误日志
- `com.gupiao.autoprocess.1510.log` - 定时任务 2 的输出日志
- `com.gupiao.autoprocess.1510.error.log` - 定时任务 2 的错误日志

## ⚠️ 注意事项

1. **权限**：首次运行可能需要添加执行权限：
   ```bash
   chmod +x *.sh
   ```

2. **虚拟环境**：所有脚本会自动激活虚拟环境，确保依赖已安装

3. **时区**：MacOS 脚本使用系统本地时间（请确保系统时区设置为北京时间）

4. **后台运行**：与 Windows 不同，MacOS 的 launchd 任务在后台运行，没有 GUI 窗口

## 🔧 故障排除

### 任务未运行

1. 检查任务是否已加载：
   ```bash
   launchctl list | grep com.gupiao
   ```

2. 检查 plist 文件是否存在：
   ```bash
   ls -la ~/Library/LaunchAgents/com.gupiao.*
   ```

3. 查看错误日志：
   ```bash
   tail -f com.gupiao.autoprocess.1430.error.log
   ```

### Python 环境问题

如果提示找不到 Python：

```bash
# 检查 Python 路径
which python3

# 修改脚本中的 PYTHON_CMD 变量（如需特定路径）
```

### 重新加载任务

如果修改了脚本需要重新加载：

```bash
# 先删除
./remove_task.sh

# 再重新设置
./schedule_task.sh
```

## 📝 自定义时间

编辑 `schedule_task.sh` 文件中的以下变量：

```bash
LOCAL_TIME_1="14:30:00"  # 第一个任务时间
LOCAL_TIME_2="15:10:00"  # 第二个任务时间
```

时间格式为 24 小时制（北京时间）。

## 🎉 完成！

设置完成后，系统会在指定时间自动运行股票分析任务，无需手动干预。
