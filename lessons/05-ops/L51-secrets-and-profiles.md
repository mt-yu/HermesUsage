---
id: L51
title: "密钥、凭证池与多 profile"
stage: 5
level: 进阶
minutes: 20
prereq: [L03, L10]
tags: ["密钥", "凭证池", "profile", "HERMES_HOME", "密钥管理器"]
sources: [secrets, credential-pools, profiles, env-vars]
updated: 2026-09-16
---

# L51 · 密钥、凭证池与多 profile

> **一句话**：密钥只放 `.env` 或外部密钥管理器，同一家 provider 的多把钥匙交给凭证池轮换，不同用途的 agent 用 profile 隔离 —— 三件事互不替代。

## 你将学会

- 用 `hermes auth list` 列出每个 provider 的凭证池，并读懂 `env:` / `config:` / `manual` 三种来源
- 说出密钥该放哪：`.env`、外部密钥管理器、以及唯一的例外（自定义端点）
- 用 `hermes profile create` 起一个隔离的 agent，并知道哪些东西**不会**被克隆
- 判断一次「轮换到下一把钥匙」为什么会让下一轮变贵
- 用一条命令证明 profile 不是沙箱

**前置**：L03、L10 · **预计耗时**：20 分钟

## 先动手

```bash
hermes auth list
hermes profile show default
hermes vault list
```

本机真实输出（节选）：

```
custom:mac-provider (1 credentials):
  #1  mac-provider         api_key id=4b9bc5 priority=0 config:mac-provider ←

deepseek (1 credentials):
  #1  DEEPSEEK_API_KEY     api_key id=2ecdca priority=0 env:DEEPSEEK_API_KEY ←
```

```
Profile: default
Path:    C:\Users\28189\AppData\Local\hermes
Model:   deepseek-v4-pro (mac-provider)
Gateway: stopped
Skills:  91
.env:    exists
SOUL.md: exists
```

```
Vault is empty. Add an item with `hermes vault add`.
```

**三行结论**：`←` 标出当前选中的凭证；`config:` 前缀说明这把钥匙来自 `config.yaml` 的自定义端点、`env:` 说明来自环境变量；而 `Path:` 就是 profile 的边界 —— 换一个 profile，这个路径就是另一个目录。[[src:credential-pools]] [[src:profiles]]

## 原理

### 密钥放哪：`.env` 是默认答案，只有一处例外

Hermes 从**进程环境**和 `~/.hermes/.env` 读取变量；密钥、bot token、OAuth secret 一律进 `.env`，非密钥的行为设置优先写 `config.yaml`（或 `hermes config set`）。[[src:env-vars]]

唯一的例外是自定义 OpenAI 兼容端点：它的 `api_key` 按设计留在 `config.yaml` 的 `providers:`（老配置是 `custom_providers:`）里，凭证池会把它收录成一条 `config:<端点名>` 条目。**[本机实测]** 这台机器的 `config.yaml` 里 `custom_providers[0].api_key` 确实存着一个真密钥（值已脱敏）—— 所以**分享或备份 `config.yaml` 之前先处理它**。[[src:credential-pools]] [[src:env-vars]]

### 外部密钥管理器：用来集中轮换

不想把密钥落在磁盘上时，可以让 Hermes 在启动时从外部密钥管理器拉：Bitwarden Secrets Manager（`bws`）、1Password（`op://` 引用）、或任意 CLI vault（`keepassxc-cli`、`secret-tool`、`pass`，用「打印 `KEY=VALUE` 行的命令助手」接）。密钥管理器自己的 bootstrap token 仍然放 `.env`。[[src:secrets]]

多个源可以同时开，按确定的优先级阶梯生效：

1. **你的 `.env` / shell 默认赢**；源只有在自己的 `override_existing: true` 时才覆盖已有值（Bitwarden 默认开，好让集中轮换生效）。[[src:secrets]]
2. **映射源赢过批量源**：显式把变量名绑到引用（`env:` 映射）的源，优先于隐式注入整个项目的源。[[src:secrets]]
3. **同形状先声明者赢**；后一个源对已被认领的变量会被跳过，并且**启动时告警，绝不静默**。[[src:secrets]]

两个跟多 profile 有关的旋钮：`secrets.preserve_existing`（这张表里的变量永远以 `.env`/shell 为准，适合每个 profile 必须不同的平台密钥）和 **profile 别名**（默认开：vault 里叫 `FOO_<PROFILE>` 的密钥会同时补水到规范的 `FOO`，后缀只认 `*_API_KEY`、`*_TOKEN`、`*_SECRET`、`*_KEY`、`*_PASSWORD`）。[[src:secrets]]

每个源注入的密钥都会带来源标签（例如 `(from Bitwarden)`），所以你永远知道一个值是从哪来的。[[src:secrets]]

### 凭证池：同一家 provider 的多把钥匙

凭证池（credential pool）给同一个 provider 注册多把钥匙，一把撞上限流或额度就自动轮换到下一把健康的，会话不至于中断。它和 fallback provider 不是一回事：**池是同一家内部轮换，fallback 是换一家**；池里的钥匙全用光了才轮到 fallback。[[src:credential-pools]]

- 三种典型路径：`hermes auth add <provider> --api-key ...`、`--type oauth`（浏览器登录）、编号环境变量（`OPENROUTER_API_KEY_2`、`_3` …）—— 编号的兄弟变量会被自动发现成池条目，不写进 `auth.json`。[[src:credential-pools]]
- 轮换策略：`fill_first`（默认，按 `priority` 用第一把健康的）、`round_robin`、`least_used`、`random`，写在 `credential_pool_strategies` 里。[[src:credential-pools]]
- 错误处理：402 额度立刻轮换（1 小时冷却）；429 先重试同一把一次，连续第二次 429 才轮换；401 先试刷新 OAuth，刷新失败才轮换。[[src:credential-pools]]
- **轮换会让 prompt 缓存失效**：provider 侧的缓存在服务请求的模型**和账号/API key** 上记账，换 key 就等于下一次要按全价重读整段对话。长会话里每次轮换都是一次全价通行。[[src:credential-pools]]
- 借来的密钥在 `auth.json` 里只留元数据：来源引用、标签、计数和不可逆指纹。[[src:credential-pools]]
- 子代理共享父级的池，所以 `delegate_task` 出去的孩子也享受同样的抗限流能力。[[src:credential-pools]]

### profile：一台机器上的多个 agent

一个 profile 就是一个独立的 Hermes home 目录：自己的 `config.yaml`、`.env`、`SOUL.md`、记忆、会话、技能、cron 与状态库。创建后它**自动变成一条命令**：`hermes profile create coder` 之后就有 `coder chat`、`coder setup`、`coder gateway start`（等价于 `hermes -p coder ...`）。[[src:profiles]]

几条硬规则：

- **不要两个进程指向同一个 home**：两边都会自动写记忆，又都会在会话开始时把对方写的读进系统提示，互相叠加到不再是你的配置为止。需要共享记忆就用外部记忆 provider。[[src:profiles]]
- clone 的边界：`--clone` 只带 `config.yaml`、`.env`、`SOUL.md`、技能和两张记忆文件；`--clone-all` 是完整快照，但**排除**会话历史、`state.db`、`backups/`、`checkpoints/`，并且**不克隆 cron**（否则同一批任务会跑两遍）。[[src:profiles]]
- **消息渠道从不克隆**：bot token 与 allowlist、`platforms:` 配置、配对数据等一律留在源 profile —— 一个 bot 只能属于一个 profile。`--clone-channels` 才显式带走。[[src:profiles]]
- **OAuth 登录是共享而不是复制**：Anthropic / Codex / xAI 的 OAuth 用单次使用的 refresh token，复制一份不是第二份凭证、而是同一个凭证两个主人；所以 `--clone-all` 会把这类行丢掉，各 profile 继续读根目录的 `auth.json`。[[src:profiles]]
- 同名 token 冲突会被拦：两个 gateway 用同一个 bot token 时，第二个会被明确报错点出冲突的 profile。[[src:profiles]]
- `hermes update` 拉一次代码，并给**所有** profile 同步新的内置技能；你改过的技能永不被覆盖。[[src:profiles]]

### profile 不是沙箱

这是最容易搞混的一点：

| 概念 | 管什么 |
|---|---|
| profile | Hermes 自己的状态目录（config / .env / 会话 / 记忆 / 技能 / cron） |
| 工作目录（`terminal.cwd`） | 终端命令从哪个目录起步 |
| 沙箱 | 限制文件系统访问 —— profile **不提供**这个 |

在默认的 `local` 终端后端下，agent 仍然拥有你账号的文件系统权限；profile 不阻止它访问 profile 目录以外的文件夹。要确定 agent 的起步目录，就在该 profile 的 `config.yaml` 里显式写 `terminal.cwd`（`cwd: "."` 的含义是「启动 Hermes 时所在的目录」，不是 profile 目录）。[[src:profiles]]

## 亲手验证

### 验证一：给一个不存在的 profile —— 看边界报错

```bash
hermes -p nosuchprofile doctor
```

真实输出：

```
Error: Profile 'nosuchprofile' does not exist. Create it with: hermes profile create nosuchprofile
```

它不会退回 default 去执行 —— profile 名字拼错就是硬错误。[[src:profiles]]

### 验证二：确认 `config.yaml` 里到底有没有密钥（不要打印值）

```bash
grep -c -iE "sk-[a-z0-9]|ghp_" ~/.hermes/config.yaml
```

本机实测输出：

```
1
```

**这一个匹配就是本课最该记住的例外**：扫描命中的是 `custom_providers[0].api_key`（自定义端点）。自定义端点的密钥按设计存在 `config.yaml`；其他 provider 的密钥应该在 `.env` 里。所以：看到 >0 时先确认它是不是自定义端点，如果是别的形状，就把它搬到 `.env`（用 `hermes config set` 或 `hermes auth add`，不要手改 `config.yaml`）。[[src:credential-pools]] [[src:env-vars]]

### 验证三：没有池的 provider 什么也不打印

```bash
hermes auth list openrouter
```

本机实测：**没有任何输出**（这台机器的池子是 `custom:mac-provider` 与 `deepseek`）。没有池不代表错 —— 首次配好一把钥匙时，Hermes 会把它自动发现成「单把钥匙的池」。[[src:credential-pools]]

| 你观察到的 | 说明什么 |
|---|---|
| `Profile 'nosuchprofile' does not exist.` | profile 名是严格匹配的；不会静默退回 default |
| `grep` 计数 = 1（本机） | `config.yaml` 里确实可能有密钥 —— 只有自定义端点这一种情况是「按设计」 |
| `hermes auth list openrouter` 无输出 | 该 provider 还没有池条目；不是错误 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `Error: Profile 'nosuchprofile' does not exist. Create it with: hermes profile create nosuchprofile` | profile 名拼错 | `hermes profile list` 看真名；`hermes profile create <name>` 建它 |
| 两个进程写同一个 home，记忆越来越怪 | 同一个 `HERMES_HOME` 被两个 agent 同时写 | 一个 agent 一个 profile；共享记忆用外部记忆 provider |
| 第二个 gateway 起不来，报 token 冲突 | 一个 bot token 只能属于一个 profile | 给新 profile 配自己的 bot token；clone 默认不带走渠道 |
| 复制 OAuth 登录后两边都被登出 | 单次使用的 refresh token：复制 = 同一凭证两个主人 | 让所有 profile 继续读根 `auth.json`，或 `hermes -p <name> auth add <provider>` |
| 长会话里换 key 之后那一轮特别贵 | 缓存在账号上记账，轮换即全价重读 | 保证池里的钥匙额度充足；长会话避免频繁轮换 |
| 以为 `hermes profile export` 能当完整备份 | 导出会剥离凭证（按设计） | 整机迁移用 `hermes backup`；见 [[L54]] |
| 把密钥写进 `config.yaml` | 只有自定义端点的 `api_key` 按设计在那里 | 用 `hermes auth add <provider> --api-key ...`；其他设置用 `hermes config set` |
| 以为 profile 能隔离文件系统 | profile 只管 Hermes 状态，不是沙箱 | 要边界就用容器终端后端，或显式设 `terminal.cwd` |

## 试一试

- [ ] 给常用 provider 加第二把钥匙（`hermes auth add <provider> --api-key ...` 或 `--type oauth`），再 `hermes auth list` 确认池里是两条
- [ ] 建一个 `coder` profile：`hermes profile create coder`，配它自己的 `.env` 和 `terminal.cwd`，观察提示符变成 `coder ❯`
- [ ] 自查：把 `config.yaml` 里出现过的密钥形状字符串找出来（**不要打印值**），决定怎么处置
- [ ] 如果你有多个 profile 共用一个外部密钥管理器：写一份 `secrets.preserve_existing` 清单
- [ ] 把结论写进 `journal/`

## 下一步

- [[L50]] —— 审批层管「命令能不能跑」，这一课管「用谁的身份跑」
- [[L32]] —— 多代理：kanban 看板与 bot mode，profile 是它们的隔离单位
- [[L52]] —— 成本与缓存：轮换清缓存那一刀，从成本角度再看一遍
- [[L54]] —— 备份、升级与迁移：`hermes backup` 与 `hermes profile export` 的区别
- 想深入：[[src:credential-pools]]（轮换算法与错误恢复表）、[[src:secrets]]（优先级阶梯的完整规则）

## 出处

- [[src:secrets]] Secrets — https://hermes-agent.nousresearch.com/docs/user-guide/secrets
- [[src:credential-pools]] Credential Pools — https://hermes-agent.nousresearch.com/docs/user-guide/features/credential-pools
- [[src:profiles]] Profiles: Running Multiple Agents — https://hermes-agent.nousresearch.com/docs/user-guide/profiles
- [[src:env-vars]] Environment Variables — https://hermes-agent.nousresearch.com/docs/reference/environment-variables
