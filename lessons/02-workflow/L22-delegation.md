---
id: L22
title: "委派：delegate_task 并行子代理"
stage: 2
level: 进阶
minutes: 20
prereq: [L20, L21]
tags: ["delegation", "并行", "子代理", "context 隔离"]
sources: [delegation, delegation-patterns, code-execution]
updated: 2026-09-17
---

# L22 · 委派：delegate_task 并行子代理

> **一句话**：把互不依赖的活派给各自带全新上下文的子代理并行做，只有结论回到你面前，中间过程不占你的上下文。

## 你将学会

- 说出哪些活该委派、哪些该自己干、哪些该用 `execute_code` 或 cron
- 用 `goal` + 自包含的 `context` 写出子代理能独立执行的委派
- 判断委派的边界：不持久、不能反问、默认 10 并发、只回收摘要
- 跑一次两路并行委派，读懂终端里的委派树和耗时

**前置**：[[L20]]、[[L21]] · **预计耗时**：20 分钟

## 先动手

```bash
hermes chat -q "用 delegate_task 并行委派两个互不依赖的子任务：(1) 统计 data.csv 有多少行数据（不含表头），用终端命令算；(2) 统计 notes.md 的字符数，用终端命令算。两个子任务完成后再合并，用两行结论分别汇报数字，并说明你是并行还是串行完成的" -Q
```

本机真实输出（终端里这几行是带进度实时刷新的，这里按阅读顺序节选）：

```
  🔀 [set 1] delegating 2 tasks
  ✓ [set 1 · 1/2] 统计文件 C:/Users/28189/AppData/Local/Temp/h  (3.88s)
  ✓ [set 1 · 2/2] 统计文件 C:/Users/28189/AppData/Local/Temp/h  (4.59s)

已核对（子代理报告与本地终端复算一致）：

- data.csv 数据行数（不含表头）= 3 行
- notes.md 字符数 = 174 个字符

完成方式：并行。两个子任务在同一次 delegate_task 调用中一次性派出，由两个独立子代理同时执行（任务0耗时3.88s、任务1耗时4.59s，总耗时5.84s，明显短于两者之和），完成后再合并结果。
```

**注意最后那句「已核对」**：子代理给的是摘要，父代理又自己复算了一遍。这就是委派该有的收尾动作。[[src:delegation-patterns]]

## 原理

### 委派换来了什么

| 换来的 | 代价 |
|---|---|
| 每个子代理一个独立会话、一个独立终端 | 它对你的对话**一无所知** |
| 只有最终摘要回到父上下文，中间工具结果全不进 | 摘要不等于证据，得抽查 |
| 互不依赖的活真并行（默认最多 10 个一批） | 每一路都是一次完整的 LLM 循环，成本随并行数上涨 |

[[src:delegation]]

### 什么该委派，什么不该

| 情形 | 用什么 |
|---|---|
| 单次工具调用就能办 | 直接调那个工具 |
| 机械的多步流程、中间有逻辑 | `execute_code`（便宜，只回 stdout） |
| 需要判断力的子任务（调试、代码审查、研究综合） | `delegate_task` |
| 会把自己的上下文灌爆的活 | `delegate_task`（只回收摘要） |
| 需要问用户的问题 | 都不行：子代理不能用 `clarify` |
| 必须熬过会话关闭/进程重启 | `cronjob` 或 `terminal(background=True, notify_on_complete=True)` |

[[src:delegation-patterns]]

### `context` 必须自包含

子代理的上下文完全来自你给的 `goal` 和 `context` 两个字段：

```python
# 坏：子代理不知道「那个错误」是什么
delegate_task(goal="Fix the error")

# 好：文件、行号、报错、项目路径、测试命令全给
delegate_task(
    goal="Fix the TypeError in api/handlers.py",
    context="""api/handlers.py 第 47 行抛 TypeError:
    'NoneType' object has no attribute 'get'。
    process_request() 从 parse_body() 收到 dict，
    但 parse_body() 在缺少 Content-Type 时返回 None。
    项目在 /home/user/myproject，Python 3.11。"""
)
```

有一个例外值得知道：父会话解析出工作目录后，子代理的系统提示会带上那个目录的项目上下文文件（`.hermes.md` > AGENTS.md 链 > CLAUDE.md > `.cursorrules`，SOUL.md 除外）—— 在仓库里干活的子代理不用重新摸索项目的约定。[[src:delegation]]

### 工具能力与并发

- 子代理**继承**父会话启用的工具集，模型不能在一次调用里自己加权限；要给它网页/终端/文件能力，先把父会话配好。[[src:delegation-patterns]]
- 子代理被屏蔽：`delegate_task`、`clarify`、`memory`、`send_message`、`cronjob`；`execute_code` 保留（机械活用它）。[[src:delegation]]
- 一批默认 10 个并发（`delegation.max_concurrent_children`，下限 1，无硬上限）；每个子代理默认 250 轮迭代预算（`delegation.max_iterations`）。撞上预算会返回 `exit_reason: max_iterations` 和 `truncated: true`。[[src:delegation]]
- **默认没有墙钟上限，但有一条卡死线**：失败来源是 API 错误、工具错误或迭代预算，不是「跑得久」；要按时长设硬上限得自己开 `delegation.child_timeout_seconds`（下限 30 秒）。另有一条失速判定：**450 秒没有任何进展**（回合之间的空闲，即 15 个 30 秒心跳周期）或 **1200 秒卡在同一个工具上**（40 个周期），心跳就停止刷新父代理的活动时钟，把这次等待交给网关的不活动超时收场 —— 等模型返回本身算进展，慢模型不会被判失速。[[src:delegation]]
- 并行改同一个仓库会互相踩：`delegation.worktree_isolation: true` 时每个子代理在自己的 git worktree 上干活，结果里带回 `path`/`branch`/`commits`。[[src:delegation]]

### 结构化回传

每个任务可以带 `output_schema`（JSON Schema）。子代理把 schema 当输出契约，父代理收到后校验；失败会补一次纠正轮，结果里带 `schema_valid` 与 `schema_errors`。**契约没达标不会丢掉它的工作**：结果仍是 `status: completed`，原始文本在 `summary` 里，只是标为未校验。[[src:delegation]]

### 失败与不持久

- 失败从不静默：终端里 `⚠️ Subagent failed — "your goal": <原因>` 一行，父代理的结果里带 `status: "failed"` 和完整 `error`。[[src:delegation]]
- 委派**不是持久执行**：`/stop`、关闭或重置会话、进程重启都会让在跑的子代理丢失或变成 `unknown`。要熬过这些边界就用 `cronjob` 或后台终端命令。[[src:delegation]]

### 和 `execute_code` 怎么分工

| 维度 | `delegate_task` | `execute_code` |
|---|---|---|
| 推理 | 完整 LLM 循环 | 只是 Python 执行 |
| 上下文 | 全新的独立会话 | 没有对话，只有脚本 |
| 工具 | 全部未屏蔽工具，带推理 | 7 个工具经 RPC，无推理 |
| 适合 | 需要判断的复杂任务 | 机械的数据处理管道 |
| 成本 | 高（完整 LLM 循环） | 低（只有 stdout 回来） |

[[src:code-execution]] [[src:delegation]]

## 亲手验证

### 验证一：给一个没有上下文的目标，看它怎么反应

```bash
hermes chat -q "用 delegate_task 让子代理修复我们刚才讨论的那个 bug" -Q
```

本机真实输出（节选）：

```
我这边没有找到"刚才讨论的那个 bug"的记录，无法凭空指派子代理去修。

这个会话是全新的，前面没有任何 bug 讨论；我翻了最近的会话历史…也翻了你这个工作目录…都没有关于某个具体 bug 的讨论。

要我派子代理去修，请给我其中一样：

1. 具体是哪个 bug —— 报错信息、复现步骤，或代码仓库路径 + 文件
2. 指向某个 issue / commit
```

| 你观察到的 | 说明什么 |
|---|---|
| 它拒绝派活，还列出需要什么 | 子代理没有对话记忆，父代理必须先把目标说清 |
| 它列举的正是该进 `context` 的东西 | 报错、复现步骤、仓库路径、文件、issue 链接 |

### 验证二：不要只信摘要

让子代理改一个测试用例，然后你别问它「成功了吗」——自己跑一遍。上面「先动手」里父代理主动复算数字，就是同一个动作。**子代理说测试通过，不等于测试通过。** [[src:delegation-patterns]]

### 验证三：看一次失败长什么样

给它一个不存在的模型或坏掉的目标（例如 `delegation.model` 写一个不存在的模型名），运行后观察终端里的 `⚠️ Subagent failed — "你的目标": <原因>` 一行；这类通知即使关掉工具进度显示也会送达。[[src:delegation]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `⚠️ Subagent failed — "your goal": HTTP 404: model not found (after 12s)` | 子代理用的模型/凭证不可用 | 检查 `delegation.model` / `delegation.provider`，或去掉覆盖走全局 |
| 子代理报「改完了、测试过了」，你一看没改 | 摘要不等于证据 | 自己跑测试或看 diff；把它写进你的验收动作 |
| 关掉会话后委派结果永远没回来 | 顶层委派挂在拥有它的会话与进程上 | 跨越会话边界的活用 `cronjob` 或 `terminal(background=True, notify_on_complete=True)` |
| `/stop` 之后子代理没了结果 | 取消跟随所有权，父代理被中断 | 这是设计行为；长活改放 cron |
| 想让子代理用一套不同工具 | `delegate_task` 不接受模型侧 `toolsets` 参数 | 先配好父会话的工具集 |
| 两个子代理改同一个文件互相覆盖 | 默认共享父会话的工作目录 | 开 `delegation.worktree_isolation: true`，或那个文件自己动手 |
| 结果里 `exit_reason: max_iterations`、`truncated: true` | 撞上 250 轮迭代预算 | 调 `delegation.max_iterations`，或把任务拆小 |
| 一批派出去成本远超预期 | 每一路都是一次完整 LLM 循环，嵌套还会相乘 | 给 worker 指定便宜模型，谨慎提高 `max_spawn_depth` |

## 试一试

- [ ] 把手上三件互不依赖的事写成一次 `delegate_task` 批量委派，比较总耗时
- [ ] 故意把 `context` 写少一半，看子代理的产出质量差在哪
- [ ] 给一个任务加 `output_schema`，检查结果里的 `schema_valid`
- [ ] 判断一件事：这件事该委派、该 `execute_code`，还是该定时跑？写下理由

## 下一步

- [[L20]] —— 委派的目标写得准不准，取决于你会不会写判据
- [[L21]] —— 子代理用的是和你同一套工具，先弄清它们的边界
- [[L23]] —— 需要熬过会话关闭的活，交给 cron 而不是委派
- [[L32]] —— 用 kanban 把多个代理排成一张有依赖的看板
- 想深入：[[src:delegation]]（全部参数与生命周期）、[[src:delegation-patterns]]（四类常用模式）

## 出处

- [[src:delegation]] Subagent Delegation — https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
- [[src:delegation-patterns]] Delegation & Parallel Work — https://hermes-agent.nousresearch.com/docs/guides/delegation-patterns
- [[src:code-execution]] Code Execution — https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution
