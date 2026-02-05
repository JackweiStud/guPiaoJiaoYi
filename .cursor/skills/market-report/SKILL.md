---
name: market-report
description: "用于触发 guPiaoJiaoYi 的行情/信号/AI分析流程并返回 JSON 摘要，适合 OpenClaw/TG 自动化。当用户说“检查行情/生成日报/看盘/给我XX代码信号/要AI分析”时使用。"
---

# 市场报告（Market Report）

使用该技能运行本地项目的统一入口 `run.py`，把结果以 JSON 形式返回，方便 TG 直接转发。

## 硬规则（必须遵守）

- 必须用 `--format json` 输出。
- 返回给用户的内容必须包含“本次实际执行的命令/参数”。
  - 优先：直接返回 `run.py` 输出的 JSON，其中应包含 `invocation.argv`（run.py 会自动回显）。
  - 若用户贴的输出里缺少命令回显，则在回复里先补一行 `COMMAND: ...` 再贴 JSON。

## 基本信息

- 项目路径：`/Users/jackwl/Code/gitcode/guPiaoJiaoYi`
- Python（虚拟环境）：`/Users/jackwl/Code/gitcode/guPiaoJiaoYi/venv/bin/python`

## 运行环境建议（减少噪音）

- 推荐加环境变量，避免 matplotlib 缓存/字体初始化造成的卡顿与告警：

```bash
export MPLCONFIGDIR=/tmp/matplotlib-cache
```

或在命令前面加：`MPLCONFIGDIR=/tmp/matplotlib-cache`。

## 默认执行（不指定代码）

当用户只说“检查行情/生成日报/看盘”，不指定代码时：

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache /Users/jackwl/Code/gitcode/guPiaoJiaoYi/venv/bin/python \
  /Users/jackwl/Code/gitcode/guPiaoJiaoYi/run.py all --no-ai --no-mail --format json
```

## 用户指定代码（只要信号）

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache /Users/jackwl/Code/gitcode/guPiaoJiaoYi/venv/bin/python \
  /Users/jackwl/Code/gitcode/guPiaoJiaoYi/run.py signal --codes 159843,512820 --format json
```

## 用户指定代码（需要 AI 分析，不发邮件）

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache /Users/jackwl/Code/gitcode/guPiaoJiaoYi/venv/bin/python \
  /Users/jackwl/Code/gitcode/guPiaoJiaoYi/run.py auto --codes 159843.SH,512820.SH --no-mail-auto --format json
```

## 网络不稳定时的兜底

- 若抓取数据失败（DNS/连接问题），可以用已有本地数据快速出信号：

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache /Users/jackwl/Code/gitcode/guPiaoJiaoYi/venv/bin/python \
  /Users/jackwl/Code/gitcode/guPiaoJiaoYi/run.py signal --codes 512820.SH --no-fetch --format json
```

- 回复时明确提示“本次使用本地已有数据（可能不是最新）”。

## 默认代码池

- 不传 `--codes` 时，会优先读取 `.env` 的 `SIGNAL_CODES` 或 `AUTO_CODES`。
- 若未设置，则使用 `strategy_params.json` 中配置的代码。
- 可列出默认池：

```bash
/Users/jackwl/Code/gitcode/guPiaoJiaoYi/venv/bin/python \
  /Users/jackwl/Code/gitcode/guPiaoJiaoYi/run.py --list-codes
```

## 错误处理

- 若提示缺依赖：

```bash
/Users/jackwl/Code/gitcode/guPiaoJiaoYi/venv/bin/python -m pip install -r \
  /Users/jackwl/Code/gitcode/guPiaoJiaoYi/requirements.txt
```

## 输出要求

- **必须返回 JSON 输出**（stdout）。
- TG 可直接转发 JSON，或抽取关键字段：
  - `signals[].signal` / `signals[].reason` / `signals[].fetch_ok`
  - `auto[].signal` / `auto[].signal_reason` / `auto[].ai_strategy` / `auto[].ai_analysis`

## 用户可说的话（示例）

- “检查下当前行情”
- “生成今天的市场日报”
- “看下 512810 的信号”
- “给我 159843、512820 的信号”
- “只要信号，不要发邮件”
- “要 AI 分析，但别发邮件”
- “网络不好，用本地数据先出结果”