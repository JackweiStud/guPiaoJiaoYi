# guPiaoJiaoYi - AI和量化投资探索

## 🚀 快速开始

### 环境要求
- Python 3.14+
- 推荐使用虚拟环境

### 安装步骤

1. **创建虚拟环境**
   ```bash
   python3 -m venv venv
   ```

2. **激活虚拟环境**
   ```bash
   # MacOS/Linux
   source venv/bin/activate
   
   # Windows
   venv\Scripts\activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

## 📁 项目结构

```
guPiaoJiaoYi/
├── scripts/
│   ├── macos/          # MacOS 脚本
│   │   ├── run_webhtml.sh
│   │   ├── autoPython_bat.sh
│   │   ├── run_all_tasks.sh
│   │   ├── schedule_task.sh
│   │   └── remove_task.sh
│   └── windows/         # Windows 脚本
│       ├── run_webhtml.bat
│       ├── autoPython_bat.bat
│       ├── run_all_tasks.bat
│       ├── schedule_task.bat
│       ├── remove_task.bat
│       └── install_dependencies.bat
├── logs/              # 自动化运行日志
├── webhtml/          # Web 报告系统
├── venv/             # Python 虚拟环境
└── README_MacOS.md   # MacOS 详细说明
```

## 🛠 核心功能模块

### 1. **数据处理** (`data_fetcher.py`, `data_manager.py`)
- 获取 ETF 日线数据（东方财富 + 新浪备用接口）
- 支持多只股票数据获取
- 自动数据存储和管理

### 2. **交易策略** (`sdd.py`, `strategyFunc`)
- **多因子量化策略**：
  - 均线交叉（金叉死叉）
  - RSI 超买超卖
  - 乖离率修复（暴跌抄底）
  - 成交量确认
- **智能参数配置**：每个股票可独立配置策略参数
- **完整回测系统**：包含绩效计算、图表生成

### 3. **AI 分析** (`deepSeekAi.py`)
- 集成 DeepSeek AI 模型进行趋势分析
- 支持数据驱动的投资建议
- 智能提取持仓策略

### 4. **自动化执行** (`autoProcess.py`)
- 定时获取最新数据
- 策略信号分析
- AI 趋势分析
- 邮件自动通知

### 5. **邮件通知** (`mailFun.py`)
- 支持 QQ、Gmail、Outlook 多种邮箱
- HTML 邮件格式
- 图表附件发送

### 6. **Web 报告** (`webhtml/`)
- 实时行情监控报告
- 指数、ETF、全球风险资产分析
- AI 智能总结
- 邮件推送

## 📊 监控股票范围

- **A股ETF**：消费、银行、科创50、创业板
- **美股ETF**：标普500、纳斯达克
- **港股**：恒生指数、港股科技30
- **全球资产**：黄金、美债、加密货币

## ⏰ 自动化运行

### MacOS
```bash
# 手动运行
./scripts/macos/run_all_tasks.sh

# 设置定时任务（每天 14:30 和 15:10）
./scripts/macos/schedule_task.sh

# 删除定时任务
./scripts/macos/remove_task.sh
```

### Windows
```bash
# 设置定时任务
scripts\windows\schedule_task.bat

# 手动运行
scripts\windows\run_all_tasks.bat
```

## 📋 策略参数说明

每个股票的参数在 `strategy_params.json` 中配置：

```json
{
  "default": {
    "short_window": 5,
    "long_window": 20,
    "volume_mavg_Value": 20,
    "MaRateUp": 0.02,
    "VolumeSellRate": 0.8,
    "rsi_period": 14,
    "rsiValueThd": 50,
    "rsiRateUp": 0.02,
    "divergence_threshold": 0.05
  },
  "159843": {
    "short_window": 5,
    "long_window": 20,
    "MaRateUp": 0.03,
    "VolumeSellRate": 1.2
  }
}
```

## 📧 邮件配置

在 `config.py` 中配置邮箱：

```python
# 选择邮箱服务商
ACTIVE_SMTP_PROVIDER = "qq"  # qq/gmail/outlook

# 邮箱认证
SENDER_CREDENTIALS = {
    "email": "your_email@qq.com",
    "password": "your_authorization_code"  # QQ邮箱用授权码
}

# 收件人
DEFAULT_RECIPIENTS = {
    "to": ["recipient@example.com"],
    "cc": ["cc@example.com"]
}
```

## 🔧 故障排除

### 网络连接问题
- **国内环境**：使用新浪接口（已配置备用）
- **国外环境**：可使用东方财富接口
- **代理设置**：确保网络能访问 akshare 接口

### Python 环境
```bash
# 检查虚拟环境
source venv/bin/activate
python3 -c "import akshare, pandas, matplotlib; print('OK')"

# 安装缺失依赖
pip install --upgrade akshare pandas matplotlib requests tenacity pydantic httpx jinja2
```

### 定时任务
```bash
# MacOS 查看任务状态
launchctl list | grep com.gupiao

# Windows 查看任务状态
schtasks /query | findstr "AutoProcess"
```

## 📈 更新日志

- **2026-02-05**: MacOS 兼容性改进，目录结构重构
- **2026-02-04**: 修复数据加载问题，适配 MacOS 环境

## ⚠️ 注意事项

1. **网络环境**：国内使用无需VPN，国外可能需要代理
2. **邮箱设置**：QQ邮箱需要授权码，非密码
3. **数据来源**：优先使用东方财富，失败自动切换新浪
4. **风险控制**：所有策略仅供参考，投资需谨慎

## 📞 支持

详细使用说明请参考：
- `readmeMd/README_MacOS.md` - MacOS 详细设置
- `readmeMd/README_QQ邮箱配置.md` - 邮箱配置说明
- `readmeMd/README_自动任务设置.md` - Windows 任务设置