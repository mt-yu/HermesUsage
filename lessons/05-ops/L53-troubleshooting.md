---
id: L53
title: "排障手册：它变笨了 / 工具不见了"
stage: 5
level: 进阶
minutes: 25
prereq: [L12, L13]
tags: ["排障", "日志", "上下文", "项目技能", "安全模式"]
sources: [troubleshooting-quality, faq, cli-symbols, cli-commands]
updated: 2026-09-16
---

# L53 · 排障手册：它变笨了 / 工具不见了

> **一句话**：感觉它变笨时按固定顺序查七件事（模型 → 上下文 → 检测到的窗口 → 记忆快照 → 技能与工具集 → 压缩），九成答案在第一、二条。

## 你将学会

- 按「命中概率从高到低」的顺序走完官方那七步诊断清单
- 用 `hermes doctor` / `hermes logs` 拿到现场证据，而不是凭感觉猜
- 复现「项目技能不加载」这个真实故障，并定位到它的第二个前提条件
- 读懂 TUI 状态栏上的 `cmp N`、`⛓ N`、`⚠ approval required` 这些符号再描述症状
- 用 `--safe-mode` 二分法判断问题出在你的配置还是 Hermes 本身

**前置**：[[L12]]、[[L13]] · **预计耗时**：25 分钟

## 先动手

先做一次体检，把已知问题摊在桌面上：

```bash
hermes doctor
hermes logs list
```

本机真实输出（节选）：

```
◆ Security Advisories
  ✓ No active security advisories

◆ Python Environment
  ✓ Python 3.11.15
  ✓ SQLite 3.53.1
  ✓ Virtual environment active
  ✓ Version files consistent (0.21.3)
...
◆ Configuration Files
  ✓ ~/AppData/Local/hermes/.env file exists
  ✓ ~/AppData/Local/hermes/config.yaml exists
  ⚠ Config version outdated (v33 → v45) (new settings available)
...
  1. Run 'hermes doctor --fix' or 'hermes setup' to migrate config
  2. Run 'hermes setup' to configure missing API keys for full tool access
```

```
Log files in ~/AppData/Local/hermes/logs/:

  agent.log                  239.7KB   just now
  desktop.log                 10.1KB   just now
  errors.log                  11.3KB   just now
  gui.log                      4.3KB   1m ago
  update.log                    656B   50m ago
```

`hermes doctor` 是「诊断配置与依赖问题」的入口，`hermes logs list` 告诉你现场记录在哪。[[src:cli-commands]]

## 原理

### 七步诊断清单（按命中概率排序）

官方给的顺序就是下面这个顺序，别跳步：[[src:troubleshooting-quality]]

| # | 症状 | 第一步命令 | 可能的真实原因 |
|---|---|---|---|
| 1 | 全面变浅、代码质量下降 | `/model`、`/status` | 会话用的模型和你以为的不是同一个（`/model <name>` 默认只对当前会话生效） |
| 2 | 开头很好，后面变慢/被截断 | `/usage`、`/context` | 上下文压力：该 `/compress` 或 `/new` 了 |
| 3 | 第一次长对话就撞上限 | 启动行的 Context limit、`/usage` | 自动检测的上下文长度不对，显式设 `model.context_length` |
| 4 | 「我让它记的，它忘了」 | 不用查，看时间 | 记忆是**会话开始时的冻结快照**，下一轮会话才进系统提示 |
| 5 | 「上周聊过的事它不记得」 | 让它 `session_search` | 记忆有界（MEMORY.md 约 2,200 字符、USER.md 约 1,375 字符），不是转写稿 |
| 6 | 丢了某项能力 | `/skills`、`/reload-skills`、`/tools list`、`/context all` | 技能被移除，或本次会话的工具集被裁过 |
| 7 | 长会话之后只剩梗概 | `/usage`、`/context` | 压缩已经发生，细节被摘要替换（默认保护最近 20 条 + 开头 3 条） |

第 7 条要补一句：默认 `in_place: true` 的压缩是**非破坏性**的 —— 同一个会话 id 保留，被压缩的轮次软归档，仍然可以用 `session_search` 搜到。[[src:troubleshooting-quality]]

### 拿证据的三个命令

```bash
hermes doctor                     # 配置 / 依赖 / 服务健康
hermes logs                       # 默认看 agent.log 最后 50 行
hermes logs errors --since 1h     # 只看最近一小时的错误日志
hermes logs --component gateway   # 按组件过滤
```

`hermes logs` 支持 `-n`、`-f`、`--level`、`--session`、`--since`、`--component`，可读的日志名是 `agent` / `errors` / `gateway` / `gui` / `desktop` / `list`。[[src:cli-commands]] 官方 FAQ 里给的等价做法是直接看文件（`cat ~/.hermes/logs/gateway.log | tail -50`）—— 两种都行，`hermes logs` 的好处是带过滤。[[src:faq]]

### 先描述症状，再谈原因：状态栏符号表

TUI 底部那一行不是装饰，它把「到底发生了什么」写在了脸上：[[src:cli-symbols]]

| 符号 | 含义 | 排障时意味着 |
|---|---|---|
| `cmp N` | 本会话已自动压缩 N 次 | 细节丢失多半是它干的（清单第 7 条） |
| `⏱ 12s/3m 45s` / `⏲` | 本轮耗时 / 会话总耗时（`⏲` 表示本轮已结束） | 变慢是可量化的，别凭感觉 |
| `⛓ N` | 当前活跃子代理数 | 它「卡住」可能是在等子代理 |
| `▶ N` | 正在跑的 `/bg` 任务数 | 同上 |
| `⚠ approval required` | 有工具在等你的明确同意 | 「它不干活了」常常是在等你回答审批 |
| `⚠ YOLO` | 审批已被绕过 | 出了事要留证据时先关掉它 |
| `✕` / `⚠` / `✓` / `•` | 错误 / 警告 / 成功 / 提示通知 | 先看带 `✕` 的那条 |

### 二分法：用 `--safe-mode` 判断是谁的问题

`hermes chat --safe-mode` 会关掉**所有**自定义项 —— 用户配置、规则与记忆注入、插件、shell 钩子、MCP 服务器（等价于同时 `--ignore-user-config` 和 `--ignore-rules`）。它的用途就是回答一个具体问题：「这是我的配置的问题，还是 Hermes 本身的问题？」[[src:cli-commands]]

配合 `hermes dump`（可复制的环境摘要，用来看清你到底配了什么）会更省事。[[src:cli-commands]]

### 报 bug 需要带上什么

官方 FAQ 的收尾要求：操作系统、Python 版本（`python3 --version`）、Hermes 版本（`hermes --version`）、完整错误信息。[[src:faq]]

## 亲手验证

### 验证一：亲手造一次「项目技能不加载」

**现象**：项目里明明有 `.hermes/skills/<你的技能>/SKILL.md`，`hermes skills list` 里却看不到。

第二个前提条件通常被忽略：**除了 `hermes skills trust .`，还要求会话的工作目录落在项目内** —— 项目根解析优先采用会话工作目录（`TERMINAL_CWD`），落在家目录就会解析成 `None`，项目技能自然不加载。

用官方代码路径自查（本机实测的两次运行，唯一差别是 `TERMINAL_CWD`）：

```bash
HH="C:/Users/28189/AppData/Local/hermes"      # Windows；macOS/Linux 用 ~/.hermes
cd /d/Projects/ai_projects/HermesUsage          # 你的项目目录

# ① 会话工作目录指向别处（本机 TERMINAL_CWD=C:\Users\28189）
"$HH/hermes-agent/venv/Scripts/python" -c "
import sys; sys.path.insert(0, r'C:/Users/28189/AppData/Local/hermes/hermes-agent')
from agent.skill_utils import find_project_root
print('project root (TERMINAL_CWD 在别处):', find_project_root())
"
# 真实输出：project root (TERMINAL_CWD 在别处): None

# ② 去掉这个变量，让项目根按进程 cwd 解析
env -u TERMINAL_CWD "$HH/hermes-agent/venv/Scripts/python" -c "
import sys; sys.path.insert(0, r'C:/Users/28189/AppData/Local/hermes/hermes-agent')
from agent.skill_utils import find_project_root
print('project root (TERMINAL_CWD 未设):', find_project_root())
"
# 真实输出：project root (TERMINAL_CWD 未设): D:\Projects\ai_projects\HermesUsage
```

**结论**：`None` 就是「项目技能不会加载」的直接证据；把它变成项目路径，项目技能才会进索引。官方 FAQ 的排查顺序也是先定位「工作目录 / 环境变量」这类环境事实，再谈配置本身。[[src:faq]]

### 验证二：亲手造一次「日志找不到」

**现象**（本机实测，照抄）：

```
Log file not found: C:\Users\28189\AppData\Local\Temp\hermes-hookdemo\logs\errors.log
(Logs are created when Hermes runs — try 'hermes chat' first)
```

**真实原因**：这一行里的路径根本不是默认 home —— 环境里的 `HERMES_HOME` 被指向了另一个目录，于是 CLI 去那里找日志。`hermes logs list` 打印的是默认 home 的日志目录，两者对不上时就会看到这种「明明有日志却找不到」。

```bash
echo "$HERMES_HOME"                          # 是不是被改过
hermes logs list                             # 真实日志目录在哪
env -u HERMES_HOME hermes logs errors -n 5   # 用默认 home 再看一次
```

去掉之后本机正常输出（节选）：

```
--- ~/AppData/Local/hermes/logs/errors.log (last 5) ---
2026-09-16 10:54:40,449 WARNING hermes_cli.tools_config: platform 'teams' has no valid toolsets configured (unknown name(s): hermes-teams) - tools will be unavailable. Run `hermes tools` to reconfigure.
```

### 验证三：把警告级别拉出来看

```bash
hermes logs --level WARNING --since 1h
```

本机真实输出里最典型的一条是上面那句 `platform 'teams' has no valid toolsets configured` —— 平台注册了不存在的工具集名，那个平台就少了一批能力。这正是「工具不见了」的一种：不是工具坏了，是名字对不上。[[src:faq]]

| 你观察到的 | 说明什么 |
|---|---|
| `project root: None` | 会话工作目录不在项目内 → 项目技能不加载 |
| `project root: D:\...\HermesUsage` | 工作目录对了，项目根解析成功 |
| `Log file not found: ...\Temp\...` | `HERMES_HOME` 被指向了别处，日志与状态都不在默认 home |
| `platform '...' has no valid toolsets configured` | 工具集名字写错 → 该平台工具缺失 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `Log file not found: ...\logs\errors.log` | `HERMES_HOME` 被指向了另一个目录 | `echo "$HERMES_HOME"`；`hermes logs list` 看真实路径；或临时 `env -u HERMES_HOME hermes logs errors` |
| `platform 'teams' has no valid toolsets configured (unknown name(s): hermes-teams)` | 平台配了不存在的工具集名 | 跑 `hermes tools` 重新配置该平台 |
| 项目技能不加载，`hermes skills list` 里也没有 | ① 没信任；② 会话工作目录不在项目内（`project root` 为 `None`） | `hermes skills trust .`，并**从项目目录启动会话** |
| 「我让它记的，它忘了」 | 记忆是会话开始时的冻结快照 | 这是设计：下一轮会话才进系统提示；本会话内靠对话历史 |
| 「上周说过的事它不记得」 | 记忆有界（约 2,200 / 1,375 字符），只存精炼事实 | 让它 `session_search` 搜历史会话 |
| 长会话后期变笨 | 上下文压力，压缩可能已触发 | `/usage`、`/context` 看占用；`/compress` 或 `/new` |
| 第一次长对话就撞上限 | 自动检测到的上下文长度不对 | 显式设 `model.context_length`；Ollama 要与你设的 `num_ctx` 对齐 |
| 首次运行就 `Error 400` | 模型名不存在或额度不足 | `hermes config show` 看配置、`hermes model` 重选、或用已知可用的模型试一次 |
| `Command blocked as dangerous` | 危险命令检测（设计如此） | 审阅后批准，或让 agent 换更安全的做法 |
| 分不清是配置问题还是 Hermes 的问题 | 自定义项太多 | `hermes chat --safe-mode` 跑一遍二分 |

## 试一试

- [ ] 完整走一遍七步清单，把每一步的观察写进 `journal/`（哪一步命中了你的问题）
- [ ] 在你自己的项目里跑一次上面的 `find_project_root()` 自查，确认它是项目路径而不是 `None`
- [ ] 用 `hermes logs --level WARNING --since 24h` 找出近一天所有的告警，逐条判断要不要处理
- [ ] 遇到一次「它不干活」时，先看状态栏是 `⚠ approval required` 还是 `⛓ N`（子代理在跑），再决定要不要打断
- [ ] 制造一次「记住 X，同一会话它却好像不知道」，验证冻结快照的行为

## 下一步

- [[L12]] —— 会话与斜杠命令：`/usage`、`/context`、`/compress`、`/new` 的完整用法
- [[L13]] —— 记忆系统：冻结快照与容量上限的机制解释
- [[L15]] —— 技能系统：项目技能的两道关（信任 + 扫描）与工作目录前提
- [[L54]] —— 排障之后的下一步：升级、备份、必要时回滚
- 想深入：[[src:troubleshooting-quality]]（七步清单原文）、[[src:cli-symbols]]（符号表全量）

## 出处

- [[src:troubleshooting-quality]] Troubleshooting: "My Agent Feels Dumber" — https://hermes-agent.nousresearch.com/docs/guides/troubleshooting-agent-quality
- [[src:faq]] FAQ & Troubleshooting — https://hermes-agent.nousresearch.com/docs/reference/faq
- [[src:cli-symbols]] CLI Symbols Glossary — https://hermes-agent.nousresearch.com/docs/reference/cli-symbols
- [[src:cli-commands]] CLI Commands Reference — https://hermes-agent.nousresearch.com/docs/reference/cli-commands
