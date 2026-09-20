---
id: L00
title: Hermes 是什么：三个心智模型
stage: 0
level: 入门
minutes: 10
prereq: []
tags: [心智模型, agent-loop, 自我改进, 多外壳]
sources: [feat-overview, quickstart, arch]
updated: 2026-09-20
---

# L00 · Hermes 是什么：三个心智模型

> **一句话**：Hermes 是「一个会用工具的循环 + 一套让它越过越强的技能与记忆」，记住这一点，你就比大多数新手起点高。

## 你将学会

- 用一句话说清 Hermes 与「网页版聊天机器人」的本质区别
- 说出 Hermes 自我改进的两个机制，以及它们各自存在磁盘的哪里
- 列举同一个内核的多种外壳，并说明为什么「学内核」比「学界面」划算
- 用两条命令确认自己机器上的版本与安装位置

**前置**：无 · **预计耗时**：10 分钟

## 先动手

打开终端：**Windows 用 Git Bash**（开始菜单搜 `Git Bash`），macOS / Linux 用系统终端。
本教程所有命令都是 bash 语法，PowerShell / cmd 里跑不了 —— 第 1 条常见坑就是这种报错。

```bash
hermes --version
hermes --help | head -40
```

> **暂时不想装 Git Bash？** 把管道那一段换成 PowerShell 的写法也能跑
> （`Select-Object -First N`、`Select-String` 本机 PowerShell 实测可用；`cmd` 没有对应的轻量写法，用 Git Bash）：

```powershell
hermes --version
hermes --help | Select-Object -First 40
```

记住这一条替换就够了：`| head -N` → `| Select-Object -First N`。本教程后面的命令都按 bash 写，
留在 PowerShell 的话按「常见坑」第 1 行的对照表逐个换。

你应该看到（我在 hermes v0.21.3 上跑出来的真实输出）：

```
Hermes Agent v0.21.3 (2026.9.14) · upstream 05fac10a
Install directory: C:\Users\28189\AppData\Local\hermes\hermes-agent
Install method: git
Python: 3.11.15
OpenAI SDK: 2.24.0
```

`hermes --help` 的开头长这样（本机 v0.21.3 共 223 行；`| head -40` 只截前 40 行 —— 这就是管道的作用）：

```
usage: hermes [-h] [--version] [-z PROMPT] [--usage-file PATH] [-m MODEL]
              [--provider PROVIDER] [--reasoning LEVEL] [-t TOOLSETS]
              [--resume SESSION] [--no-restore-cwd] [--in DIR]
              [--continue [SESSION_NAME]] [--worktree] [--accept-hooks]
              [--skills SKILLS] [--yolo] [--pass-session-id]
              [--ignore-user-config] [--ignore-rules] [--safe-mode] [--tui]
              [--cli] [--dev]
              <command> ...

Hermes Agent - AI assistant with tool-calling capabilities

positional arguments:
  <command>             Command to run
    chat                Interactive chat with the agent
    model               Select default model and provider
    moa                 Configure Mixture of Agents provider/model slots
```

**注意第二行**：`Install directory` 里有 `hermes-agent` 这个 git 检出。
你后面读的官方文档、源码、示例，都来自这个目录 —— 这是「可考证」的底气所在。

## 原理

### 模型一：它不是聊天框，是「会用工具的循环」

普通聊天机器人：你问 → 它答。一轮结束。

Hermes：你问 → **它自己决定要不要调用工具**（读文件、跑命令、搜网页）→
拿到结果 → 塞回上下文 → 再想下一步 → 直到它认为任务完成，才把最终答复给你。

```
你的话 ──► 组装上下文 ──► 模型思考 ──┬──► 只说话 ──► 给你答复
                                    │
                                    └──► 要工具 ──► 执行工具 ──► 结果回填 ──┐
                                                                          │
                                              ◄───────────────────────────┘
                                                     （再来一轮）
```

这个循环由 `AIAgent` 驱动，官方叫它 **agent loop**：

```text
run_conversation()
  1. 记录你的消息
  2. 组装/复用系统提示（缓存优先）
  3. 判断是否需要压缩上下文
  4. 组装 API 消息
  5. 发起可中断的 API 调用
  6. 解析响应：
     - 有工具调用 → 执行、回填结果、回到第 4 步
     - 是文字回复 → 落盘会话、必要时刷记忆、返回
```

**这个模型最重要的推论**：循环能跑多少步，取决于它能不能**自己验证**结果。
所以「让它自己检查一下」这类话，对它不是客套，而是加速器。[[src:arch]]

### 模型二：让它变强的不是换模型，是「技能 + 记忆」

| 机制 | 是什么 | 存在哪 | 谁写 |
|---|---|---|---|
| **技能 Skills** | 按需加载的操作说明书（一个 `SKILL.md`） | `$HERMES_HOME/skills/` | 你，或 agent 自己写 |
| **记忆 Memory** | 跨会话保留的事实：你的偏好、环境、踩过的坑 | `$HERMES_HOME/memories/` | agent 自己写（`memory` 工具） |

技能的加载方式是**渐进式披露**：会话开始时只把「名字 + 一句话描述」放进上下文，
真正用到才读全文。所以装 50 个技能不会拖垮每一轮对话。[[src:feat-overview]]

**这就意味着你的最优投资方向不是「换更贵的模型」，而是**：
把重复交代的事情写成技能，把长期有效的事实交给记忆。L13 / L15 会各讲一课。

### 模型三：一个内核，多种外壳

| 外壳 | 命令 | 典型场景 |
|---|---|---|
| 经典 CLI | `hermes` | 终端里直接聊 |
| Ink TUI | `hermes --tui` | 鼠标选择、弹层、非阻塞输入 |
| 桌面 App | `hermes desktop` | 图形界面、流式工具输出、语音 |
| Web 面板 | `hermes dashboard` | 管理配置/密钥/定时任务 |
| 消息平台机器人 | `hermes gateway run` | Telegram / Discord / Slack / 飞书 … |
| IDE（ACP） | `hermes acp` | VS Code / Zed / JetBrains 内使用 |
| OpenAI 兼容 API | `hermes proxy` / `hermes api-server` | 让别的程序用你的模型额度 |

**它们共享同一份会话、技能、记忆、配置**。所以你在 Telegram 里养出来的技能，
在桌面 App 里立刻可用。学会内核 = 学会全部外壳；只学界面 = 换个平台就得重学。[[src:feat-overview]]

## 亲手验证

上面的「一个内核多种外壳」是可以当场证伪/证实的 —— 看这些外壳是不是真的在**同一个命令**里：

```bash
hermes --help | grep -E "desktop|dashboard|proxy|acp|gateway|tui"
# PowerShell 等价写法：hermes --help | Select-String "desktop|dashboard|proxy|acp|gateway|tui"
```

预期：你会看到 `desktop`、`dashboard`、`proxy`、`acp`、`gateway` 全是**同一个
`hermes` 命令的子命令**，而不是需要另外安装的工具。

再验证「你的安装目录确实是一份 git 检出」（后面所有引用都指向它）：

```bash
cd "$HERMES_HOME/hermes-agent" && git log -1 --format="%h %ci"
```

| 你观察到的 | 说明什么 |
|---|---|
| 同一个 `hermes` 下有全部外壳 | 它们共享内核；学内核的投入不会因为换界面而作废 |
| 安装目录是一条 git 历史 | 官方文档/源码可被本地核对 → 教程的「可考证出处」才成立 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `head : 无法将“head”项识别为 cmdlet、函数、脚本文件或可运行程序的名称`（`grep`、`wc` 同理） | 在 **PowerShell / cmd** 里跑了本教程的 bash 管道 —— `head`、`grep`、`wc` 都是 Git Bash 自带的外部命令，PowerShell 里不存在 | 换到 **Git Bash** 里跑（推荐，本教程全程用 bash）；非要留在 PowerShell 就把管道换掉：`| head -40` → `| Select-Object -First 40`，`| grep -E "a|b"` → `| Select-String "a|b"`；数行（`| wc -l`）没有同口径的替代，回 Git Bash 数 |
| `hermes: command not found` | 安装后没重载 shell | `source ~/.bashrc`（zsh 用 `~/.zshrc`）；Windows 重开 Git Bash |
| 以为「换到桌面 App 就是另一个产品」 | 把外壳当内核 | 记住模型三：会话/技能/记忆是共享的 |
| 以为装很多技能会拖慢对话 | 不了解渐进式披露 | 技能只在被用到时读全文，装多了不心疼 |
| 找不到 `$HERMES_HOME` 到底在哪 | 用了自定义 profile | `hermes config path` 与 `hermes config env-path` 会告诉你确切位置 |

## 试一试

- [ ] 跑一遍 `hermes --version`，把版本号和你安装目录记到 `journal/` 里（后面排查问题时用得上）
- [ ] 跑一遍 `hermes --help`，挑一个你没见过的子命令，给它加 `--help` 看看它能做什么
- [ ] 用自己的话说一遍「agent loop」，写进 `journal/`，然后对照本节原理检查漏了什么

## 下一步

- [[L01]] —— 还没装好的话先装；已装好的话直接跳到「第一次对话」
- [[L02]] —— 把本节模型一（循环）拆到命令级别，看清每一轮到底发了什么
- [[L03]] —— 把模型二落成一张「哪个文件管什么」的地图

## 出处

- [[src:feat-overview]] Features Overview — https://hermes-agent.nousresearch.com/docs/user-guide/features/overview
- [[src:quickstart]] Hermes Agent Quickstart — https://hermes-agent.nousresearch.com/docs/getting-started/quickstart
- [[src:arch]] Architecture — https://hermes-agent.nousresearch.com/docs/developer-guide/architecture
