---
id: L30
title: "钩子 hooks：在生命周期节点插入你的代码"
stage: 3
level: 进阶
minutes: 20
prereq: [L22, L23]
tags: ["hooks", "shell hooks", "生命周期", "拦阻"]
sources: [hooks, plugins]
updated: 2026-09-16
---

# L30 · 钩子 hooks：在生命周期节点插入你的代码

> **一句话**：钩子让 Hermes 在「要调工具了」「要问模型了」「子代理结束了」这些时刻先跑你的脚本 —— 脚本可以只记录，也可以直接拦下这次调用。

## 你将学会

- 说出四套钩子系统各自的注册位置、运行位置和能做的事
- 在 `config.yaml` 挂一个 shell 钩子，用 `hermes hooks list` / `test` / `doctor` 确认它到底会不会被执行
- 用退出码 2 拦下一次工具调用，并说清 fail-open 与 fail-closed 的差别
- 用 `pre_llm_call` 把一段自己的信息注入每一轮上下文

**前置**：[[L22]]、[[L23]] · **预计耗时**：20 分钟

## 先动手

目标：3 分钟内在你自己机器上挂一个钩子，并看到它的「同意状态」。

```bash
mkdir -p ~/.hermes/agent-hooks
```

写 `~/.hermes/agent-hooks/block-rm-rf.sh`（钩子收到的 JSON 从 stdin 进来，回执从 stdout 出去）：

```bash
#!/usr/bin/env bash
payload="$(cat -)"
case "$payload" in
  *'rm -rf /'*)
    printf '{"decision": "block", "reason": "blocked: rm -rf / is not permitted"}\n'
    ;;
  *)
    printf '{}\n'
    ;;
esac
```

```bash
chmod +x ~/.hermes/agent-hooks/block-rm-rf.sh
```

在 `~/.hermes/config.yaml` 顶层加一段（与 `model:`、`platforms:` 平级）：

```yaml
hooks:
  pre_tool_call:
    - matcher: "terminal"
      command: "~/.hermes/agent-hooks/block-rm-rf.sh"
      timeout: 5
```

```bash
hermes hooks list
```

本机真实输出（我做实验时把 `HERMES_HOME` 指到一个临时目录，并且 command 写成
`bash <绝对路径>` 的形式，所以这里回显的是那个临时路径）：

```
Configured shell hooks (1 total):

  [pre_tool_call]
    - bash C:/Users/28189/AppData/Local/Temp/hermes-hookdemo/agent-hooks/block-rm-rf.sh matcher='terminal' (timeout=5s, ✗ not allowlisted)
```

这一行就是你 3 分钟要拿到的东西：钩子被读进来了（说明事件名、路径、matcher 都对），
而 `✗ not allowlisted` 说明它**还没有被批准，运行时不会执行**。[[src:hooks]]

Windows 提示：如果脚本没有执行位，把 command 写成 `bash ~/.hermes/agent-hooks/block-rm-rf.sh`
（我本机就是这样跑的）。macOS / Linux 上 `chmod +x` 之后可以省掉 `bash` 前缀。[[src:hooks]]

## 原理

### 四套钩子，各管一段

| 系统 | 注册方式 | 运行位置 | 用来干什么 |
|---|---|---|---|
| **Gateway hooks** | `~/.hermes/hooks/<name>/HOOK.yaml` + `handler.py` | 只在网关进程里 | 记录活动、发告警、转发到外部 HTTP |
| **Plugin hooks** | 插件里 `ctx.register_hook()` | CLI + 网关 | 拦截工具、指标、护栏 |
| **Shell hooks** | `config.yaml` 的 `hooks:` 块指向脚本 | CLI + 网关 + Desktop / TUI / dashboard | 拦截、自动格式化、注入上下文 |
| **Outbound webhooks** | `config.yaml` 的 `hooks.outbound:` 列表 | CLI + 网关 | 把签名事件 POST 到外部 HTTP 端点 |

钩子回调抛错会被隔离并记日志，不会让 agent 崩掉；但钩子不都是被动的 —— 指令/控制类钩子
能改流程，transform 类能替换内容，shell 的 `pre_tool_call` 能拦阻或 fail closed。[[src:hooks]]

### 各自的约束不一样，别混着记

- **Gateway hooks**：目录里两个文件，`HOOK.yaml` 声明 `events:`，`handler.py` 里必须有一个
  名为 `handle` 的函数（`async def` 或普通 `def` 都行），签名是 `handle(event_type, context)`。
  事件名是网关生命周期事件，例如 `gateway:startup`、`session:start`、`agent:start`、
  `agent:step`、`agent:end`、`command:*`（支持通配）。[[src:hooks]]
- **Plugin hooks**：注册语句就是一行 `ctx.register_hook("post_tool_call", on_tool_call)`，
  只能用 Python，跑在同一进程里。插件默认不启用：必须在 `config.yaml` 的
  `plugins.enabled` 里点名，代码才会被加载。[[src:plugins]]
- **Shell hooks**：任何语言（Bash、Python、编译好的二进制都行），每次事件由 Hermes
  拉起一个子进程，跟主进程隔离。[[src:hooks]]
- **Outbound webhooks**：只能观察，不能拦阻 —— 响应体被忽略。[[src:hooks]]

### shell 钩子的线协议：stdin 进、stdout 出

每次事件触发，Hermes 对每个匹配的钩子起一个子进程，把 JSON 从 **stdin** 喂进去，
从 **stdout** 收 JSON 回来。stdin 的形状：[[src:hooks]]

```json
{
  "hook_event_name": "pre_tool_call",
  "tool_name":       "terminal",
  "tool_input":      {"command": "rm -rf /"},
  "session_id":      "sess_abc123",
  "cwd":             "/home/user/project",
  "profile":         "default",
  "extra":           {"task_id": "...", "tool_call_id": "..."}
}
```

stdout 是可选回执，四种形状（Hermes 规范写法与 Claude Code 兼容写法都收）：[[src:hooks]]

```jsonc
{"action": "block",  "message": "Forbidden: rm -rf"}   // 拦下这次工具调用
{"action": "modify", "args": {"new_string": "fixed"}}  // 改写参数后再执行
{"context": "Today is Friday, 2026-04-17"}             // 只对 pre_llm_call 生效：注入上下文
{}                                                     // 什么也不做
```

JSON 写坏、退出码非零、超时 —— 都只记一条警告，不会中断 agent 循环。[[src:hooks]]

### 退出码 2 = 拦阻（Claude Code / Cursor 兼容）

`pre_tool_call` 钩子只要以退出码 **2** 结束，就算 stdout 里没有 block JSON，这次工具调用
也会被拦下。拦阻理由的优先级是：stdout 的 block JSON → stderr 的前 400 字符 →
默认文案 `Blocked by shell hook.`。所以最小的拦阻钩子只有三行：[[src:hooks]]

```bash
#!/usr/bin/env bash
echo "policy violation: rm -rf is not permitted" >&2
exit 2
```

对**除 `pre_tool_call` 以外**的事件，退出码 2 被当成普通非零退出：记警告，然后照常解析 stdout。[[src:hooks]]

### fail-open 与 fail-closed：安全钩子必须显式选后者

shell 钩子默认 **fail open**：起不来、超时、输出不是 JSON —— 都只记警告，动作照常执行。
这对「观测型」钩子是对的，对「安全闸门」是错的。[[src:hooks]]

| 失败情形 | 默认（fail open） | `fail_closed: true` |
|---|---|---|
| 命令找不到 / 不可执行 | 警告，继续 | **拦阻** |
| 超时 | 警告，继续 | **拦阻** |
| stdout 不是 JSON（例如一段堆栈） | 警告，继续 | **拦阻** |
| 正常退出、合法空回执 `{}` | 继续 | 继续 |

`fail_closed` 只对可拦阻事件（目前就是 `pre_tool_call`）有意义。[[src:hooks]]

### 超时与优先级

shell 钩子的 `timeout` 默认 60 秒，**上限 300 秒**，写更大只会被截断。插件钩子的回调有
自己的上限：`plugins.hook_callback_timeout` 默认 30 秒，超时的 `pre_tool_call` 回调按
fail closed 处理（拦下工具）。两类钩子走同一个分发器，Python 插件先注册、shell 后注册，
所以同分情况 Python 的 block 决策优先，且**第一个有效的 block 立即生效**。[[src:hooks]] [[src:plugins]]

### 同意模型：为什么「配了却不生效」

每一对唯一的 `(事件, 命令)` 在第一次出现时都会问你要不要批准，决定写进
`~/.hermes/shell-hooks-allowlist.json`。三个免交互的口子任选一个即可：[[src:hooks]]

```bash
hermes --accept-hooks chat      # CLI 标志
export HERMES_ACCEPT_HOOKS=1    # 环境变量
```

```yaml
# ~/.hermes/config.yaml
hooks_auto_accept: true
```

网关、cron、CI 这类非 TTY 运行必须用其中之一，否则新加的钩子会静默地不注册。
另外 allowlist 记录的是**命令字符串**，不是脚本哈希：改脚本内容不会重新征求同意，
所以 `hermes hooks doctor` 会专门报 mtime 漂移，让你自己判断要不要重新批准。[[src:hooks]]

## 亲手验证

### 验证一：让钩子对着合成 payload 跑，把回执读出来

把刚才的脚本临时换成「无条件是拦阻」的版本，再用 CLI 喂它一份合成 payload：

```bash
cat > ~/.hermes/agent-hooks/block-rm-rf.sh <<'EOF'
#!/usr/bin/env bash
echo "policy violation: this command is not permitted" >&2
exit 2
EOF
hermes hooks test pre_tool_call --for-tool terminal
```

本机真实输出：

```
Firing 1 hook(s) for event 'pre_tool_call':

  → bash C:/Users/28189/AppData/Local/Temp/hermes-hookdemo/agent-hooks/block-rm-rf.sh
      exit=2  elapsed=0.125s
      stderr: policy violation: this command is not permitted
      parsed (Hermes wire shape): {"action": "block", "message": "policy violation: this command is not permitted"}
```

`parsed (Hermes wire shape)` 这一行就是分发器**实际会收到的东西** —— 你写的三行 shell 脚本
被规范化成了 Hermes 的 block 回执。[[src:hooks]]

### 验证二：让它自己告诉你「这个钩子不会生效」

```bash
hermes hooks doctor
```

本机真实输出（脚本还没被批准时）：

```
Checking 1 configured shell hook(s)...

  [pre_tool_call] bash C:/Users/28189/AppData/Local/Temp/hermes-hookdemo/agent-hooks/block-rm-rf.sh
      ✓ script exists and is executable
      ✗ not allowlisted — hook will NOT fire at runtime (run with --accept-hooks once, or confirm at the TTY prompt)
      ℹ skipped JSON smoke test — not allowlisted yet. Approve the hook first (via TTY prompt or --accept-hooks), then re-run `hermes hooks doctor`.

1 issue(s) found.  Fix before relying on these hooks.
```

### 验证三：写错事件名的后果（最容易被骗的一次）

把 `config.yaml` 里的键从 `pre_tool_call:` 改成 `pre_tool_cal:`（少一个 `l`），再跑：

```bash
hermes hooks list
```

本机真实输出：

```
No shell hooks or outbound webhooks configured in ~/.hermes/config.yaml.
See `hermes hooks --help` or
    website/docs/user-guide/features/hooks.md
for the config schema and worked examples.
```

`hermes hooks doctor` 同样会回你 `No shell hooks configured — nothing to check.`
不认识的事件名会被跳过，配置看起来「写过了」，实际上一条都没注册 —— 所以排查第一步
永远是 `hermes hooks list` 看它有没有被读进来。[[src:hooks]]

### 验证四：上限会被悄悄截断

```yaml
hooks:
  post_llm_call:
    - command: "~/.hermes/agent-hooks/block-rm-rf.sh"
      timeout: 999
      fail_closed: true
```

```bash
hermes hooks list
```

本机真实输出（节选）：

```
  [post_llm_call]
    - bash C:/Users/28189/AppData/Local/Temp/hermes-hookdemo/agent-hooks/block-rm-rf.sh (timeout=300s, ✗ not allowlisted)
```

写 999，读到 300 —— 超出上限被截断。同一段里 `fail_closed: true` 写在 `post_llm_call`
这种不可拦阻的事件上不生效，列表里也没有额外标记。[[src:hooks]]

| 你观察到的 | 说明什么 |
|---|---|
| `✗ not allowlisted` 但 `✓ script exists and is executable` | 脚本没问题，缺的是「同意」这一步 |
| 事件名写错后 `hooks list` 什么都不显示 | 事件名必须在 VALID_HOOKS 里，否则被静默跳过 |
| `timeout=999` 变成 `timeout=300s` | 超时上限 300 秒，不会被接受更大的值 |
| exit=2 的脚本产出 `{"action": "block", ...}` | 退出码 2 被转成规范化的 block 回执 |
| `hooks test` 与真实运行的同意状态一致 | 用 `test` 预演是可靠的，不用等到真实会话里才发现问题 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `✗ not allowlisted — hook will NOT fire at runtime` | 首次使用要批准，非 TTY 进程没法回答提示 | `hermes --accept-hooks chat`，或 `HERMES_ACCEPT_HOOKS=1`，或 `hooks_auto_accept: true` |
| 配了钩子，`hermes hooks list` 里一条都没有 | `hooks:` 块位置不对（必须在顶层），或事件名拼错 | 把 `hooks:` 与 `model:` 平级放；抄文档里的事件名 |
| 安全扫描脚本崩了，危险命令照样执行 | 默认 fail open | 在 `pre_tool_call` 条目上加 `fail_closed: true` |
| 换了脚本内容，行为却没有变化 | allowlist 认命令字符串，不认脚本哈希 | `hermes hooks doctor` 看 mtime 漂移；必要时 `hermes hooks revoke <command>` |
| 钩子里等 10 分钟的外部调用从来没跑完 | shell 钩子超时上限 300 秒 | 钩子只做判断，重活交给 cron 或 webhook |
| `fail_closed: true` 写了但没用 | 事件不是 `pre_tool_call` | 挪到 `pre_tool_call` 条目上 |
| 自动格式化脚本跑了，agent 说的还是旧内容 | 钩子只改磁盘，不改上下文里的那份 | 让 agent 重新 `read_file` 一次 |
| 网关/cron 里钩子不生效，CLI 里正常 | 非 TTY 运行需要上面三种放行方式之一 | 同上第一条 |
| 在 `config.yaml` 里写了 `hooks:` 却没反应 | 改动在下一次 CLI 会话或网关重启后才生效 | 重开会话 / `hermes gateway restart` |

## 试一试

- [ ] 写一个 `pre_llm_call` 钩子，把 `git status --porcelain` 的输出以 `{"context": "..."}` 注入每一轮，然后在一个未提交改动的仓库里问它「现在有哪些改动」
- [ ] 把 `matcher` 改成 `"terminal|write_file|patch"`，观察 `hermes hooks list` 里 matcher 的回显
- [ ] 在 `config.yaml` 里加一个 `hooks.outbound:` 目标，指向 `https://httpbin.org/post`，跑一次会话，去 httpbin 看收到的 JSON 里有没有 `X-Hermes-Event` 头
- [ ] 用 `hermes hooks revoke "<你的命令字符串>"` 撤掉同意，再跑 `hermes hooks doctor` 确认状态回到未批准
- [ ] 把这一课的实验记录写进 `journal/` 并提交

## 下一步

- [[L41]] —— 要用 Python 做同样的拦截，正式路径是写插件（`ctx.register_hook()`）
- [[L31]] —— 反方向的另一半：外部事件进来触发 agent
- [[L34]] —— 把钩子、cron、webhook 拼成一条无人值守流水线
- 想深入：[[src:hooks]] 的 Plugin Hooks 与 Outbound Webhooks 两节

## 出处

- [[src:hooks]] Event Hooks — https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- [[src:plugins]] Plugins — https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
