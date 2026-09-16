---
id: L20
title: "提问与指挥：把模糊需求变成可验证任务"
stage: 2
level: 进阶
minutes: 20
prereq: [L12, L14]
tags: ["提问", "判据", "prompt-size", "上下文文件"]
sources: [tips, troubleshooting-quality, cli]
updated: 2026-09-16
---

# L20 · 提问与指挥：把模糊需求变成可验证任务

> **一句话**：把「动哪里 + 怎么算做完 + 拿什么当证据」一次说清，它就从猜谜变成执行。

## 你将学会

- 用「范围 / 判据 / 证据」三个零件，把一句模糊需求改写成它自己会去核对的任务
- 用 `--query-file` 把长提示、代码块、报错原文原样送进去，不被 shell 吃掉
- 跑 `hermes prompt-size` 量出每次对话的固定成本，并据此决定要关掉哪些工具集
- 遇到「它变笨了」时，先按检查清单排除环境原因，再回头改提问

**前置**：L12、L14 · **预计耗时**：20 分钟

## 先动手

同一个目录（只有 `notes.md` 和 `data.csv`）、同一件事，两种问法。下面是真实输出。

问法一，模糊：

```bash
hermes chat -q "帮我优化一下这个文件" -Q
```

```
目录里有两个文件，我不确定你指的是哪个：

- notes.md（项目笔记，TODO 列表）
- data.csv（3 行 CSV 数据）

你要我优化哪一个？
```

问法二，带判据：

```bash
hermes chat -q "读取 notes.md，把其中三条 TODO 改写成 Markdown 表格（列：任务|负责人|截止日；负责人统一写「待定」，截止日统一写 2026-09-21），其余内容保持不变，写回同一个文件；最后用终端命令输出该文件全文作为证据" -Q
```

```
完成。三条 TODO 已改写为 Markdown 表格（任务|负责人|截止日，负责人均为「待定」，截止日均 2026-09-21），其余内容原样保留。文件全文如上，已写回并验证。
```

两次都很快，区别在于：第一次你还要再补一轮，第二次你已经可以自己打开文件核对。**把上下文一次给足，比来回三轮便宜**。[[src:tips]]

## 原理

### 判据式提问的三个零件

| 零件 | 要写清的东西 | 上面那句话里的位置 |
|---|---|---|
| **范围** | 动哪个文件 / 目录 / 系统 | 读取 notes.md |
| **判据** | 什么状态算做完 | 三条 TODO 改写成表格；其余内容保持不变 |
| **证据** | 它用哪个工具自证 | 用终端命令输出该文件全文 |

含糊的提示产生含糊的结果；把文件路径、报错原文、期望行为一次前置，一条写好的消息胜过三轮澄清 —— 报错堆栈可以整段粘进去，它会自己解析。[[src:tips]]

### 长提示怎么送进去

命令行里塞长提示容易被引号和反引号吃掉，改成从文件读：

```bash
hermes chat --query-file prompt.txt
hermes chat --query-file - < prompt.txt
```

`--query-file` 里的内容不经 shell 解释，引号、`$(...)`、反引号按原样到达模型。[[src:cli]]

交互模式下的多行输入用 `Alt+Enter` 或 `Ctrl+J`；在 Windows Terminal 上 `Alt+Enter` 会被终端自己捕获（切换全屏），改用 `Ctrl+J`。[[src:cli]]

### 你自己敲的命令不算它的话

以 `!` 开头的行是 shell 模式：不调用模型、不花 token、不进对话历史，危险命令的审批规则照旧生效。[[src:cli]]

```text
> !git status
> !pytest -x tests/
```

想先自己看一眼再决定要不要交给它，用这个。

### 先量固定成本，再谈提示技巧

```bash
hermes prompt-size
```

本机真实输出（节选）：

```text
Prompt-size breakdown (platform=cli, model=deepseek-v4-pro)

  System prompt total :   22,453 B  (21.9 KB, 22,327 chars)

  Major blocks:
    skills index       :    8,464 B  (8.3 KB)

  Tool schemas         :   41,186 B  (40.2 KB, 25 tools)

  Toolsets by size (tool-schema JSON, largest first):
    toolset                tools      schema
    file                       4     5,619 B  (5.5 KB)
    delegation                 1     4,519 B  (4.4 KB)
    browser                    5     4,407 B  (4.3 KB)
```

工具 schema（41 KB）比系统提示（22 KB）还大，而且**每一轮都带着**。所以「少挂技能、收窄工具集」是在你开口之前就先省下的部分；`/usage` 看运行中的消耗，`hermes prompt-size` 看发车前的固定部分（离线可用）。[[src:tips]]

### 它变笨了，先查这七件事

顺序是按「最常是答案」排的：模型是不是被切到了别的（`/model`）、上下文用量（`/usage`）、被自动检测错的上下文长度、记忆冻结快照、记忆容量与 `session_search`、技能与工具是否还在（`/skills`、`/tools list`）、压缩的副作用。[[src:troubleshooting-quality]]

**先把这七条排除掉，再回头改自己的提问。** 大部分「它变笨了」是环境，不是提示。

## 亲手验证

### 验证一：让它答一个不存在的东西

给一个错误前提，看它是核对还是编造。本机真实输出：

```bash
hermes chat -q "notes.md 里第 4 条 TODO 是什么？只给答案" -Q
```

```
notes.md 里没有 TODO，只有表格中的 3 条任务，不存在第 4 条 TODO。
```

再命令它删一行不存在的数据：

```bash
hermes chat -q "把 data.csv 里日期为 2026-09-04 的那一行删掉并写回文件" -Q
```

```
data.csv 里没有日期为 2026-09-04 的行。文件当前内容只有三行数据：

2026-09-01,widget,3
2026-09-02,gadget,5
2026-09-03,widget,7

没有可删的 2026-09-04 行，文件保持不变。需要我删别的行吗？
```

| 你观察到的 | 说明什么 |
|---|---|
| 它没有编出「第 4 条 TODO」 | 前提与文件冲突时，它会先读文件再回答 |
| 它没有假装删掉一行再报成功 | 判据里写了「写回文件」，它就真的得读到那一行才能写 |
| 它反问「需要我删别的行吗」 | 边界情况它交回给你判断，而不是自己扩大范围 |

### 验证二：把判据从「做完了」改成「拿证据」

把上面第二条提示的最后半句去掉再跑一次，比较两次的回答：带证据的那次你会拿到文件全文，不带的那次你只能相信它说的「完成」。

### 验证三：量一次自己的固定成本

```bash
hermes prompt-size
```

| 你观察到的 | 说明什么 |
|---|---|
| 工具 schema 常常比系统提示还大 | 关掉不用的工具集是立竿见影的降本动作 |
| `skills index` 是单独一块 | 技能越多，每一轮带着的索引越大 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `目录里有两个文件，我不确定你指的是哪个` | 提示里没有范围 | 把文件路径写进提示；或先 `!ls` 看一眼再发问 |
| 提示里的 `$(...)`、反引号到手后变了样 | 被 shell 先解释了一遍 | `hermes chat --query-file prompt.txt` |
| Windows Terminal 里 `Alt+Enter` 不换行，反而切了全屏 | 该组合键被终端捕获 | 用 `Ctrl+J` |
| 「你说没有第 4 条，可我要的就是第 4 条」 | 前提本身是错的 | 先让它列出现状，再提要求 |
| 长会话后半段变慢、丢细节 | 上下文压力，压缩已经触发 | `/compress` 主动压缩，或 `/new` 开新会话 |
| 上一轮说过的事它不记得 | 那部分已经不在本次会话的上下文里 | 用 `hermes -c` 续原会话，或把关键事实重贴一遍 |
| 换过模型之后它像换了一个人 | `/model <name>` 默认只作用于当前会话 | `/model` 确认当前模型；要写回配置加 `--global` |
| 反复交代同一个规范 | 每次都靠对话说 | 写进 `AGENTS.md`（见 [[L14]]） |

## 试一试

- [ ] 把今天真正想让它做的一件事，按「范围 / 判据 / 证据」写成一条提示，跑一次
- [ ] 用 `--query-file` 送一条含引号和 `$(...)` 的提示，确认原样到达
- [ ] 跑 `hermes prompt-size`，写下三个你愿意关掉的工具集，然后 `hermes tools` 关掉它们
- [ ] 挑一个你反复交代的规范写进项目根目录的 `AGENTS.md`

## 下一步

- [[L14]] —— 复述型规则写进上下文文件，比每轮重复便宜
- [[L13]] —— 事实类的交给记忆，跨会话生效
- [[L21]] —— 判据定好之后，让它真的动手去碰终端、文件和浏览器
- [[L23]] —— 无人值守时判据更重要：cron 里的 agent 没有对话记忆
- 想深入：[[src:tips]]（提问、成本、快捷键）、[[src:troubleshooting-quality]]（七步诊断清单）

## 出处

- [[src:tips]] Tips & Best Practices — https://hermes-agent.nousresearch.com/docs/guides/tips
- [[src:troubleshooting-quality]] Troubleshooting: "My Agent Feels Dumber" — https://hermes-agent.nousresearch.com/docs/guides/troubleshooting-agent-quality
- [[src:cli]] CLI Interface — https://hermes-agent.nousresearch.com/docs/user-guide/cli
