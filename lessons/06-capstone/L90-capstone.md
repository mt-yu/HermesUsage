---
id: L90
title: 毕业项目：自动化一件你真正在做的活
stage: 9
level: 进阶
minutes: 60
prereq: [L12, L15, L23, L34, L50]
tags: ["毕业项目", "capstone", "cron", "webhook", "技能", "交付", "归档"]
sources: [automation-blueprints, automate-with-cron, delegation-patterns, secure-work-machine]
updated: 2026-09-16
---

# L90 · 毕业项目：自动化一件你真正在做的活

> **一句话**：把阶段 0-5 的能力拧成一条产线——挑一件你每周真在手工做的活，写成技能 + 触发器 + 交付目标，再用证据证明它在你不在的时候也跑了。

## 你将学会

- 用三条筛子从 4 个候选场景里选定一个能立刻开工的活，并写出一页需求
- 把它落成三件东西：一个技能、一个触发器（cron 或 webhook）、一个交付目标
- 用 `hermes cron create` / `hermes webhook subscribe` 真正上线，并跑通一条排障链定位「没触发」和「没收到」
- 把结果交付到 Telegram 或本地文件，并把整个过程归档进 `journal/` + git 提交
- 用 12 条验收清单自己判定这门课是否真的过了

**前置**：[[L12]]、[[L15]]、[[L23]]、[[L34]]、[[L50]]（没学完也能开工，缺的部分回来补）· **预计耗时**：60 分钟

## 先动手

第一步不是建任务，而是量基线：**你这台机器现在能不能无人值守**。

```bash
hermes cron status
hermes cron list
hermes gateway status
```

你应该看到（本机实测，Windows 11 + Git Bash + hermes v0.21.3）：

```
✗ Gateway is not running — cron jobs will NOT fire

  To enable automatic execution:
    hermes gateway install    # Install as a user service
    sudo hermes gateway install --system  # Linux servers: boot-time system service
    hermes gateway            # Or run in foreground

  No active jobs
```

```
No scheduled jobs.
Create one with 'hermes cron create ...' or the /cron command in chat.
```

```
✗ Gateway is not running

To start:
  hermes gateway run      # Run in foreground
  hermes gateway install  # Install as Windows Scheduled Task (auto-start on login)
```

**看到 `✗` 就是你的 0 号工单**：cron 任务由 gateway 进程驱动，没有它，任务只是清单上的一行字。

第二步，3 分钟内产出这节课的输入——一页需求：

```bash
mkdir -p ~/capstone && cd ~/capstone
cat > BRIEF.md <<'MD'
# 我要自动化的活
1. 我每天/每周手工做的是什么：
2. 频率（每天 / 每周 / 外部事件触发）：
3. 结果要送到哪（telegram / 本地文件 / 平台评论）：
4. 我怎么知道它跑失败了：
5. 它跑坏了最坏会怎样（能重跑吗 / 会不会碰到别人的东西）：
6. 我给它起什么名字：
MD
ls
```

你应该看到 `BRIEF.md`。**这 6 行就是整个毕业项目的需求说明书**，后面每一步都在填它。

## 原理

### 一、触发器只有三种，先选类型再写内容

| 触发方式 | 什么时候触发 | 用什么建 |
|---|---|---|
| 时间表 | 按节奏跑（每小时 / 每晚 / 每周） | `cronjob` 工具或 `/cron` 斜杠命令 |
| GitHub 事件 | PR 打开、push、issue、CI 结果 | webhook 平台（`hermes webhook subscribe`） |
| API 调用 | 外部服务 POST JSON 到你的端点 | webhook 平台（config.yaml 路由 或 `hermes webhook subscribe`） |

三种都能把结果交付到 Telegram、Discord、Slack、SMS、email、GitHub 评论或本地文件。[[src:automation-blueprints]]

**判据**：如果你的活是「到了某个时间就该看一眼」，用时间表；如果是「别人做了某件事才需要我动」，用 webhook。

### 二、把一件活切成三层

```text
① 机械层：抓取 / 比对 / 落盘        → 脚本干（便宜、稳定、可重复）
② 判断层：这算不算重要 / 该怎么归类  → agent 干（贵、但只会这里出错）
③ 交付层：送到哪、长什么样           → --deliver + prompt 里的格式约定
```

`script` 参数就是这条分界线的开关：Python 脚本在每次执行前先跑，它的 stdout 成为 agent 的上下文。脚本负责机械部分（发请求、做 diff、记录状态），agent 只对脚本输出做推理。这比让 agent 自己去抓数据更便宜也更可靠。[[src:automate-with-cron]]

### 三、cron 里的 agent 没有你的聊天记录

cron 任务跑在**全新的会话**里，对当前聊天毫无记忆。**prompt 必须完全自包含**：把仓库名、URL、要跑的命令、格式要求、交付目标全部写进去。持久记忆会加载，所以写进 `MEMORY.md` 的长期偏好能带过去，但别依赖它承载任务关键细节。[[src:automate-with-cron]]

推论：**能写成技能的就别塞进 prompt**。技能按顺序在 prompt 之前加载，所以你该按「技能写怎么做、prompt 写这次做什么」来切分。[[src:automate-with-cron]]

### 四、交付目标决定你「看不看得见」

| 目标 | 写法 | 用在什么时候 |
|---|---|---|
| 创建它的那个聊天 | `--deliver origin`（默认） | 交互里临时试 |
| 本地文件 | `--deliver local` | 只想留档、不想被打扰 |
| Telegram / Discord / Slack | `--deliver telegram` / `discord` / `slack` | 你每天真的会看的地方 |
| 指定会话 / 话题 | `--deliver telegram:CHAT_ID`、`telegram:-100123:456` | 团队成员一起看 |
| 注入 Bot Chat | `--deliver bot-chat` | 想让机器人**读到并回应**这条输出 |

`bot-chat` 与其它目标不同：它把输出当作一条真实消息投进某个 profile 的 Bot Chat，机器人会像收到普通消息一样处理它——这是「定时任务的结果要触发布局下一位 bot」的用法。注意它**按机器本地解析**（profile 必须存在于跑调度器的这台机器上），并且**每投一次就烧一个 bot 回合**。[[src:automation-blueprints]] [[src:automate-with-cron]]

**安静与失败要分开设计**：监控类任务在「没事发生」时应该回 `[SILENT]`，cron 把这个标记当作静默符，投递会被抑制——安静时段不吵你。[[src:automation-blueprints]] [[src:automate-with-cron]]

但 `[SILENT]` 只管成功那一次：任务**硬失败**时引擎会往它的交付目标发一条 `⚠️ Cron 'X' failed…` 通知。往繁忙的公共频道投递的任务，用 `--failure-deliver local` 把这些通知彻底压掉（跑的状态仍然能在 `hermes cron list` 和运行历史里看到），或者用 `--failure-deliver slack:C_OPS` 指到运维频道；语法和 `--deliver` 一样，不写就跟 `--deliver` 走。[[src:automate-with-cron]]

### 五、零 token 的两条岔路

不是所有自动化都需要 LLM。当脚本自己就能产出最终那条消息时（内存告警、磁盘告警、心跳），有两条约零成本的路：[[src:automate-with-cron]]

- **script-only cron 任务**：同一个调度器，不跑 LLM，脚本 stdout 直接当交付内容。CLI 上对应 `--no-agent`（`hermes cron create --help` 原文：*Skip the LLM entirely — run --script on schedule and deliver its stdout directly. Empty stdout = silent.*）
- **从一个已在运行的脚本里一次性发出去**：CI 步骤、post-commit 钩子、部署脚本这类已经有触发者的场景，用 `hermes send` 把 stdout 或文件直接管道到 Telegram / Discord / Slack，不用建 cron 条目

**判据**：这件事需要「判断」吗？不需要 → `--no-agent` 或 `hermes send`。需要 → 才付 LLM 的钱。

### 六、该委派的部分才委派，该持久的别委派

毕业项目里最容易犯的错，是把「必须活过这次会话」的任务交给 `delegate_task`。委派适合：推理重的子任务（调试、代码评审、研究综合）、会产生大量中间数据从而淹没你上下文的活、可以并行推进的独立工作流。[[src:delegation-patterns]]

典型用法是「并行研究」——三个主题同时跑，每个子代理各自检索后交回一份摘要，父代理再综合成一份简报。[[src:delegation-patterns]]

**但委派不持久**：顶层委派在后台跑、结果稍后回贴，可它仍然绑在所属会话与 Hermes 进程上。会话关闭、`/stop`、`/new` 或进程重启都可能取消或遗弃正在进行的工作。**必须活过这些边界的活，交给 `cronjob`（或 `terminal(background=True, notify_on_complete=True)`）。**[[src:delegation-patterns]]

另外两条要记住的：子代理**什么都不知道**（必须显式传文件路径、报错原文、项目结构、约束），以及**子代理的一句话总结不是证据**——它说「改好了、测试过了」，你要自己跑一遍或读 diff。[[src:delegation-patterns]]

### 七、它跑在你的主力机上，先把护栏收紧

默认值已经做了大部分事：危险命令要审批（`approvals.mode: smart` 用辅助模型判风险，低风险自动放行、真危险的自动拒绝、拿不准的手动弹窗）；审批弹窗**失败即拒绝**（默认 300 秒不响应就拒绝，走开不会静默批准）；一份 hardline 黑名单永远生效（`rm -rf /`、fork 炸弹这类，无视审批模式和 `--yolo`，且没有覆盖开关）；`write_file` / `patch` 写不进 `~/.ssh/`、`~/.aws/`、`.env` 这类敏感路径；输出里的疑似密钥默认打码（`security.redact_secrets`）；没有遥测，数据只去你配的模型供应商。[[src:secure-work-machine]]

在共享机器或工作机上，再叠这几层：[[src:secure-work-machine]]

```yaml
approvals:
  mode: manual                  # 每一条被标记的命令都由你自己看
  timeout: 300                  # 不响应=拒绝（fail-closed）
  deny:                         # 永不运行清单——连 /yolo 也拦得住
    - "git push --force*"
    - "*curl*|*sh*"
    - "dd if=* of=/dev/*"

checkpoints:
  enabled: true                 # 破坏性操作前自动快照，事后 /rollback

terminal:
  backend: docker               # 或 ssh：把命令执行挪出宿主机
  docker_forward_env: []        # 显式白名单；空 = 密钥不进容器
```

想限制写入范围，用 `HERMES_WRITE_SAFE_ROOT`（多个根在 Unix 上用 `:` 分隔）。注意别把它只设成项目目录——那样 agent 就写不了 `~/.hermes/cron/jobs.json` 和 profile 技能了，要**把 Hermes home 作为第二个根**写进去。[[src:secure-work-machine]]

最后一句要清醒：这些是**给「诚实但弄错」的 agent 的护栏，不是对故意作恶的进程的沙箱**。真要隔离就换执行后端（Docker / ssh），那是为隔离设计的边界。[[src:secure-work-machine]]

### 八、先选场景：4 个能立刻开工的候选

| 候选 | 触发器 | 立刻能跑的最小命令（复制即可开工） |
|---|---|---|
| **① 每日信息简报**（行业新闻 / 竞品动态 / arXiv） | 时间表 | `hermes cron create "0 8 * * *" "读 ~/capstone/sources.md 里的来源，抓最近 24 小时的内容，跨来源去重后输出最多 5 条：标题 — 为什么相关 — 链接。无新内容只回 [SILENT]。" --name "每日简报" --deliver telegram` |
| **② PR 自动评审** | GitHub 事件 | `hermes webhook subscribe github-pr-review --events "pull_request" --prompt "Review PR #{pull_request.number}: {pull_request.title}。Diff 用 curl -sL {pull_request.diff_url} 取。检查安全、性能、可读性、是否缺测试，写一段简短中文评审。" --skills github-code-review --deliver github_comment` |
| **③ 页面 / 价格监控** | 时间表 + 比对 | `hermes cron create "every 1h" "脚本输出 CHANGE DETECTED 就总结变了什么、为什么重要；输出 NO_CHANGE 只回 [SILENT]。" --script ~/.hermes/scripts/watch-site.py --name "价格监控" --deliver telegram` |
| **④ 周报自动生成 + 归档** | 时间表 | `hermes cron create "0 9 * * 1" "汇总本周：本仓库 git log --since=7.days 的提交、未完成的 TODO、下周优先级。写成 300 字以内的周报，存到 ~/capstone/reports/$(date +%Y%m%d).md 并把路径打出来。" --name "周报" --deliver local` |

参考量级：简报 / 周报在官方 blueprint 里就是 `0 8 * * *`（每天 8:00）与 `0 9 * * 1`（每周一 9:00）；监控类用 `every 30m` / `every 1h`。[[src:automation-blueprints]] [[src:automate-with-cron]]

**三条筛子**（三条都过才值得做）：

1. **频率 ≥ 每周一次**，且每次都在做同一套动作——做一次的活不值得自动化；
2. **你已经在手工做**——不是「听起来该做」的新想法，否则你会在第七天关掉它；
3. **失败可忍受**——它能重跑、不碰生产数据、不替你发对外消息。做不到就先把交付目标降级成 `--deliver local`。

### 九、从需求到上线的六步

| 步 | 产出 | 判据 |
|---|---|---|
| ① 选场景 | `BRIEF.md` 的第 1-2 行 | 过上面三条筛子 |
| ② 写下来 | 完整的 `BRIEF.md` | 第 6 行有名字，第 4-5 行能回答「失败怎么办」 |
| ③ 变技能 | `.hermes/skills/<name>/SKILL.md` | `description` 一句话说清「什么时候该用我」 |
| ④ 接触发器 | 一条真实 job / 一条真实订阅 | `hermes cron list --all` 或 `hermes webhook list` 里能看到它 |
| ⑤ 验证 | 一次真实执行 + 一次失败演练 | 交付物真的到了；失败真的被记录了 |
| ⑥ 归档 | journal 条目 + 独立提交 | `python scripts/journal.py log` 里能看到它 |

技能文件的完整规范见 [[L15]] 与本仓库自带的 `.hermes/skills/session-journal/SKILL.md`（现成样例，直接抄形状）；本课只负责把它**挂到触发器上**。

### 十、可以直接抄的四段骨架

#### 骨架 A：技能（`.hermes/skills/daily-briefing/SKILL.md`）

```markdown
---
name: daily-briefing
description: "Use when producing the daily information briefing from my source list. Enforces dedupe, 5-item cap, and link-only output."
version: 1.0.0
---

# 每日信息简报

## 何时用
当任务要求「生成今日简报」「汇总我关注的来源」时。

## 固定流程
1. 读 `~/capstone/sources.md`，每行一个 URL
2. 逐条抓取，只保留最近 24 小时的内容
3. 跨来源去重（同一条消息出现在两个站，只留最早出现的那个）
4. 按「与我相关的程度」排序，**最多输出 5 条**
5. 每条一行：`标题 — 一句为什么相关 — 链接`
6. 全部来源都没有新内容时，只输出 `[SILENT]`

## 硬约束
- 任何一条链接必须是抓到的原文链接；抓不到正文就跳过该来源，并在末尾列出「跳过：<URL>（原因）」
- 不写总结段落，不写「综上所述」
```

#### 骨架 B：cron 任务（时间表型）

```bash
hermes cron create "0 8 * * *" \
  "你是我的每日信息简报员。按 daily-briefing 技能的固定流程执行。

来源清单：~/capstone/sources.md（每行一个 URL）
时间窗：最近 24 小时
输出：最多 5 条，每条一行：标题 — 为什么相关 — 链接
无新内容时：只输出 [SILENT]

硬约束：不要编造链接；拿不到正文就跳过并在末尾列出跳过项。" \
  --name "每日信息简报" \
  --skill daily-briefing \
  --script ~/.hermes/scripts/briefing-fetch.py \
  --deliver telegram \
  --failure-deliver local \
  --workdir "$HOME/capstone"
```

四个参数值得单独说：`--skill` 挂技能（可重复，技能按顺序在 prompt 之前加载）；`--script` 先跑采集脚本、stdout 注入 agent 的 prompt；`--failure-deliver local` 把失败通知压成本地记录；`--workdir` 固定 job 的运行目录，同时会把该目录的上下文文件注入进来、并作为 terminal/file/code_exec 的 cwd（路径要写绝对路径）。[[src:automate-with-cron]]

其它常用开关（本机 `hermes cron create --help` 实测存在）：`--no-agent`（不跑 LLM，脚本 stdout 直接交付，空输出=静默）、`--monitor-script` / `--monitor-url`（每次 tick 先跑廉价源脚本/抓一次 URL，输出未变则**完全跳过 agent**）、`--continuity`（每次带上次输出醒来，便于去重）、`--paused` + `--paused-reason`（先建不启用）、`--model` / `--provider`（把 job 钉在某个模型上）、`--repeat`（跑几次后停）。[[src:automate-with-cron]]

监控型任务的最小脚本骨架（脚本负责机械比对，agent 只判断「这算不算重要」）：

```python
# ~/.hermes/scripts/watch-site.py
import hashlib, json, os, urllib.request

URL = "https://example.com/pricing"
STATE_FILE = os.path.expanduser("~/.hermes/scripts/.watch-site-state.json")

req = urllib.request.Request(URL, headers={"User-Agent": "Hermes-Monitor/1.0"})
content = urllib.request.urlopen(req, timeout=30).read().decode()
current_hash = hashlib.sha256(content.encode()).hexdigest()

prev_hash = None
if os.path.exists(STATE_FILE):
    with open(STATE_FILE) as f:
        prev_hash = json.load(f).get("hash")

with open(STATE_FILE, "w") as f:
    json.dump({"hash": current_hash, "url": URL}, f)

if prev_hash and prev_hash != current_hash:
    print(f"CHANGE DETECTED on {URL}")
    print(f"Previous hash: {prev_hash}")
    print(f"Current hash: {current_hash}")
    print(f"\nCurrent content (first 2000 chars):\n{content[:2000]}")
else:
    print("NO_CHANGE")
```

配套的 prompt 只要一句话：脚本说 `CHANGE DETECTED` 就总结变了什么、为什么重要；说 `NO_CHANGE` 就只回 `[SILENT]`。[[src:automate-with-cron]]

#### 骨架 C：webhook 订阅（事件驱动型）

**写法一：动态订阅（CLI）**

```bash
hermes webhook subscribe github-pr-review \
  --events "pull_request" \
  --prompt "Review this pull request:
Repository: {repository.full_name}
PR #{pull_request.number}: {pull_request.title}
Author: {pull_request.user.login}
Action: {action}
Diff URL: {pull_request.diff_url}

Fetch the diff with: curl -sL {pull_request.diff_url}

Review for:
- Security issues (injection, auth bypass, secrets in code)
- Performance concerns (N+1 queries, unbounded loops, memory leaks)
- Code quality (naming, duplication, error handling)
- Missing tests for new behavior

Post a concise review. If the PR is a trivial docs/typo change, say so briefly." \
  --skills github-code-review \
  --deliver github_comment
```

`--prompt` 里的 `{dot.notation}` 会被 payload 字段替换；可用变量包括 `{repository.full_name}`、`{pull_request.title}`、`{issue.number}`、`{action}`、`{sender.login}`，以及取整个 JSON 的 `{__raw__}`（4000 字符处截断）。[[src:automation-blueprints]]

**写法二：静态路由（config.yaml）**

```yaml
platforms:
  webhook:
    enabled: true
    extra:
      port: 8644
      secret: "your-global-secret"
      routes:
        github-pr-review:
          events: ["pull_request"]
          secret: "github-webhook-secret"
          prompt: |
            Review PR #{pull_request.number}: {pull_request.title}
            Repository: {repository.full_name}
            Author: {pull_request.user.login}
            Diff URL: {pull_request.diff_url}
            Review for security, performance, and code quality.
          skills: ["github-code-review"]
          deliver: "github_comment"
          deliver_extra:
            repo: "{repository.full_name}"
            pr_number: "{pull_request.number}"
```

[[src:automation-blueprints]]

两边都对上之后，在 GitHub 侧：**Settings → Webhooks → Add webhook**，Payload URL 填 `http://your-server:8644/webhooks/github-pr-review`，Content type 选 `application/json`，Secret 填 `github-webhook-secret`，Events 选 **Pull requests**。[[src:automation-blueprints]]

平台没开的时候，`hermes webhook list` 会直接把开启方式打给你——本机实测：

```
  Webhook platform is not enabled. To set it up:

  1. Run the gateway setup wizard:
     hermes gateway setup

  2. Or manually add to ~/AppData/Local/hermes/config.yaml:
     platforms:
       webhook:
         enabled: true
         extra:
           port: 8644
           secret: "your-global-hmac-secret"

  3. Or set environment variables in ~/AppData/Local/hermes/.env:
     WEBHOOK_ENABLED=true
     WEBHOOK_PORT=8644
     WEBHOOK_SECRET=your-global-secret

  Then start the gateway: hermes gateway run
```

#### 骨架 D：把结果交付出去

**送到 Telegram / 你的手机：**

```bash
# cron 任务：结果直接进 Telegram
hermes cron create "0 9 * * 1" "生成本周周报：..." --name "周报" --deliver telegram

# 已有脚本 / CI 步骤：一次性把 stdout 或文件管道出去（不需要 cron）
echo "deploy finished" | hermes send --to telegram
hermes send --to telegram:-1001234567890 -f ~/capstone/report.md -s "本周周报"
```

`hermes send` 复用 gateway 已经配好的平台凭证（`~/.hermes/.env` + `~/.hermes/config.yaml`）——没有 LLM、没有 agent 循环，Telegram / Discord / Slack / Signal 这类 bot-token 平台**不需要 gateway 在跑**。[[src:automate-with-cron]]

**只留档、不打扰：** 用 `--deliver local`，产物落在本机（本机实测存在 `~/.hermes/cron/output/` 目录，进去按 job ID 找；不要凭猜写路径，用 `ls` 确认）。[[src:automation-blueprints]]

## 亲手验证

这一节的四个验证，目标是**让真实失败暴露出来**。跑成功的路径谁都会，能定位失败才算会了。

### 验证一：cron 没触发，按这五步查

```bash
hermes cron status              # ① 调度器活着吗
hermes cron list --all          # ② 任务在不在、叫什么名字（--all = Include disabled jobs）
hermes cron runs --limit 20     # ③ 有没有执行记录
hermes cron doctor              # ④ 任务自身健康吗
hermes cron incidents           # ⑤ 有没有失败事件
```

本机实测（gateway 没启动 + 无 active job）：

```
✗ Gateway is not running — cron jobs will NOT fire
...
  No active jobs
```

```
No scheduled jobs.
Create one with 'hermes cron create ...' or the /cron command in chat.
```

```
No cron execution attempts recorded.
```

```
✓ Cron doctor found no issues
  No active jobs configured.
```

```
No cron failure incidents recorded.
```

**读法**：① 是 `✗` 就到此为止——先 `hermes gateway install`（Windows 上装成开机自启的计划任务）或前台 `hermes gateway run`，再回来；①绿而②空，说明任务根本没建成或被暂停了（`hermes cron list --all` 的 `--all` 就是用来算上 disabled 任务的）；②有任务、③却一直是 `No cron execution attempts recorded.`，那就是调度器没在跑——本机实测过这个组合：任务 `[active]`、有 `Next run`，但 `hermes cron tick` 什么都不做（没有到点的任务），`hermes cron runs` 依然是空的。

想立刻验证内容而不等排期，用 `hermes cron run <job_id>`（下一次调度 tick 执行它）：

```
Triggered job: capstone-probe2 (fe4186a17950)
  Job is paused/disabled; resume it before running.
```

**这条输出很典型**：paused 的任务 `run` 不动，得先 `hermes cron resume <job_id>`。[[src:automate-with-cron]]

### 验证二：webhook 没收到，按这三步查

```bash
hermes webhook list                                     # ① 平台开没开、订阅在不在
hermes webhook test github-pr-review --payload '{"action":"opened"}'   # ② 自己发一条测试 POST
hermes gateway status                                   # ③ 网关进程在不在
```

本机实测（Webhook 平台未启用）：

```
  Webhook platform is not enabled. To set it up:
  ...
  Then start the gateway: hermes gateway run
```

`hermes webhook test` 的 `--payload` 默认发一条测试 payload；没有平台时它和 `list` 一样先被这道门挡住。[[src:automation-blueprints]]

**读法**：①就被挡 → 先按 ③ 开启平台并启动 gateway，别去查 payload；平台开着、①有订阅、②却 200 而 agent 没动 → 先核对 `--events`（事件名对不上就直接被忽略）和 `--secret`（HMAC 对不上会拒收）；②进去了但没交接成功 → 用 `--deliver log` 让渲染结果先落到日志里看模板渲染对不对。

### 验证三：故意制造一次失败，看通知去哪

失败路径必须演练一次，否则你永远不知道它会往哪个频道喊。

```bash
hermes cron list --all
hermes cron run <job_id>        # 或等到点
hermes cron runs --limit 5      # 看有没有这次执行
hermes cron incidents           # 看有没有失败事件
```

| 你观察到的 | 说明什么 |
|---|---|
| `hermes cron runs` 出现了这次执行 | 执行记录是持久的，事后可查 |
| `hermes cron incidents` 出现了条目 | 连续失败会升级成 incident，等你去 `ack` |
| 你的公共频道没被 `⚠️ Cron 'X' failed…` 刷屏 | `--failure-deliver local` 生效了 |
| paused 的 job 报 `Job is paused/disabled; resume it before running.` | 先 resume，再触发 |

失败通知的形态与投递目标见 [[src:automate-with-cron]]；incident 的过滤维度用 `hermes cron incidents --state {detected,alerted,resolved,closed}`（本机 `--help` 实测存在）。

### 验证四：用 git 证明变化真的发生过

自动化最怕「它好像跑了，但没留下痕迹」。每次收尾都留一条可回滚的记录：

```bash
python scripts/journal.py commit --kind session \
  --title "上线每日信息简报" \
  --scope L90 \
  --summary "新增 daily-briefing 技能；建 cron job；交付到 telegram" \
  --learned "gateway 没装前 cron 只是清单上的一行字"

python scripts/journal.py log          # 看这条记录在不在
git log --oneline -5                   # 看独立提交在不在
```

**判据**：`journal.py log` 里有这条、`git log` 里有对应提交、并且需要时能 `git revert`。归档流程与规则见本仓库 `.hermes.md` 第 4 节。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `✗ Gateway is not running — cron jobs will NOT fire` | cron 由 gateway 进程驱动；你只装了 CLI，没装/没启动服务 | `hermes gateway install`（Windows 装成计划任务）；临时用 `hermes gateway run`；复查 `hermes cron status` |
| `No scheduled jobs.` 但 `~/.hermes/cron/jobs.json` 里明明有任务 | 默认视图只列会被调度的任务，paused/disabled 的可能不出现（`hermes cron list --all` 的说明是 *Include disabled jobs*）；本机实测还遇到 `--all` 也为空、而 `jobs.json` 里确有一条 `paused` 任务的情况 | 先 `hermes cron list --all`；仍为空就直接读 `~/.hermes/cron/jobs.json` 核对，再用 `hermes cron resume <job_id>` 把它拉回 active |
| 建完任务时出现 `⚠  Gateway is not running — jobs won't fire automatically.` | 创建成功，但没人驱动调度 | 这是警告不是失败；按第一条装 gateway，`hermes cron list` 里 `Next run` 会给出排期时间 |
| `Triggered job: X` 紧跟 `Job is paused/disabled; resume it before running.` | `run` 不会自动 resume | `hermes cron resume <job_id>` 之后再 `hermes cron run <job_id>` |
| `hermes cron runs` 永远回 `No cron execution attempts recorded.` | 一次都没执行过（通常=调度器没跑） | 先 `hermes cron status`，再手动 `hermes cron run <job_id>` 造一次记录 |
| `Webhook platform is not enabled. To set it up:` | `platforms.webhook.enabled` 没开 | 用 `hermes gateway setup`，或给 config.yaml 加 `platforms.webhook.enabled: true` + `extra.port` / `extra.secret`，然后 `hermes gateway run` |
| `hermes webhook test <name>` 也是同一句「platform is not enabled」 | 平台门在订阅校验之前 | 先开平台——它不会告诉你「订阅不存在」，别被误导去查名字 |
| 安静时段仍被通知刷屏 | prompt 里没写清静默条件 | 明确写「没有新内容时只输出 `[SILENT]`」，并且不要让它解释这个标记 |
| 公共频道被 `⚠️ Cron 'X' failed…` 刷屏 | 失败通知默认跟着 `--deliver` 走 | 加 `--failure-deliver local`（压掉）或指向 ops 频道（`--failure-deliver slack:C_OPS`） |
| 任务里 agent 说「我按你说的那个文件改好了」，但找不到文件 | cron 会话没有你的聊天历史，prompt 不自包含 | 把绝对路径、命令、格式要求全部写进 prompt；用 `--workdir "$HOME/xxx"` 固定运行目录 |
| 把「必须活过这次会话」的活丢给 `delegate_task`，结果半途没了 | 顶层委派绑在会话与进程上，不持久 | 改用 `cronjob`（或 `terminal(background=True, notify_on_complete=True)`）[[src:delegation-patterns]] |
| 子代理报 `⚠️ Subagent failed — "your goal": <reason>` | 子代理进程死了（供应商报错、超时、崩溃） | 错误完整回传给父代理；把目标拆小、把 context 补齐后重跑 [[src:delegation-patterns]] |
| 「它明明改好了」但代码没动 | 子代理的总结只是总结 | 自己跑测试或读 diff 才算验证过 [[src:delegation-patterns]] |
| 危险命令一直被等审批、最后被拒 | `approvals.mode: smart` 会弹窗；不响应超时（默认 300 秒）即**拒绝**（fail-closed） | 人在旁边就回答弹窗；无人值守的任务不要把危险命令写进 prompt；`approvals.deny` 里显式禁掉不该跑的命令 [[src:secure-work-machine]] |
| 设了 `HERMES_WRITE_SAFE_ROOT` 之后 agent 写不了 `~/.hermes/cron/jobs.json`、也动不了技能 | 限制成项目目录一个根，把 Hermes 自己的状态目录也关在外面了 | 把 Hermes home 作为第二个根写进去，Unix 上用 `:` 分隔 [[src:secure-work-machine]] |

## 试一试

把毕业项目真正做完，然后逐条打勾。

### 12 条验收清单

- [ ] `BRIEF.md` 的 6 行全填了，没有一行是「看情况」或「待定」
- [ ] `hermes cron status` 不再显示 `✗`（或你已经明确知道自己在用前台 `hermes gateway run`）
- [ ] `hermes cron list --all` 能列出你的任务，且 `Next run` 不是 `None`
- [ ] 存在一份 `.hermes/skills/<name>/SKILL.md`，`description` 一句话说清「什么时候该用我」
- [ ] 创建命令里有 `--skill <你的技能名>`（cron 按顺序在 prompt 之前加载它）
- [ ] 端到端跑通过至少一次：`hermes cron runs --limit 5` 里能查到这次执行
- [ ] 交付可见：Telegram 收到过一条真实消息，或 `--deliver local` 的产物文件确实存在于 `~/.hermes/cron/output/` 下
- [ ] 安静路径有效：没有任何新内容的那一次，你没有收到通知（`[SILENT]` 生效）
- [ ] 失败路径可见：按验证三演练过，`hermes cron runs` 或 `hermes cron incidents` 里有记录
- [ ] 失败通知没打进公共频道（`--failure-deliver local`，或指向了专门的 ops 频道）
- [ ] 记录里没有明文密钥：`grep -riE 'sk-|ghp_|xox[bp]-' BRIEF.md .hermes/skills/*/SKILL.md` 没有命中
- [ ] 有归档：`python scripts/journal.py log` 能看到这一条，`git log --oneline -5` 里有对应的独立提交

### 四道进阶练习

- [ ] **省一次钱**：把那条最频繁的任务改成 `--no-agent`（脚本自己能产出最终消息）或加 `--monitor-url`，对比前后 `hermes cron runs` 里的执行次数
- [ ] **加一条并行**：给它加一个「同时查另一个来源」的子任务，用 `delegate_task` 并行跑，观察子代理的中间工具调用**有没有**进你的上下文（答案和你想的不一样）[[src:delegation-patterns]]
- [ ] **补一次演练**：把 `--deliver` 临时改成 `--deliver local`，跑一次，确认安静时段真的不吵你，再改回来
- [ ] **写一条记忆**：把这节课踩到的那个坑写进 `MEMORY.md`（一句话 + 判据），下次开新会话看它还在不在

## 下一步

- [[L25]] —— 配方库：20 个可直接抄的工作流，给第二个项目找灵感
- [[L34]] —— 无人值守流水线：把 cron + webhook + skill 拼成一条完整产线
- [[L31]] —— 事件驱动：把 webhook 从 GitHub 扩到你自己服务的 API 调用
- [[L23]] —— 定时与循环：`/loop`、`/goal`、`/heartbeat` 与 cron 的分工
- [[L50]] —— 安全模型与审批：把本节那套护栏按你的机器调细
- [[L53]] —— 排障手册：任务「变笨了 / 工具不见了」时的官方诊断清单
- 想深入：[[src:automation-blueprints]]（12 个现成 blueprint）、[[src:secure-work-machine]]（本机安全姿态全文）

## 出处

- [[src:automation-blueprints]] Automation Blueprints — https://hermes-agent.nousresearch.com/docs/guides/automation-blueprints
- [[src:automate-with-cron]] Automate Anything with Cron — https://hermes-agent.nousresearch.com/docs/guides/automate-with-cron
- [[src:delegation-patterns]] Delegation & Parallel Work — https://hermes-agent.nousresearch.com/docs/guides/delegation-patterns
- [[src:secure-work-machine]] Running Hermes on a Personal or Work Machine — https://hermes-agent.nousresearch.com/docs/guides/secure-hermes-on-a-work-machine
