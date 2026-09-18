---
id: L31
title: "事件驱动：webhooks 让外部事件触发 Hermes"
stage: 3
level: 进阶
minutes: 20
prereq: [L23, L30]
tags: ["webhooks", "事件驱动", "HMAC", "GitHub"]
sources: [webhooks, webhook-github-pr-review, pipe-script-output]
updated: 2026-09-16
---

# L31 · 事件驱动：webhooks 让外部事件触发 Hermes

> **一句话**：webhooks 让 GitHub、JIRA、Supabase 这类服务拿着签名 POST 一个 JSON 过来，Hermes 把它渲染成 prompt 跑一次 agent，再把结果送回你指定的地方。

## 你将学会

- 打开 webhook 平台并创建一条订阅，读出它的 URL 与事件过滤条件
- 说清一个 POST 进来之后要经过哪几道闸门（签名 → 路由 → 过滤 → 模板 → 交付）
- 用 `deliver_only` 和 `cron_job` 两种方式控制「这次事件要不要花钱」
- 亲手制造一次「测试 POST 连不上」的失败，并从报错定位到真正的原因

**前置**：[[L23]]、[[L30]] · **预计耗时**：20 分钟

## 先动手

第一步，先看它现在是什么状态（不需要任何配置就能跑）：

```bash
hermes webhook list
```

本机真实输出：

```

  Webhook platform is not enabled. To set it up:

  1. Run the gateway setup wizard:
     hermes gateway setup

  2. Or manually add to ~/.hermes/config.yaml:
     platforms:
       webhook:
         enabled: true
         extra:
           port: 8644
           secret: "your-global-hmac-secret"

  3. Or set environment variables in ~/.hermes/.env:
     WEBHOOK_ENABLED=true
     WEBHOOK_PORT=8644
     WEBHOOK_SECRET=your-global-secret

  Then start the gateway: hermes gateway run
```

第二步，按它说的做（把 secret 换成你自己的随机串）：

```yaml
# ~/.hermes/config.yaml
platforms:
  webhook:
    enabled: true
    extra:
      port: 8644
      secret: "your-global-hmac-secret"
```

第三步，创建一条订阅，拿到 URL：

```bash
hermes webhook subscribe demo-issues \
  --events "issues" \
  --prompt "New issue #{issue.number}: {issue.title}" \
  --deliver log
```

本机真实输出（Secret 那一行我打了码 —— 那是自动生成的，别贴进教程或聊天记录）：

```

  Created webhook subscription: demo-issues
  URL:    http://localhost:8644/webhooks/demo-issues
  Profile: default
  Secret: <自动生成的随机串，此处已打码>
  Events: issues
  Deliver: log
  Prompt: New issue #{issue.number}: {issue.title}

  Configure your service to POST to the URL above.
  Use the secret for HMAC-SHA256 signature validation.
  The gateway must be running to receive events (hermes gateway run).
```

再跑一次 `hermes webhook list`，就能看到订阅被持久化了：[[src:webhooks]]

```
  1 webhook subscription(s):

  ◆ demo-issues
    Agent-created subscription: demo-issues
    URL:     http://localhost:8644/webhooks/demo-issues
    Profile: default
    Events:  issues
    Deliver: log
```

不想要了就 `hermes webhook remove demo-issues`。[[src:webhooks]]

## 原理

### 一次 POST 进来之后发生什么

```text
外部服务 ──POST──▶ :8644/webhooks/<route>
                     │
                     ├─ 1. HMAC 签名校验（失败 → 401）
                     ├─ 2. 按路径找路由（找不到 → 404）
                     ├─ 3. events 白名单（不匹配 → {"status":"ignored","event":"ping"}）
                     ├─ 4. filters / script 过滤（不匹配 → {"status":"ignored","reason":"filter"}）
                     ├─ 5. 幂等检查（同一个 delivery id 第二次来 → duplicate）
                     ├─ 6. 渲染 prompt 模板
                     └─ 7. 交付：agent 跑一轮 → deliver 目标
                          （或者 deliver_only / cron_job 两条绕开 agent 的路线）
```

### 路由的两种写法

- **静态路由**：写进 `config.yaml` 的 `platforms.webhook.extra.routes`，进程启动时加载。[[src:webhooks]]
- **动态订阅**：`hermes webhook subscribe`，存在 `~/.hermes/webhook_subscriptions.json`，
  适配器每次收到请求都热加载这个文件（mtime 判断），**不用重启网关**。同名的静态路由
  优先于动态订阅。[[src:webhooks]]

### 路由的字段（挑常用的）

| 字段 | 作用 |
|---|---|
| `events` | 接受哪些事件类型；空着＝全收。事件类型读 `X-GitHub-Event` / `X-GitLab-Event` / payload 里的 `event_type` |
| `secret` | HMAC 密钥，必填（可用全局 `secret` 兜底）；测试期可写 `"INSECURE_NO_AUTH"` 跳过校验 |
| `prompt` | 模板，支持点号取值 `{pull_request.title}`，`{__raw__}` 表示整份 payload（截断到 4000 字符） |
| `filters` | 声明式过滤，在签名/事件过滤之后、唤醒 agent 之前执行 |
| `script` | 更复杂的过滤/改写脚本，必须放在 `~/.hermes/scripts/` 下 |
| `deliver` | 结果去哪：`log`（默认）、`github_comment`、`telegram`、`discord`、`slack`、`email`… |
| `deliver_only` | `true` 时跳过 agent，模板渲染出来就是最终消息 |
| `cron_job` | 不新起会话，改为触发一个已存在的 cron job |
| `coalesce` | 同一实体的连续事件去抖，合成一次运行 |
| `skills` / `toolsets` | 这次运行要加载的技能 / 工具集 |

模板只有 `{field}` 和 `{nested.field}` 两种替换，**没有** if/else 之类的条件语法；
没解析到的键会原样留着 `{key}` 不报错。[[src:webhooks]]

### 过滤要在唤醒 agent 之前做

GitHub 的 `pull_request` 事件会带一堆 action（`opened`、`synchronize`、`reopened`、
`closed`、`labeled`…）。在 prompt 里写「如果是 closed 就停在这里别评论」**不能省钱** ——
agent 照样会跑一整轮。要省钱就在路由上过滤：[[src:webhook-github-pr-review]]

```yaml
filters:
  - field: "action"
    in: ["opened", "synchronize", "reopened"]
```

### 三条路线，成本差一个数量级

| 路线 | 谁会跑 | 什么时候用 |
|---|---|---|
| 默认（agent 模式） | 一个完整的 agent 轮次 | 内容需要推理、判断、写评论 |
| `deliver_only: true` | 没有模型，只有模板渲染 | 数据库变更通知、监控告警、纯推送 |
| `cron_job: "<job>"` | 一个已存在的 cron job | 想复用已有的 prompt / 技能 / 交付目标 |

`deliver_only` 的 POST 是同步返回的：投递成功回 `200 OK`，目标拒绝回 `502`，
你的上游服务可以据此重试。[[src:webhooks]]

### 默认工具集是收窄过的

webhook 触发的 agent 运行默认只拿到 `web_search`、`web_extract`、`vision_analyze`、
`clarify` —— 因为 payload 里的文本（PR 标题、issue 正文）可能是任意第三方写的，
不该因为一段注入指令就能碰到你的终端。要放宽只能手动改 `config.yaml` 给某条路由加
`toolsets:`，`hermes webhook subscribe` **故意不提供**这个开关，避免 agent 自己给自己扩权。[[src:webhooks]]

### 四道默认闸门

| 闸门 | 默认值 |
|---|---|
| 速率上限 | 每条路由 30 请求/分钟（`rate_limit` 可调），超出回 `429` |
| 幂等 | delivery id 缓存 1 小时，重复投递静默丢弃并回 `200` |
| 请求体上限 | 1 MB（`max_body_bytes` 可调），超出回 `413` |
| 签名 | 每个路由必须有 secret；没有的话适配器**启动就失败** |

签名方式按来源自动选：GitHub 用 `X-Hub-Signature-256`（`sha256=` 前缀的 HMAC-SHA256），
GitLab 用 `X-Gitlab-Token`（明文比对），通用来源推荐 V2（`X-Webhook-Signature-V2` +
`X-Webhook-Timestamp`，时间戳必须落在 ±300 秒内，能挡住重放）。[[src:webhooks]]

**签名只证明「发送方」是谁，不证明「内容」可信**：PR 标题、commit message 都是第三方写的。
所以官方给的加固方向是收紧能力面（换 docker/ssh 后端、只开需要的工具集、保留审批），
而不是指望过滤输入文本。[[src:webhooks]]

### 反方向：不需要网关的 `hermes send`

不是所有场景都值得起一条 webhook 路由。如果脚本自己就知道要说什么，直接推：

```bash
hermes send --to telegram "deploy finished"
echo "RAM 92%" | hermes send --to telegram:-1001234567890
hermes send --to slack:#eng --subject "[CI] build.log" --file build.log
```

对 Telegram / Discord / Slack 这类 bot-token 平台，`hermes send` 直接用
`~/.hermes/.env` 与 `config.yaml` 里的凭证调平台 REST 接口，**不需要网关在跑**；
只有依赖常驻连接的自定义插件平台才要求网关。退出码是 Unix 惯例：
`0` 成功、`1` 投递失败、`2` 参数/配置错误，脚本里可以直接分支。[[src:pipe-script-output]]

一个例外值得记住：监控**网关自己**是否健康的看门狗（OOM、磁盘满）别用 `hermes send` ——
机器已经在抖的时候 Python 可能起不来，那种场景用最小化的 `curl`。[[src:pipe-script-output]]

## 亲手验证

### 验证一：订阅建好了，但 HTTP 端口其实没人听

```bash
hermes webhook test demo-issues
```

本机真实输出（网关没在跑的时候）：

```
  Sending test POST to http://localhost:8644/webhooks/demo-issues
  Error: <urlopen error [WinError 10061] 由于目标计算机积极拒绝，无法连接。>
  Is the gateway running? (hermes gateway run)
```

同一条边界用 `curl` 看会更直接：

```bash
curl -s -m 5 http://localhost:8644/health
```

本机真实结果：没有任何输出，shell 退出码 `7`（curl 的 `CURLE_COULDNT_CONNECT`）。
网关起来之后，同一个地址应该回 `{"status": "ok", "platform": "webhook"}`。[[src:webhooks]]

**这就是事件驱动系统最常见的故障形态**：配置全对，订阅也在，只是监听进程没起来。
`hermes webhook test` 只对动态订阅有效，读不到 `config.yaml` 里的静态路由。[[src:webhook-github-pr-review]]

### 验证二：确认「谁在做签名校验」

```bash
grep -n -A6 "routes:" ~/.hermes/config.yaml
```

改成一条**没有 secret** 的路由再启动网关，适配器会在启动阶段直接拒绝启动 ——
这是刻意设计：一个没有密钥的入口等于任何人都能唤醒你的 agent。[[src:webhooks]]

### 验证三：本地烟测（不需要真的 GitHub）

用 `openssl` 自己签一份 payload，直接打给你的路由。下面这段来自官方指南，
`deliver` 记得先改成 `log`，否则 agent 会真的去给假的 `org/repo#99` 发评论：[[src:webhook-github-pr-review]]

```bash
SECRET="your-webhook-secret-here"
BODY='{"action":"opened","number":99,"pull_request":{"title":"Test PR","user":{"login":"testuser"},"html_url":"https://github.com/org/repo/pull/99"},"repository":{"full_name":"org/repo"}}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print "sha256="$2}')

curl -s -X POST http://localhost:8644/webhooks/github-pr-review \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$BODY"
# 预期：{"status":"accepted","route":"github-pr-review","event":"pull_request","delivery_id":"..."}
```

| 你观察到的 | 说明什么 |
|---|---|
| `hermes webhook test` 报连接被拒 | 订阅保存了，但监听进程不在 —— 先看网关 |
| `curl /health` 退出码 7、无输出 | 端口上没有任何东西在听，与 Hermes 配置无关 |
| 网关起来后 `/health` 回 `{"status": "ok"}` | 适配器活了；这时再测签名才有意义 |
| 故意改错 secret 后回 `401 Unauthorized` | 签名校验是硬闸门，不是提示词层面的建议 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `Webhook platform is not enabled.` | `platforms.webhook.enabled` 还是 false | 加 `enabled: true` + `secret`，或 `hermes gateway setup` |
| 事件发出去了，Hermes 没反应 | 网关没跑（`hermes gateway status` 显示 not running） | `hermes gateway run` 前台跑一次，先看日志 |
| GitHub 回 `401 Unauthorized` | 路由里的 secret 与 GitHub 上填的不一致 | 两边改成同一个值；GitHub 看 `X-Hub-Signature-256` |
| GitHub 的 ping 事件没日志 | `ping` 不在 `events` 里，被安全忽略并回 `{"status":"ignored","event":"ping"}`，且只在 DEBUG 级别记录 | 不用管，它是来确认连通性的 |
| 同一个 PR 收到两条评论 | 上游没带 delivery id 头，幂等缓存认不出重复 | 确认源带 `X-GitHub-Delivery` / `X-Request-ID` 之类的头 |
| agent 说「我评论不了这个 PR」 | 默认 webhook 工具集里没有 `terminal`，它跑不了 `gh` | 给该路由手动加 `toolsets: ["terminal", "web"]` |
| `deliver: github_comment` 报 gh 相关错误 | 网关主机上 `gh` 没装或没登录 | `gh auth login`，并确认账号对该仓库有写权限 |
| 每次事件都烧一次 token | 过滤写在了 prompt 里，而不是 `filters` 里 | 把条件挪到路由的 `filters:` |
| 把 `INSECURE_NO_AUTH` 用在公网 | 只有绑定在 loopback 上时才接受；配成 `0.0.0.0` 会拒绝启动 | 只在本地测试用；上线必须配真实 secret |
| 事件密集时一个实体被跑了 5 次 | 上游连续推送，每个事件都有新的 delivery id | 给路由加 `coalesce`，按实体去抖 |

## 试一试

- [ ] 建一条 `deliver_only: true` 的路由，用 `curl` 打一次，确认在 `~/.hermes/logs/gateway.log` 里**没有**模型调用
- [ ] 给一条路由加 `coalesce: {key: "{repository.full_name}#{pull_request.number}", window_seconds: 30}`，快速连打三次同一个 PR，观察只跑一轮
- [ ] 复制官方 GitHub PR 审查示例，把它改成你仓库的；github.com 上填的 Payload URL 用 `ngrok http 8644` 给的地址（免费版每次重启都会换域名，记得同步改）[[src:webhook-github-pr-review]]
- [ ] 写一个脚本，用 `hermes send --to <平台名>` 把当天构建结果推到 Slack 或 Telegram（注意 `--to` 只接平台名或频道，不是文件路径）[[src:pipe-script-output]]
- [ ] 给一条路由加上 `- field: "action"` 的 `filters`，然后对比加过滤前后网关日志里 agent 运行的次数
- [ ] 把这次实验写进 `journal/`

## 下一步

- [[L33]] —— 网关本身：把 Hermes 接成常驻机器人的那套东西
- [[L34]] —— 用 `cron_job` 把 webhook 事件接进已有的定时任务，拼成流水线
- [[L30]] —— 出方向的那一半：`hooks.outbound` 把 Hermes 的事件推给外部
- 想深入：[[src:webhooks]] 的 Per-route toolsets 与 Security 两节

## 出处

- [[src:webhooks]] Webhooks — https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks
- [[src:webhook-github-pr-review]] Automated GitHub PR Comments with Webhooks — https://hermes-agent.nousresearch.com/docs/guides/webhook-github-pr-review
- [[src:pipe-script-output]] Pipe Script Output to Messaging Platforms — https://hermes-agent.nousresearch.com/docs/guides/pipe-script-output
