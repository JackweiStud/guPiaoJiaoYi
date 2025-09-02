## 金融行情监控仪表盘 (webhtml)

### 快速开始
- 进入本目录：`cd webhtml`
- 安装依赖：`pip install -r requirements.txt`
- 运行：`python -m webhtml.main`
- 输出：生成 `output/reports/report_YYYY-MM-DD.html` 与日志 `output/logs/`

### 说明
- 默认使用 mock 数据生成报告，确保可直接出结果。
- 可选邮件发送默认关闭（见 `config/settings.py`）。
- 目录结构已按《需求说明书.md》规划，后续将补充 `data_handler/fetcher.py`、`analysis/calculator.py`、`analysis/ai_summary.py` 的实时数据逻辑。

### 配置
- `config/settings.py`：路径、模板名、开关（SEND_MAIL、USE_DEEPSEEK）等。
- `config/market_watch_list.py`：监控清单（指数、风格ETF、行业与全球指标）。


