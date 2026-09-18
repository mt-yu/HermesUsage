---
id: L14
title: 上下文文件：你怎么给它下规矩
stage: 1
level: 入门
minutes: 20
prereq: [L03, L12]
tags: [".hermes.md", "AGENTS.md", "SOUL.md", "@引用", "项目规则"]
sources: [context-files, context-references, personality, slash-commands]
updated: 2026-09-16
---

# L14 · 上下文文件：你怎么给它下规矩

> **一句话**：想让规则「每次都自动生效」，就得把它放对文件 —— 而「放对」的唯一判据是：这条规则属于**这个项目**，还是属于**你这个人**。

## 你将学会

- 在 `.hermes.md` / `AGENTS.md` / `CLAUDE.md` / `.cursorrules` / `SOUL.md` 之间做出正确选择
- 解释「首个命中者胜出」与「`.hermes.md` 向上走到 git 根、`AGENTS.md` 只看 cwd」的实际差别
- 用 `@` 引用把文件、目录、git diff、URL 精确注入到某一条消息里
- 用 `/context` 诊断「我的规则文件为什么没生效」

**前置**：[[L03]]、[[L12]] · **预计耗时**：20 分钟

## 先动手

在项目根目录建一个 `.hermes.md`，写两行：

```markdown
# 我的项目规则

- 回复一律用中文，命令保持英文原样。
- 改完代码必须跑 `python -m pytest -q`，通过后才能说“完成”。
```

然后**在子目录里**启动一次，验证它在任何子目录都生效：

```bash
mkdir -p /tmp/cf-demo/sub && cd /tmp/cf-demo
printf '# 项目\n\n- 回答时先说结论。\n' > .hermes.md
cd sub
hermes chat -q "你在当前项目里读到了什么规则？一句话说"
```

你应该看到它复述「回答时先说结论」—— 尽管 cwd 是 `sub/`，规则文件在上一级。

> **注意**：`.hermes.md` 是沿着**当前目录向上找，直到 git 根**；所以顶层规则在子目录
> 依然有效。而 `AGENTS.md` 只在「cwd 恰好是它所在目录」时被读到。[[src:context-files]]

## 原理

### 优先级链：只有一份会被加载

每个会话只加载**一个**项目上下文文件，**首个命中者胜出**：

```
.hermes.md  →  AGENTS.md  →  CLAUDE.md  →  .cursorrules
```

`SOUL.md` **不在这条链里** —— 它总是被独立加载，代表 agent 的身份。[[src:context-files]]

### 选哪个：一张决策表

| 你的目标 | 用 | 为什么 |
|---|---|---|
| 项目规则要在**任何子目录**都生效 | **`.hermes.md`** | 发现过程向上走到 git 根 |
| 同一份规则要给 Claude Code / Codex 也读 | `AGENTS.md` | cwd-only 的约定让它在各工具间可移植 |
| 从 Cursor 迁过来 | `.cursorrules` | 兼容 |
| 想改 agent 的**语气与人格**（跟项目无关） | `SOUL.md`（在 `$HERMES_HOME`） | 身份而非项目规则；永远加载 |
| 只是一次性的语气调整 | `/personality` | 会话级覆盖，不用改文件 |

**反向判据（很重要）**：如果想让它跟着你到处走 → 属于身份 → `SOUL.md`；
如果只在这个项目里成立 → 属于项目 → `.hermes.md`。[[src:context-files]] [[src:personality]]

### 上限与截断

- 每个上下文文件上限 **20,000 字符**（超过会**头尾截断，丢掉中间**，并留 `[...truncated...]` 标记）
- 因此：**规则很长时，正解是拆成技能**（见 [[L15]]），而不是硬塞一个文件

### 安全扫描

所有上下文文件在进入系统提示前会过一遍威胁模式扫描：匹配到提示注入 / promptware 的片段
会被替换成 `[BLOCKED: ...]` 占位符 —— 是**内容**被拦，不是整个文件被拦，
所以文件其余部分照常加载。[[src:context-files]]

### `@` 引用：把内容精确塞进「这一条消息」

在消息里打 `@` 触发补全，Hermes 会把内容展开并附在 `--- Attached Context ---` 段落下：[[src:context-references]]

| 语法 | 注入什么 |
|---|---|
| `@file:path/to/file.py` | 文件内容 |
| `@file:path/to/file.py:10-25` | 指定行范围（1 起始，含端点） |
| `@folder:path/to/dir` | 目录树列表 + 文件元信息 |
| `@diff` | `git diff`（工作区未暂存改动） |
| `@staged` | `git diff --staged` |
| `@git:5` | 最近 N 次提交及补丁（最多 10） |
| `@url:https://example.com` | 抓取并注入网页内容 |

一条消息里可以用多个引用；引用值末尾的 `,` `.` `;` `!` `?` 会被自动去掉。[[src:context-references]]

**和不写引用的区别**：不写引用，它得自己决定要不要读文件（可能读也可能不读）；
写了引用，内容**当场就在这条消息里** —— 对「必须用这个版本的文件」的场景更可靠。

## 亲手验证

### 验证一：`/context` 直接告诉你规则文件为什么没生效

```bash
hermes -c
#   ❯ /context
```

输出末尾的 **Context files** 清单会逐个列出候选文件及其状态：
loaded / truncated over `context_file_max_chars` / shadowed（被更高优先级遮蔽）/
blocked by the injection scan / empty or unreadable / suppressed by the install-tree guard。
这**就是**「我的 CLAUDE.md 为什么被忽略」的官方答案。[[src:slash-commands]]

### 验证二：亲手制造「首个命中者胜出」

```bash
cd /tmp/cf-demo                       # 上一节建的目录，已有 .hermes.md
printf '# AGENTS\n\n- 回答时先说三个感叹号。\n' > AGENTS.md
hermes chat -q "你读到的项目规则是哪一条？"
```

| 你观察到的 | 说明什么 |
|---|---|
| 它复述的是 `.hermes.md` 的内容 | `.hermes.md` 优先级高于 `AGENTS.md`，另一份根本不加载 |

再把它挪到子目录，观察差别：

```bash
mkdir -p /tmp/cf-demo2/a && cd /tmp/cf-demo2/a
printf '# 只在这一层\n\n- 说“收到”。\n' > AGENTS.md
hermes chat -q "你读到了什么项目规则？"
```

### 验证三：`@` 引用确实把内容带进了消息

```bash
hermes chat -q "看一下 @file:sources/registry.yaml 里登记了多少条来源？只说数字"
```

对比不带引用时的行为（它会自己去读文件）—— 两条路都能到终点，但**控制权不同**。

### 验证四：一次性隔离变量

```bash
hermes --ignore-rules      # 跳过全部项目上下文 + SOUL.md + 用户配置 + 插件 + MCP
```

用于判断「问题是出在我的配置，还是 Hermes 本身」。[[src:context-files]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 规则在子目录不生效 | 用了 `AGENTS.md`（只看 cwd） | 改用 `.hermes.md`（向上走到 git 根） |
| 两份规则都写了，只有一份生效 | 首个命中者胜出 | 只维护一份，另一份留指针 |
| 编辑后没反应 | 上下文在会话开始时组装 | 开新会话，并用 `/context` 确认 |
| 文件太长被截断（丢的是中间！） | 20,000 字符上限 + 头尾截断 | 拆成技能；别把长文档塞进去 |
| 规则内容被 `[BLOCKED: ...]` 替换 | 命中威胁模式扫描 | 改掉像提示注入的措辞（例如“忽略之前的指令”） |
| 改了 agent 指令类文件却弹出审批 | 这类文件受保护，写入需要你确认 | 确认后再写；这是有意的护栏 |
| 把「我的偏好」写进 `.hermes.md` | 定位错了：那是跨项目的 | 属于你的偏好 → 让 agent 记进记忆（[[L13]]） |

## 试一试

- [ ] 给一个你真实的项目写一份 `.hermes.md`：包含构建/测试命令、代码风格、禁止事项
- [ ] 用 `/context` 验证它被加载了，并记录它占了多少 token
- [ ] 用 `@git:3` 让它 summarize 你最近三次提交，体会「精准注入」的手感
- [ ] 判断：`SOUL.md` 里应该放哪三样东西？写下你的答案，再对照 [[src:personality]] 修正

## 下一步

- [[L15]] —— 规则文件放不下时，用技能做「按需加载的知识」
- [[L21]] —— 把 `@` 引用与工具组合用于真实任务
- [[L52]] —— 这些上下文文件每一轮都在花 token：理解它们的成本
- 想深入：[[src:context-files]]（完整发现顺序与安全扫描）、[[src:personality]]（SOUL.md 该写什么）

## 出处

- [[src:context-files]] Context Files — https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
- [[src:context-references]] Context References — https://hermes-agent.nousresearch.com/docs/user-guide/features/context-references
- [[src:personality]] Personality & SOUL.md — https://hermes-agent.nousresearch.com/docs/user-guide/features/personality
