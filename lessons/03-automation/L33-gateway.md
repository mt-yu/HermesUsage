---
id: L33
title: "网关：把 Hermes 变成机器人"
stage: 3
level: 进阶
minutes: 25
prereq: [L12, L21]
tags: ["网关", "gateway", "消息平台", "配对", "权限"]
sources: [gateway-messaging, security, slash-commands]
updated: 2026-09-16
---

# L33 · 网关：把 Hermes 变成机器人

> **一句话**：网关让**同一个 agent 内核**住进 20 多个聊天平台；装它之前先想清楚一件事——谁能指挥它。

## 你将学会

- 说清网关与 CLI 共享什么、不共享什么（会话、技能、记忆、配置）
- 用 `hermes gateway` 的子命令安装、启停、查状态，并知道「没在跑」时会发生什么
- 用配对（pairing）与权限配置控制「谁能让这个机器人干活」
- 判断某个平台该不该接：先过一遍「谁能给它发指令」这道闸

**前置**：[[L12]]、[[L21]] · **预计耗时**：25 分钟

## 先动手

```bash
hermes gateway status
hermes gateway list
hermes send --list
```

本机真实输出（网关未运行时）：

```
✗ Gateway is not running
✗ default (current) — not running

No messaging platforms configured or no channels discovered yet.
```

然后看出安装网关要做什么：

```bash
hermes gateway --help
```

本机真实子命令清单：

```
run  start  stop  restart  status  install  uninstall  list  setup  migrate
```

**注意 `install`**：网关不是「跑个前台进程」，它要被装成一个常驻服务
（Windows 上做成计划任务，Linux/macOS 上是服务）。关掉终端它还得活着 ——
因为它的价值就在「你不在的时候」。[[src:gateway-messaging]]

## 原理

### 一个内核，一层壳

网关不是另一个 Hermes。它把**同一条 agent 内核**接到各个平台的适配器上，
所以这些东西是**共享**的：会话库（`state.db`）、技能、记忆、`config.yaml`、审批策略。
你在 Telegram 上让它学会的流程，回到 CLI 立刻可用。[[src:gateway-messaging]]

支持面很宽：Telegram、Discord、Slack、WhatsApp、Signal、Email、SMS、Matrix、
Mattermost、Microsoft Teams、LINE、SimpleX、ntfy、Google Chat、Home Assistant、
DingTalk、Feishu、WeCom、Weixin、API Server、Webhooks，以及通过插件接入的 IRC 等。[[src:gateway-messaging]]

**平台是能力差异的来源**：语音频道、消息反应、文件投递这些能力因平台而异，
所以工具集是**按平台**配置的（`platform_toolsets.<平台>`）。你可以让手机端权限收窄、
桌面端放开 —— 这是网关安全的第一条实践。

### 装它之前先回答一个问题：谁能指挥它？

这是网关最容易被忽略、后果最严重的一层。一个 `@你的机器人 帮我删掉临时文件`
如果是陌生人发的，你就把机器交出去了。

三道闸：

| 闸 | 是什么 | 配置点 |
|---|---|---|
| **① 配对 / 允许名单** | 只有被批准的用户/群能让它干活 | `hermes pairing list` / `approve` / `revoke`；各平台的 allowlist |
| **② 斜杠命令分级** | 管理员能用全部命令；普通用户只能用你列出来的 | `allow_admin_from` + `user_allowed_commands`（`/help`、`/whoami` 是永远允许的底） |
| **③ 审批与拒单** | 危险命令要不要问、无人值守时要不要直接拒 | `approvals.mode`（本机为 `smart`）、`approvals.cron_mode`（本机为 `deny`） |

第一道闸的实测形态：

```bash
hermes pairing list
# 本机真实输出：No pairing data found. No one has tried to pair yet~
hermes pairing --help
# 真实子命令：list / approve / revoke / clear-pending
```

第二道闸的规则（官方）：每个支持按用户允许名单的平台（Telegram、Discord、Slack、
Matrix、Mattermost、Signal…）都支持管理员/普通用户两级斜杠命令：管理员拿到全部命令，
普通用户只拿到你列在 `user_allowed_commands` 里的那些（外加永远允许的 `/help`、`/whoami`）。
若某个范围没设 `allow_admin_from`，该范围就停留在「不限制」的向后兼容模式。[[src:slash-commands]]

**判据**：任何面向**群**的机器人，第一件事是把第二道闸配好；只给自己用的私聊机器人，
至少配第一道闸。[[src:security]]

## 亲手验证

### 验证一：网关没跑时，依赖它的东西一起哑火

```bash
hermes gateway status          # ✗ Gateway is not running
hermes cron status             # 会告诉你 cron 任务不会触发
hermes send --to telegram "test"
# 本机真实输出：hermes send: Platform 'telegram' is not configured...  (exit=1)
```

| 你观察到的 | 说明什么 |
|---|---|
| `send` 报平台未配置而不是「网关没跑」 | 先决条件是平台配置，其次才是网关 |
| cron 明确说不会触发 | 定时任务依赖网关进程常驻 |

### 验证二：把「谁能指挥它」这条问出来

```bash
hermes config get approvals
hermes config get platform_toolsets
```

本机真实输出（节选）：

```
mode: smart
timeout: 300
cron_mode: deny
single_query_mode: deny
unattended_mode: deny
```

解读：**无人值守场景默认是「拒绝」而不是「自动批准」** —— 这是有意为之的保守默认值。

### 验证三：先在本机闭环，再上平台

```bash
hermes gateway setup      # 交互式选平台
hermes gateway start
hermes gateway status     # 这一步必须变成 running 才算数
```

先确认 `status` 是 running，再去平台上测试；否则你会在「到底是配置错还是没启动」
之间来回猜。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 接了平台但机器人不回话 | 网关没在跑（或没装成服务） | `hermes gateway status` → 不是 running 就先 `install` / `start` |
| 关掉终端后机器人失联 | 只在终端前台跑过 `run` | `hermes gateway install` 装成常驻服务 |
| cron 任务到点不触发 | 网关没跑（cron 依赖它） | 先起网关；`hermes cron doctor` 辅助排查 |
| 群里的陌生人能让机器人干活 | 没配允许名单/配对 | `hermes pairing list` 检查，配 `allow_admin_from` 与 `user_allowed_commands` |
| 给了普通用户全部命令 | 未设 `user_allowed_commands` 时该范围处于不限制模式 | 显式列出允许的命令 |
| 手机上权限太大 | 工具集是全局的 | 用 `platform_toolsets.<平台>` 按平台收窄 |
| 一个平台出问题怀疑内核坏了 | 分不清「平台适配器」与「内核」 | 先在 CLI 复现同样任务：CLI 正常就是平台层问题 |

## 试一试

- [ ] 跑 `hermes gateway list`，确认当前 profile 的网关状态，把输出记进 `journal/`
- [ ] 选一个你最可能用的平台，读官方对应的单页文档，写下它需要的凭证类型
- [ ] 给自己设计一条权限方案：哪几个人能用、能用哪些命令、哪些命令永远禁用
- [ ] 判断：公司群里放一个能读内部仓库的 Hermes，你要先配哪两道闸？

## 下一步

- [[L50]] —— 安全模型与审批：把「危险命令怎么办」讲透
- [[L51]] —— 密钥、凭证池与多 profile：多平台多身份时的隔离
- [[L34]] —— 无人值守流水线：把网关、cron、webhook 拼成产线
- 想深入：[[src:gateway-messaging]]（各平台逐页配置说明）

## 出处

- [[src:gateway-messaging]] Messaging Gateway — https://hermes-agent.nousresearch.com/docs/user-guide/messaging
- [[src:security]] Security — https://hermes-agent.nousresearch.com/docs/user-guide/security
- [[src:slash-commands]] Slash Commands Reference — https://hermes-agent.nousresearch.com/docs/reference/slash-commands
