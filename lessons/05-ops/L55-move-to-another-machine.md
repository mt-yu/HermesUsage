---
id: L55
title: "换一台电脑：把记忆、技能和会话带走"
stage: 5
level: 进阶
minutes: 25
prereq: [L13, L15, L54]
tags: ["迁移", "换电脑", "备份", "profile 导出", "多机"]
sources: [faq, updating, cli-commands, profile-commands, profile-distributions, multi-connection-desktop, skills, memory-providers, sessions]
updated: 2026-09-17
---

# L55 · 换一台电脑：把记忆、技能和会话带走

> **一句话**：你的「习惯」全在 `$HERMES_HOME` 里 —— 整机搬用 `hermes backup` + `hermes import`，只搬一个 agent 用 `hermes profile export`，两台机同时用就别搬文件、让它连过来。

## 你将学会

- 说出「对话习惯」具体落在哪几个文件：`memories/`、`SOUL.md`、`skills/`、`state.db`、`config.yaml`、`cron/`
- 用 `hermes backup` + `hermes import` 把整台机器搬过去，并用 `hermes journey` 证明记忆与已学技能真的到了新机器
- 分清 `hermes backup` 与 `hermes profile export` 各自「带得走 / 带不走」什么（含一个容易搞错的：`state.db`）
- 判断什么时候**不该**搬文件：两台电脑同时用时，让第二台连过来，或者把技能放进共享目录
- 在把导出包发给别人之前，先列出里面到底有什么

**前置**：L13、L15、L54 · **预计耗时**：25 分钟

## 先动手

三件事、两分钟：备份 → 导进一个临时 home → 看记忆还在不在。全程不碰你自己的 `$HERMES_HOME`。

```bash
hermes backup -o ~/hermes-move-test.zip -k 0
```

本机真实输出（Windows 11 / Git Bash，2026-09-17）：

```
Scanning ~/AppData/Local/hermes ...
Backing up 748 files ...
Backup complete: C:\Users\28189\AppData\Local\Temp\hb-test.zip
  Files:       748
  Original:    94.4 MB
  Compressed:  35.7 MB
  Time:        8.3s

  Excluded directories:
    backups/            cache\browser-use/   cache\delegation/   cache\project_skill_scans/
    cache\spillover/    cache\terminal/      cache\terminal-output/   cache\vision/
    checkpoints/        hermes-agent/        lsp\node_modules/   state-snapshots/
```

现在把包导进一个**临时** home，再去里面看记忆与技能：

```bash
# macOS / Linux
export HERMES_HOME="$HOME/hh-test-home"
# Windows（Git Bash）：必须给原生路径，MSYS 风格的 /c/... 会被解释成 D:\c\...（见「常见坑」）
# export HERMES_HOME="C:/Users/<你>/hh-test-home"

hermes import ~/hermes-move-test.zip --force
hermes journey
```

本机真实输出：

```
Import complete: 745 files restored in 4.0s
  Target: ~/AppData/Local/Temp/hh-import-test

  Preserved 3 runtime state file(s) (kept this machine's, not the backup's):
    gateway.lock
    gateway_state.json
    processes.json

Note: The hermes-agent codebase was not included in the backup.
  If this is a fresh install, run: hermes update
```

```
✦ Journey · learned skills & memories over time
  ● skills (8)   ◆ memories (8)
  ● software-development (4)  ● github (3)  ● autonomous-ai-agents (1)
  ...
  8 learned skills · 8 memories · 10 skill links
```

**结论**：`hermes backup` 拿走了 748 个文件、`hermes import` 放回 745 个（差额是三个「属于本机」的运行时文件，导入时**故意保留新机器的**），然后新 home 里的 `hermes journey` 直接显示 8 条记忆、8 个已学技能 —— 习惯确实跟着包走了。[[src:cli-commands]]

## 原理

### 「习惯」到底是哪些文件

全部在 `$HERMES_HOME`（默认 `~/.hermes`，Windows 上默认 `%LOCALAPPDATA%\hermes`，见 L03）下，就这么几处：

| 路径 | 装的是什么 | 有它才能 |
|---|---|---|
| `memories/MEMORY.md`、`memories/USER.md` | 你的笔记与画像 | 新机器上一开口它就知道你是谁 |
| `SOUL.md` | 人格 / 说话风格 | 语气不变 |
| `skills/` | 技能（含你自己写的） | 一句话复用老活法 |
| `state.db` | 会话历史（SQLite + FTS5 全文索引） | `/resume`、`session_search` 翻旧对话 |
| `config.yaml` | 设置：模型、工具集、审批、界面 | 行为一致 |
| `cron/jobs.json` + `scripts/` | 定时任务与它们的包装脚本 | 无人值守照旧 |
| `.env`、`auth.json` | 密钥与 OAuth 令牌 | 能连上 provider |

[[src:sessions]] [[src:skills]]

### 路线 A：整机搬（`hermes backup` → `hermes import`）

一个 zip 覆盖整个 `$HERMES_HOME`（所有 profile、全局配置、密钥、会话），**不含** `hermes-agent` 代码本身。文档明确的排除项：SQLite 的 `-wal/-shm` 边车文件、`checkpoints/`、根目录的 `models/`、`runtimes/`、`node/`（几十 GB 的可再生下载）、可再生的 `cache/` 条目、Unix socket / 符号链接。[[src:cli-commands]]

备份用 SQLite 的 `backup()` API，所以 **Hermes 正在跑也能备份**；恢复出来的包不含 `gateway.pid` / `cron.pid` 这类机器本地运行时文件。[[src:cli-commands]]

到新机器上还有两步文档专门强调：

```bash
hermes update      # 代码不在包里，新机器需要自己一份
hermes setup       # 验证 API key 与 provider 配置
```

`hermes update` 自带的「升级前快照」是给**原地升级**用的，不是迁移工具 —— 整机换硬件时官方指的就是 `backup` + `import`。[[src:faq]] [[src:updating]]

### 路线 B：只搬一个 agent（`hermes profile export` / `hermes profile import`）

只打包**单个 profile**，`auth.json` 与 `.env` **永远被剔除**（按设计），所以它不能当完整备份用。[[src:profile-commands]] [[src:profile-distributions]]

这里有个必须分清的区别（本机实测印证了文档的措辞）：

| 你导出的是 | 打包方式 | 结果 |
|---|---|---|
| `default`（`~/.hermes` 本身） | **允许清单**：`config.yaml`、`SOUL.md`、`skills/`、`plugins/`、`cron/`、`scripts/`、`sessions/`、`memories/`… | 记忆与技能在；**`state.db` 不在包里 → 会话历史不跟着走** |
| 命名 profile（`~/.hermes/profiles/<name>`） | 整目录拷贝（除 `auth.json` / `.env`） | 连 `state.db`、日志、缓存一起走，包也更大 |

导入时不能落成 `default`（那是内置根 profile），要么换名字 `--name work-restored`，要么先删旧的；桌面端导出的包还会多带一个 `desktop.json`（皮肤、明暗、布局），所以「长得也像」发件人。[[src:profile-commands]] [[src:profile-distributions]]

想**版本化地**分享/更新一个 agent，用 profile distribution（一个 git 仓库 + `distribution.yaml`，`hermes profile install <git-url>`）——它硬排除 `memories/`、`sessions/`、`state.db`、`logs/`、`auth.json`、`.env`，所以「发出去」这件事本身就安全得多。[[src:profile-distributions]]

### 路线 C：别搬文件，让两台机共用一份

如果你本来就是两台电脑换着用，「复制文件」是最差的方案（两边都会变，越复制越乱）。三个更省事的做法：

1. **agent 只在一台机上跑，另一台只当客户端。** 桌面端的连接注册表能同时登记 Local、Remote gateway（HTTP(S)，LAN / Tailscale / 公网）、SSH、Hermes Cloud 四种连接：远端 gateway 用 session token 或 OAuth 认证，SSH 那条由 App 自己开隧道并拉起 dashboard。这样习惯天然只有一份。[[src:multi-connection-desktop]]
2. **技能放进共享目录。** 在 `config.yaml` 里配 `skills.external_dirs`（支持 `~` 与 `${VAR}`，不存在就静默跳过）指向你的 git 仓库或同步盘，两台机看到同一批技能；再配 `skills.create_dir`，让 agent 新写的技能直接落进那个共享目录 —— 文档明确说这个目录「完全整合」：出现在技能索引、`skills_list`、`skill_view` 与斜杠命令里。[[src:skills]]
3. **记忆搬到服务端。** `hermes memory setup` 可以挂外部 memory provider（honcho / mem0 / supermemory 等，自托管或云），此时记忆的真相在服务端而不是本机 `MEMORY.md`；内置记忆始终同时生效。[[src:memory-providers]]

> **技能跨设备同步还有一条官方命令**：`hermes sync`（Skill Sync，`status/pull/push/now/enable/disable/device/propose`）。本机 v0.21.3 的 CLI 里它真实存在，但本项目登记的官方文档快照里**还没有这一页**，所以本课只给出实跑输出，不做更多承诺：

```bash
hermes sync status
```

```
Not logged into Nous Portal — sync is inert.
{
  "nous_admin": false, "logged_in": false, "feature_enabled": false,
  "default_opt_in": false,
  "base_url": "https://gateway-gateway.nousresearch.com",
  "opted_in_skills": [], "local_head": null, "owner": null, ...
}
```

要真的用它，得先 `hermes portal` 登录。

### 一张总表：什么跟着走，什么必须在新机器重做

| 跟着走 ✅ | 不跟着走 ❌（原因 → 怎么办） |
|---|---|
| `memories/`、`SOUL.md`、`skills/` | `hermes-agent/` 代码树（包是用户数据，不是仓库快照）→ 新机装 Hermes 后 `hermes update` |
| `config.yaml`（设置） | 机器本地运行时：`gateway.pid`、`cron.pid`、`gateway.lock` → 导入时自动保留新机的 |
| `cron/jobs.json` + `scripts/` | `checkpoints/`（影子 git 库按目录哈希，本来就不该跨机）→ 新机上没有 `/rollback` 历史 |
| `state.db`（整机 backup） | `models/`、`runtimes/`、`node/`（可再生，几十 GB）|
| `.env`、`auth.json`（整机 backup，**含**凭证） | `profile export` 里**永不**含凭证 → 新机重新登录 / 填 key |
| 会话导出文件（`hermes sessions export`） | 网关服务与开机自启 → 新机 `hermes gateway install` |
| | `config.yaml` 里的绝对路径（本机就有一处 `D:\Projects\ai_projects\HermesUsage`）→ 用 `hermes config set` 改 |

[[src:cli-commands]] [[src:faq]]

只要**对话历史**（不要别的）时：`hermes sessions export backup.jsonl` 把会话导成 JSONL（也可 `--format md/qmd/html`），`--redact` 会把内容里的 API key / token 擦掉；文档里的「导入」只覆盖从 Claude Code / Codex CLI 拉会话这一条路。[[src:sessions]]

## 亲手验证

### 验证一：亲手撞上「profile 导出里没有 state.db」这个边界

```bash
hermes profile export default -o ~/hh-export-test.tar.gz
tar -tzf ~/hh-export-test.tar.gz | head -8
tar -tzf ~/hh-export-test.tar.gz | grep -E "state\.db|\.env|auth\.json" || echo "没有 state.db / .env / auth.json"
```

本机真实输出（节选）：

```
✓ Exported 'default' to C:\Users\28189\AppData\Local\Temp\hb-export.tar.gz

default
default/SOUL.md
default/config.yaml
default/cron
default/memories
default/scripts
default/sessions
default/skills

没有 state.db / .env / auth.json
```

包内条目共 **807** 个，其中 `default/skills/` **747** 条、`default/cron/` **44** 条、`default/memories/` **4** 条（两个 `.md` 加两个 `.lock`）、`default/sessions/` 只有 **1** 条请求转储。

**结论**：`default` 的 profile 导出是允许清单 —— 记忆、技能、设置、cron 都在，**凭证与会话历史库 `state.db` 都不在**。要连会话历史一起搬，用整机的 `hermes backup`。[[src:profile-distributions]] [[src:profile-commands]]

### 验证二：亲手确认「记忆的真相在哪」

```bash
hermes memory status
hermes config get memory
```

本机真实输出：

```
provider: ''

memory_enabled: true
user_profile_enabled: true
write_approval: false
memory_char_limit: 2200
user_char_limit: 1375
nudge_interval: 10
flush_min_turns: 6
```

`provider: ''` 说明这台机器上的记忆还是**内置文件**（`memories/MEMORY.md` / `USER.md`）——所以它才会被 `hermes backup` 原样带走。挂上外部 provider 之后，记忆的存续位置就换到了服务端，`hermes memory status` 会显示具体那一家的配置。[[src:memory-providers]]

### 验证三：让一条命令真实失败（Windows / Git Bash 路径坑）

```bash
export HERMES_HOME="/c/Users/28189/AppData/Local/Temp/hh-msys-test"
hermes profile show default
```

本机真实输出：

```
Profile: default
Path:    \c\Users\28189\AppData\Local\Temp\hh-msys-test
Gateway: stopped
Skills:  0
.env:    not configured
```

注意两处：`Path:` 变成了**盘符相对**的 `\c\Users\...`（MSYS 风格 `/c/...` 被当成当前盘根下的 `c` 目录），`Skills: 0` 是因为它在一个空的「新 home」里看。**给 `HERMES_HOME` 或 `hermes import` 的路径要用原生的 `C:/Users/<你>/...`**，与 L54 那条 `hermes import` 的坑是同一个根源。

| 你观察到的 | 说明什么 |
|---|---|
| `745 files restored` + `journey` 里 8 条记忆 | 记忆、技能、会话库随 `hermes backup` 整机走 |
| profile 导出里没有 `state.db` / `.env` | 单 profile 导出是允许清单 + 凭证强制剔除，不是完整备份 |
| `provider: ''` | 记忆还存本机文件；换了外部 provider 才是跨机存续 |
| `Path: \c\Users\...`、`Skills: 0` | MSYS 风格路径会被原生程序解释错，用 `C:/...` |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 把 `hermes backup` 的 zip 发给同事 | 该 zip **含** `.env` 与 `auth.json` | 分享用 `hermes profile export`（凭证按文件名剔除）或 distribution |
| 以为导出的 profile「干净」就发出去了 | profile 导出**会**带 `memories/`、`sessions/`、`USER.md`，内容不做扫描 | 先 `tar -tzf <包>` 看一遍目录；要给外人用 distribution（硬排除记忆与会话） |
| 导入后 `session_search` 找不到旧对话 | 你用的是 profile 导出，包里没有 `state.db` | 会话历史只有整机 `hermes backup` 带得走；只要历史可用 `hermes sessions export` |
| 新机器上 `hermes` 起不来 / 缺模块 | 包里没有 `hermes-agent` 代码 | 先在新机装好 Hermes，再 `hermes import`，然后 `hermes update` |
| 导入后密钥不通、模型报错 | 目标是新机器的 provider/网络 | 跑一次 `hermes setup` 复核 |
| 导入后某个工具/审批行为变了 | `config.yaml` 也被带过去了 | `hermes config check`，重点看 `tools` 与 approvals 段 |
| 换机后 `/rollback` 空 | `checkpoints/` 被 backup 排除（影子库按目录哈希，不可移植） | 这是设计如此；需要项目级回退就用 git |
| 导入后 cron 任务不跑 | 新机器上网关没起；包装脚本路径也可能指向旧机器 | `hermes gateway install` + `hermes cron status` |
| `hermes import "$HOME/x.zip"` 报 `Error: File not found: D:\c\Users\...` | MSYS 风格路径被拼进原生程序参数 | 用 `~/x.zip` 或 `C:/Users/<你>/x.zip` |
| `export HERMES_HOME="/c/Users/..."` 后看起来「什么都没了」 | 同上：被解释成盘符相对路径，指向一个空目录 | 用 `C:/Users/<你>/...` 原生路径 |
| 两台机互相复制 `~/.hermes`，越用越乱 | 复制不是同步：两边都在变 | 改成「agent 只跑一台 + 远端连接」，或把技能放 `skills.external_dirs` 共享目录 |
| `hermes sync` 什么都不做 | 它要登录 Nous Portal（本机实测：`sync is inert`） | 先 `hermes portal` 登录 |

## 试一试

- [ ] 跑一次完整 `hermes backup`，把「文件数 / 原始大小 / 压缩后大小」记进 `journal/`
- [ ] 按「先动手」把包导进一个临时 `HERMES_HOME`，用 `hermes journey` 确认记忆与技能到了
- [ ] 导出一次 `default` profile，用 `tar -tzf | grep` 确认里面没有 `state.db`、`.env`、`auth.json`
- [ ] 给 `skills.external_dirs` 加一个你自己的 git 仓库路径（用 `hermes config set`），新开一个会话后确认技能出现在 `hermes skills list`
- [ ] 写下你自己的换机清单：装 Hermes → `hermes import` → `hermes update` → `hermes setup` → `hermes gateway install` → `hermes config check`

## 下一步

- [[L54]] —— 升级、备份与回滚：本课用到的 `hermes backup` 在那边是「升级前快照」的语境
- [[L51]] —— profile 与凭证的边界：为什么导出永远不含 `.env`
- [[L13]] —— 记忆系统：`MEMORY.md` / `USER.md` 与外部 provider 的分工
- [[L15]] —— 技能系统：`external_dirs` 与项目级 `.hermes/skills` 的区别
- 想深入：[[src:profile-distributions]]（导出包/发行版分别含什么）、[[src:faq]] 的「Exporting Hermes to another machine」

## 出处

- [[src:faq]] FAQ & Troubleshooting — https://hermes-agent.nousresearch.com/docs/reference/faq
- [[src:updating]] Updating & Uninstalling — https://hermes-agent.nousresearch.com/docs/getting-started/updating
- [[src:cli-commands]] CLI Commands Reference — https://hermes-agent.nousresearch.com/docs/reference/cli-commands
- [[src:profile-commands]] Profile Commands — https://hermes-agent.nousresearch.com/docs/reference/profile-commands
- [[src:profile-distributions]] Profile Distributions: Share a Whole Agent — https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions
- [[src:multi-connection-desktop]] Connecting Desktop to Many Hermes Instances — https://hermes-agent.nousresearch.com/docs/user-guide/multi-connection-desktop
- [[src:skills]] Skills — https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- [[src:memory-providers]] Memory Providers — https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers
- [[src:sessions]] Sessions — https://hermes-agent.nousresearch.com/docs/user-guide/sessions
