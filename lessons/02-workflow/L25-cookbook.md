---
id: L25
title: "配方库：20 个可直接抄的工作流"
stage: 2
level: 进阶
minutes: 30
prereq: [L20, L23]
tags: ["配方", "工作流", "cron", "hermes send", "技能"]
sources: [tips, automation-blueprints, work-with-skills, pipe-script-output]
updated: 2026-09-16
---

# L25 · 配方库：20 个可直接抄的工作流

> **一句话**：20 条抄下来就能跑的配方，每条都标明它的依据在哪一页官方文档 —— 用得顺手的那几条，再回去读对应的课。

## 你将学会

- 抄用 20 个覆盖提问、会话、批量、技能、定时、投递的现成工作流
- 判断一条配方该放进上下文文件、技能，还是定时作业
- 亲手让 `hermes send` 失败一次，学会靠退出码在脚本里分支
- 知道每个配方的依据出处，方便日后官方文档变了再核对

**前置**：L20、L23 · **预计耗时**：30 分钟

## 先动手

先看两端：能用的技能，和能把结果送出去的目标。

```bash
hermes skills list | head -8
hermes send --list
```

本机真实输出：

```
                               Installed Skills
┌────────────────────────┬──────────────────────┬─────────┬─────────┬─────────┐
│ Name                   │ Category             │ Source  │ Trust   │ Status  │
├────────────────────────┼──────────────────────┼─────────┼─────────┼─────────┤
│ hermes-desktop-plugins │                      │ local   │ local   │ enabled │
│ yuanbao                │                      │ local   │ local   │ enabled │
│ claude-code            │ autonomous-ai-agents │ builtin │ builtin │ enabled │
```

```
No messaging platforms configured or no channels discovered yet.
Set one up with `hermes gateway setup`, or run the gateway once so
channel discovery can populate ~/.hermes/channel_directory.json.
```

**技能是「怎么干」，`hermes send` 是「干完往哪喊」。** 下面 20 条配方就在这两端之间。[[src:work-with-skills]] [[src:pipe-script-output]]

## 原理

### 一条配方怎么读

| 部分 | 你要看的是 |
|---|---|
| 抄这行 | 命令本身，直接复制（占位符 `<...>` 换成你的） |
| 换来什么 | 这条配方省掉的动作 |
| 依据 | 官方文档页；变了就去核对，别信记忆 |

### 一句判断：这条配方该放哪

| 你想重复的事 | 放哪 |
|---|---|
| 每次都要交代的规范/偏好 | 上下文文件（`AGENTS.md`），零成本自动生效 [[src:tips]] |
| 多步流程、有坑、要复用 | 技能（`/skills` 里能搜到、能用斜杠命令调） [[src:work-with-skills]] |
| 到点自动跑 | cron 作业（提示必须自包含） [[src:automation-blueprints]] |
| 脚本跑完想通知我 | `hermes send`（不需要模型、不需要网关常驻） [[src:pipe-script-output]] |

## 配方 20 条

### 提问与交互

**1. 报错别转述，整段贴进去**

```bash
hermes chat -q "这段报错说明什么，修掉它：<把堆栈整段粘进来>"
```

它会自己解析堆栈，比「我这边报错了」少一轮往返。[[src:tips]]

**2. 长提示用 Ctrl+J 换行，粘贴会自动缓冲**

```text
❯ 第一行
  第二行（按 Ctrl+J 换行，不要按 Enter）
```

粘贴一大段代码或报错时，CLI 自动检测多行粘贴并当成**一条**消息发送。[[src:tips]]

**3. 剪贴板里的截图直接问**

```text
Ctrl+V        # 把剪贴板里的图片贴进对话
```

它用视觉能力看图 —— 报错弹窗、UI 稿、图表都不用先存文件。[[src:tips]]

**4. 发现它跑偏，一次 Ctrl+C 打断并改道**

```text
Ctrl+C        # 打断当前响应，然后直接输入纠正
Ctrl+C ×2     # 双击才是退出
```

打断后你输入的纠正会接管这一轮，已展示的工具结果与推理保留在上下文里。[[src:tips]]

### 会话与成本

**5. 接着上次那个会话继续**

```bash
hermes -c                        # 最近一个会话
hermes -r "my research project"  # 按标题找
```

忘了上文不用重讲，整段历史恢复。[[src:tips]]

**6. 给会话起名，别让它堆成无名氏**

```text
/title auth-refactor
```

命名后 `hermes sessions list` 里能认出来，`hermes -r "auth-refactor"` 能直接续上。[[src:tips]]

**7. 长会话先压缩，再看用量**

```text
/usage        # 看 token 用量
/compress     # 摘要历史，保留关键上下文
```

感觉回答变慢或开始丢细节时先做这两步，而不是硬撑。[[src:tips]]

**8. 让它把「正在做什么」显示出来**

```text
/verbose      # off → new → all → verbose 循环
```

`all` 适合盯着它干活，`off` 适合只要答案的场景。[[src:tips]]

### 批量与并行

**9. 批量操作写成一个脚本一次跑完**

```bash
hermes chat -q "写一个 Python 脚本把所有 .jpeg 改名成 .jpg 并运行它" -Q
```

一次脚本执行比逐条命令便宜也快 —— 中间结果不进上下文。[[src:tips]]

**10. 三个话题并行研究**

```bash
hermes chat -q "并行研究这三件事，各给一段结论：(1) … (2) … (3) …" -Q
```

它内部会用 `delegate_task` 并行派子代理，只有各自的摘要回到主对话，主对话的 token 消耗大幅下降。[[src:tips]]

**11. 先量固定成本，再决定关掉什么**

```bash
hermes prompt-size
```

离线可用，列出系统提示、技能索引、记忆、以及每个工具集的 schema 体积 —— 从中挑出你不用的工具集关掉。[[src:tips]]

**12. 简单活换便宜模型**

```text
/model
```

注意：**每次显式切模型都会重置前缀缓存**，长会话里来回切会让成本翻倍 —— 长时间换模型不如另开一个会话。[[src:tips]]

### 技能

**13. 先找现成的，别急着自己写**

```bash
/skills
/skills search docker
```

装好的每个技能都自动变成斜杠命令，`/` 按 Tab 能补全。[[src:work-with-skills]]

**14. 装一个官方可选技能**

```bash
hermes skills install official/research/arxiv
/skills browse
```

官方可选技能随 Hermes 一起分发但不默认启用，装上后出现在技能列表并可用斜杠命令调用；**技能在新会话生效**，当前会话要 `/reset` 或加 `--now`。[[src:work-with-skills]]

**15. 把刚做顺的流程存成技能**

```text
把刚才这套步骤存成一个叫 deploy-staging 的技能
```

复杂多步任务做完后它常会主动提议把方法存成技能（内部用 `skill_manage`），这些「agent 自己写的技能」会把它踩过的坑一起记下来。[[src:work-with-skills]]

**16. 给技能配参考文件与配置项**

```bash
hermes skills config gif-search     # 交互式填这个技能需要的 key
```

技能可以带 `references/`、`templates/`、`scripts/`，agent 按需用 `skill_view("my-skill", "references/api-docs.md")` 取用；需要凭证的技能在 frontmatter 里声明，首次加载时会提示你填。[[src:work-with-skills]]

### 定时与投递

**17. 夜间批量分诊，白天只看摘要**

```bash
hermes cron create "0 2 * * *" \
  "你是一个项目管理助手。用 gh issue list --state open --json number,title,labels,createdAt --limit 30 拉取议题；找出最近 24 小时新开的；给每条建议优先级与分类标签；最后汇总总数与新开数。没有新议题就只回复 [SILENT]。" \
  --name "夜间分诊" \
  --deliver telegram
```

这是官方蓝图里的「Nightly Backlog Triage」，可以整段改成你自己的仓库。[[src:automation-blueprints]]

**18. 探活只在挂了才喊**

```python
# ~/.hermes/scripts/check-uptime.py（节选官方蓝图）
down = [r for r in results if r.get("status") == "DOWN" or (isinstance(r.get("status"), int) and r["status"] >= 500)]
print("OUTAGE DETECTED" if down else "NO_ISSUES")
```

```bash
hermes cron create "every 30m" \
  "If the script reports OUTAGE DETECTED, summarize which services are down and suggest likely causes. If NO_ISSUES, respond with [SILENT]." \
  --script ~/.hermes/scripts/check-uptime.py \
  --name "Uptime monitor" \
  --deliver telegram
```

脚本干体力活（HTTP 请求、比对），agent 只对 stdout 做判断。[[src:automation-blueprints]]

**19. 让它知道往哪送结果**

```text
/sethome              # 在你想收结果的 Telegram / Discord 会话里设一次
```

不设主页频道，主动发起的消息就没有地方可送；投递目标也可以在建作业时指定：`origin`（默认，创建它的会话）、`local`（只落文件）、`telegram`/`discord`/`slack`，或具体会话如 `telegram:-1001234567890`。[[src:automation-blueprints]]

**20. CI 或长任务结束时，一条通知**

```bash
./scripts/deploy.sh && hermes send --to slack:#deploys "deployed ${CI_COMMIT_SHA:0:7}" \
  || tail -n 100 deploy.log | hermes send --to slack:#deploys --subject "deploy failed"
```

`hermes send` 复用 gateway 的平台凭证，**不需要模型、不需要常驻网关**（bot-token 类平台直接调 REST）；`-q` 只留退出码，`--json` 能拿到 `message_id` 供后续编辑或串帖。[[src:pipe-script-output]]

## 亲手验证

### 验证一：让一条投递失败，看退出码

```bash
hermes send --to telegram "test"
```

本机真实输出：

```
hermes send: Platform 'telegram' is not configured. Set up credentials in ~/.hermes/config.yaml or environment variables.
```

退出码：`1`。

| 你观察到的 | 说明什么 |
|---|---|
| 未配置的平台会明确报错，不是静默丢弃 | 脚本里可以 `hermes send ... || echo "投递失败"` 把它暴露出来 |
| 退出码是标准的 Unix 约定 | 可以像对 `curl` / `grep` 那样直接 `if` 分支 |
| 官方文档的退出码表把 `1` 记为「平台层失败」、`2` 记为「参数/配置错误」，而本机未配置平台拿到的是 `1` | 别在脚本里假设固定映射，用实际退出码验证一次 |
| 任何平台都有目标可送之前，重定向到 `hermes send --list` | 先确认有什么可用，别盲写目标 |

### 验证二：看频道目录是空的

```bash
hermes send --list
```

```
No messaging platforms configured or no channels discovered yet.
Set one up with `hermes gateway setup`, or run the gateway once so
channel discovery can populate ~/.hermes/channel_directory.json.
```

人性化的目标名（`discord:#ops`）是拿 `~/.hermes/channel_directory.json` 解析的，而这个目录由网关运行时刷新 —— 所以先起一次网关再抄配方里的目标。[[src:pipe-script-output]]

### 验证三：确认技能真的在

```bash
hermes skills list | grep -i arxiv
/skills search arxiv
```

装完看不见，通常是「技能在新会话生效」这条在起作用，不是装失败。[[src:work-with-skills]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `hermes send: Platform 'telegram' is not configured. Set up credentials in ~/.hermes/config.yaml or environment variables.` | 那个平台的凭证没配 | `hermes gateway setup`；先用 `hermes send --list` 看有哪些目标 |
| `no channels discovered yet` | 频道目录还没生成 | 起一次网关让它刷新 `~/.hermes/channel_directory.json` |
| 配方里的 cron 要求「没事别发」，结果还是发了 | 只写了自然语言的「别打扰我」 | 明确写 `respond with only [SILENT]` |
| 技能装好了但当前会话里没有 | 技能在新会话生效 | `/reset` 重开会话；加 `--now` 会立刻作废缓存（更贵） |
| 长会话里来回 `/model` 换模型，账单飙升 | 每次切换都重置前缀缓存 | 简单活用便宜模型另开一个会话，别和复杂活来回切 |
| 为了抄配方方便把 `GATEWAY_ALLOW_ALL_USERS=true` 打开 | 给有终端权限的机器人开了全放行 | 用平台 allowlist 或 DM pairing，见 [[L50]] |
| 多行提示粘进去被拆成好几条 | 终端没送出行边界 | 现在的 CLI 会自动缓冲多行粘贴；老环境用 `hermes chat --query-file prompt.txt` |

## 试一试

- [ ] 从上面 20 条里挑 3 条，今天真的用一次
- [ ] 把第 17 条的分诊提示改成你自己仓库的 URL，用 `--paused` 建出来，`hermes cron run` 试跑一次再决定要不要启用
- [ ] 把第 20 条的通知接进你手里任意一个脚本，跑一次看到消息落地
- [ ] 找一条你每周都在重复的活，判断它属于上下文文件、技能，还是 cron
- [ ] 把结果记到 `journal/` 里并提交（见 CONTRIBUTING.md 的会话总结流程）

## 下一步

- [[L20]] —— 配方里的提示为什么这么写：范围、判据、证据
- [[L23]] —— cron 的排程、投递与失败语义
- [[L21]] —— 配方背后那些工具的真实边界
- [[L31]] —— 把「到点跑」换成「出事就跑」：webhook 触发
- [[L40]] —— 配方不够用时，自己写一个技能
- [[L90]] —— 毕业项目：把一条配方变成无人值守
- 想深入：[[src:automation-blueprints]]（更多可直接抄的蓝图）、[[src:pipe-script-output]]（投递到 20 多个平台）

## 出处

- [[src:tips]] Tips & Best Practices — https://hermes-agent.nousresearch.com/docs/guides/tips
- [[src:automation-blueprints]] Automation Blueprints — https://hermes-agent.nousresearch.com/docs/guides/automation-blueprints
- [[src:work-with-skills]] Working with Skills — https://hermes-agent.nousresearch.com/docs/guides/work-with-skills
- [[src:pipe-script-output]] Pipe Script Output to Messaging Platforms — https://hermes-agent.nousresearch.com/docs/guides/pipe-script-output
