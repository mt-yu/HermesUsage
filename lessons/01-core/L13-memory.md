---
id: L13
title: 记忆系统：它怎么记住你
stage: 1
level: 入门
minutes: 20
prereq: [L03, L12]
tags: [记忆, MEMORY.md, USER.md, 冻结快照, session_search]
sources: [memory, which-file, memory-providers]
updated: 2026-09-16
---

# L13 · 记忆系统：它怎么记住你

> **一句话**：记忆是**有容量上限的、由它自己维护的**两小块笔记；它的价值不在「记得多」，而在「记得准」。

## 你将学会

- 说出 MEMORY.md 与 USER.md 的分工和各自的字符上限
- 解释 `memory` 工具的三种动作，以及为什么**没有 read**
- 用「会话边界」思维使用记忆：什么时候它是资产，什么时候纯属浪费上下文
- 亲手让 agent 写一条记忆，并从磁盘和下一个会话两个角度验证它

**前置**：[[L03]]、[[L12]] · **预计耗时**：20 分钟

## 先动手

在交互界面里说这一句：

```
记住：我是中国开发者，偏好中文回答和能直接复制的命令，不喜欢长篇铺垫。
```

它应当告诉你已经保存。然后**开一个新会话**再问：

```bash
hermes                      # 新会话
#   ❯ 你记得我的什么偏好吗？
```

你应该看到它复述了刚才那条偏好。

再直接看磁盘（本机真实结构）：

```bash
ls "$HERMES_HOME/memories/"
hermes memory status
```

## 原理

### 两个文件，两种归属

| 文件 | 装什么 | 字符上限 |
|---|---|---|
| **MEMORY.md** | agent 自己的笔记 —— 环境事实、约定、学到的东西 | **2,200 字符**（约 800 tokens） |
| **USER.md** | 用户画像 —— 你的偏好、沟通风格、期望 | **1,375 字符**（约 500 tokens） |

两者都在 `~/.hermes/memories/`，在会话开始时作为**冻结快照**注入系统提示。
agent 通过 `memory` 工具管理自己的记忆。[[src:memory]]

**一句话记忆法**：MEMORY.md 是「它学到什么」，USER.md 是「你是谁」。[[src:which-file]]

### 记忆长什么样（系统提示里的真实形态）

```
══════════════════════════════════════════════
MEMORY (your personal notes) [67% — 1,474/2,200 chars]
══════════════════════════════════════════════
User's project is a Rust web service at ~/code/myapi using Axum + SQLx
§
This machine runs Ubuntu 22.04, has Docker and Podman installed
§
User prefers concise responses, dislikes verbose explanations
```

要点：有**表头**（哪个库、用了多少容量），条目之间用 `§` 分隔，条目可以多行。
**agent 能看见自己还剩多少容量** —— 这是它能主动整理的前提。[[src:memory]]

### `memory` 工具的三个动作（注意：没有 read）

| 动作 | 干什么 |
|---|---|
| **add** | 新增一条 |
| **replace** | 用 `old_text` 子串匹配后替换（**新内容同样受上限约束**） |
| **remove** | 用 `old_text` 子串匹配后删除 |

**为什么没有 read**：因为记忆在会话开始时已经自动注入系统提示了 —— 它在上下文里
就能看到，不需要再读一次。[[src:memory]]

### 满了会怎样：报错，而不是偷偷丢

> 内存**不会自动压缩**。当一次写入会超限时，`memory` 工具**返回错误**，而不是悄悄丢掉条目。
> 然后 agent 自己腾地方 —— 在同一个回合里合并或删除条目，再重试。

`replace` 也一样受上限约束：用一个更长的条目替换，同样可能溢出。[[src:memory]]

**这解释了一个现象**：有时你会看到它在保存记忆前后「顺便整理了一下」。那不是废话，
是在腾空间。

### 为什么记忆需要「会话边界」

整个记忆系统是围绕会话**结束**那一刻建的：`MEMORY.md` / `USER.md` 把关键点带进下一会话，
`session_search` 在旧上下文消失后补上缺口。在一个会话内部，这套机器**没有理由运转**
（重要的东西都还在活上下文里）。[[src:memory]]

**实践**：

| 场景 | 做法 |
|---|---|
| 任务收尾 / 换话题 / 一天开始 | 跑 `/new` |
| 想立刻让它把经验沉淀成记忆/技能 | 跑 `/refine` 或明确说「把这条记下来」 |
| 需要找很久以前聊过的东西 | 让它用 `session_search`（跨会话全文检索） |
| 两个 agent 共用一个 `$HERMES_HOME` | **不要**。两个写者会把彼此的条目搅在一起 → 给第二个 agent 一个独立 profile |

`hermes memory status` 能看到当前生效的存储与已装的记忆后端插件。[[src:memory]] [[src:memory-providers]]

### 什么时候该上「记忆后端插件」

内置记忆是**有界且精心维护**的（就那 3,575 字符）。当你需要的是
「跨会话的用户建模 / 深度个性化 / 大规模长期记忆」时，才考虑外挂后端：
Honcho、OpenViking、Mem0、Hindsight、Holographic、RetainDB、ByteRover、Supermemory。[[src:memory-providers]]

**判据**：先问自己「我要的是它记住**几条关键事实**，还是要它**理解我这个人**」。
前者用内置记忆就够，后者才需要插件。

## 亲手验证

### 验证一：记忆确实写到了磁盘上的文件

```bash
hermes                      # 说一句：记住：我最常用的目录是 D:/work
ls -la "$HERMES_HOME/memories/"
grep -rn "D:/work" "$HERMES_HOME/memories/" || echo "（没找到，看看是不是写进了别的条目）"
```

### 验证二：冻结快照 —— 同一个会话内不刷新

```bash
hermes
#   ❯ 记住：我的项目代号是 ProjectX
#   ❯ 你现在的系统提示里，记忆块中有没有 ProjectX？  ← 大概率说没有
#   ❯ （退出，再开一个新会话）你记得我的项目代号吗？  ← 这次有了
```

| 你观察到的 | 说明什么 |
|---|---|
| 同会话内看不到刚写的条目 | 系统提示是冻结快照（为了保住缓存） |
| 新会话里能看到 | 记忆在会话开始时重新载入 |
| 但同会话内它**仍然能用**这个信息 | 因为它还在对话上下文里，只是不在「记忆块」里 |

### 验证三：看它怎么处理「放不下」

```bash
hermes
#   ❯ 请往记忆里存一条很长的内容（贴 3000 字）
```

观察它的反应：它应该会报容量不足，然后**自己合并/删除旧条目**再重试 ——
而不是假装存好了。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 「我告诉它我的名字，下一轮又像不知道」 | 冻结快照 | 开新会话即生效；同会话内它仍能用（在上下文里） |
| 记忆里塞了长文档 | 上限只有 2,200 / 1,375 字符 | 放「指针」：文件路径 + 一句话，别放全文 |
| 更新一条记忆后发现别的不见了 | 写入超限，它自己腾了空间 | 用 `/refine` 或明确说「合并这两条」 |
| 两个 agent 共用一个 home，行为混乱 | 多写者互相污染 | 给第二个 agent 独立 profile |
| 期望记忆能代替检索 | 上限太小 | 大量历史用 `session_search`；长期画像用记忆后端插件 |
| 把「项目规则」写进记忆 | 项目规则该进 `.hermes.md` | 见 [[L14]] |
| 记忆内容与事实不符还留着 | 没人复核 | 定期让它念一遍记忆，删错的（这是很好的 5 分钟周维护） |

## 试一试

- [ ] 让它写 3 条关于你的记忆，然后开新会话验证；再把其中一条改得更简洁
- [ ] 跑一次「记忆体检」：让它把 MEMORY.md 与 USER.md 逐条读给你，你标记保留 / 删除
- [ ] 找到一件你反复交代它的事，判断它应该变成**记忆**（事实）还是**技能**（流程）—— 答案见 [[L15]]
- [ ] 检查 `hermes memory status`，确认你没有不小心启用两个记忆后端

## 下一步

- [[L14]] —— 项目规则该放哪：`.hermes.md` 与记忆的分工
- [[L15]] —— 流程类的知识不要塞记忆，塞技能
- [[L53]] —— 记忆相关故障排查
- 想深入：[[src:memory]]（容量、`write_approval`、检索机制）、[[src:memory-providers]]（八个后端插件对比）

## 出处

- [[src:memory]] Persistent Memory — https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- [[src:which-file]] Which File Does What? — https://hermes-agent.nousresearch.com/docs/user-guide/which-file-does-what
- [[src:memory-providers]] Memory Providers — https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers
