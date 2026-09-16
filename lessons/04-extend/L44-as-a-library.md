---
id: L44
title: "当作库来用：Python / ACP / API Server"
stage: 4
level: 进阶
minutes: 25
prereq: [L41]
tags: ["Python 库", "AIAgent", "ACP", "API Server", "集成"]
sources: [programmatic, python-library, api-server, acp]
updated: 2026-09-16
---

# L44 · 当作库来用：Python / ACP / API Server

> **一句话**：Hermes 不只是一个终端程序 —— 它有三条「让别的程序驱使它」的正式通道，选错通道会让你写一堆不必要的胶水代码。

## 你将学会

- 区分三条集成通道（Python 库 / ACP / OpenAI 兼容 API）并选对场景
- 在自己的 Python 脚本里跑起 `AIAgent`，并读懂它的两类启动期报错
- 用 `hermes acp --check` 验证编辑器接入是否就绪
- 说清「进程内调用」与「起一个服务」各自的代价

**前置**：L41 · **预计耗时**：25 分钟

## 先动手

用 Hermes 自己的虚拟环境跑一个最小脚本（**不要**用系统 Python，依赖在 venv 里）：

```bash
export HERMES_HOME="${HERMES_HOME:-$LOCALAPPDATA/hermes}"     # Windows
# macOS/Linux: export HERMES_HOME="$HOME/.hermes"
"$HERMES_HOME/hermes-agent/venv/Scripts/python" - <<'PY'
import sys, os
sys.path.insert(0, os.path.join(os.environ["HERMES_HOME"], "hermes-agent"))
from run_agent import AIAgent

agent = AIAgent(model="<你本机在用的模型名>", enabled_toolsets=["web"], quiet_mode=True)
print("RESULT:", agent.chat("Reply with exactly one word: library-ok"))
PY
```

本机真实输出（模型名填对时）：

```
RESULT: library-ok
```

**先确认你该填哪个模型名**：

```bash
hermes config get model
```

## 原理

### 三条通道，选错就开始还债

| 通道 | 形态 | 适合 | 代价 |
|---|---|---|---|
| **Python 库**（`AIAgent`） | 在你的进程里跑 | 自己的脚本、数据管道、批处理 | 与 Hermes 同进程，依赖要装它的 venv |
| **ACP** | 编辑器 ↔ Hermes 的协议 | VS Code / Zed / JetBrains 里用 | 面向编辑器，不适合自定义逻辑 |
| **OpenAI 兼容 API** | 一个本地 HTTP 端点 | 任何会说 OpenAI 格式的前端（Open WebUI、LobeChat…） | 多一个常驻进程 |
| （附）**TUI gateway JSON-RPC** | 给 UI 用的底层协议 | 做 TUI/桌面类前端 | 最底层、最不稳定 |

三条协议都是「正式通道」，不是把 CLI 包一层 `subprocess`。[[src:programmatic]]

### 进程内调用：两个接口

```python
# 简单接口：只要最终答复
response = agent.chat("Fix the bug in main.py")

# 完整接口：拿到消息、元数据、用量
result = agent.run_conversation(
    user_message="Fix the bug in main.py",
    system_message=None,          # 省略则自动构建
    conversation_history=None,    # 省略则从会话加载
    task_id="task_abc123",
)
```

`chat()` 是 `run_conversation()` 的薄封装（取 `final_response`）。所以「我想拿到 token
用量和完整消息」时，用后者。[[src:programmatic]]

### ACP：给编辑器用

```bash
hermes acp --check        # 本机真实输出：Hermes ACP check OK
hermes acp --version      # 本机真实输出：0.21.3
```

`--check` 通过就意味着编辑器那边可以接上了：聊天、工具活动、文件 diff、终端命令
都在编辑器里渲染。[[src:acp]]

### API Server：把 Hermes 变成一个 OpenAI 端点

它让**任何**会说 OpenAI 格式的前端把你的 Hermes 当成一个「模型」来用：
Open WebUI、LobeChat、LibreChat 等。[[src:api-server]]

启动分两步：先把开关写进 `~/.hermes/.env`，再起网关 —— API Server 是**网关的一个平台**，
所以命令是 `hermes gateway run`（**没有** `hermes api-server` 这个子命令）。[[src:api-server]]

```bash
# ~/.hermes/.env
API_SERVER_ENABLED=true
API_SERVER_KEY=change-me-local-dev
```

```bash
hermes gateway run
```

本机真实输出（横幅落在网关日志 `$HERMES_HOME/logs/gateway.log`，是 INFO 级；把 stdout
重定向到文件时只看到 WARNING 级行，所以别只在终端上找它。文档页面把它写作
`[API Server] …`，实际运行时是下面这个写法，末尾还会带上模型名）：

```
[Api_Server] API server listening on http://127.0.0.1:8642 (model: hermes-agent)
```

端点确实起来了 —— 本机实测三条（同一个临时环境里 `curl` 出来的原文）：

```bash
curl http://127.0.0.1:8642/health
# {"status": "ok", "platform": "hermes-agent", "version": "0.21.3"}

curl -H "Authorization: Bearer change-me-local-dev" http://127.0.0.1:8642/v1/models
# {"object": "list", "data": [{"id": "hermes-agent", "object": "model", ...}]}

curl http://127.0.0.1:8642/v1/models      # 不带 Authorization
# 401 —— API_SERVER_KEY 是必需的，哪怕是绑定在 127.0.0.1 上
```

> **复现范围**：本机复现用的是**隔离的临时 `HERMES_HOME`**（没有动你自己的 `~/.hermes`），
> 所以 `/v1/models` 里只有默认 profile 的 `hermes-agent` 一个 id，也没有接真实前端做联调。
> 端口、模型名、版本号以你自己的输出为准。

## 亲手验证

### 验证一：空模型名会被 provider 拒绝（错误信息很有信息量）

```python
AIAgent(model="", quiet_mode=True).chat("hi")
```

本机真实输出：

```
HTTP 400: The supported API model names are deepseek-flash, deepseek-v4-pro, but you passed .
```

**读法**：`model=""` 不会「自动选一个」，它会被原样发给 provider 并被拒；
而且**错误信息会告诉你本机 provider 支持的模型名**——这是一条很好的自查手段。
（对照 [[L10]]：新装机器上 `config.yaml` 里的 `model: ""` 是「未配置」的哨兵值。）[[src:python-library]]

### 验证二：没有 provider 时，它拒绝启动而不是瞎猜

在清掉了 provider 环境变量的干净环境里：

```
RuntimeError: No LLM provider configured. Run `hermes model` to select a provider,
or run `hermes setup` for first-time configuration.
```

| 报错 | 含义 | 下一步 |
|---|---|---|
| `HTTP 400 … but you passed .` | `model` 传了空字符串 | `hermes config get model` 拿真名，或先 `hermes model` |
| `No LLM provider configured` | 这个进程/环境里没有可用凭证 | 用**宿主的** `HERMES_HOME`（凭证在 `$HERMES_HOME/.env` 与 `auth.json`） |

### 验证三：ACP 就绪自检

```bash
hermes acp --check && echo "编辑器可以接了"
```

### 验证四：分清「库」与「服务」

```bash
# 库：一次调用结束，进程退出，没有常驻
"$HERMES_HOME/hermes-agent/venv/Scripts/python" your_script.py

# 服务：起一个端点，别人连你
hermes gateway run       # 先按上面的 API_SERVER_ENABLED / API_SERVER_KEY 开好开关
```

**判据**：你要的是「我的程序调用 agent」→ 库；「别人的程序调用我的 agent」→ 服务。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `ImportError: run_agent` | 用了系统 Python | 用 `$HERMES_HOME/hermes-agent/venv` 里的解释器，并把安装目录加进 `sys.path` |
| `HTTP 400 … but you passed .` | `model=""` | 显式传模型名；别指望它自动挑 |
| `No LLM provider configured` | 环境里没有凭证（常见于隔离的 `HERMES_HOME`） | 用宿主的 `HERMES_HOME`，或先配好 provider |
| 想拿用量却只拿到字符串 | 用了 `chat()` | 用 `run_conversation()` 拿结果字典 |
| 用 `subprocess` 调 `hermes chat -q` 当集成方案 | 把 CLI 当 API | 进程内用 `AIAgent`，跨进程用 API Server / ACP |
| 把凭证写进脚本 | 想图方便 | 凭证留在 `$HERMES_HOME/.env`；脚本只引用环境 |
| 批处理时并发十个 `AIAgent` | 没考虑速率限制与额度 | 用凭证池（[[L51]]）或 `batch_runner` 的思路分批跑 |

## 试一试

- [ ] 写一个 20 行的脚本：读一个本地文件 → 让 `AIAgent` 总结 → 写回另一个文件
- [ ] 故意传 `model=""`，把报错里的「支持的模型名」抄进 `journal/`（这是一条现成的自查命令）
- [ ] 跑 `hermes acp --check`，如果你用 VS Code/Zed，接上试一次
- [ ] 判断：你要做一个「每天早上把三个数据源汇总成一份简报」的工具，该用库还是服务？写下理由

## 下一步

- [[L41]] —— 插件：当你要扩展的是**内核行为**而不是外部程序时
- [[L90]] —— 毕业项目：把这些通道用到你真实的自动化里
- [[L51]] —— 多身份与凭证：集成里最容易被忽略的一层
- 想深入：[[src:programmatic]]（三条协议的完整契约）、[[src:python-library]]（库用法样例）

## 出处

- [[src:programmatic]] Programmatic Integration — https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
- [[src:python-library]] Using Hermes as a Python Library — https://hermes-agent.nousresearch.com/docs/guides/python-library
- [[src:api-server]] API Server — https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
- [[src:acp]] ACP Host Integration — https://hermes-agent.nousresearch.com/docs/user-guide/features/acp
