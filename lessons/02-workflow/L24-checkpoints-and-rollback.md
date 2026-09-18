---
id: L24
title: "检查点与回滚：干坏事了怎么办"
stage: 2
level: 进阶
minutes: 15
prereq: [L11, L21]
tags: ["checkpoints", "rollback", "影子仓库", "备份"]
sources: [checkpoints, faq]
updated: 2026-09-16
---

# L24 · 检查点与回滚：干坏事了怎么办

> **一句话**：它在改你文件之前可以先拍一张快照，出事时一条 `/rollback` 退回去 —— 但快照默认是关的，你得先确认它开着。

## 你将学会

- 用 `hermes checkpoints` 判断当前有没有可回滚的快照，用 `--checkpoints` 打开它
- 说清哪些动作会触发快照，以及为什么你自己的手改默认不会被覆盖
- 亲手验证「没带开关时它改了文件却没留回滚点」这个边界
- 在检查点之外再加一层：危险命令审批与 `hermes backup` 整机备份

**前置**：[[L11]]、[[L21]] · **预计耗时**：15 分钟

## 先动手

```bash
hermes checkpoints      # 先看现状
```

本机真实输出（干净机器上就是这样）：

```
Checkpoint base: C:\Users\28189\AppData\Local\hermes\checkpoints
Total size:      0 B
  store/         0 B
  legacy-*       0 B
Projects:        0
```

然后带着开关跑一次会话，让它去改文件：

```bash
hermes chat --checkpoints -q "把 notes.md 里「已完成」那一行删掉，并把标题改成「项目笔记（已整理）」，其它不动" -Q
hermes checkpoints
```

```
完成。已删除「- 已完成：把日志级别改成 info」这一行，并把标题改为「# 项目笔记（已整理）」。
```

```
Checkpoint base: C:\Users\28189\AppData\Local\hermes\checkpoints
Total size:      27.1 KB
  store/         27.1 KB
  legacy-*       0 B
Projects:        1

  WORKDIR                                                       COMMITS    LAST TOUCH  STATE
  C:\Users\28189\AppData\Local\Temp\hu-demo                           1       11s ago  live
```

那个目录多了一条快照 —— 这就是出事时你能回去的地方。[[src:checkpoints]]

## 原理

### 默认是关的

检查点是**选择加入**的功能：从 v2 起默认关闭（多数人不用 `/rollback`，而影子存储会随时间变大）。两种开法：

```bash
hermes chat --checkpoints          # 只这一次会话
```

```yaml
# ~/.hermes/config.yaml
checkpoints:
  enabled: true
```

[[src:checkpoints]]

### 什么会触发快照

- **文件工具**：`write_file` 和 `patch`
- **破坏性终端命令**：`rm`、`rmdir`、`cp`、`install`、`mv`、`sed -i`、`truncate`、`dd`、`shred`、输出重定向 `>`，以及 `git reset` / `clean` / `checkout`

同一个目录**每轮最多拍一张**，所以长会话不会疯狂刷快照。[[src:checkpoints]]

### 它在哪、会不会碰你的 .git

一个共享影子 git 仓库放在 `~/.hermes/checkpoints/store/`，**你项目的 `.git` 不会被动**；所有项目共用一个对象库，靠 git 的内容寻址去重。[[src:checkpoints]]

### 回滚命令

| 命令 | 做什么 |
|---|---|
| `/rollback` | 列出所有检查点及改动统计 |
| `/rollback <N>` | 恢复到第 N 个，**保留你的手改**（同时撤销最后一轮对话） |
| `/rollback <N> --all` | 全量恢复，连你的手改一起覆盖 |
| `/rollback diff <N>` | 先看从第 N 个到现在改了什么 |
| `/rollback <N> <file>` | 只恢复一个文件 |

[[src:checkpoints]]

**为什么手改会被保留**：每次成功的 `write_file`/`patch` 会把文件内容哈希记进一张「agent 写入账本」；恢复时，凡是当前内容与账本不符的文件（你后来改过，或 Hermes 从没碰过）会被跳过并列出：

```
✅ Restored to checkpoint a1b2c3d4: before write_file
↷ Kept your hand-edits: src/config.py, notes.md
Use /rollback <N> --all to restore those too.
```

[[src:checkpoints]]

### 有一层它不会覆盖的护栏

危险命令还会先被拦一道：Hermes 把每条命令对照一份危险模式清单检查（递归删除、`DROP TABLE`、把 curl 管道进 shell 等）。

```
Command blocked as dangerous
```

**原因**：检测到潜在的破坏性命令，这是安全特性。**解决**：审阅它要执行的内容后按 `y` 批准；或者让它换一个更安全的做法。它不会静默执行破坏性命令。[[src:faq]]

### 整机级别的兜底

检查点管的是项目文件；如果你的配置、密钥、记忆、会话一起出问题，那是另一层：

```bash
hermes backup                     # 打包整个 ~/.hermes（含 .env 与 auth.json）到 ~/hermes-backup-<时间戳>.zip
hermes import ~/hermes-backup-<时间戳>.zip
hermes profile export work ./work-backup.tar.gz   # 只导出某个 profile（凭证会被剥掉，方便分享）
```

[[src:faq]]

### 它会跳过什么

| 护栏 | 行为 |
|---|---|
| PATH 里没有 `git` | 检查点透明地停用 |
| 目录过宽（`/`、`$HOME`） | 跳过，不拍快照 |
| 目录文件数超过 50,000 | 跳过 |
| 单个文件超过 `max_file_size_mb`（默认 10 MB） | 该文件不进快照 |

[[src:checkpoints]]

## 亲手验证

### 验证一：不带开关改文件，快照不会增加

这是本课最该亲手做一次的实验。

```bash
hermes checkpoints                                          # 记下 Projects 与 COMMITS 数字
hermes chat -q "把 notes.md 的标题行改成「# 项目笔记（第二次改动）」，其它不动" -Q
hermes checkpoints                                          # 再看一次
```

本机真实输出：

```
标题行已改为「# 项目笔记（第二次改动）」，其余内容未动。
```

```
  WORKDIR                                                       COMMITS    LAST TOUCH  STATE
  C:\Users\28189\AppData\Local\Temp\hu-demo                           1        2m ago  live
```

| 你观察到的 | 说明什么 |
|---|---|
| 文件真的被改了 | 不带开关，它照改不误 |
| `COMMITS` 还是 1，没有增加 | 开关关着时它根本不给你留回滚点 |
| `LAST TOUCH` 没刷新（还是上一次带开关运行的时间） | 那两个数字属于上一次带 `--checkpoints` 的会话 |

**结论**：`/rollback` 有没有东西可退，取决于**你在出事之前**有没有把它打开。

### 验证二：恢复之前先看 diff

```text
/rollback diff 1        # 先看第 1 个检查点到现在改了什么
/rollback 1 src/x.py    # 只想救一个文件
/rollback 1             # 整目录恢复，保留你的手改
```

（`/rollback` 是斜杠命令，要在会话里敲。）先 diff 再恢复，能避免「救回一个文件、毁了三个」这类事故。[[src:checkpoints]]

### 验证三：确认它的两个前提

```bash
git --version                  # 检查点依赖 git；没有它会被静默停用
hermes checkpoints status      # 看 store 大小、项目数、每个项目的状态（live / orphan）
```

| 你观察到的 | 说明什么 |
|---|---|
| `git` 不在 PATH 时检查点无声消失 | 这是透明降级，不是 bug；要么装 git，要么靠 `hermes backup` 兜底 |
| `orphan` 状态 | 那个工作目录已经不在了；清理用 `hermes checkpoints prune`，自动清理不会动 orphan |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `/rollback` 说没有检查点，`hermes checkpoints` 显示 `Projects: 0` | 检查点默认关闭 | `hermes chat --checkpoints`，或配置里 `checkpoints.enabled: true` |
| `↷ Kept your hand-edits: src/config.py`，我改过的文件没被回滚 | 手改默认受保护（写入账本） | `/rollback <N> --all` 强制全量恢复 |
| `Command blocked as dangerous` | 检测到破坏性命令模式（`rm -rf`、`DROP TABLE` 等） | 审阅后按 `y`；或让它换更安全的做法 |
| 回滚完发现对话也对不上了 | 恢复会顺带撤销最后一轮对话 | 这是刻意设计：让上下文和文件保持一致 |
| 大文件没进快照 | 超过单文件上限（默认 10 MB）被排除 | 大文件自己用 git 管；别指望检查点 |
| 在 `$HOME` 或根目录干活时没有检查点 | 过宽的目录被跳过 | 在项目子目录里工作 |
| 一台机器上检查点完全不生效 | PATH 里没有 `git` | 装 git；或用 `hermes backup` 做整机兜底 |
| store 越滚越大 | 每个项目默认保留 20 个快照、总量上限 500 MB、默认保留 7 天 | `hermes checkpoints status` 看占用，`hermes checkpoints prune` 手动瘦身，`clear` 清空 |

## 试一试

- [ ] 在一个有测试的项目里，带 `--checkpoints` 让它改坏一个文件，再用 `/rollback diff` + `/rollback` 救回来
- [ ] 故意手改一个它写过的文件，然后 `/rollback <N>`，确认它提示「Kept your hand-edits」
- [ ] 跑一次 `hermes backup`，记下备份文件位置（升级/迁移时会用到）
- [ ] 检查你的项目是否在 git 里：检查点保的是会话内的一次操作，git 保的是长期历史，两者都要

## 下一步

- [[L12]] —— 会话边界：回滚为什么要顺带撤销最后一轮
- [[L21]] —— 哪些工具会改你的文件，心里要有数
- [[L30]] —— 用 hooks 在危险动作前后插入自己的检查
- [[L50]] —— 审批与危险命令拦截的完整规则
- [[L54]] —— 升级、备份与迁移
- 想深入：[[src:checkpoints]]（store 布局与清理策略）、[[src:faq]]（危险命令与备份恢复）

## 出处

- [[src:checkpoints]] Checkpoints and /rollback — https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback
- [[src:faq]] FAQ & Troubleshooting — https://hermes-agent.nousresearch.com/docs/reference/faq
