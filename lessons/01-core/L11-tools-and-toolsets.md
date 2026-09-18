---
id: L11
title: 工具与工具集：它到底能做什么
stage: 1
level: 入门
minutes: 20
prereq: [L02, L10]
tags: [工具, toolset, 权限边界, 终端后端]
sources: [tools, toolsets-reference, tools-reference]
updated: 2026-09-16
---

# L11 · 工具与工具集：它到底能做什么

> **一句话**：工具是它的手，工具集（toolset）是给这双手划的权限范围 —— 这两件事分开之后，你就能精确控制「它能碰什么」。

## 你将学会

- 按用途说出 Hermes 的六大类工具，并指出哪些属于「会改变你系统」的高危类别
- 用 `hermes tools` 查看与开关工具集，用 `--toolsets` 临时限制某一次运行
- 亲手做一次实验：关掉工具集，看它如何诚实地承认「我做不到」
- 说出终端后端（local / docker / ssh …）的区别，并知道什么时候必须换后端

**前置**：[[L02]]、[[L10]] · **预计耗时**：20 分钟

## 先动手

```bash
hermes tools list              # 看本机工具集开关状态（✓ / ✗）
hermes tools                   # 交互式开关（curses 界面）
```

本机真实输出（节选）：

```
Built-in toolsets (cli):
  ✓ enabled  web  🔍 Web Search & Scraping
  ✓ enabled  browser  🌐 Browser Automation
  ✓ enabled  terminal  💻 Terminal & Processes
  ✓ enabled  file  📁 File Operations
  ✓ enabled  code_execution  ⚡ Code Execution
  ✗ disabled  video  🎬 Video Analysis
  ✓ enabled  skills  📚 Skills
  ✓ enabled  memory  💾 Memory
  ✓ enabled  delegation  👥 Task Delegation
  ✓ enabled  cronjob  ⏰ Cron Jobs
  ...
```

**第一眼要建立的认知**：`terminal`、`file`、`browser` 这些开着的，意味着它在你机器上
**有真实的动手能力**。这不是模拟。

## 原理

### 工具的分类地图

| 类别 | 代表工具 | 说明 |
|---|---|---|
| **Web** | `web_search`、`web_extract` | 搜索并抽取网页内容 |
| **X Search** | `x_search` | 搜 X（Twitter）帖子，依赖 xAI 凭证，**默认关闭** |
| **Terminal & Files** | `terminal`、`process`、`read_file`、`patch` | 执行命令、操作文件 —— **高危区** |
| **Browser** | `browser_navigate`、`browser_snapshot`、`browser_vision` | 交互式浏览器自动化，支持文本与视觉 |
| **Media** | `vision_analyze`、`image_generate`、`text_to_speech` | 多模态分析与生成 |
| **Agent 编排** | `todo`、`clarify`、`execute_code`、`delegate_task` | 规划、反问、代码执行、派子代理 |
| **记忆与检索** | `memory`、`session_search` | 持久记忆与历史会话检索 |
| **自动化** | `cronjob` | 定时任务（create/list/update/pause/resume/run/remove） |
| **集成** | `ha_*`、MCP 工具 | Home Assistant、MCP 服务器等 |

权威清单不在文档里，而在代码里：`hermes tools list` 与官方
[Built-in Tools Reference](https://hermes-agent.nousresearch.com/docs/reference/tools-reference)。[[src:tools]]

### 工具集（toolset）是权限边界

常用的工具集名字（可以直接用于 `--toolsets`）：

```
web  search  terminal  file  browser  vision  image_gen  skills  tts  todo
memory  session_search  cronjob  code_execution  delegation  clarify
homeassistant  messaging  spotify  discord  discord_admin  debugging  safe
```

三种用法：

```bash
# ① 看清单
hermes tools

# ② 按平台配置（交互式）
hermes tools

# ③ 只给某一次运行开特定工具集
hermes chat --toolsets "web,terminal"
```

**最小权限原则的实操**：让 agent 只做研究时，就只给 `web`；
要它改代码时才给 `file` + `terminal`。工具集是**按平台**生效的
（CLI / Telegram / Discord 各配一套），所以你可以让手机上的机器人权限收窄、
桌面上的权限放开。[[src:tools]]

### 终端后端：它到底在哪执行命令

`terminal` 这个工具的执行位置是可换的，这是安全与可复现性的关键：

| 后端 | 说明 | 适用 |
|---|---|---|
| `local` | 直接跑在你的机器上（默认） | 开发、可信任务 |
| `docker` | 隔离容器 | 安全、可复现 |
| `ssh` | 远程服务器 | 沙箱化，把 agent 挡在自己的代码之外 |
| `singularity` | HPC 容器 | 集群计算、无 root |
| `modal` | 云端执行 | 无服务器、弹性 |
| `daytona` | 云沙箱工作区 | 持久远程开发环境 |
| `vercel_sandbox` | Vercel 云 microVM | 带快照持久化的云执行 |

配置方式：

```bash
hermes config set terminal.backend docker
hermes config set terminal.backend ssh
```

**判据**：如果你不敢让一个陌生助手在你主力机器上敲命令，那就换成 `docker` 或 `ssh`。[[src:tools]]

### 两个值得知道的结果注解

这些细节在你看 agent 执行记录时会用到：[[src:tools]]

| 场景 | 行为 |
|---|---|
| 命令被信号杀死 | 结果里带人话解释：`-9` / `137` → "terminated by signal 9: SIGKILL — often the kernel OOM killer…"，段错误、SIGTERM、管道断裂同样被标注 |
| 读到 UTF-16 文本文件 | **自动转码成 UTF-8 展示**（Windows 记事本、PowerShell `>` 重定向的常见格式），而不是当成二进制拒绝；`patch`/`write_file` 回写时按 UTF-8 编码 |

## 亲手验证

### 验证一：工具集真的是硬边界（本机实测）

```bash
hermes chat -q "用终端命令看一下当前目录有哪些文件" --toolsets web
```

本机真实输出：

```
如果你需要查看当前目录文件，可以自己在终端里运行：

ls -la
```

**注意它做了什么**：它**没有**编一个假的目录列表，而是告诉你它没有这个能力。
再跑一次不加限制的版本对比：

```bash
hermes chat -q "用终端命令看一下当前目录有哪些文件"
```

| 你观察到的 | 说明什么 |
|---|---|
| 限制后它承认做不到 | 工具集是硬开关，不是提示词建议 |
| 不限制时它直接执行 | 工具是真的在你的机器上跑 |
| 它没有幻觉出结果 | 工具缺失时模型倾向于放弃而非编造（前提是提示里没逼它「必须回答」） |

### 验证二：确认工具集与平台绑定

```bash
hermes tools list                 # 看 cli 平台的开关
hermes config get platform_toolsets
```

| 你观察到的 | 说明什么 |
|---|---|
| 配置按平台分节 | 你可以让手机端的机器人权限收窄 |
| Blank Slate 模式会写显式白名单 | 那次安装选过什么，升级后依然是什么 |

### 验证三：找出你机器上的高危开关

```bash
hermes tools list | grep -E "terminal|computer_use|code_execution"
```

如果这三项都开着你又不需要，就在 `hermes tools` 里关掉 —— 这是投入产出比最高的安全动作。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 「它说没有能力做某事」 | 该工具集被关了 | `hermes tools` 打开，或本次用 `--toolsets` 加上 |
| 装了 MCP 但工具不出现 | MCP 工具集需按服务器名动态加入 | 见 [[L43]]，用 `mcp-<server>` 工具集 |
| 让 agent 在自己主力机器上乱跑 | 用默认 `terminal.backend: local` | 换 `docker` / `ssh`，或收窄工具集 |
| 被 OOM 杀掉的命令看起来像神秘失败 | 没注意结果里的信号说明 | 读结果里的文字注解（会直接告诉你可能是 OOM） |
| Windows 上读文件报「二进制」 | 文件是 UTF-16 | 现代 Hermes 会自动转码；若仍失败，手动转成 UTF-8 |
| 中途改工具集 | 会破坏系统提示的字节稳定性 → 缓存失效 | 改完重开会话；别在长会话中途改 |

## 试一试

- [ ] 跑一次 `hermes chat --toolsets web -q "列出我 Home 目录下的文件"`，记录它的反应
- [ ] 用 `hermes tools` 关掉一个你从不用的工具集，跑一次任务，观察有什么变化
- [ ] 数一数本机开着多少个工具集，写下其中三个你「宁愿关掉」的及理由
- [ ] 判断一个问题：如果你要让 agent 帮你做代码审查但绝不希望它改文件，该怎么配工具集？

## 下一步

- [[L12]] —— 会话与斜杠命令：把「一次对话」当成可管理的对象
- [[L21]] —— 把工具用出组合拳：终端 / 文件 / 浏览器怎么串起来干活
- [[L43]] —— MCP：不写代码就把外部工具接进来
- 想深入：[[src:toolsets-reference]]（全部工具集与平台预设）

## 出处

- [[src:tools]] Tools & Toolsets — https://hermes-agent.nousresearch.com/docs/user-guide/features/tools
- [[src:toolsets-reference]] Toolsets Reference — https://hermes-agent.nousresearch.com/docs/reference/toolsets-reference
- [[src:tools-reference]] Built-in Tools Reference — https://hermes-agent.nousresearch.com/docs/reference/tools-reference
