---
name: market-report
description: "用于触发 guPiaoJiaoYi 的行情/信号/AI分析流程并返回 JSON 摘要，适合 OpenClaw/TG 自动化。当用户说"检查ETF行情/生成A股金融日报/A股看盘/给我XXETF代码信号/A股的AI分析"时使用。"
---

# 市场报告（Market Report）

使用该技能运行本地项目的统一入口 `run.py`，把结果以 JSON 形式返回，方便 TG 直接转发。

## 硬规则（必须遵守）

- 必须用 `--format json` 输出。
- 返回给用户的内容必须包含"本次实际执行的命令/参数"。
  - 优先：直接返回 `run.py` 输出的 JSON，其中应包含 `invocation.argv`（run.py 会自动回显）。
  - 若用户贴的输出里缺少命令回显，则在回复里先补一行 `COMMAND: ...` 再贴 JSON。

## 超时与耗时提醒（重要）

根据模式不同，超时设置建议：

| 模式 | 典型耗时 | 建议超时 |
|------|---------|---------|
| `fetch` | 5-15秒 | 60秒 |
| `signal` | 10-30秒 | 60秒 |
| `report` | 30-90秒 | 120秒 |
| `auto` (含 AI) | 60-180秒 | 180秒 |
| `all` (全流程) | 120-300秒 | 300秒 |

如果出现超时，可重试或使用 `--no-fetch` 兜底（见下文）。

## 基本信息

```bash
# 项目路径
PROJECT=/Users/jackwl/Code/gitcode/guPiaoJiaoYi

# Python 虚拟环境
PYTHON=$PROJECT/venv/bin/python

# 运行入口
RUNPY=$PROJECT/run.py

# 环境变量（减少 matplotlib 噪音）
export MPLCONFIGDIR=/tmp/matplotlib-cache
```

## 运行模式速查

| 模式 | 说明 | 典型场景 |
|------|------|---------|
| `all` | 全流程：拉数据→信号→报告 | 每日综合日报 |
| `signal` | 仅计算交易信号 | 快速查看买卖点 |
| `auto` | AI 深度分析流程 | 需要 AI 解读时使用 |
| `report` | 仅生成 HTML 报告 | 生成 Web 报告/邮件 |
| `fetch` | 仅拉取最新数据 | 只更新数据不分析 |

---

## 常用命令示例

### 默认执行（不指定代码）

当用户只说"检查行情/生成日报/看盘"，不指定代码时：

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache $PYTHON $RUNPY all --no-mail --format json
```

> 默认开启 AI 总结。如需禁用可加 `--no-ai`。

### 用户指定代码（只要信号）

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache $PYTHON $RUNPY signal --codes 159843,512820 --format json
```

### 用户指定代码（需要 AI 分析，不发邮件）

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache $PYTHON $RUNPY auto --codes 159843.SH,512820.SH --no-mail-auto --format json
```

### 仅生成 HTML 报告（不拉取数据、不发邮件）

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache $PYTHON $RUNPY report --no-ai --no-mail --format json
```

### 仅更新数据（不分析）

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache $PYTHON $RUNPY fetch --codes 159843,512820 --format json
```

### 网络不稳定时的兜底

若抓取数据失败（DNS/连接问题），可以用已有本地数据快速出信号：

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache $PYTHON $RUNPY signal --codes 512820.SH --no-fetch --format json
```

> ⚠️ 回复时明确提示"本次使用本地已有数据（可能不是最新）"。

### 将结果保存到文件

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache $PYTHON $RUNPY signal --codes 159843 --format json --summary-file /tmp/result.json
```

---

## 默认代码池

- 不传 `--codes` 时，会优先读取 `.env` 的 `SIGNAL_CODES` 或 `AUTO_CODES`。
- 若未设置，则使用 `strategy_params.json` 中配置的代码。
- 可列出默认池（注意：此命令输出纯文本，非 JSON）：

```bash
$PYTHON $RUNPY --list-codes
```

---

## 完整参数列表

| 参数 | 说明 |
|------|------|
| `--codes` | 指定代码，多个用逗号分隔（如 `159843,512820.SH`） |
| `--no-fetch` | 跳过数据抓取，直接使用本地缓存 |
| `--no-ai` | 禁用 HTML 报告中的 AI 市场总结 |
| `--no-mail` | 禁用 HTML 报告的邮件发送 |
| `--no-mail-auto` | 禁用 auto 模式的邮件发送 |
| `--format` | 输出格式：`text`（默认）或 `json` |
| `--summary-file` | 将运行结果保存到指定文件 |
| `--list-codes` | 列出当前配置的所有监控代码并退出 |

---

## JSON 输出结构

```json
{
  "generated_at": "2026-02-06 09:30:00",
  "mode": "signal",
  "invocation": {
    "python": "/path/to/python",
    "cwd": "/path/to/project",
    "argv": ["run.py", "signal", "--codes", "159843", "--format", "json"]
  },
  "signals": [
    {
      "code": "159843.SZ",
      "signal": "买入",
      "reason": "金叉 + RSI超卖",
      "fetch_ok": true
    }
  ],
  "report": {
    "report_date": "2026-02-06",
    "report_path": "/path/to/report.html",
    "ai_summary": "..."
  },
  "auto": [
    {
      "code": "512820.SH",
      "signal": "持有",
      "signal_reason": "...",
      "ai_strategy": "...",
      "ai_analysis": "..."
    }
  ]
}
```

> 注意：不同模式返回的字段不同，`signals` 仅在 signal/all 模式出现，`auto` 仅在 auto 模式出现。

---

## 错误处理

若提示缺依赖：

```bash
$PYTHON -m pip install -r $PROJECT/requirements.txt
```

---

## 用户可说的话（示例）

- "检查下当前行情"
- "生成今天的市场日报"
- "看下 512810 的信号"
- "给我 159843、512820 的信号"
- "只要信号，不要发邮件"
- "要 AI 分析，但别发邮件"
- "网络不好，用本地数据先出结果"
- "只更新数据，不用分析"
- "生成报告但不发邮件"