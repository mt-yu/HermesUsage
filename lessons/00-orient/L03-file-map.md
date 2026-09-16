---
id: L03
title: 文件地图：哪个文件管什么
stage: 0
level: 入门
minutes: 15
prereq: [L00]
tags: [SOUL.md, MEMORY.md, USER.md, config.yaml, 上下文文件]
sources: [which-file, context-files, configuration]
updated: 2026-09-16
---

# L03 · 文件地图：哪个文件管什么

> **一句话**：Hermes 的「大脑」不是一个文件，而是六个各司其职的文件；搞错文件是新手最常见的挫败来源。

## 你将学会

- 说出 SOUL.md / USER.md / MEMORY.md / 项目上下文文件 / config.yaml / .env 各自的唯一职责
- 解释「我刚说的话它怎么就忘了」这个经典困惑背后的**冻结快照**机制
- 用 `hermes config path` / `env-path` / `hermes memory status` 定位这些文件
- 判断一条信息应该写进哪个文件（而不是乱塞）

**前置**：L00 · **预计耗时**：15 分钟

## 先动手

```bash
ls "$HERMES_HOME" | head -30
hermes config path
hermes config env-path
hermes memory status
```

你应该看到（本机真实输出，节选）：

```
config.yaml
hooks
memories
sandboxes
sessions
shared-state.db
skills
...
C:\Users\28189\AppData\Local\hermes\config.yaml
C:\Users\28189\AppData\Local\hermes\.env
Memory status
────────────────────────────────────────
  Built-in (MEMORY.md / USER.md):
    Memory injection:   enabled ✓
    User profile:       enabled ✓
    Memory tool:        enabled ✓
  Provider:  (none — built-in only)
```

**注意**：`memories/` 目录现在可能是**空的** —— 记忆不是装完就有的，是你告诉它、
它才会写。这一课后面会解释。

## 原理

### 六文件总表

| 文件 | 装什么 | 谁写 | 什么时候被它看到 | 位置 |
|---|---|---|---|---|
| **SOUL.md** | agent 的**人格与语气**（它「是谁」） | 你（Hermes 只在不存在时种一份模板，永不覆盖） | 系统提示的**第 1 号槽位**，会话开始时 | `$HERMES_HOME/SOUL.md`（**不是**工作目录） |
| **USER.md** | **你**是谁：姓名、角色、偏好、沟通方式 | agent 自己（用 `memory` 工具） | 会话开始时作为**冻结快照**注入 | `$HERMES_HOME/memories/` |
| **MEMORY.md** | agent 自己的笔记：环境事实、项目约定、工具怪癖 | agent 自己（同上） | 同上，冻结快照 | `$HERMES_HOME/memories/` |
| **`.hermes.md`** | **项目**规则与约定 | 你 / 项目作者 | 启动时注入，**向上找到 git 根**，优先级最高 | 你的项目里 |
| **AGENTS.md** | 同上的通用版（给多个 agent 共用） | 你 / 项目作者 | 启动时注入，**只看当前目录** | 你的项目里 |
| **config.yaml** / **.env** | 设置 / 密钥 | 你（用 `hermes config set`） | 进程启动时 | `$HERMES_HOME/` |

一句话记忆法：[[src:which-file]]

- **SOUL.md 是它「是谁」** —— 该跟着你到处走的，放这里
- **USER.md 是「你是谁」** —— agent 替你维护
- **MEMORY.md 是它「学到什么」** —— agent 自己维护
- **`.hermes.md` / AGENTS.md 是「这个项目要什么」** —— 属于项目的放这里

### 关键机制：记忆是「冻结快照」

**症状**：你告诉它「我叫小明」，它当场记住了；但下一轮它的行为好像又不知道你叫小明？

**真相**：记忆在会话开始时被**一次性快照**进系统提示，中途不再刷新。
它在会话中保存你的名字**确实成功了**（已落盘），但系统提示里那一块还是会话开始时的状态。[[src:which-file]]

为什么要这样设计？**为了不破坏 prompt 缓存**。系统提示每轮变一次，缓存就得重建一次，
成本立刻上一个量级（L52 会展开讲）。所以官方选择：宁可让你开新会话才看到更新。

**实践结论**：

| 你想干的事 | 正确做法 |
|---|---|
| 让它记住一条事实 | 直接说「记住：我偏好简洁回答」，它自己写进 USER.md / MEMORY.md |
| 让它现在就按新记忆行动 | 开新会话（记忆会在新会话的系统提示里） |
| 改它的说话风格 | 编辑 `$HERMES_HOME/SOUL.md`，然后**重开会话** |
| 给项目立规矩 | 在项目里放 `.hermes.md`，然后**重开会话** |
| 临时换个风格玩一下 | 用 `/personality` 斜杠命令（会话级覆盖，不用改文件） |

### 只加载「一个」项目上下文文件

每个会话只加载**一个**项目上下文文件，**首个命中者胜出**：

```
.hermes.md  →  AGENTS.md  →  CLAUDE.md  →  .cursorrules
```

（`SOUL.md` 不在这条链里，它独立且总是加载。）[[src:context-files]]

**推论（本项目就踩过）**：`.hermes.md` 会向上走到 git 根，所以在
`lessons/02-core/` 这种子目录里运行也能读到项目规则；而 `AGENTS.md` 只在
「cwd 恰好是它所在目录」时生效。**如果你希望规则在任何子目录都生效，用 `.hermes.md`。**

> 本仓库就是这么做的：规则写在 [`.hermes.md`](../../.hermes.md) —— 一份，且能在任何子目录生效。
> （本仓库刻意**不**再放一份 `AGENTS.md`：两份规则必然分叉，而 `.hermes.md` 优先级更高、覆盖面更广。）

## 亲手验证

### 验证一：项目上下文文件确实按「首个命中」生效

```bash
# 在仓库根目录（有 .hermes.md）
hermes chat -q "用一句话说出你在本目录读到的项目规则里，关于引用格式的要求"

# 在任意非项目目录
cd ~ && hermes chat -q "你现在的项目上下文里有规则文件吗？"
```

| 你观察到的 | 说明什么 |
|---|---|
| 根目录里它能说出 `.hermes.md` 里的规则 | 项目上下文确实被注入 |
| 换目录后说不出来 | 上下文是「按目录」而非「全局」的 |

### 验证二：记忆是冻结快照

```bash
# 第 1 次会话：告诉它一件事
hermes chat -q "请记住：我在做的项目叫 HermesUsage。记完告诉我你把它写在哪个文件。"

# 第 2 次会话：直接问
hermes chat -q "我在做的项目叫什么？"
```

| 你观察到的 | 说明什么 |
|---|---|
| 它说存进了 USER.md 或 MEMORY.md | 记忆由 agent 自己写，不是你手改 |
| 新会话里它能答上来 | 冻结快照在**下一个**会话生效 |

顺手确认落盘：

```bash
ls "$HERMES_HOME/memories"     # 现在应该有文件了
```

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 「我把自己的偏好写进 SOUL.md，USER.md 还是空的」 | SOUL.md 和 USER.md 是两套系统，互不喂饭 | 想让 agent 记住你 → 告诉它，让它写记忆；SOUL.md 只管语气人格 |
| 「我刚说的它下轮就忘」 | 冻结快照机制 | 同会话内它**能**用（在上下文里）；要改注入块就开新会话 |
| 「编辑了 AGENTS.md 但它没反应」 | 上下文在会话开始时组装 | 重开会话 |
| 「规则在子目录不生效」 | AGENTS.md 只认当前目录 | 改用 `.hermes.md`（向上走到 git 根） |
| 「`.hermes.md` 和 `AGENTS.md` 我都写了，只有一份生效」 | 首个命中者胜出 | 只维护一份，另一份留指针 |
| 文件太长被截断 | 每个上下文文件上限 20,000 字符，超出会头尾截断 | 拆成多个技能，别硬塞一个文件 |

## 试一试

- [ ] 打开 `hermes config path` 指向的 `config.yaml`，找出现在用的模型名（只读，别改）
- [ ] 让它记住三条关于你的偏好，然后开新会话验证它是否记得
- [ ] 在 `$HERMES_HOME/SOUL.md` 里加一句语气要求，感受一下「人格」和「记忆」的区别
- [ ] 把这一课的六文件总表默写进 `journal/`，然后对照检查漏了哪个

## 下一步

- [[L13]] —— 把记忆系统讲透：容量上限、`write_approval`、跨会话检索
- [[L14]] —— 把项目上下文文件讲透：`.hermes.md` / SOUL.md / `@` 引用
- [[L15]] —— 技能系统：当「一个文件」不够用时，怎么把知识拆成按需加载的技能

## 出处

- [[src:which-file]] Which File Does What? — https://hermes-agent.nousresearch.com/docs/user-guide/which-file-does-what
- [[src:context-files]] Context Files — https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
- [[src:configuration]] Configuration — https://hermes-agent.nousresearch.com/docs/user-guide/configuration
