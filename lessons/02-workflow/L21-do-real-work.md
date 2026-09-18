---
id: L21
title: "让它动真格：终端 / 文件 / 浏览器 / 网页"
stage: 2
level: 进阶
minutes: 25
prereq: [L11, L20]
tags: ["terminal", "browser", "web_extract", "code_execution"]
sources: [tools, tools-reference, browser, web-search, code-execution]
updated: 2026-09-16
---

# L21 · 让它动真格：终端 / 文件 / 浏览器 / 网页

> **一句话**：这四类工具各有各的代价与边界 —— 知道哪个贵、哪个改系统、哪个抓不到，你才不会用错手。

## 你将学会

- 说出终端 / 文件 / 浏览器 / 网页抓取四类工具各自适合什么、代价差在哪
- 用 `--toolsets` 按任务收窄权限，并知道容器后端会跳过危险命令检查
- 亲手触发一次 `web_extract` 的抓取失败，学会改走 `browser_navigate` 或 `web_search`
- 判断什么时候该让它写脚本（`execute_code`）而不是一步步调工具

**前置**：[[L11]]、[[L20]] · **预计耗时**：25 分钟

## 先动手

```bash
hermes chat -q "用浏览器工具打开 https://example.com，然后告诉我页面的 h1 标题文字" -Q
```

本机真实输出：

```
页面的 h1 标题文字是：Example Domain
```

**这不是抓字符串**：它启动了一个真实浏览器、加载了页面，读的是页面的可访问性树快照（文本形式，交互元素带 `@e1` 这类 ref ID），而不是抓一段 HTML 字符串。同一个会话里它还能顺手跑终端命令、改文件 —— 这就是「动真格」的意思。[[src:browser]]

## 原理

### 四类工具的边界

| 类别 | 代表工具 | 适合 | 代价/注意 |
|---|---|---|---|
| **终端** | `terminal`、`process` | 跑命令、构建、起后台进程 | 直接改你的系统；在哪个环境执行由终端后端决定 |
| **文件** | `read_file`、`search_files`、`write_file`、`patch` | 读改代码与配置 | `write_file` 会整文件覆盖；改动前先读 |
| **浏览器** | `browser_navigate`、`browser_snapshot`、`browser_click`、`browser_type`、`browser_vision` | 需要点击、填表、登录态的页面 | 慢、贵；官方明确建议：**简单信息检索优先用轻量抓取工具** [[src:browser]] |
| **网页抓取** | `web_search`、`web_extract` | 搜索 + 抽正文（含 PDF） | 只读；`web_extract` 一次最多 5 个 URL [[src:tools-reference]]，超大页面走确定性字符预算截断（不做 LLM 摘要） [[src:web-search]] |

工具清单的权威版本在代码里：`hermes tools list` 与官方 Built-in Tools Reference。当前注册表约 86 个工具，其中浏览器核心 10 个、文件 4 个、终端 2 个、web 2 个。[[src:tools-reference]]

`browser_cdp` 和 `browser_dialog` 属于 CDP 门控工具：只有会话启动时能连上 Chrome DevTools Protocol 端点才会注册（通过 `/browser connect`、`browser.cdp_url` 配置等）。[[src:tools-reference]]

`web_search` / `web_extract` 背后是一个可切换的搜索后端：官方 Backends 表把 `EXA_API_KEY`、`PARALLEL_API_KEY`、`FIRECRAWL_API_KEY`、`TAVILY_API_KEY`、`PERPLEXITY_API_KEY`、`KEENABLE_API_KEY` 列为对应厂商的凭证。一张凭证都没有的新装机器也不会全挂 —— 官方说请求会轮询免费额度池（Exa / Parallel / Firecrawl / Keenable），要关掉设 `web.keyless_fallback: false`。[[src:web-search]]

### 终端后端决定「它在哪动手」

| 后端 | 位置 | 什么时候用 |
|---|---|---|
| `local` | 你这台机器（默认） | 开发、可信任务 |
| `docker` | 隔离容器 | 跑不信任的代码、要可复现 |
| `ssh` | 远程服务器 | 把它挡在你自己的代码之外 |
| `singularity` / `modal` / `daytona` / `vercel_sandbox` | HPC 容器、云上 | 集群、无服务器、远程工作区 |

```bash
hermes config set terminal.backend docker
```

[[src:tools]]

**agent 的终端命令忽然全部超时**这类怪事的常见原因是 shell 初始化：agent 的终端调用是**非交互式**的，`.bashrc` 里任何会 `read`、attach `tmux`、或跑网络请求的东西都会把它挂住。标准修法是在 `.bashrc` 顶部加一个非交互式早退 guard。[[src:tools]]

### 读结果时要看懂的两个注解

| 场景 | 行为 |
|---|---|
| 命令被信号杀死 | 结果里带人话解释：`-9`/`137` → SIGKILL，通常会提示可能是 OOM |
| 读到 UTF-16 文本文件 | 自动转码成 UTF-8 展示（Windows 记事本、PowerShell `>` 重定向的常见格式），而不是当二进制拒绝 |

[[src:tools]]

### 三步以上带逻辑的活，写脚本而不是连点工具

`execute_code` 让 agent 写一段 Python，通过 RPC 调用 Hermes 工具：

```python
from hermes_tools import web_search, web_extract
results = web_search("Rust async runtime comparison 2025", limit=5)
# ...过滤、循环、取需要的字段...
print(summary)
```

关键收益：**中间的工具结果根本不进上下文**，只有脚本的 `print()` 回到模型。[[src:code-execution]]

| 资源 | 上限 |
|---|---|
| 超时 | 5 分钟（300s） |
| stdout | 50 KB（超出部分落盘，结果里给路径） |
| 工具调用 | 每次执行 50 次 |
| 可用工具 | `web_search`、`web_extract`、`read_file`、`write_file`、`search_files`、`patch`、`terminal`（仅前台） |

本地后端下每个会话还有一个常驻 Python kernel，变量和已加载的数据在多次调用之间保留；子代理有自己的 kernel，不与主会话共享。[[src:code-execution]]

**环境是清洗过的**：名字里含 `KEY`、`TOKEN`、`SECRET`、`PASSWORD`、`CREDENTIAL`、`PASSWD`、`AUTH` 的环境变量默认不传给脚本，只有 `PATH`、`HOME`、`LANG`、`SHELL`、`PYTHONPATH`、`VIRTUAL_ENV` 这类安全变量通过。[[src:code-execution]]

## 亲手验证

### 验证一：让抓取失败一次

```bash
hermes chat -q "用 web_search 搜 'Hermes Agent Nous Research documentation'，再挑一条结果用 web_extract 抓取正文，告诉我你用了哪些工具、抓到的页面标题是什么" -Q
```

本机真实输出（节选，它自己写的复盘）：

```
1. web_search —— 成功。查询 'Hermes Agent Nous Research documentation'，返回 5 条结果…
2. web_extract —— 失败，共尝试了 3 次，全部被同一个错误拦下：
   "Blocked: URL targets a private or internal network address"
   …连 github.com 这种公网地址都被判成"私有/内网地址"…
   …我没能拿到"抓到的页面标题"——工具没返回 title，三处返回的 title 都是空字符串…
   我如实说明，而不是编一个标题给你。
```

| 你观察到的 | 说明什么 |
|---|---|
| `web_search` 有结果 | 搜索后端是通的 |
| `web_extract` 连公网地址都被判内网 | 这是抓取后端的 SSRF 防护在拦，属于环境问题，不是你的 URL 写错了 |
| 它如实说「没拿到标题」 | 工具真的失败时，它倾向于报失败而不是编一个结果 |

**遇到同一个报错时的替代路径**：用 `web_search` 返回的标题与摘要，或者换 `browser_navigate` 直接开页面 —— 官方对这一类「抓不动」的页面的建议正是改用浏览器工具拿实时 DOM。[[src:web-search]]

### 验证二：确认哪些浏览器工具真的注册了

```bash
hermes tools list | grep -i browser
hermes prompt-size        # Toolsets by size 一节能看到 browser 的 schema 体积
```

本机 `hermes tools list` 里 browser 一行是开着的：

```
  ✓ enabled  browser  🌐 Browser Automation
```

如果哪天 `browser_cdp`、`browser_dialog` 不在工具列表里，那不是坏了 —— 它们要有 CDP 端点才注册。[[src:tools-reference]]
接法在官方 Browser Automation 页：`/browser connect`（或配 `browser.cdp_url`），连上之后所有浏览器工具都在你自己的 Chrome / Brave / Chromium / Edge 实例上操作，而不是另起一个云端浏览器。[[src:browser]]

### 验证三：看一次「中间结果不进上下文」

```bash
hermes chat -q "用 execute_code 分别搜 3 个关键词，每个关键词取前 5 条结果，最后只打印一张汇总表" -Q
```

你应该看到的是**一段汇总**，而不是十几段原始搜索结果 —— 那些中间数据留在脚本进程里，没有进对话上下文。跑完可以问它这次用了多少次工具调用、耗时多少秒（结果里带 `status` / `tool_calls_made` / `duration_seconds`）。[[src:code-execution]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `Blocked: URL targets a private or internal network address` | `web_extract` 的 SSRF 防护拦下了目标 | 用 `web_search` 的标题摘要，或换 `browser_navigate` |
| 需要登录态的页面抓不到 | `web_extract` 是无状态抓取，没有浏览器会话 | 用浏览器工具；登录表单走凭证库流程 |
| `browser_cdp` / `browser_dialog` 不在工具列表里 | 这两个要 CDP 端点才注册 | `/browser connect`，或配 `browser.cdp_url` |
| 一次要跑十几步，上下文被塞满 | 该用脚本而不是连点工具 | 让它用 `execute_code`，只回最后一行 |
| `Script timed out after 300s and was killed.` | 单次执行 5 分钟上限 | 拆成多次；长跑命令改用 `terminal(background=true)` |
| 脚本里读不到自己的 API key | 名字含 KEY/TOKEN/SECRET 的环境变量被清洗 | 在 `terminal.env_passthrough` 里显式加白名单 |
| agent 的终端命令全部超时，自己手动跑没事 | shell rc 在非交互模式下阻塞 | 在 `.bashrc` 顶部加非交互早退 guard |
| 结果里出现 `-9` 或 `137` 这类怪数字 | 命令被信号杀死 | 读结果里的人话注解（会写明可能是 OOM），缩小任务重跑 |
| 在容器后端里跑，危险命令不再弹审批 | 容器被当作安全边界，危险命令检查被跳过 | 确保镜像本身是收紧的；见 [[L50]] |

## 试一试

- [ ] 跑一次「终端 + 文件」组合任务：让它读一个文件、算出统计、把结果写进新文件
- [ ] 用 `hermes chat --toolsets web,terminal` 只给两类工具，观察它怎么绕路完成同一个任务
- [ ] 用 `execute_code` 跑一次批量改名（`.jpeg` → `.jpg`），对比一步步让它改的 token 消耗
- [ ] 打开 `hermes prompt-size`，看 `browser` 这一类工具占多少 schema 字节

## 下一步

- [[L11]] —— 工具集是权限边界，`hermes tools` 是开关
- [[L22]] —— 把多件互不依赖的活派给并行子代理，而不是串着做完
- [[L24]] —— 它动手改文件之前，先把回滚点准备好
- [[L43]] —— 把外部工具通过 MCP 接进来
- 想深入：[[src:tools-reference]]（全部内置工具）、[[src:code-execution]]（脚本执行的限额与安全模型）、[[src:browser]]（浏览器工具全貌与后端选择）、[[src:web-search]]（搜索后端、缓存与抓取限额）

## 出处

- [[src:tools]] Tools & Toolsets — https://hermes-agent.nousresearch.com/docs/user-guide/features/tools
- [[src:tools-reference]] Built-in Tools Reference — https://hermes-agent.nousresearch.com/docs/reference/tools-reference
- [[src:browser]] Browser Automation — https://hermes-agent.nousresearch.com/docs/user-guide/features/browser
- [[src:web-search]] Web Search & Extract — https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search
- [[src:code-execution]] Code Execution — https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution
