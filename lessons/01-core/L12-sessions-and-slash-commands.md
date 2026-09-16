---
id: L12
title: 会话与斜杠命令：一次对话的边界
stage: 1
level: 入门
minutes: 20
prereq: [L02, L11]
tags: [会话, 斜杠命令, 上下文, state.db]
sources: [sessions, slash-commands, cli]
updated: 2026-09-16
---

# L12 · 会话与斜杠命令：一次对话的边界

> **一句话**：会话不是一个窗口，而是一条**会被永久保存、会花钱、需要你主动收尾**的记录线；斜杠命令就是你操作这条线的方向盘。

## 你将学会

- 说清会话存在哪、存了什么，以及「上下文里到底有什么」的准确答案
- 用 `/status`、`/context` 自查当前会话的健康度与上下文构成
- 用 `/new`、`/compress`、`/resume` 管理会话生命周期，并知道该在什么时候用哪个
- 说出「上下文膨胀」最常见的真实原因，并据此改掉自己的用法

**前置**：L02、L11 · **预计耗时**：20 分钟

## 先动手

在交互界面里（`hermes` 或 `hermes --tui`）依次敲：

```
/status        ← 这个会话是什么状态
/context       ← 上下文窗口都被谁吃掉了
```

`/status` 会告出：模型、provider、profile、session ID、工作目录、标题、创建/更新时间、
token 总量、agent 是否在跑，然后附一段**本地计算的 Session recap**（最近几轮对话数、
工具结果数、最常用工具、最近碰过的文件、最近一次提问与回复）——
且不花一次 LLM 调用。[[src:slash-commands]]

`/context` 会给你一张上下文构成表：系统提示、工具定义、规则、技能索引、MCP、子代理、
记忆、对话各占多少，以及**每个上下文文件的加载情况**（`.hermes.md` / `AGENTS.md` /
CLAUDE.md / `.cursorrules` / `SOUL.md` 各自多少 token、是否加载、是否被截断、
是否被更高优先级类型遮蔽、是否被安全扫描拦下）。这是回答「我的规则文件为什么没生效」
的官方手段。[[src:slash-commands]]

## 原理

### 会话存在哪、有什么

每个会话都被自动保存 —— 无论来自 CLI、Telegram、Discord、Slack 还是别的平台：

**SQLite 数据库 `~/.hermes/state.db`**，内含结构化元数据 + FTS5 全文检索 + 完整消息历史。[[src:sessions]]

| 存储内容 | 例子 |
|---|---|
| 会话 ID、来源平台、用户 ID | `20260916_104434_f54b89` / `cli` |
| 会话标题（唯一、人类可读） | 「Hermes agent 初学者教程与 Git 工作流」 |
| 模型名与配置、系统提示快照 | 用于复盘「当时到底用了什么」 |
| 完整消息历史（角色、内容、工具调用、工具结果） | 本教程 [[L02]] 就是靠它做验证 |
| token 计数、时间戳 | `input_tokens` / `output_tokens` / `started_at` |
| 父会话 ID | 压缩触发的会话分裂 |

> **本机实测的坑**：Windows 上 `$HERMES_HOME/sessions/` 目录是**空的** ——
> 真相在 `state.db` 里。找不到 jsonl 不代表会话没存。

### 「上下文里到底有什么」的准确答案

Hermes 存着全部历史，但**并不是每轮都把用过的每个字节再发一遍**。每一轮模型看到的只有：[[src:sessions]]

1. 选定的系统提示
2. 当前对话窗口
3. 这一轮 Hermes 显式注入的内容

**媒体附件是按轮处理的**：

| 类型 | 处理方式 |
|---|---|
| 图片 | 原生附到下一条模型调用；当前模型不支持视觉时，先转成文字描述 |
| 音频 | 配置了语音转文字时，转成文本 |
| 文本文档 | 抽取的文本可以被包含；其他文档类型通常只留一个本地路径 + 简短说明 |

所以：**原始的图片/音频/二进制字节不会被反复复制进未来的提示**。
你发一张图让它做表情包，下一轮不会再把原图带着走。[[src:sessions]]

### 上下文膨胀的真实原因

> 最常见的原因不是媒体文件，而是**啰嗦的文本**：粘贴的完整日志、大段 transcript、
> 巨型工具输出、长 diff、反复的状态汇报、详细的证据堆。

**替代做法**：要摘要、要文件路径、要聚焦的片段、要「用工具去查」，
而不是把大件复制进聊天。[[src:sessions]]

### 会话该在哪里收尾

```bash
/new       # 开新会话（新 ID + 全新历史）
/compress  # 压缩当前上下文（刷记忆 + 摘要）
/resume    # 恢复一个命名过的会话
/sessions  # 浏览并恢复历史会话
```

**纪律**：在自然的边界上跑 `/new` —— 一个任务做完、话题切换、一天开始。
每个边界都是记忆发挥作用的地方：它会重读更新后的 `MEMORY.md` / `USER.md` 快照、
从一个便宜的短上下文出发、需要历史时才去 `session_search`。

**这条在消息平台上尤其重要**：Telegram/Discord 上的一个聊天是**刻意设计成一条连续会话**的，
能扛过重启、崩溃、关机 —— 关机过夜**不算**会话结束。如果你从不重置，一个聊天可以连续跑几周：
方便，但越来越贵（压缩在越来越长的历史上反复跑），而且「忘记 → 从记忆回忆 →
检索旧会话」这个学习闭环几乎永远不会触发，新写的记忆也因为冻结快照而看不到。[[src:sessions]]

### 一张能救命的高频命令表

| 命令 | 什么时候用 |
|---|---|
| `/status` | 想知道「现在这个会话是什么状态」 |
| `/context` | 想知道「上下文为什么这么满 / 我的规则文件为什么没加载」 |
| `/new [名字]` | 任务切换、话题切换、一天开始 |
| `/compress [here [N] \| 主题]` | 长会话但不想丢线索；`here N` = 保留最近 N 轮原文 |
| `/steer <提示>` | 任务跑到一半要微调方向，**不打断**当前工具调用 |
| `/queue <提示>` | 想排队下一条指令，不影响当前回复 |
| `/btw <问题>` | 就当前对话问个侧问题，不打断、不动缓存 |
| `/bg <提示>` | 丢到独立后台会话里跑，当前会话继续 |
| `/undo`、`/retry` | 后悔药 |
| `/rollback`、`/diff` | 文件被改坏了 / 想看看改了啥（见 [[L24]]） |
| `/refine [方向]` | 立刻触发「把这次经验写成技能/记忆」的自我改进复盘 |
| `/review [说明]` | 派一个独立评审子代理去审刚讨论的产物（见 [[L22]]） |

（完整清单见 [[src:slash-commands]]，或用 `/help`。）[[src:slash-commands]]

## 亲手验证

### 验证一：`/context` 就是「规则文件没生效」的诊断器

```bash
hermes -c
#   ❯ /context
```

| 你观察到的 | 说明什么 |
|---|---|
| 输出里有 **Context files** 清单 | 每个候选规则文件的加载状态都能看到 |
| 某个文件标注 truncated / shadowed / blocked | 就是它没生效的原因（截断 / 被更高优先级遮蔽 / 被安全扫描拦下） |

### 验证二：会话真的落盘了（并且能被外部脚本读到）

```bash
hermes sessions list
python - <<'PY'
import sqlite3, os, pathlib
home = pathlib.Path(os.environ.get("HERMES_HOME") or (pathlib.Path.home() / ".hermes"))
con = sqlite3.connect(f"file:{home / 'state.db'}?mode=ro", uri=True)
print("会话总数:", con.execute("select count(*) from sessions").fetchone()[0])
print("消息总数:", con.execute("select count(*) from messages").fetchone()[0])
for r in con.execute("select id, title, message_count, input_tokens, output_tokens "
                     "from sessions order by started_at desc limit 3"):
    print("  ", r[0], "|", (r[1] or "")[:24], "| 消息", r[2], "| in", r[3], "out", r[4])
PY
```

| 你观察到的 | 说明什么 |
|---|---|
| `state.db` 里有会话与消息计数 | 会话持久化是数据库级的，不是内存态 |
| token 计数按会话记录 | 你可以自己按会话审计成本 |

### 验证三：`/new` 前后对比上下文成本

```bash
hermes -c          # 续上长会话
#   ❯ /status      ← 记下 token 总量
#   ❯ /new         ← 开新会话
#   ❯ /status      ← 对比：应该只剩系统提示的量级
```

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 消息平台上会话越跑越贵 | 平台会话是刻意连续的，关机不算结束 | 在自然边界主动 `/new` |
| 以为「关掉终端会话就没了」 | 会话是永久的 | 用 `/resume` / `hermes sessions list` 找回；要删用 `hermes sessions prune` |
| 粘贴大日志后它开始变笨、变贵 | 啰嗦文本是上下文膨胀的头号原因 | 改用文件路径 + 让它自己读 |
| 图片/附件反复占用上下文 | 误解 | 实际不会重复携带；真凶通常是文本 |
| 改了规则文件却看不到效果 | 上下文在会话开始时组装 | 开新会话（并用 `/context` 确认加载状态） |
| 想在中途补一句又怕打断 | 不知道 `/steer` | 用 `/steer`：在下一个工具调用后送达，不新起一轮 |
| 在消息平台上乱用 `/new` 丢线索 | 没先 `/compress` | 先压缩保留要点，再开新会话 |

## 试一试

- [ ] 跑一次 `/context`，把「上下文构成表」记进 `journal/`，标出你没想到的那一项
- [ ] 用 `/status` 和 `hermes sessions list` 找出你最贵的那次会话，分析为什么
- [ ] 今天做任何任务时，刻意在收尾时跑一次 `/new`，感受第二天开始时的成本差异
- [ ] 用 `/btw` 问一个侧问题，观察它有没有打断你正在跑的任务

## 下一步

- [[L13]] —— 让它跨会话记住你：记忆系统与 `session_search`
- [[L23]] —— 定时与循环：`/loop`、`/goal`、`/heartbeat` 与 cron 的分工
- [[L24]] —— 检查点与回滚：`/rollback`、`/diff` 的完整用法
- 想深入：[[src:cli]]（CLI 的交互细节与键位）、[[src:slash-commands]]（全部命令）

## 出处

- [[src:sessions]] Sessions — https://hermes-agent.nousresearch.com/docs/user-guide/sessions
- [[src:slash-commands]] Slash Commands Reference — https://hermes-agent.nousresearch.com/docs/reference/slash-commands
- [[src:cli]] CLI — https://hermes-agent.nousresearch.com/docs/user-guide/cli
