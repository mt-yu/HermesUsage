---
id: L34
title: "无人值守流水线：cron + webhook + skill"
stage: 3
level: 进阶
minutes: 30
prereq: [L23, L31, L33]
tags: ["cron", "webhook", "流水线", "无人值守", "投递"]
sources: [automate-with-cron, cron-script-only, automation-blueprints, cron, pipe-script-output, webhooks]
updated: 2026-09-16
---

# L34 · 无人值守流水线：cron + webhook + skill

> **一句话**：无人值守不是「挂一个定时任务」，而是**触发源 + 技能 + 投递 + 失败可见**这四件事各自到位；缺任何一件，你都会在三天后才发现它其实没跑。

## 你将学会

- 组装一条最小的无人值守链路，并说清每个零件负责什么
- 用 `hermes cron` 的 create/run/resume/runs/doctor/tick 做闭环验证
- 区分「定时触发」与「事件触发」，知道各自的验证方式不同
- 在无人值守场景下处理失败：它不问你，所以你必须在设计时就替它决定

**前置**：L23、L31、L33 · **预计耗时**：30 分钟

## 先动手

先看现状 —— **网关在不在跑，决定这一切是否成立**：

```bash
hermes cron status
hermes cron list
```

本机真实输出（网关未运行时）：

```
✗ Gateway is not running — cron jobs will NOT fire
No scheduled jobs. Create one with 'hermes cron create ...'
```

现在创建一个「脚本模式」任务（不需要 LLM，最便宜也最可靠）：

```bash
hermes cron create "every 5m" --no-agent --script hu-demo-ping.py --name hu-demo-ping --deliver local
```

本机真实输出（成功时）：

```
Created job: 7f1f905eff70
Mode: no-agent (script stdout delivered directly)
```

## 原理

### 链路有四个零件，少一个都不算「无人值守」

| 零件 | 干什么 | 配错了会怎样 |
|---|---|---|
| **① 触发源** | 到点触发（cron）或外部事件触发（webhook） | 任务永远不跑，而你以为它在跑 |
| **② 技能/提示** | 干什么活，判据是什么 | 它每天按时产出一堆没用的东西 |
| **③ 投递** | 结果去哪（平台/本地/文件） | 跑对了我也不知道 |
| **④ 失败可见** | 出错时谁能知道 | 连续失败一周没人发现 |

④ 是最常被跳过的一环，也是最贵的。`hermes cron doctor` 与 `hermes cron runs <job_id>`
就是为它准备的。[[src:cron]]

### 定时触发：两种任务形态

```bash
# 形态一：agent 任务（要 LLM，能思考、能用工具）
hermes cron create "0 9 * * *" "检查昨天的构建失败，有失败就列出根因" --name morning-check

# 形态二：纯脚本任务（不要 LLM，stdout 直接投递）
hermes cron create "every 5m" --no-agent --script disk-alert.sh --name disk-alert
```

**形态二的关键规矩**（本机真实报错）：

```
$ hermes cron create "every 5m" --no-agent
Failed to create job: create with no_agent=True requires a script — the script is the job.
```

也就是说：`--no-agent` 模式下**脚本就是任务本身**，它的 stdout 被原样投递；
**stdout 为空则什么都不发**（watchdog 模式），这正是「没消息就是好消息」的实现方式。[[src:cron-script-only]]

### 脚本被约束在固定目录里

入口脚本必须在 `$HERMES_HOME/scripts/` 下 —— 这是一道刻意的护栏（本机真实报错）：

```
$ hermes cron create "every 5m" --no-agent --script "../evil.sh"
Failed to create job: Script path escapes the scripts directory via traversal: '../evil.sh'

$ hermes cron create "every 5m" --no-agent --script "no-such.sh"
Failed to create job: Script file not found: <HERMES_HOME>\scripts\no-such.sh
```

所以「让脚本能做任何事」的正解是：`$HERMES_HOME/scripts/` 里放一个**薄包装器**，
让它去调用你真正想跑的那份代码（本项目就这么干：包装器会调用仓库里的
`scripts/journal.py autocommit`）。

### 排程写法：文档有冲突，以实测为准

官方两处口径不一致：`automate-with-cron` 指南写「自然语言如 `daily at 9am` 不支持」，
而 `cron` 特性页把 `every day at 9am` / `weekdays at 9am` 列在支持格式里。
**本机实测**：`hermes cron create "daily at 9am" ...` 被接受，回显
`Next run: 2026-09-17T09:00:00+08:00`。[[src:cron]] [[src:automate-with-cron]]

**建议**：脚本化、可评审的场景一律用标准 cron 表达式（`0 9 * * *`），
别依赖自然语言的模糊边界。

### 事件触发：验证方式完全不同

```bash
hermes webhook subscribe my-issues        # 本机输出 URL + 自动生成的 Secret
hermes webhook test my-issues             # 网关没跑时：真实报错 Is the gateway running?
```

`subscribe` 会给你一个形如 `http://localhost:8644/webhooks/<name>` 的地址与一个 Secret。
定时任务的验证是「等它到点」；事件任务的验证是「**打一发**」——所以事件驱动更容易
做闭环测试，也更适合当第一批自动化。[[src:webhooks]]

### 投递：别让它默默成功

```bash
hermes send --list                      # 看有哪些可用目标
hermes send --to telegram "test"        # 平台没配时：real error, exit=1
```

投递目标可以是平台频道、`local`（只保存不投递）等。**本机的真实教训**：在没有配任何
平台时，`send` 会明确报错而不是静默丢弃 —— 这是好事；但如果你用 `--deliver local`
又不看日志，它就会「成功」得无声无息。[[src:pipe-script-output]]

## 亲手验证

### 验证一：跑一次、查一次（闭环的最小单位）

```bash
hermes cron run hu-demo-ping          # 立即触发一次
hermes cron runs 7f1f905eff70         # 用 job id 查执行记录
```

本机真实差异（这个坑值得记住）：

```
$ hermes cron runs hu-demo-ping
No cron execution attempts recorded.

$ hermes cron runs 7f1f905eff70
d834beae709f… completed job=7f1f905eff70 source=direct 2026-09-16T11:01:28…
```

**用名字查不到、用 id 查得到** —— 验证时别被「查不到记录」误导成「任务没跑」。

### 验证二：让它替你检查自己的健康

```bash
hermes cron doctor        # 本机真实输出：✓ Cron doctor found no issues / Checked N active job(s).
hermes cron tick          # 手动推进一次调度（不等钟点）
```

### 验证三：故意配错一次，看它拦在哪

```bash
hermes cron create "not-a-schedule" "test"
# 真实报错：Failed to create job: Invalid schedule 'not-a-schedule'.
#          Use: Interval/One-shot delay/Weekly-daily/Cron/Timestamp

hermes cron run <一个 paused 的任务>
# 真实报错：Job is paused/disabled; resume it before running.
```

### 验证四：确认「网关是总闸」

```bash
hermes cron status
```

若输出里有 `✗ Gateway is not running — cron jobs will NOT fire`，
那么**你后面所有排程实验都不会触发**。先解决这一步，再谈别的。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 任务登记了但从不触发 | 网关没在跑 | `hermes gateway install` / `start`，再 `hermes cron status` 确认 |
| `cron runs <名字>` 查不到记录 | 该子命令按 job id 查 | 用 `hermes cron list` 里的 id |
| `--no-agent` 建任务失败 | 缺 `--script`（脚本才是任务） | 补 `--script <name>`，文件放在 `$HERMES_HOME/scripts/` |
| 脚本路径报 traversal 错误 | 想用 `../` 跳出 scripts 目录 | 放一个薄包装器在 `scripts/` 里，让它调用真正的代码 |
| 到点了但没收到任何消息 | 脚本 stdout 为空（watchdog 模式不投递） | 这是设计行为；要确认存活就输出一行状态 |
| webhook 测试失败提示 Is the gateway running? | 网关没跑 | 先起网关；`curl -s http://localhost:8644/health` 自测 |
| 自然语言排程行为怪异 | 两处官方文档口径不一致 | 一律用 cron 表达式 |
| 无人值守时它卡在审批弹窗 | 无人值守默认不自动批准 | 本机 `approvals.cron_mode: deny` —— 设计任务时要避开危险操作 |
| 连续失败三天没人知道 | 没配失败投递 | 用 `failure_deliver` 把失败送到独立目标 |

## 试一试

- [ ] 用 `--no-agent` 建一条「脚本 stdout 为空则静默」的 watchdog 任务，然后故意让脚本失败一次，观察你怎么收到通知
- [ ] 给一个 agent 任务配 `failure_deliver`，把失败送到与你不同的聊天目标
- [ ] 跑一次 `hermes cron tick`，对比「等钟点」与「手动推进」的差别
- [ ] 设计一条完整链路并写下四个零件：触发源 / 技能 / 投递 / 失败可见 —— 写不出第四个就别上线
- [ ] 参考官方蓝图库里的现成配方，把其中一个改成你自己的场景 [[src:automation-blueprints]]

## 下一步

- [[L90]] —— 毕业项目：把这条链路变成你自己真实在用的自动化
- [[L30]] —— 钩子：在流水线的关键节点插日志与告警
- [[L50]] —— 无人值守场景下的安全与审批
- 想深入：[[src:automate-with-cron]]（真实自动化模式）、[[src:cron-script-only]]（纯脚本任务）

## 出处

- [[src:automate-with-cron]] Automate Anything with Cron — https://hermes-agent.nousresearch.com/docs/guides/automate-with-cron
- [[src:cron-script-only]] Script-Only Cron Jobs (No LLM) — https://hermes-agent.nousresearch.com/docs/guides/cron-script-only
- [[src:automation-blueprints]] Automation Blueprints — https://hermes-agent.nousresearch.com/docs/guides/automation-blueprints
- [[src:cron]] Scheduled Tasks (Cron) — https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- [[src:pipe-script-output]] Pipe Script Output to Messaging Platforms — https://hermes-agent.nousresearch.com/docs/guides/pipe-script-output
- [[src:webhooks]] Webhooks — https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks
