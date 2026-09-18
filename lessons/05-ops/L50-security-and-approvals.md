---
id: L50
title: "安全模型与审批：危险命令怎么拦住"
stage: 5
level: 进阶
minutes: 20
prereq: [L11, L14]
tags: ["安全", "审批", "approvals", "hardline-blocklist", "密码保管箱"]
sources: [security, secure-work-machine, credential-vault]
updated: 2026-09-16
---

# L50 · 安全模型与审批：危险命令怎么拦住

> **一句话**：默认值已经在替你拦危险命令 —— 你要搞清楚的是拦在哪一层、哪一层永远拦得住，以及它拦错时怎么放行。

## 你将学会

- 用 `hermes config get approvals` 读出当前审批模式与三种无人值守策略
- 说清 hardline blocklist 与 `approvals.deny` 的分工：哪一层能被 `/yolo` 绕过，哪一层不能
- 写一条 deny 规则挡住一类命令，并复现「引号没写」导致的 YAML 解析失败
- 判断一次危险命令为什么在本地后端被拦、在容器后端却不弹提示
- 说清密码保管箱为什么从不让模型看到密码

**前置**：[[L11]]、[[L14]] · **预计耗时**：20 分钟

## 先动手

先把你机器上的实体旋钮读出来（两条命令都只读，不改任何东西）：

```bash
hermes config get approvals
hermes config get security
```

你应该看到（本机 v0.21.3 真实输出，节选）：

```
mode: smart
timeout: 300
cron_mode: deny
single_query_mode: deny
unattended_mode: deny
deny: []
mcp_reload_confirm: true
destructive_slash_confirm: true
```

```
redact_secrets: true
allow_private_urls: false
tirith_enabled: true
tirith_fail_open: true
website_blocklist:
  enabled: false
allow_lazy_installs: true
```

**读到这两段你就拿到了本课的全部旋钮**：`mode` 决定由谁判断一条命令危不危险；`cron_mode` / `single_query_mode` / `unattended_mode` 决定「没有人在场时怎么办」；`deny` 是你自己的永久禁止清单；`redact_secrets` 决定工具输出里长得像密钥的文本要不要打码。[[src:security]]

## 原理

### 八层，从「谁能跟它说话」到「它的输入干不干净」

Hermes 的安全模型有八层：用户授权、危险命令审批、文件写入安全、容器隔离、MCP 凭证过滤、上下文文件扫描、跨会话隔离、输入清洗。[[src:security]]

本课讲第 2、3 层，以及你每天真的会碰到的部分；第 1 层（谁能跟它对话）和第 4 层（容器隔离）属于部署形态，见 [[L33]]。

### 审批模式：谁来判断「危险」

| 模式 | 行为 |
|---|---|
| `smart`（默认） | 用辅助 LLM 评估风险：低风险命令只放行这一次；真正危险的自动拒绝；拿不准才来问你 |
| `manual` | 命中就一律问你 |
| `off` | 关闭全部审批检查，等价于 `--yolo` |

`--yolo`、斜杠命令 `/yolo`、环境变量 `HERMES_YOLO_MODE=1` 三条路都能在**当前会话**里绕过审批提示，其中 `/yolo` 是开/关切换。[[src:security]]

但 `--yolo` 不是万能钥匙 —— 下面两条底线它绕不过去。

### 底线一：hardline blocklist（代码内置，没有覆盖开关）

`rm -rf /` 及其明显变体、bash fork bomb、`mkfs.*` 作用在已挂载的根设备、`dd if=/dev/zero of=/dev/sd*`、把不可信 URL 直接管进 `sh` —— 这些在审批层**之前**就被拒绝。不管 `--yolo`、`approvals.mode: off`、cron 的 approve 模式，还是你点了「always」，都不会执行。引号解析不出来时也走 fail-closed（报 `malformed executable payload`）。[[src:security]]

### 底线二：`approvals.deny`（你自己写的永久禁止清单）

`approvals.deny` 是内置 blacklist 的用户可编辑版本：一串 glob，命中的终端命令**无条件**被拦，同样在 `--yolo` 和 `mode: off` 之前判定。[[src:security]]

```yaml
approvals:
  deny:
    - "git push --force*"
    - "dd if=* of=/dev/*"
```

要点：

- 规则是 fnmatch glob（`*`、`?`、`[...]`），大小写不敏感，匹配整条命令文本与各个可执行命令候选：`git push --force*` 命中 `git push --force origin main`，不命中 `git push origin main`。[[src:security]]
- 匹配跑在「去混淆后的命令变体」上，`git pu""sh --force` 这种引号把戏躲不过。[[src:security]]
- **YAML 里必须带引号**：裸写的 `*` 开头值是 YAML 别名，整份配置直接解析失败。[[src:security]]
- 命中后返回 BLOCKED 给模型，并告诉它不要重试、不要换写法。[[src:security]]
- 改完立刻生效，不用重开会话（配置缓存按 mtime 判定）。[[src:security]]

威胁模型要摆正：deny 规则是给「诚实但会犯错的 agent」用的护栏，跟危险模式检测属于同一个模型；它**不是**对抗恶意进程的沙箱。要真正的隔离，用容器后端或受限的网络出口。[[src:security]] [[src:secure-work-machine]]

### 没有人在场时：三档 deny

审批提示需要有人回答。cron、`hermes chat -q`、webhook/API 这三类无人值守形态各有自己的策略键，默认全是 `deny`：命令直接失败，agent 必须换条路。`approvals.timeout` 默认 300 秒，超时同样按拒绝处理 —— 你走开不会等于默认同意。[[src:security]] [[src:secure-work-machine]]

### 文件写入：立刻报错，没有弹窗

`write_file` / `patch` 在落盘前检查目标路径，命中就立刻返回错误，**不给审批弹窗**，也无法从聊天界面覆盖。永久拒绝的类别包括：`~/.ssh/`、`~/.aws/`、`~/.kube/`、`/etc/sudoers`、`~/.netrc`，以及 Hermes 自己的凭证存储（`.env`、`auth.json`、`vault/`、`pairing/` 等）。项目里的 `.env` / `.env.local` / `.envrc` 是「可以写，但读不回来」。[[src:security]]

可选的写沙箱用一个环境变量就能开：`HERMES_WRITE_SAFE_ROOT`。设了它，`write_file` / `patch` 只能写列出的路径前缀，其他一律硬拦（不经过审批层）。Windows 上多个根用 `;` 分隔，Unix 用 `:`。**别顺手把它塞进 `.env`**：沙箱一旦只指向项目目录，agent 就写不了 `~/.hermes/` 下的状态文件了。[[src:security]] [[src:secure-work-machine]]

### 容器后端：审批被跳过，因为容器本身就是边界

| 后端 | 隔离 | 危险命令检查 |
|---|---|---|
| `local` | 无，跑在宿主机上 | 会检查 |
| `ssh` | 远端机器 | 会检查 |
| `docker` / `singularity` / `modal` / `daytona` / `vercel_sandbox` | 容器 / 云沙箱 | 跳过 |

跳过不是疏漏：容器里的破坏伤不到宿主机。代价是容器镜像本身必须收紧过。[[src:security]]

### 密码：模型看不到，无人值守直接拒绝

`hermes vault` 保存本地加密的登录、卡片与地址；密码通过受监督浏览器的 CDP 通道直接填进页面，模型看到的工具结果只有 `{filled_fields: 1, origin: "https://github.com"}` 这种形状。**每次填卡都要你按同意**，走的是和危险命令同一个审批提示；cron / webhook / API server / `hermes chat -q` 这类没有人能回答的会话会被直接拒绝 —— 提示注入就算把 agent 骗到结账页，也花不掉钱。地址填充不需要确认。[[src:credential-vault]]

它**不保证**的事：密码一旦填进页面，那个站点（以及它跑的脚本）就拿到了，跟你自己手打没有区别。[[src:credential-vault]]

## 亲手验证

### 验证一：让审批层自己说话（本机实测）

本机跑 `hermes update --help`（只是看帮助文本）时，终端里出现了这一行：

```
Command was flagged (hermes update (restarts gateway, kills running agents)) and auto-approved by smart approval.
```

这就是 `smart` 模式的日常形态：模式匹配先标出「这条属于危险类」，再由辅助模型判定风险低、放行，并把判定理由写给你看。[[src:security]]

想复现，让 agent 在终端里跑一条 `python -c "print(1)"` —— 它会命中「script execution via -e/-c flag」这一类，被标出来。

### 验证二：亲手制造一次 YAML 解析失败（边界情况）

把引号去掉，看会发生什么：

```bash
python -c "import yaml; yaml.safe_load('approvals:\n  deny: [*git push*]\n')"
```

真实输出：

```
ComposerError found undefined alias 'git'
```

裸 `*` 在 YAML 里是别名引用，不是通配符 —— 所以 `approvals.deny` 的每一条都必须写成带引号的字符串。[[src:security]]

### 验证三：看审批历史里到底有什么

```bash
hermes approvals suggest
```

本机真实输出（节选）：

```
Proposed command_allowlist additions (from approval history, last 90 days):

  1. script execution via -e/-c flag    — approved 2x (class key)
...
Nothing has been changed. Apply selected entries with:
  hermes approvals suggest --apply 1,3
```

它是**只读**的：默认什么都不改，只有你显式 `--apply N` 才写进 `command_allowlist`；而且递归删除、`sudo`、磁盘写入、凭据与系统配置编辑、管道到 shell、SQL DROP 这些破坏类**永不**被提议，命令里出现的凭据会被打码。[[src:security]]

| 你观察到的 | 说明什么 |
|---|---|
| flagged + auto-approved（验证一） | smart 模式在工作：低风险自动放行，并留下理由 |
| `ComposerError found undefined alias`（验证二） | 规则没加引号 → 配置解析失败；deny 一律带引号 |
| `Nothing has been changed`（验证三） | 挖历史默认只读；破坏类永不被自动提议 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `Command was flagged (...) and auto-approved by smart approval.` | 不是报错：smart 模式自动放行了低风险命令 | 不用处理；想每条都自己看就把 `approvals.mode` 改成 `manual` |
| `ComposerError found undefined alias 'git'` | `approvals.deny` 的规则没加引号 | 一律写成 `"*git push*"` 这种带引号形式 |
| 命令被拒，且被告知不要重试 | 命中 `approvals.deny` 或 hardline blocklist | deny 规则可以改；blocklist 没有覆盖开关，只能换个做法 |
| `Write denied: '...' is a protected system/credential file.` | 目标在受保护路径（`~/.ssh/`、`.env`、`auth.json` 等） | 换路径；确实要改就用 `hermes config edit` 人工改 |
| `Write denied: '...' is outside HERMES_WRITE_SAFE_ROOT (...)` | 设过写沙箱，目标在沙箱之外 | 把根加进 `HERMES_WRITE_SAFE_ROOT`（Windows 用 `;` 分隔） |
| 进了容器后端后不再弹审批 | docker / modal 等后端跳过了危险命令检查 | 这是设计：把镜像收紧；容器内能碰到的东西仍会被改到 |
| 以为批准一次就永久放行 | 四个选项 once / session / always / deny，只有 always 才写进 `config.yaml` | 先选 session，稳定后再 always |
| 担心密码进模型上下文 | 不会：密码只进页面，不进工具结果、日志、会话库 | 填卡仍需你按同意；无人值守会话会被直接拒绝 |
| 以为 deny 规则能挡住一切 | 它是护栏不是沙箱；变量、别名、重命名的二进制都能绕 | 要隔离就用容器后端 / 受限出口网络 |

## 试一试

- [ ] 把 `approvals.mode` 改成 `manual`，让 agent 跑一条 `python -c "print(1)"`，观察它必须等你回答（测完改回 `smart`）
- [ ] 按带引号的写法给 `approvals.deny` 加三条你机器上绝对不能跑的命令，再故意触发一条看 BLOCKED 长什么样
- [ ] 跑 `hermes approvals suggest`，看过去 90 天你批准过什么，判断哪一条值得进白名单
- [ ] 用 `hermes config get security` 确认 `redact_secrets` 与 `website_blocklist` 的状态，决定要不要开网站黑名单
- [ ] 把你的取舍写进 `journal/`

## 下一步

- [[L51]] —— 审批管「这条命令能不能跑」，密钥与凭证池管「用谁的身份去跑」
- [[L21]] —— 终端 / 文件 / 浏览器三类工具各自的边界，本课只讲了拦阻层
- [[L24]] —— 审批是「事前拦」，检查点与 `/rollback` 是「事后退」
- [[L53]] —— 被拦之后怎么找证据：`hermes logs --component tools`
- 想深入：[[src:security]]（八层逐层展开）、[[src:credential-vault]]（填充流程与它的不保证）

## 出处

- [[src:security]] Security — https://hermes-agent.nousresearch.com/docs/user-guide/security
- [[src:secure-work-machine]] Running Hermes on a Personal or Work Machine — https://hermes-agent.nousresearch.com/docs/guides/secure-hermes-on-a-work-machine
- [[src:credential-vault]] Passwords & Logins — https://hermes-agent.nousresearch.com/docs/user-guide/features/credential-vault
