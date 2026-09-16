---
id: L54
title: "升级、备份与迁移"
stage: 5
level: 进阶
minutes: 15
prereq: [L01, L12]
tags: ["升级", "备份", "迁移", "checkpoints", "回滚"]
sources: [updating, faq, checkpoints]
updated: 2026-09-16
---

# L54 · 升级、备份与迁移

> **一句话**：升级前先看计划与快照（`hermes update --plan`），升级后按四步复核；备份、检查点、导出是三条不同的退路，别混着用。

## 你将学会

- 用 `hermes update --check` / `--plan` 在不改任何东西的前提下判断「该不该升、升了会重启什么」
- 说出 `hermes update` 的八个步骤，以及语法校验失败时的自动回滚机制
- 区分 `hermes backup`、`hermes profile export`、`checkpoints` 三条退路各自能救什么
- 亲手验证「检查点默认关闭」这个边界，并把它打开
- 走一遍完整回滚流程（`git checkout` → 重装依赖 → 重启 gateway → `hermes config check`）

**前置**：L01、L12 · **预计耗时**：15 分钟

## 先动手

三条都是只读命令，先把自己现在的状态摸清楚：

```bash
hermes --version
hermes update --plan
hermes checkpoints status
```

本机真实输出：

```
Hermes Agent v0.21.3 (2026.9.14) · upstream 05fac10a
Install directory: C:\Users\28189\AppData\Local\hermes\hermes-agent
Install method: git
Python: 3.11.15
```

```
Update plan:
  Install: git (v0.21.3 @ 05fac10a)
  Profiles: default
  Running services to restart (1):
    • serve [default] pid 19788 — desktop
      restart: Desktop app respawns its serve backend
```

```
Checkpoint base: C:\Users\28189\AppData\Local\hermes\checkpoints
Total size:      0 B
  store/         0 B
  legacy-*       0 B
Projects:        0
```

**这三段回答了升级前该问的三个问题**：我现在是什么版本、这次升级会重启哪些服务、以及我有没有事后可退的快照。`--plan` 是只读的：它打印安装类型（git / Docker 镜像 / Nix 包）、所有 profile 上正在运行的 Hermes 服务及其监管方式、以及每个服务会怎么重启。[[src:updating]]

## 原理

### `hermes update` 到底做了哪八件事

[[src:updating]]

1. **升级前快照**：默认存一份轻量状态快照（配对数据、cron、`config.yaml`、`.env`、`auth.json` 等运行时会被改的状态文件），单文件超过 1 GiB 会跳过；因为代码切换与 gateway 重启会碰到每个 profile，**每个 profile 各存一份**。
2. **git pull**：从 `main` 拉代码并更新子模块。
3. **拉取后语法校验 + 自动回滚**：编译九个启动必import的关键文件，任何一个解析失败（比如遗留的冲突标记、被截断的文件）就 `git reset --hard <pre-pull-sha>`，保证你的 shell 还能启动。
4. **装依赖**：`uv pip install -e ".[all]"`。
5. **配置迁移**：检测新增配置项并提示你设置。
6. **桌面端重建（先暂存后替换）**：失败时旧版本原样保留且可启动，更新会报 `⚠ Update partially complete`，`hermes desktop` 可重试。
7. **gateway 自动重启**：先 drain —— 拒绝新回合、等在途工作（聊天回合、cron、API 运行）结束，上限由 `agent.restart_after_turn_timeout` 控制（默认 30 分钟）。
8. **多 profile 复用迁移**：profile ≥ 2 且仍是「每个 profile 一个 gateway」的安装，会被并成单个复用 gateway（有阻塞项就不动，只打印阻塞原因）。

备份档位由 `updates.pre_update_backup` 一个键控制：`quick`（默认）、`full`（quick + 整个 `HERMES_HOME` 的 zip）、`off`。`--backup` 强制一次 full，`--no-backup` 跳过本次全部备份。

> **要能「时点一致地回滚」，用 `--backup`**：quick 快照是找回文件用的，不是代码回滚保险。[[src:updating]]

### 只读预演与收据

```bash
hermes update --check     # 只比较提交，判断有没有更新
hermes update --plan      # 全机器计划：安装类型 + 每个服务的重启方式
```

跑完一次真实更新后会留下机器可读的收据：`~/.hermes/logs/update_receipts/`（保留最近 20 份，`latest.json` 指向最新）。重启阶段之后它会拿每个活着的 gateway 实际在跑的代码跟新代码比对，发现哪个 profile 还在跑旧代码就大声报出来并以非零退出码结束。[[src:updating]]

终端断线也不怕：更新忽略 `SIGHUP`，输出镜像到 `~/.hermes/logs/update.log`（`Ctrl-C` 与关机信号仍然生效，那是你主动取消）。[[src:updating]]

### Windows 上的两条闸门

- 有别的 `hermes.exe` 占着 venv 入口（桌面端后台、另一个 REPL、正在跑的 gateway）→ 更新直接**拒绝**，并给出 PID；确认无影响才用 `--force`。[[src:updating]]
- 有进程正从 venv 的解释器上跑（桌面后台、gateway、Python REPL）→ 另一条闸门拒绝动 venv，**`--force` 不解**，只能用 `--force-venv`。[[src:updating]]

### 回滚：三条命令 + 一次复核

[[src:updating]]

```bash
cd <你的 hermes-agent 目录>
git log --oneline -10              # 找到要回去的提交
git checkout <commit-hash>         # 或 git checkout vX.Y.Z 回到某个 tag
uv pip install -e ".[all]"
hermes gateway restart
hermes config check                # 回滚后可能有不认识的配置项，检查并清掉
```

### 检查点：它不是 git，也不是备份

检查点是**可选的**（默认关闭），由内部的 Checkpoint Manager 维护一个共享的影子 git 库 `~/.hermes/checkpoints/store/`，**不碰**你项目真正的 `.git`。[[src:checkpoints]]

- 触发点：文件工具（`write_file`、`patch`）与破坏性终端命令（`rm`、`rmdir`、`cp`、`install`、`mv`、`sed -i`、`truncate`、`dd`、`shred`、输出重定向 `>`、`git reset`/`clean`/`checkout`）。每个目录每回合**最多一个**检查点。[[src:checkpoints]]
- 会话内用法：`/rollback`（列出）、`/rollback diff <N>`（先预览）、`/rollback <N>`（恢复，**默认保留你手改过的文件**）、`/rollback <N> --all`（连手改一起覆盖）、`/rollback <N> <file>`（只恢复一个文件）。[[src:checkpoints]]
- 恢复前会先给当前状态拍一张「回滚前快照」，所以「反悔的反悔」也能做；恢复同时会撤销最后一个对话回合，让 agent 的上下文与磁盘状态一致。[[src:checkpoints]]
- 保留手改靠一份 agent 写入账本（记录 Hermes 每次写文件后的内容哈希）：当前内容跟 Hermes 最后写的对不上（你后来手改过，或 Hermes 压根没碰过）的文件会被跳过并列出，用 `--all` 才强制覆盖。[[src:checkpoints]]
- 容量与安全阀：`max_snapshots: 20`、`max_total_size_mb: 500`、单文件超 `max_file_size_mb`（默认 10 MB）不进快照、超过 50,000 个文件的目录跳过、`git` 不在 `PATH` 上时透明禁用、所有错误只记 debug 不影响工具执行。[[src:checkpoints]]
- 自动维护默认开：`auto_prune: true` + `retention_days: 7` + `min_interval_hours: 24`，在后台清理过期的项目条目，**从不**自动删「孤儿」条目（工作目录找不到 = 已删项目还是没挂载的盘，无法区分）。[[src:checkpoints]]

### 三条退路的边界（这张表值得背）

| 工具 | 范围 | 含凭证？ | 用途 |
|---|---|---|---|
| `hermes backup` | 整个 `~/.hermes`（所有 profile、全局配置、会话） | **含**（`.env`、`auth.json`） | 整机迁移 |
| `hermes profile export` | 单个 profile | **不含**（按设计剥离） | 分享 / 搬一个 agent |
| `checkpoints` | 项目文件（影子 git 库） | 无关 | 撤销 agent 对代码的破坏性改动 |

[[src:faq]] [[src:checkpoints]]

迁移到新机器的流程是「源机 `hermes backup` → 拷 zip → 新机 `hermes import <zip>` → 新机跑 `hermes setup` 验证密钥与 provider」。手动兜底可以用 `rsync`，但记得排除代码仓库 `hermes-agent`。[[src:faq]]

## 亲手验证

### 验证一：亲手撞上「检查点默认关闭」这个边界

```bash
hermes config get checkpoints
```

本机真实输出：

```
enabled: false
max_snapshots: 20
max_total_size_mb: 500
max_file_size_mb: 10
auto_prune: true
retention_days: 7
min_interval_hours: 24
```

再对照 `hermes checkpoints status`：`Total size: 0 B`、`Projects: 0`。

**结论**：默认状态下 `/rollback` 没有任何东西可退 —— 你现在让 agent 大改一通文件，事后也没有检查点。想有退路必须显式打开：单次会话 `hermes chat --checkpoints`，或全局 `checkpoints.enabled: true`。[[src:checkpoints]]

### 验证二：升级前先问「有没有更新」

```bash
hermes update --check
```

本机真实输出：

```
→ Fetching from origin...
☤ Update available: 29 commits behind origin/main.
  Run 'hermes update' to install.
```

它只 fetch 与比较提交，**不改文件、不重启 gateway**，所以适合放进脚本或 cron 里当开关。[[src:updating]]

### 验证三：让一条命令真实失败（Windows / Git Bash 路径坑）

```bash
hermes import "$HOME/nope-does-not-exist.zip"
```

本机真实输出：

```
Error: File not found: D:\c\Users\28189\nope-does-not-exist.zip
```

注意这个怪路径 `D:\c\Users\28189\...` —— 本机实测里，命令里的 `$HOME` 被展开成了 `D:\c\Users\28189`（Git Bash 的 `/c/...` 风格路径拼进原生 Windows 程序参数时会被错误翻译），于是它去找一个根本不存在的文件。**改用 `~/` 或原生的 `C:/Users/<你>/...` 路径**：

```bash
hermes import ~/hermes-backup-20260916.zip
```

| 你观察到的 | 说明什么 |
|---|---|
| `enabled: false` + `Projects: 0` | 检查点默认关；不开就没有可回退的历史 |
| `Update available: 29 commits behind` | 「该不该升」是可判定的，不必凭感觉 |
| `Error: File not found: D:\c\Users\...` | MSYS 路径拼进原生程序的参数会被错误展开，用 `~/` 或原生路径 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `✗ Another hermes.exe is running: PID ...` | Windows 上有别的 `hermes.exe` 占着 venv 入口 | 关掉桌面端 / REPL / gateway 再跑；确认无影响才 `--force` |
| 更新时报 venv 被占用，`--force` 也没用 | 有进程正从 venv 解释器上跑，第二条闸门不吃 `--force` | 用 `--force-venv`，并先关掉那些进程 |
| `⚠ Update partially complete` | 桌面端重建失败（旧版本完好可启动） | `hermes desktop` 重试重建 |
| 更新后某个 profile 的 gateway 还在跑旧代码 | 重启阶段中断；收据里会点名 | 按提示重启，注意更新会以非零退出码结束 |
| `/rollback` 没有内容可列 | 检查点默认**关闭**（`enabled: false`） | `hermes chat --checkpoints`，或在 `config.yaml` 设 `checkpoints.enabled: true` |
| `↷ Kept your hand-edits: ...` | 你手改过的文件默认不被覆盖 | 要连手改一起还原用 `/rollback <N> --all` |
| 影子库越占越大 | 检查点会随会话累积 | `hermes checkpoints status` / `prune`；调低 `max_total_size_mb` |
| `Error: File not found: D:\c\Users\...` | Git Bash 的 MSYS 路径被拼进原生程序参数 | 用 `~/` 或 `C:/Users/...` 原生路径 |
| 把 `hermes backup` 的 zip 随手分享出去 | 该 zip **含** `.env` 与 `auth.json` | 分享用 `hermes profile export`（凭证被剥离） |
| 迁移后新机器上跑不动 | 路径与 provider 变了 | 新机器上跑 `hermes setup` 验证密钥与模型 |
| 回滚后启动报配置错误 | 回滚是代码回退，配置可能已被升级迁移过 | `hermes config check`，清掉不认识的键 |

## 试一试

- [ ] 跑一次 `hermes update --check`，把「落后多少提交」记进 `journal/`，一周后再看一次
- [ ] 给一个 profile 打开检查点（`hermes chat --checkpoints`），让 agent 改一个文件，然后用 `/rollback diff` 预览、`/rollback` 恢复
- [ ] 做一次 `hermes backup`，确认 zip 落盘位置与大小；想清楚它该不该进你的同步盘
- [ ] 把 `hermes update` 的收据目录 `~/.hermes/logs/update_receipts/` 看一眼，你会知道上次升级动了什么
- [ ] 写一张你自己的「升级前检查清单」：版本、`--plan`、快照档位、回滚提交号

## 下一步

- [[L24]] —— 检查点与回滚的日常用法（本课只讲了它在升级语境下的位置）
- [[L51]] —— 迁移前先弄清 profile 与凭证的边界：哪些会跟着走、哪些不会
- [[L53]] —— 升级之后行为变了，回到排障手册按顺序查
- [[L90]] —— 把这一整套（配置 + 密钥 + 备份 + 检查点）用在你的毕业项目上
- 想深入：[[src:updating]]（八个步骤与恢复机制原文）、[[src:checkpoints]]（影子库结构与维护命令）

## 出处

- [[src:updating]] Updating & Uninstalling — https://hermes-agent.nousresearch.com/docs/getting-started/updating
- [[src:faq]] FAQ & Troubleshooting — https://hermes-agent.nousresearch.com/docs/reference/faq
- [[src:checkpoints]] Checkpoints and /rollback — https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback
