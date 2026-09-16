---
id: L23
title: "定时与循环：cron / loops / goals"
stage: 2
level: 进阶
minutes: 25
prereq: [L12, L22]
tags: ["cron", "loop", "goal", "heartbeat", "无人值守"]
sources: [cron, loops, goals, heartbeat, automate-with-cron]
updated: 2026-09-16
---

# L23 · 定时与循环：cron / loops / goals

> **一句话**：你不在的时候有四条不同的路让它继续干活 —— cron 活在会话之外，loop 和 goal 活在你这个会话里，heartbeat 只在你这个线程内定时敲一下。

## 你将学会

- 分清除 cron、`/loop`、`/goal`、`/heartbeat` 各自的触发条件与寿命，按需选型
- 建一个不花 token 的 `no_agent` 看门狗作业，跑一次、查执行历史、再删掉
- 用 `hermes cron status` / `doctor` 判断作业为什么不跑
- 写出能在全新会话里独立执行的 cron 提示（自包含 + `[SILENT]`）

**前置**：L12、L22 · **预计耗时**：25 分钟

## 先动手

```bash
hermes cron list
hermes cron status
```

本机真实输出：

```
No scheduled jobs.
Create one with 'hermes cron create ...' or the /cron command in chat.
```

```
✓ Gateway is running — cron jobs will fire automatically
  PID: 58432
  Ticker heartbeat: 13s ago

  1 active job(s)
  Next run: 2026-09-16T11:06:13.735203+08:00
```

（那 1 个是我当场建的测试作业，验证完就删掉了；现在 `hermes cron list` 又是 `No scheduled jobs.`。）

**第一眼要建立的认知**：cron 的调度器挂在网关进程里，网关不在跑，作业就不会自己触发；而作业跑的时候**没有你的对话记忆**。[[src:cron]] [[src:automate-with-cron]]

## 原理

### 四种「不在你手上」的形态

| | `/loop` | `/goal` | cron |
|---|---|---|---|
| 触发 | 定时（也可自适应） | 每轮之后由裁判模型判定 | 排程，在会话之外 |
| 活在哪 | 你当前这个会话 | 你当前这个会话 | 每次运行一个独立会话 |
| 何时结束 | 停止条件 / 上限 / 你喊停 | 目标达成 / 预算 / 你喊停 | 你把它删掉 |
| 适合 | 轮询、盯梢、周期性重跑 | 一个目标，反复推进到达成 | 无人值守、长周期排程 |

[[src:loops]]

再加一个 `/heartbeat`：它给**当前会话**一条循环指令，只在会话空闲时以普通 user 消息注入 —— 同一个对话、同一份上下文、同一个缓存前缀。它和 cron 的分界很简单：**要会话上下文的用 heartbeat，自包含的活交给 cron**。[[src:heartbeat]]

### cron 能做的事

建一次性或循环任务、暂停/恢复/编辑/触发/删除、挂 0 到多个技能、把结果投递回来源会话或本地文件或平台、跑 no-agent 模式（脚本就是作业，stdout 原样投递，**零 LLM**）、以及被 webhook 事件触发。这些操作对 Hermes 自己也是可调的：你直接用中文说，它内部调 `cronjob` 工具。[[src:cron]]

```bash
/cron add "in 30m" "Remind me to check the build"
/cron add "every 2h" "Check server status"
hermes cron create "every 1h" "Summarize new feed items" --skill blogwatcher
```

### 排程怎么写

| 写法 | 含义 |
|---|---|
| `in 30m` / `in 2h` | 一次性，30 分钟/2 小时后跑 |
| `30m` / `every 30m` / `every 2h` | 循环，裸时长就是循环 |
| `every day at 9am` / `weekdays at 9am` / `every monday 9am` | 自然日时（内部编译成 cron 表达式） |
| `0 9 * * *` / `0 9 * * 1-5` / `0 */6 * * *` | 标准 cron 表达式 |
| `2026-03-15T09:00:00` | ISO 时间戳，一次性 |

[[src:cron]]

一次性默认只跑 1 次，间隔与 cron 表达式默认永远跑，都可以用 `repeat` 覆盖。[[src:cron]]

### 结果投递到哪

| 目标 | 例子 | 用途 |
|---|---|---|
| `origin` | `--deliver origin` | 创建作业的那个会话（默认） |
| `local` | `--deliver local` | 只落本地文件 |
| `telegram` / `discord` / `slack` | `--deliver telegram` | 该平台的主频道 |
| 具体会话/话题 | `--deliver telegram:-1001234567890:17585` | 指定群或话题 |

[[src:automate-with-cron]]

### `no_agent`：不需要 LLM 的看门狗

```bash
hermes cron create "every 5m" \
  --no-agent \
  --script memory-watchdog.sh \
  --deliver telegram \
  --name "memory-watchdog"
```

语义值得背下来：脚本 stdout（去掉首尾空白）**原样投递**；**空 stdout = 静默 tick，不投递**（这就是「只在出问题时才喊」的看门狗模式）；非零退出或超时会投递一条错误告警，所以坏掉的看门狗不会静默失败。脚本必须放在 `$HERMES_HOME/scripts/` 里面。[[src:cron]]

### 提示要自包含

cron 的 agent 跑在全新会话里，没有你的对话记忆，所以提示里要带上 URL、仓库名、格式要求、投递方式。生产上还会用 `[SILENT]` 抑制投递：

```text
If nothing noteworthy happened, respond with only [SILENT].
```

[[src:automate-with-cron]]

### 关于模型：作业会被「快照」

作业的模型解析顺序是：作业自己的 pin → `cron.model` → 全局默认。关键在于：**创建时会快照当时的 provider 与 model**，之后你换默认模型，作业还是跑在创建时的那个上（每次运行会记一行 INFO 说明差异）。想让它跟上新默认值，用 `hermes cron resnap <job_id>`（或 `--all`），或者 `hermes cron edit <job_id> --model ... --provider ...` 显式 pin。[[src:cron]]

### 两种「自己推进」的会话内形态

- `/loop 5m <提示>`：每 5 分钟一次真实 agent 轮，读当前状态、干活、回报。停止条件有四种 —— agent 自己以 `LOOP_COMPLETE` 宣告完成、`--times N` 次数上限、`--until <条件>` 判据、你 `/loop stop`；还有 `loops.max_ticks`（默认 100）兜底，防止无人值守时无限烧。[[src:loops]]
- `/goal <文本>`：每轮之后一个轻量裁判模型判断目标是否达成，没达成就自动喂一条继续指令。可以用 `/goal draft <文本>` 生成**完成契约**（`outcome` / `verification` / `constraints` / `boundaries` / `stop_when`），也可以内联写 `verify:`、`constraints:`、`boundaries:`、`stop when:` 字段；带契约时裁判只在**判据被具体证据满足**时才判定 done。[[src:goals]]

两者共存时有一条硬规则：**活跃的 goal 拥有会话**，goal 在跑时 loop 的唤醒往后排；goal 完成、暂停或停在等待屏障上，loop 接着用空闲时间。[[src:loops]]

## 亲手验证

### 验证一：建一个零 token 的看门狗，跑一次，再删掉

先写一个脚本到 `$HERMES_HOME/scripts/`（本机是 `~/AppData/Local/hermes/scripts/`）：

```python
# hu-demo-ping.py
import pathlib

state = pathlib.Path(__file__).with_name(".hu-demo-ticks")
n = int(state.read_text().strip() or "0") if state.exists() else 0
n += 1
state.write_text(str(n))
print(f"hu-demo watchdog tick #{n} - all normal")
```

然后：

```bash
hermes cron create "every 5m" --no-agent --script hu-demo-ping.py --name hu-demo-ping --deliver local
hermes cron run hu-demo-ping
hermes cron runs hu-demo-ping
hermes cron doctor
hermes cron remove hu-demo-ping
```

本机真实输出：

```
Created job: 7f1f905eff70
  Name: hu-demo-ping
  Schedule: every 5m
  Script: hu-demo-ping.py
  Mode: no-agent (script stdout delivered directly)
  Next run: 2026-09-16T11:06:13.735203+08:00
```

```
Triggered job: hu-demo-ping (hu-demo-ping)
  Next run: 2026-09-16T11:06:29.410164+08:00
  Ran now: succeeded.
```

```
✓ Cron doctor found no issues
  Checked 1 active job(s).
```

```
Removed job: hu-demo-ping (hu-demo-ping)
```

### 验证二：用名字查执行历史，得到空

```bash
hermes cron runs hu-demo-ping          # 用作业名
hermes cron runs 7f1f905eff70          # 用作业 id
```

本机真实输出：

```
No cron execution attempts recorded.
```

```
d834beae709f49a9a7743a8d98b9fc48  completed  job=7f1f905eff70  source=direct  2026-09-16T11:01:28.708306+08:00
```

| 你观察到的 | 说明什么 |
|---|---|
| 用名字查 `runs` 是空的 | 这条子命令按作业 id 匹配（`pause`/`resume`/`run`/`remove`/`edit` 才支持按名字） |
| 用 id 查到了那一次运行 | 执行历史是持久的，能事后复盘「那次到底跑没跑」 |
| `no_agent` 作业全程没有模型参与 | 脚本 stdout 直接投递，零 token、零 provider 依赖 |

### 验证三：亲手造一次静默

把脚本最后一行 `print(...)` 删掉再跑一次 —— stdout 为空，本次 tick **不投递任何消息**。这就是看门狗「只在异常时喊」的实现方式。[[src:cron]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `No cron execution attempts recorded.` | 用作业名去查运行历史，而该子命令要作业 id | `hermes cron runs <job_id>`，id 从 `hermes cron list` 拿 |
| 作业到点了但一次都没跑 | 调度器不在跑，或预检没过 | `hermes cron status` 看网关与 ticker；`hermes cron doctor` 查健康；`hermes cron list` 看 `last_status` |
| 定时提示里写「继续昨天的活」，它说找不到 | cron 的 agent 跑在全新会话，没有对话记忆 | 提示自包含：URL、路径、格式、投递目标全写进去 |
| 要求「没事别打扰」但消息还是来了 | 只在提示里写了自然语言，没有抑制标记 | 明确写 `respond with only [SILENT]` |
| 抄来的排程 `daily at 9am` 报错 | 官方两处文档口径不一致（guides 里写不支持自然语言，features 里列了 `daily at 7am` 这类形式） | 直接用 `0 9 * * *`，两种口径都认 |
| 每个 tick 都觉得很贵 | 每次 tick 都是一次完整 agent 轮 | 拉长间隔、改用 `no_agent` 脚本模式、用 `[SILENT]` 抑制空跑投递 |
| 想在一个 cron 作业里再建作业 | 默认禁止（防止失控的排程循环） | 确实需要时显式开 `cron.allow_agent_scheduling: true` |
| 换了默认模型，作业还跑在老模型上 | 创建时快照成了这个作业的 pin | `hermes cron resnap <job_id>`（或 `--all`），或 `hermes cron edit ... --model` |
| 半夜 `/loop` 还在烧 token | loop 活在会话里，没人审批 | `--times N` / `--until`、`loops.max_ticks` 兜底；长周期改用 cron |
| 作业状态是 `blocked_config` | 预检发现凭证/技能/投递目标配不通，**没有发起任何 LLM 调用** | 按提示补齐配置；下次健康运行会自动清掉这个状态 |

## 试一试

- [ ] 建一个 `every 1h` 的自包含 cron 作业，用 `[SILENT]` 抑制空跑，明天看它的第一次投递
- [ ] 用 `--paused` 建一个作业当金丝雀，确认输出没问题后再 `hermes cron resume`
- [ ] 把一件需要反复说「继续」的事，改成 `/goal draft <目标>` 让它自己推完
- [ ] 用 `/heartbeat every 15m <提示>` 在会话里盯一个长任务，结束后 `/heartbeat clear`

## 下一步

- [[L21]] —— cron 里的 agent 用的还是那套工具，顺手把边界复习一遍
- [[L22]] —— 需要并行的长活先委派，需要跨会话存活的才上 cron
- [[L24]] —— 无人值守之前，先把回滚点准备好
- [[L31]] —— 用 webhook 让外部事件触发作业，而不是等下一个 tick
- [[L34]] —— 把 cron + webhook + 技能拼成一条产线
- 想深入：[[src:cron]]（全部参数与失败语义）、[[src:goals]]（完成契约与质量门）、[[src:loops]]（自适应用户节奏）

## 出处

- [[src:cron]] Scheduled Tasks (Cron) — https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- [[src:loops]] Recurring Loops — https://hermes-agent.nousresearch.com/docs/user-guide/features/loops
- [[src:goals]] Persistent Goals — https://hermes-agent.nousresearch.com/docs/user-guide/features/goals
- [[src:heartbeat]] Session Heartbeats — https://hermes-agent.nousresearch.com/docs/user-guide/features/heartbeat
- [[src:automate-with-cron]] Automate Anything with Cron — https://hermes-agent.nousresearch.com/docs/guides/automate-with-cron
