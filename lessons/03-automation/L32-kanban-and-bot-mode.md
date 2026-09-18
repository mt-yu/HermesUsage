---
id: L32
title: "多代理：kanban 看板与 bot mode"
stage: 3
level: 进阶
minutes: 25
prereq: [L22, L23]
tags: ["kanban", "多代理", "profiles", "bot mode"]
sources: [kanban, bot-mode, profiles]
updated: 2026-09-17
---

# L32 · 多代理：kanban 看板与 bot mode

> **一句话**：kanban 是一张存在 SQLite 里的任务队列，每个任务派给一个 profile 当 worker；bot mode 是同一批 profile 的图形外壳，让它们有名字、有群聊、能互相发消息。

## 你将学会

- 说出 kanban 与 `delegate_task` 的分工，判断一个任务该走哪条路
- 亲手建板、建任务，并用 `hermes kanban dispatch --dry-run` 看出哪些任务永远不会被认领
- 说出一个 Bot 在磁盘上到底是什么（就是 profile），以及它的 Routines 落在哪个文件里
- 认出「把任务派给不存在的 profile」「scratch 工作区完成任务后被删掉」这两个坑

**前置**：[[L22]]、[[L23]] · **预计耗时**：25 分钟

## 先动手

```bash
hermes profile list
```

本机真实输出（一台只装了默认 profile 的机器）：

```
 Profile          Model                        Gateway      Alias        Distribution
 ───────────────    ───────────────────────────    ───────────    ───────────    ────────────────────
 ◆default         deepseek-v4-pro              stopped      —            —
```

接着建板、建任务：

```bash
hermes kanban list        # 还没 init 的话
hermes kanban init
hermes kanban create "写一份本周依赖更新摘要" --assignee default
hermes kanban list
```

本机真实输出（顺序同上）：

```
kanban: could not initialize database: unable to open database file

Kanban DB initialized at <HERMES_HOME>\kanban.db

Discovered 1 profile(s) on disk; any of these can be an --assignee:
  default

Next step: start the gateway so ready tasks actually get picked up.
  hermes gateway start

The gateway hosts an embedded dispatcher that ticks every 60 seconds
by default (config: kanban.dispatch_interval_seconds). Without a
running gateway, tasks stay in 'ready' forever.

⚠  No gateway is running — the task will sit in 'ready' until you start it. Run:
    hermes gateway start
Created t_e7acbd8d  (ready, assignee=default)

▶ t_e7acbd8d  ready     default               写一份本周依赖更新摘要
```

任务 id 是随机生成的，所以你的会是 `t_` 开头的另一串字符。[[src:kanban]]

## 原理

### 看板上的六个概念

| 概念 | 是什么 |
|---|---|
| **Board** | 一条独立的队列，有自己的 SQLite 库、workspaces 目录和调度循环；一台机器可以有多个板（一个项目一个板） |
| **Task** | 一行记录：标题、正文、一个 assignee（profile 名）、状态 |
| **Status** | `triage` / `todo` / `ready` / `running` / `blocked` / `review` / `done` / `archived` |
| **Link** | 父 → 子依赖；所有父任务 `done` 之后，调度器把子任务从 `todo` 提到 `ready` |
| **Comment** | 代理之间的协议：worker 被（重新）拉起时会读到完整评论串 |
| **Workspace** | worker 干活用的目录，三种：`scratch`、`dir:<绝对路径>`、`worktree` |

工作区三种类型的行为差别很大，值得单独记住：

- `scratch`（默认）是 `~/.hermes/kanban/workspaces/<id>/` 下的临时目录，**任务完成时会被删掉**；
  只有通过 `kanban_complete(artifacts=[...])` 显式声明的东西会被复制到持久的附件存储里。
- `dir:<path>` 必须写**绝对路径**（相对路径在派发阶段就被拒绝），完成后保留。
- `worktree` 是在 `.worktrees/<id>/` 下建的 git worktree，完成后保留，适合写代码的任务。[[src:kanban]]

### kanban 与 `delegate_task` 不是一回事

| | `delegate_task` | Kanban |
|---|---|---|
| 形态 | RPC 调用（fork → join） | 持久消息队列 + 状态机 |
| 父方 | 阻塞等子代理返回 | `create` 之后就不管了 |
| 子方身份 | 匿名子代理 | 有名字的 profile，带持久记忆 |
| 可恢复性 | 没有 —— 失败就是失败 | 可 block → unblock → 重跑；崩了可回收 |
| 人在环路 | 不支持 | 任何时候都能评论/解阻 |
| 审计 | 上下文压缩后就没了 | SQLite 里的行永久保留 |

一句话区分：`delegate_task` 是一次函数调用，kanban 是一张任何 profile（或人）都能看、能改的工作队列。
两者可以共存 —— 一个 kanban worker 在自己的运行里照样能调 `delegate_task`。[[src:kanban]]

### worker 用的是工具，不是 CLI

调度器拉起 worker 时会在子进程环境里设 `HERMES_KANBAN_TASK=t_xxxx`，这个变量打开模型 schema 里的
一套 **kanban 工具集**。worker 从头到尾不会去 shell 里敲 `hermes kanban`。[[src:kanban]]

| 工具 | 用途 |
|---|---|
| `kanban_show` | 读自己的任务（标题、正文、历史尝试、父任务交接、评论、`worker_context`） |
| `kanban_list` | 列任务摘要，给编排者用 |
| `kanban_complete` | 带 `summary` + `metadata` 的收尾交接 |
| `kanban_request_review` | 发起同卡评审，任务进 `review` |
| `kanban_request_changes` | 评审否决，把任务退回原实现者 |

同一个工具集也可以给"编排者" profile 显式开启：

```bash
hermes -p planner tools enable kanban                      # CLI / TUI / Desktop 会话
hermes -p planner tools enable kanban --platform telegram  # 某个网关平台
```

改完要开新会话，已存在的会话保留旧的工具 schema 与提示缓存。[[src:kanban]]

### 调度器住在网关里

默认 `kanban.dispatch_in_gateway: true`，调度器跑在网关进程内，每 60 秒（`kanban.dispatch_interval_seconds`）
扫一遍所有板：回收过期认领、回收崩掉的 worker、提升 `ready`、原子认领、拉起对应的 profile。
网关不在跑，`ready` 任务就一直原地待着 —— 这也是 `hermes kanban create` 会当场提醒你的原因。[[src:kanban]]

分配错了也有兜底：同一个任务连续派发失败到 `kanban.failure_limit` 次（默认 2）之后，
调度器自动把它 block 掉并写上最后一次的错误，避免对着一个不存在的 profile 反复重试。[[src:kanban]]

### boards：多项目的硬隔离

```bash
hermes kanban boards list
hermes kanban boards create atm10-server --name "ATM10 Server" --switch
hermes kanban --board atm10-server list
```

本机真实输出（`boards list`）：

```
    SLUG                      NAME                          COUNTS
●   default                   Default                       (empty)

Current board: default
```

每个板一个 SQLite 库、一套 workspaces 目录和日志目录；worker 只看得到自己那个板
（调度器给它设了 `HERMES_KANBAN_BOARD`）。跨板 link 是不允许的。[[src:kanban]]

### Bot Mode：profile 的图形外壳

关键事实只要记住一句：**一个 Bot 就是一个 profile**，隔离的 config、记忆、技能、凭证、会话历史都在
`~/.hermes/profiles/<name>/` 下。Bot Mode 是桌面端给这个原语套的界面，不是新东西。[[src:bot-mode]]

| 在 Bot Mode 里 | 对应的命令行/文件 |
|---|---|
| 跟某个 Bot 聊天 | `hermes -p <bot> chat` |
| 这个 Bot 的文件、技能、记忆 | `~/.hermes/profiles/<bot>/` |
| Routines（例行任务） | `hermes cron list`，任务名长这样：`[bot:<name>] <routine>` |
| 建 / 看 profile | `hermes profile create`、`hermes profile list` |

三点容易踩的细节：[[src:bot-mode]]

- 每个 Bot 有一个常驻的 **Bot Chat**；在里面敲 `/new` 会被改写成 `/compact`（换新工作上下文、
  不换对话），因为「把关系 fork 成一次性会话」正是 Bot Mode 承诺不发生的。
- **群聊**是 2–6 个 Bot 一间房，你发一条消息最多触发 **3 轮串行**成员发言；@谁谁答，
  没人被 @ 时大家都答；房间有硬上限（单次最多 10 条消息、3 轮）。
- Bot 之间用 `message_agent` 互相发消息。这个工具要**同时**满足两件事才出现：① 会话标题
  **恰好**是 `Bot Chat` —— 普通会话、群聊成员会话、CLI 会话都拿不到；② 这台安装是
  **Bot-Mode-managed**，也就是**任意一个** profile 的 `profile.yaml` 里带 `ui_meta` 下的
  `hermes-bots` 块（建 Bot 的桌面端会替你写下它）。所以在**没装桌面端的机器**上（纯 gateway
  或纯 CLI），即使 `agent.bot_mode_protocol` 是开着的，这个工具也不会出现；要手工补齐这两件事：
  `hermes -p <bot> chat -c "Bot Chat" --create-if-missing` 建出规范会话，再往该 profile 的
  `profile.yaml` 写一行 `ui_meta: {hermes-bots: {}}`（空块就够，标记的是整台安装）。
  发送是 fire-and-forget：对方稍后作为后台完成通知把回复送回来。

本地同时活着几个 Bot 是有上限的：Settings → Advanced → **Warm Bot Backends**，默认 3 个，
闲置的按超时回收（默认 10 分钟）。要是你在跑大编制（成员多的群聊、跨很多 profile 的 kanban 派发），
就得把这个数字调大，并给机器配上对应的内存。[[src:bot-mode]]

### profile 是这里的地基

- 一个 profile = 一个独立的 Hermes 家目录：自己的 `config.yaml`、`.env`、`SOUL.md`、记忆、会话、技能、cron、状态库。[[src:profiles]]
- 建完 profile 会**自动获得同名命令**：`hermes profile create coder` 之后就有 `coder chat`、`coder setup`、`coder gateway start`。[[src:profiles]]
- **绝对不要让两个 agent 进程指向同一个 profile**：两边都会自动写记忆，又都在会话开始时把对方的写入读进系统提示，状态会互相叠加到面目全非。需要共享记忆应该用外部记忆 provider。[[src:profiles]]
- 打算拿它当 kanban worker 的话，建的时候带 `--description "<角色>"`，编排器才知道它擅长什么：
  `hermes profile create researcher --description "读源码和外部文档，写结论。"`[[src:profiles]]

## 亲手验证

### 验证一：把一个任务派给根本不存在的 profile

```bash
hermes kanban create "给不存在的 profile 派活" --assignee ghost
```

本机真实输出：

```
Created t_48f63a65  (ready, assignee=ghost)
```

**它照样建出来了，不报错** —— 然后：

```bash
hermes kanban dispatch --dry-run
```

本机真实输出：

```
Reclaimed:    0
Crashed:      0
Timed out:    0
Stale:        0
Auto-blocked: 0
Promoted:     0
Spawned:      1
  - t_e7acbd8d  ->  default  @ - (dry)
Skipped (non-spawnable assignee — terminal lane, OK): t_48f63a65
```

`t_48f63a65` 落进了 `non-spawnable assignee` 桶里，永远不会被拉起。
上线前用 `--dry-run` 过一遍，比等两个小时看它没动要快得多。写错 profile 名的任务是"建成功但永不运行"的。[[src:kanban]]

### 验证二：先看谁真的在磁盘上

```bash
hermes kanban assignees
```

本机真实输出：

```
NAME                  ON DISK   COUNTS
default               yes       ready=1
```

再 `hermes profile list` 对一遍，两处都对得上才说明 assignee 是有效的。[[src:kanban]] [[src:profiles]]

### 验证三：没有网关，任务不会动

```bash
hermes gateway status
hermes kanban stats
```

`hermes gateway status` 会告诉你 `✗ Gateway is not running`；`hermes kanban stats` 只统计到
`ready`，没有任何 `running`。调度器住在网关里，这是设计，不是故障。[[src:kanban]]

### 验证四：tasks 的状态可以从 CLI 直接看

```bash
hermes kanban show t_e7acbd8d
```

本机真实输出：

```
Task t_e7acbd8d: 写一份本周依赖更新摘要
  status:    ready
  assignee:  default
  workspace: scratch
  max-retries: 2 (default)
  created:   2026-09-16 10:58 by user
```

`workspace: scratch` —— 记住这一行：这个任务一旦 `complete`，它的临时工作目录就被删了，
只有用 `kanban_complete(artifacts=[...])` 声明过的文件才会被留下来。[[src:kanban]]

| 你观察到的 | 说明什么 |
|---|---|
| `--assignee ghost` 建卡成功 | 建卡不校验 profile 是否存在，派发时才暴露 |
| `dispatch --dry-run` 报 `non-spawnable assignee` | 这张卡永远不会运行；dry-run 是上线前的体检 |
| 没有网关时状态停在 `ready` | 调度器是网关的一个循环，不是独立服务 |
| `workspace: scratch` | 默认工作区是临时的，完成即回收 |
| `hermes profile list` 里只有 `default` | 一台机器可以有任意多个 profile，但每个 bot token 只能属于一个 profile |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `kanban: could not initialize database: unable to open database file` | 还没建库 | `hermes kanban init` |
| 任务建好了，几小时都没动 | 网关没跑（调度器住在网关里） | `hermes gateway start`，或前台 `hermes gateway` |
| 卡在 `ready` 不动，`dispatch --dry-run` 说 `non-spawnable assignee` | assignee 写了一个不存在的 profile | `hermes kanban assignees` 查真实名字，`hermes kanban reassign <id> <profile>` |
| 任务跑完了，产出的文件找不到了 | 默认 `scratch` 工作区在完成任务时被删除 | 完成时用 `kanban_complete(artifacts=[...])` 声明；或一开始就用 `--workspace dir:/abs/path` |
| 两个 Bot 抢同一套记忆/配置，行为越来越怪 | 两个 agent 进程指向了同一个 profile | 一 agent 一 profile；共享记忆用外部 provider |
| 克隆 profile 后两个 bot 互相抢消息 | 克隆默认**不**带消息渠道，但用 `--clone-channels` 会共享同一份 token | 别给两个 profile 配同一个 bot token；新 profile 单独 `setup` |
| 复制一份 profile 当备份，结果 cron 跑了两遍 | `--clone-all` 不克隆 cron（会重复执行），但 `hermes profile export` / `hermes backup` 是另一回事 | 备份用 `hermes backup`，不要指望 clone 带走定时任务 |
| 群聊里所有 Bot 都在抢话 | 没被 @ 时全员都会答 | `@具体名字` 把这一轮限定到该成员 |
| Bot 在群聊里回了空消息 | 它以 `[SILENT]` / `NO_REPLY` 这类静默 token 收尾 | 这是刻意的：沉默是投递决策，turn 仍留在记录里 |
| Kanban 卡片被反复 unblock 后进了 `triage` | 同一原因 re-block 到 `BLOCK_RECURRENCE_LIMIT`（默认 2）次，熔断器介入 | 先解决它为什么反复 block，再 unblock |

## 试一试

- [ ] 用 `hermes kanban boards create demo --name "Demo" --switch` 建第二个板，把同一个任务在两个板上各建一次，确认 `hermes kanban --board default list` 看不到对方的任务
- [ ] 建两个任务，用 `hermes kanban link <父> <子>` 连起来，观察子任务在父任务 `complete` 之前一直停在 `todo`
- [ ] 给一张卡加 `--idempotency-key "nightly-ops-$(date -u +%Y-%m-%d)"`，连续建两次，确认第二次返回的是同一个任务 id
- [ ] 用 `hermes kanban --help` 找出 `heartbeat`、`tail`、`runs` 三个子命令，说出各自在长任务排查里看什么
- [ ] 把这一课的实验（包括 `dispatch --dry-run` 的输出）记进 `journal/` 并提交

## 下一步

- [[L33]] —— 网关是把这些零件托起来的运行环境
- [[L34]] —— 用 cron 定时往看板上投放任务，做成无人值守的产线
- [[L51]] —— 一个 profile 一套密钥与凭证：多 profile 的正确隔离方式
- 想深入：[[src:kanban]] 的 Worker lifecycle 与 Multi-tenant usage 两节

## 出处

- [[src:kanban]] Kanban (Multi-Agent Board) — https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- [[src:bot-mode]] Bot Mode — https://hermes-agent.nousresearch.com/docs/user-guide/bot-mode
- [[src:profiles]] Profiles: Running Multiple Agents — https://hermes-agent.nousresearch.com/docs/user-guide/profiles
