---
id: L56
title: "公司机与个人机：一个内核，两个身份"
stage: 5
level: 进阶
minutes: 30
prereq: [L13, L51, L55]
tags: ["公司电脑", "个人电脑", "profile", "隔离", "撤离", "合规"]
sources: [profiles, multi-profile-gateways, secure-work-machine, secrets, faq, profile-commands, profile-distributions, skills]
updated: 2026-09-17
---

# L56 · 公司机与个人机：一个内核，两个身份

> **一句话**：隔离单位是 **profile** 而不是「机器」—— 公司机只放 `work` profile、个人机放自己的，两者互不共享密钥/记忆/会话；能带回家的只有技能与人格，密钥和会话历史一律不带。

## 你将学会

- 用 profile 把「公司身份」和「个人身份」拆成两个互不共享记忆、会话、密钥、技能的 agent
- 亲手撞上 `--clone` 的陷阱：它会把你的个人 `.env` 与 `MEMORY.md` 一起拷进公司 profile
- 给公司机配一套收紧值（`approvals.mode: manual` + `approvals.deny` + `HERMES_WRITE_SAFE_ROOT` + `terminal.backend: docker`）
- 逐类判断「属于个人的可以带回家」与「一旦沾了公司数据就不该外带」的文件
- 走一遍撤离：导出该留的、删 profile、清残留

**前置**：[[L13]]、[[L51]]、[[L55]] · **预计耗时**：30 分钟

## 先动手

在隔离的临时 HOME 里建两个 profile，看看克隆到底拷了什么 —— 三分钟，不碰你真实的 `~/.hermes`。

```bash
# macOS / Linux：export HH="$HOME/hh-split-home"
export HH="C:/Users/<你>/hh-split-home"          # Windows 用原生路径（见 L55 的坑）
export USERPROFILE="$HH" HOME="$HH" HERMES_HOME="$HH/hermes"
mkdir -p "$HERMES_HOME/memories"
printf 'PROVIDER_KEY=sk-PERSONAL-AAAA\n' > "$HERMES_HOME/.env"
printf '个人记忆：我偏爱中文交付\n' > "$HERMES_HOME/memories/MEMORY.md"

hermes profile create work --no-alias              # A：空 profile（推荐姿势）
hermes profile create workcopy --clone --no-alias  # B：克隆一份，看看它拷了什么

grep -c PERSONAL "$HERMES_HOME/profiles/workcopy/.env"          # B 的 .env
cat "$HERMES_HOME/profiles/workcopy/.env" | tail -1             # 看看有没有你的 key
cat "$HERMES_HOME/profiles/workcopy/memories/MEMORY.md"         # 看看有没有你的记忆
ls -a "$HERMES_HOME/profiles/work/.env" && tail -3 "$HERMES_HOME/profiles/work/.env"
```

本机真实输出（2026-09-17）：

```
1                                       ← workcopy/.env 里出现了 1 行 PERSONAL 匹配
PROVIDER_KEY=sk-PERSONAL-AAAA           ← 你的个人密钥被整行拷进「公司」profile ⚠

个人记忆：我偏爱中文交付                  ← 你的个人记忆也被整份拷过去 ⚠

C:/Users/.../hermes/profiles/work/.env
# Per-profile secrets for this Hermes profile.
# API keys and tokens set here override the shell environment.
# Behavioral settings belong in config.yaml, not here.
```

**结论**：`--clone` 是「把当前 profile 的身份复制一份」（含 `.env`、`SOUL.md`、`skills/`、`memories/MEMORY.md`、`USER.md`）—— 这在「起个兄弟 agent」时很省事，但在公司机上就是**把你的个人密钥与个人记忆搬进雇主设备**。公司 profile 应该**空建**。[[src:profiles]]

## 原理

### 隔离单位是 profile，不是机器

一个 profile = 一个独立的 Hermes home：自己的 `config.yaml`、`.env`、`SOUL.md`、`memories/`、`sessions/` + `state.db`、`skills/`、`cron/`、`logs/`。[[src:profiles]]

```bash
hermes profile create work        # 建 + 自动给一个 work 命令别名
hermes -p work chat               # 任何位置都能指定 profile
hermes -p work doctor
hermes profile use work           # 设成 sticky 默认：之后裸 hermes 就是 work
hermes profile use default        # 切回来
```

本机实测（隔离 HOME 里）：

```
Profile: work
Path:    C:\...\hh-split-home\hermes\profiles\work
Gateway: stopped
Skills:  58          ← 新 profile 自带 bundled 技能（由 hermes update 统一同步）
.env:    exists
SOUL.md: exists
```

```
 Profile          Model       Gateway    Alias    Distribution
 ◆default         —           stopped    —        —
  work            —           stopped    —        —
  workcopy        —           stopped    —        —
```

- **别名**：`hermes profile create coder` 之后你直接就有 `coder chat` / `coder doctor` —— 底层就是 `hermes -p coder`。[[src:profiles]]
- **知道你在哪**：提示符 `work ❯`、启动横幅 `Profile: work`、`hermes profile show`，另有 sticky 默认记录在 `~/.hermes/active_profile`。[[src:profiles]] [[src:faq]]
- **官方硬规则**：**绝不让两个 agent 指向同一个 profile/home**。两边都会自动写记忆、会话启动时各自加载对方的写入，状态会越用越糊。要真正共享记忆用外部 memory provider，而不是共用一个 home。[[src:faq]] [[src:multi-profile-gateways]]

隔离到什么程度？multiplexed 网关的隔离表把它写成了逐项清单（摘录）：provider key 与 `${VAR}` 只从该 profile 自己的 `.env` 解析，缺了就**失败**、绝不回落到 default；授权 allowlist、`command_allowlist`（「always 允许」）、`terminal.*`、`security.redact_secrets`、会话命名空间、日志、代理环境变量，全部按 profile 各自解析。[[src:multi-profile-gateways]]

### 公司机上放哪几个 profile：三种布局

| 布局 | 公司机上有什么 | 适合 | 代价 / 注意 |
|---|---|---|---|
| **A 只用 `work`** | 只有 work profile（公司 key、公司记忆） | 公司政策严、个人机就在身边 | 在公司机学到的技能要**手动捞回**（见下） |
| **B `work` + `personal`** | 两个 profile，各自密钥与记忆 | 通勤/午休也想用自己的 agent | 个人记忆与会话落在了雇主设备上（可被备份/审计），要自知 |
| **C 公司机只当客户端** | 不落地个人数据，连你个人机的 gateway / SSH | BYOD 且允许外联 | 需要个人机常开、网络可达；公司常禁隧道 |

[[src:profiles]] [[src:multi-profile-gateways]]

### 归属清单：什么可以带回家

| 类别 | 在哪 | 带回家？ | 理由与做法 |
|---|---|---|---|
| 技能 | `skills/`，或 `skills.external_dirs` 指向的 git 仓库 | ✅ 带 | 工具性知识，通常不含秘密；放你自己的 git 是更好的载体 [[src:skills]] |
| 人格 / 风格 | `SOUL.md` | ✅ 带 | 就是你的偏好，`profile export` 会带上 |
| 配置模板 | `config.yaml` | ⚠️ 先过一眼 | 里面可能有内网地址、内部模型端点、放宽过的审批设置 |
| 记忆 | `memories/MEMORY.md`、`USER.md` | ⚠️ 逐条读 | 工作记忆必然混着公司项目细节，含公司信息就别外带 |
| 会话历史 | `state.db` | ❌ 不带 | 一定有公司内容；`profile export` 的 default 允许清单里本来也没有它（见 L55） |
| 密钥 | `.env`、`auth.json` | ❌ 双向都不带 | 公司 key 属于公司；个人 key 不该进公司设备（等于把个人账号放进雇主审计范围）[[src:multi-profile-gateways]] |
| 定时任务 | `cron/jobs.json` + `scripts/` | ⚠️ 按条看 | 常有内网 URL、内部系统凭据 |

把技能与人格带回家最省事的方式：在`work` profile 里 `hermes profile export work -o ~/work.tar.gz`（**凭证按设计被剥离**），回家 `hermes profile import ~/work.tar.gz --name work-home`；要长期跟着版本走，把技能放进你自己的 git 仓（`skills.external_dirs`），公司机读同一个仓。[[src:profile-commands]] [[src:skills]]

### 公司机上的收紧清单

官方那份「在个人机或工作机上跑 Hermes」的指南给的就是这套（配置直接抄）：

```yaml
approvals:
  mode: manual                  # 每条被标记的命令都要你自己点
  timeout: 300                  # 不回答 = 拒绝（fail-closed）
  deny:                         # 永不运行清单 —— 连 /yolo 也拦
    - "git push --force*"
    - "*curl*|*sh*"
    - "dd if=* of=/dev/*"

security:
  redact_secrets: true          # 默认已开，写出来是为了让你知道

checkpoints:
  enabled: true                 # 破坏性操作前自动快照（默认是关的！）

terminal:
  backend: docker               # 或 ssh：把命令执行挪出主机
  docker_forward_env: []        # 空 = 容器里没有宿主机的密钥
```

```bash
# ~/.hermes/.env（或该 profile 的 .env）
HERMES_WRITE_SAFE_ROOT=/path/to/project:/home/you/.hermes
```

`HERMES_WRITE_SAFE_ROOT` 把 `write_file` / `patch` 锁在你给的目录前缀里，清单外的写入直接硬拒；**要把 Hermes home 也列进去**，否则 agent 连 `cron/jobs.json` 和自己的技能都写不了。走网关的话再配 allowlist 或 DM pairing，并且**永远不要** `GATEWAY_ALLOW_ALL_USERS=true`。[[src:secure-work-machine]]

官方对这套控制有一句必须原样转达的边界：**deny 规则与写入护栏是对付「诚实但会犯错的 agent」的护栏，不是对敌意进程的沙箱**；要「关住」它就该换隔离后端（Docker / 远程机）。[[src:secure-work-machine]]

密钥层面还有一条更干净的路：公司机上的 key 不进 `.env`，改用外部密钥管理器（Bitwarden Secrets Manager / 1Password），启动时按需取。这样「撤离」时你不需要去翻哪些 key 落过盘。[[src:secrets]]

### 让「个人的那份」始终掌握在你自己手里

三条规矩，按重要性排：

1. **个人基线放你自己的地方**：技能层做成一个你自己的 git 仓（`skills.external_dirs` 指向它），两台机都读它；新建技能用 `skills.create_dir` 直接落进去，而不是留在某台机器的 `~/.hermes/skills/` 里。[[src:skills]]
2. **不要指望记忆自动跨身份流动**：内置记忆是本机文件、profile 之间完全隔离；真要跨机共享记忆就用外部 memory provider —— 但在公司机上要先问清楚「公司数据能不能进这个 provider」，这属于政策问题不是技术问题。[[src:faq]] [[src:multi-profile-gateways]]
3. **到期能干净撤离**：先导出你真正要留的（技能/人格），再删：

```bash
hermes profile export work -o ~/work-keep.tar.gz     # 凭证被剥离，可安全带走
hermes profile delete work --yes                     # 停网关 → 删服务与别名 → 删数据
```

本机实测：删除后 profile 目录消失，`profiles/` 下留一个 `.deleted` 墓碑文件（防止被网关/定时器重新枚举出来）。

**另一种撤离**：把整个 agent 交给同事/下一个人，用 profile distribution（git 仓 + `distribution.yaml`，`hermes profile install <git-url>`）—— 它硬排除 `memories/`、`sessions/`、`state.db`、`.env`、`auth.json`，所以「发给别人」这件事本身是安全的。[[src:profile-distributions]]

## 亲手验证

### 验证一：两个 profile 的目录互不相干

```bash
ls -a "$HERMES_HOME/profiles/work"
hermes profile show work
hermes profile list
```

本机真实输出（节选）：

```
.  ..  .env  cron  home  logs  memories  plans  sessions  skills  skins  SOUL.md  workspace
```

```
Profile: work
Path:    C:\...\hh-split-home\hermes\profiles\work
Gateway: stopped
Skills:  58
.env:    exists
SOUL.md: exists
```

```
 Profile          Model       Gateway    Alias    Distribution
 ◆default         —           stopped    —        —
  work            —           stopped    —        —
  workcopy        —           stopped    —        —
```

每个 profile 都是**另一个完整的 Hermes home**：自己的 `sessions/`、`memories/`、`skills/`、`cron/`、`.env`。「A 里写的记忆 B 看不到」不是靠约定，是靠目录边界。[[src:multi-profile-gateways]]

### 验证二：`--clone` vs 空建，差在哪一行

```bash
grep -c PERSONAL "$HERMES_HOME/profiles/workcopy/.env"    # → 1（个人 key 被拷进来）
grep -c PERSONAL "$HERMES_HOME/profiles/work/.env"        # → 0（空建的是纯注释模板）
```

| 你观察到的 | 说明什么 |
|---|---|
| `workcopy/.env` 出现 `PROVIDER_KEY=sk-PERSONAL-AAAA` | `--clone` 会连 `.env` 一起复制：在公司机上等于把个人密钥装进雇主设备 |
| `workcopy/memories/MEMORY.md` 有内容 | 记忆被当作身份的一部分一起克隆（官方就是这么设计的） |
| `work/.env` 只有三行注释 | 空建 profile 的 `.env` 是模板，等你自己填**公司**的 key |

**要克隆但要空记忆**：官方给的做法是建完删掉 `memories/MEMORY.md` 与 `USER.md`（agent 不会回落到别的 profile 的记忆）。[[src:profiles]]

### 验证三：删掉一个 profile 之后残留什么

```bash
hermes profile delete workcopy --yes
ls -a "$HERMES_HOME/profiles"
```

本机真实输出：

```
  • All config, API keys, memories, sessions, skills, cron jobs
✓ Removed C:\...\hh-split-home\hermes\profiles\workcopy
Profile 'workcopy' deleted.

.  ..  .deleted  work
```

目录真的没了，但 `profiles/.deleted` 这个墓碑文件留在原地（用于让已删除的 profile 不再被枚举/重建）。[[src:multi-profile-gateways]]

> **还要自己清的残留**：`logs/`、`backups/`、`state-snapshots/`、`checkpoints/`、`cache/`、`profile-exports/` 里可能还有这个 profile 的拷贝，别只删 `profiles/<name>/` 就以为干净了。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 公司机上 `hermes profile create work --clone`，结果出现个人 key | `--clone` 明确会复制 `.env`、`SOUL.md`、skills、`memories/MEMORY.md` | 空建（不加 `--clone`），只填公司的 key；要克隆就建完删两份记忆文件、重写 `.env` |
| 两个 profile 用同一个 bot token | 平台 token 是独占的，第二个网关连不上 | 一个 profile 一个 bot（Telegram 找 @BotFather 再建一个）[[src:faq]] |
| 两台机各跑一个 agent、都指向同一份同步盘上的 home | 两边都自动写记忆，互相污染（官方明令禁止） | 一台机一个 home；跨机用 profile 导出、技能 git 仓或远端连接 |
| `hermes profile delete` 后仍看到旧任务/旧流程报错 | 删的是 profile，外部引用（脚本、cron 包装器、别名写法）还在 | 删前先 `hermes -p <name> cron list`、检查脚本引用；删后确认 `profiles/` 只剩墓碑 |
| 个人 provider key 出现在公司机的 `.env` 里 | 图省事 copy 了个人配置 | 公司侧用公司账号的 key；更干净的是 `hermes secrets`（Bitwarden/1Password）按需取用 |
| 把公司 profile 的 `hermes backup` 包带回家 | 包里**含** `.env`、`auth.json`、`state.db`、全部记忆与会话 | 只带 `profile export`（凭证剥离）+ 技能 git 仓；记忆与会话留在公司 |
| `HERMES_WRITE_SAFE_ROOT` 设了之后 agent 连自己的技能都改不了 | 只列了项目目录，没把 Hermes home 列进去 | 两个根：`/path/to/project:/home/you/.hermes` |
| 忘了 `-p`，命令打到默认 profile | 默认 profile 叫 `default`，sticky 默认可切换 | `hermes profile use work`，并看提示符 `work ❯` / 启动横幅 |
| 以为 deny 规则能挡住恶意进程 | 它是护栏，不是沙箱；`terminal` 用的是同一个 OS 用户 | 需要真隔离就用 `terminal.backend: docker` 或远程机 |
| 公司机上开了网关但没配 allowlist | 看起来「没配就是全开」？恰恰相反：默认全拒 | 让它显式：`GATEWAY_ALLOWED_USERS` 或 DM pairing；永不 `GATEWAY_ALLOW_ALL_USERS=true` |

## 试一试

- [ ] 在你自己的机器上**空建**一个 `work` profile，只把公司 provider key 写进 `~/.hermes/profiles/work/.env`
- [ ] 给 `work` 配上「收紧清单」那四段配置，然后 `hermes -p work config get approvals` 核对
- [ ] 设 `HERMES_WRITE_SAFE_ROOT` 为「项目目录 + Hermes home」，让 agent 试写目录外的文件，看它被拒
- [ ] 把技能层放进你自己的 git 仓，用 `hermes config set skills.external_dirs` 让两个 profile 都读它
- [ ] 演练撤离：`hermes profile export work -o ~/work-keep.tar.gz` → 确认包里没有 `.env` / `auth.json` → `hermes profile delete work --yes` → 清理残留目录

## 下一步

- [[L51]] —— profile 与凭证的边界：哪些不会跟着克隆走
- [[L50]] —— 审批与 deny 规则的全貌（本课只取了工作机该用的那几条）
- [[L55]] —— 换电脑怎么搬：整机 `backup` / 单 profile 导出 / 多机共用
- [[L15]] —— 技能系统：`external_dirs` 与 `create_dir` 怎么用
- [[L13]] —— 记忆系统：为什么 profile 之间不会共享记忆
- 想深入：[[src:secure-work-machine]]（工作机安全态势原文）、[[src:multi-profile-gateways]]（逐项隔离表）

## 出处

- [[src:profiles]] Profiles: Running Multiple Agents — https://hermes-agent.nousresearch.com/docs/user-guide/profiles
- [[src:multi-profile-gateways]] Running Many Gateways at Once — https://hermes-agent.nousresearch.com/docs/user-guide/multi-profile-gateways
- [[src:secure-work-machine]] Running Hermes on a Personal or Work Machine — https://hermes-agent.nousresearch.com/docs/guides/secure-hermes-on-a-work-machine
- [[src:secrets]] Secrets (external secret sources) — https://hermes-agent.nousresearch.com/docs/user-guide/secrets/
- [[src:faq]] FAQ & Troubleshooting — https://hermes-agent.nousresearch.com/docs/reference/faq
- [[src:profile-commands]] Profile Commands — https://hermes-agent.nousresearch.com/docs/reference/profile-commands
- [[src:profile-distributions]] Profile Distributions: Share a Whole Agent — https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions
- [[src:skills]] Skills — https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
