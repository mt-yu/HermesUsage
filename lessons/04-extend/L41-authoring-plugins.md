---
id: L41
title: 写一个插件：工具 / 钩子 / 中间件
stage: 4
level: 进阶
minutes: 30
prereq: [L30, L40]
tags: ["插件", "plugin.yaml", "register", "hooks", "middleware"]
sources: [plugins-guide, plugins, adding-tools, middleware]
updated: 2026-09-16
---

# L41 · 写一个插件：工具 / 钩子 / 中间件

> **一句话**：技能是「教它怎么做」，插件是「给它新能力」—— 一个目录、一个 `plugin.yaml`、一个 `register(ctx)`，就能往内核里加工具、挂钩子、改写请求。

## 你将学会

- 写出一个能被 `hermes plugins doctor` 判为 OK 的最小插件（四个文件的职责分工）
- 用 `ctx.register_tool` / `ctx.register_hook` / `ctx.register_middleware` 分别加能力、加观测、改行为
- 分清 hook（观察）和 middleware（改写）的边界，以及四类 middleware 的返回契约
- 知道什么时候该写插件、什么时候该改内核自带的工具（`tools/` + `toolsets.py`）
- 亲手用 doctor 复现两类真实失败：manifest 与注册漂移、回调签名不接受 `**kwargs`

**前置**：[[L30]]、[[L40]] · **预计耗时**：30 分钟

## 先动手

最小可跑骨架是**四个文件**，但跑通只要两个：`plugin.yaml`（声明我是谁）+ `__init__.py`（把工具挂上去）[[src:plugins]]。

```bash
mkdir -p "$HERMES_HOME/plugins/hello"     # Windows: %LOCALAPPDATA%\hermes\plugins\hello
cd "$HERMES_HOME/plugins/hello"

cat > plugin.yaml <<'EOF'
name: hello
version: 1.0.0
description: Minimal demo plugin for the L41 lesson
provides_tools:
  - hello_world
provides_hooks:
  - post_tool_call
EOF

cat > __init__.py <<'EOF'
"""Minimal Hermes plugin — registers one tool and one hook."""

import json


def register(ctx):
    schema = {
        "name": "hello_world",
        "description": "Returns a friendly greeting for the given name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Name to greet"}},
            "required": ["name"],
        },
    }

    def handle_hello(params, **kwargs):
        del kwargs
        return json.dumps({"success": True, "greeting": f"Hello, {params.get('name', 'World')}!"})

    ctx.register_tool(name="hello_world", toolset="hello_world", schema=schema, handler=handle_hello)

    def on_tool_call(tool_name, params, result, **kwargs):
        print(f"[hello] tool called: {tool_name}")

    ctx.register_hook("post_tool_call", on_tool_call)
EOF
```

不用重启 Hermes 也能先自检 —— `doctor` 跑的是 Hermes 自己那套发现、解析、导入、注册流程 [[src:plugins-guide]]：

```bash
hermes plugins doctor . --ci
```

**你应该看到**（本机实测输出，路径会换成你自己的）：

```
Plugin Doctor: C:\Users\28189\AppData\Local\Temp\hermes-l41-check\hello
  manifest: hello 1.0.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 1 tool(s), 1 hook(s)
```

`1 tool(s), 1 hook(s)` 和你在 `register()` 里写的数量对上，就说明插件的骨架是通的。接下去启动一次会话，banner 的工具列表里会出现 `hello_world`，模型可以直接调用它 [[src:plugins-guide]]。

## 原理

### 四个文件，四种职责

```
~/.hermes/plugins/hello/
├── plugin.yaml      # manifest：我是什么，我提供什么
├── __init__.py      # register(ctx)：把 schema 和 handler 连起来
├── schemas.py       # 给 LLM 看的：工具名、描述、参数
└── tools.py         # 真正执行的代码
```

把 schema 和 handler 拆开不是洁癖：`schemas.py` 里的文字是**模型唯一的判断依据**，它该写「什么时候用我」；`tools.py` 是纯逻辑，测试时不需要模型在场 [[src:plugins-guide]]。

### 目录深度与发现规则

原生插件只认两种位置：`<插件名>/plugin.yaml`（平铺）或**深一层**的分类目录（`<分类>/<插件名>/plugin.yaml`）。再深就不看了 —— `HERMES_PLUGINS_DEBUG=1` 会把这类目录标成 `no plugin.yaml, depth cap reached` [[src:plugins-guide]]。

```bash
HERMES_PLUGINS_DEBUG=1 hermes plugins list    # 每个被扫描的目录、每个 manifest、每个跳过原因
```

### 插件默认是「关闭」状态

装好不等于生效。`hermes plugins list` 的 Status 列会显示 `not enabled`，调试日志里则是 `not enabled in config` [[src:plugins]]：

```bash
hermes plugins enable hello     # 加进 allow-list
hermes plugins list             # Status 变成 enabled
```

项目内的插件（`./.hermes/plugins/`）另外还有一层：默认不加载，需要显式设置 `HERMES_ENABLE_PROJECT_PLUGINS=true` 才在可信仓库里启用 [[src:plugins]]。

### `register(ctx)` 能做的事

| 能力 | API |
|---|---|
| 加工具 | `ctx.register_tool(name=, toolset=, schema=, handler=)` |
| 加钩子 | `ctx.register_hook("post_tool_call", callback)` |
| 加斜杠命令 | `ctx.register_command(name, handler, description)` |
| 加 CLI 子命令 | `ctx.register_cli_command(name, help, setup_fn, handler_fn)` |
| 从命令里调工具 | `ctx.dispatch_tool(name, args)`（走正常的审批、脱敏、预算管线） |
| 改请求/执行 | `ctx.register_middleware(kind, callback)` |
| 存设置 | `ctx.get_config()` / `ctx.set_config()` → `plugins.entries.<id>.settings` |
| 存运行时状态 | `ctx.state`（profile 级、原子替换、每插件上限 10 MiB） |
| 打包技能 | `ctx.register_skill(name, path)`，加载用 `skill_view("plugin:skill")` |

上表来自官方的能力清单 [[src:plugins]]；`register()` 在启动时**只调用一次**，而且**它崩了只会禁用这个插件，Hermes 继续跑** [[src:plugins-guide]]。

### 需要特权就得先申请：capabilities

想覆盖内置工具、想替 host 决定用哪个模型，都要在 manifest 里声明并让用户点一次确认 [[src:plugins-guide]]：

```yaml
name: my-plugin
capabilities:
  - tools.override        # 替换内置工具
  - llm.model_override    # 为 host 发起的 LLM 调用选模型
```

没声明或没同意的能力是**fail closed（直接关掉）**，所以要探针式使用 [[src:plugins-guide]]：

```python
def register(ctx):
    if ctx.has_capability("tools.override"):
        ctx.register_tool(..., override=True)
    else:
        ctx.register_tool(...)      # 换个不冲突的名字注册
```

capabilities 是「同意 + 审计」，**不是沙箱** —— 它管的是 host API 的入口，不是代码能不能跑 [[src:plugins-guide]]。

### hook（观察）与 middleware（改写）的分界

一句话判据：**hook 看，middleware 改** [[src:plugins-guide]]。

```python
def cap_find_output(tool_name, args, **kwargs):
    """把 terminal 里的 find 命令改写为限量版。"""
    command = args.get("command", "")
    if tool_name == "terminal" and command.startswith("find "):
        return {"args": {**args, "command": command + " | head -100"},
                "source": "my-plugin", "reason": "cap find output"}
    return None          # 返回 None = 不改

def register(ctx):
    ctx.register_middleware("tool_request", cap_find_output)
```

四类 middleware 的返回契约 [[src:plugins-guide]]：

| 种类 | 收到什么 | 返回什么 |
|---|---|---|
| `tool_request` | `tool_name`、`args`、`original_args` | `{"args": {...}}` 替换生效参数；`None` 表示不改 |
| `llm_request` | `request`、`original_request` | `{"request": {...}}` 替换发往 provider 的参数 |
| `tool_execution` | payload + `next_call` | 调一次 `next_call(payload)` 再返回结果（`next_call` 只能用一次） |
| `llm_execution` | payload + `next_call` | 同上，包住 provider 调用 |

两条必须记住的顺序 [[src:middleware]]：

1. 工具调用链是：解析参数 → `tool_request` middleware → 审批/护栏 → `tool_execution` middleware → `post_tool_call` 钩子 → `transform_tool_result`。
2. `tool_request` **跑在审批之前** —— 你改掉的 command/path/URL，就是后面策略要评估的那个值。
3. middleware 抛异常是 fail-open：记一条警告然后跳过，**永远不会弄坏主链路** [[src:middleware]]。

### 如果你要的是「改内核自带的工具」

插件加的是**新**能力。要改 Hermes 自带的工具，路子在源码树里，只碰两个文件 [[src:adding-tools]]：

1. `tools/your_tool.py` —— 写好 `check_fn`（依赖缺失时返回 `False`，工具被静默剔除）、schema、handler，最后顶层调一次 `registry.register(...)`；有顶层 `register()` 调用的文件会被自动发现，不用维护 import 列表
2. `toolsets.py` —— 把工具名加进 `_HERMES_CORE_TOOLS`，或者新建一个独立 toolset

三条铁律 [[src:adding-tools]]：handler **必须返回 JSON 字符串**（不是 dict）、错误**必须**作为 `{"error": "..."}` 返回而不是抛异常、handler 签名是 `(args: dict, **kwargs)`。这三条和插件侧完全一致。

## 亲手验证

### 验证一：manifest 与注册漂移（doctor 会 WARN）

先把 manifest 写成「声明了两个工具、一个钩子」，代码只注册一个工具：

```bash
mkdir -p "$HERMES_HOME/plugins/drift-demo" && cd "$HERMES_HOME/plugins/drift-demo"

cat > plugin.yaml <<'EOF'
name: drift-demo
version: 1.0.0
description: Declares two tools but registers only one
provides_tools:
  - hello_world
  - never_registered
provides_hooks:
  - post_tool_call
EOF

cat > __init__.py <<'EOF'
import json


def register(ctx):
    schema = {
        "name": "hello_world",
        "description": "Returns a friendly greeting.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}},
    }

    def handle_hello(params, **kwargs):
        del kwargs
        return json.dumps({"greeting": f"Hello, {params.get('name', 'World')}!"})

    ctx.register_tool(name="hello_world", toolset="drift", schema=schema, handler=handle_hello)
EOF

hermes plugins doctor .
```

**本机实测输出**：

```
Plugin Doctor: C:\Users\28189\AppData\Local\Temp\hermes-l41-check\drift-demo
  manifest: drift-demo 1.0.0 (standalone)
  WARN: manifest declares hook 'post_tool_call' but registration did not add it
  WARN: manifest declares tool 'never_registered' but registration did not add it
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 1 tool(s), 0 hook(s)
```

| 你观察到的 | 说明什么 |
|---|---|
| 两条 `WARN: manifest declares ... but registration did not add it` | 声明和代码不一致；doctor 把两边对账，这是最常见的自我欺骗 |
| 最后一行仍然是 `OK` | WARN 不是错误，`--ci` 也不会因此退出非零 —— 但它在提示你「用户按 manifest 以为有的东西其实没有」 |

### 验证二：回调签名漏了 `**kwargs`（doctor 会 ERROR）

把钩子回调写成固定三个参数：

```bash
mkdir -p "$HERMES_HOME/plugins/bad-hook" && cd "$HERMES_HOME/plugins/bad-hook"

cat > plugin.yaml <<'EOF'
name: bad-hook
version: 1.0.0
description: Hook callback without **kwargs
provides_hooks:
  - post_tool_call
EOF

cat > __init__.py <<'EOF'
def register(ctx):
    def on_tool_call(tool_name, params, result):
        print(f"[bad-hook] {tool_name}")

    ctx.register_hook("post_tool_call", on_tool_call)
EOF

hermes plugins doctor ./ 2>&1 | head -6
```

**本机实测输出**：

```
Plugin Doctor: C:\Users\28189\AppData\Local\Temp\hermes-l41-check\bad-hook
  manifest: bad-hook 1.0.0 (standalone)
  ERROR: hook callback 'on_tool_call' for 'post_tool_call' must accept **kwargs for forward compatibility
  registrations: 0 tool(s), 1 hook(s)
```

`ok` 那一行没了、只剩 `ERROR` —— 这就是 `--ci` 会挡住的那类问题 [[src:plugins-guide]]。**每次改完插件都跑 `hermes plugins doctor . --ci`**，比开一次会话去试快得多，而且零 API 花费。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `ERROR: hook callback 'on_tool_call' for 'post_tool_call' must accept **kwargs for forward compatibility` | 回调签名写死了参数列表 | 每个 hook/middleware/tool handler 都加 `**kwargs`，再跑 `hermes plugins doctor . --ci` [[src:plugins-guide]] |
| `WARN: manifest declares tool 'x' but registration did not add it` | `plugin.yaml` 的 `provides_tools` / `provides_hooks` 与 `register()` 实际注册的不一致 | 两边对齐；要么补注册，要么删声明 |
| `hermes plugins list` 里 Status 是 `not enabled`（`HERMES_PLUGINS_DEBUG=1` 的日志里写的是 `not enabled in config`） | 插件是 opt-in 的 | `hermes plugins enable <name>`；名字按 `plugins list` 里的显示写（嵌套布局会是 `<category>/<plugin>`）[[src:plugins-guide]] |
| 插件目录放进去了但完全没被发现，日志里是 `no plugin.yaml, depth cap reached` | 目录比允许的层级更深 | 只放在 `<名字>/plugin.yaml` 或一层分类目录下 [[src:plugins-guide]] |
| 模型调用工具后报错、整次调用失败 | handler 把异常抛了出去 | `try/except` 兜住，`return json.dumps({"error": str(e)})`；同理别返回 dict [[src:adding-tools]] |
| 插件装了、启用了，工具却不在 banner 里 | 只加了工具却没启用它的 toolset，或有 `check_fn` 返回了 `False` | 检查工具所属 toolset 是否开启；`check_fn` 为 `False` 时工具会被**静默**剔除 [[src:adding-tools]] |
| 改写过的命令被审批拦下了 | `tool_request` middleware 跑在审批之前，审批看的是改写后的值 | 这是设计如此，不是 bug；把改写意图写进返回的 `reason` 里，它会进 `middleware_trace` [[src:middleware]] |

## 试一试

- [ ] 复现官方的 calculator 插件：`calculate` + `unit_convert` 两个工具，配一个统计调用次数的钩子 [[src:plugins-guide]]
- [ ] 给它加一条 `tool_request` middleware，把 `terminal` 里的 `rm -rf` 拦下来（返回改写成 `echo blocked`），观察审批面板里看到的是哪一条命令
- [ ] 用 `hermes plugins capabilities` 看自己声明的能力和实际授权是否一致
- [ ] 写一个 `requires_env: [SOME_API_KEY]` 的插件，观察缺失时它怎么被跳过
- [ ] 判断：下面三件事分别该用技能、插件，还是改 `tools/`？① 固定一套发布流程 ② 加一个内部 HTTP API 工具 ③ 改 `read_file` 的输出截断长度
- [ ] 跑 `hermes plugins doctor . --ci`，把输出记到 `journal/` 里并提交

## 下一步

- [[L30]] —— 钩子与中间件的理论面：生命周期节点、可观测与可拦阻
- [[L40]] —— 更轻的扩展：先考虑能不能用一个 SKILL.md 解决
- [[L42]] —— 把插件能力画到界面上：桌面插件、TUI、皮肤
- [[L43]] —— 不想碰内核也不想装插件？用 MCP 接外部工具服务器
- 想深入：[[src:plugins-guide]] 的「Specialized plugin types」—— 加一个模型 provider、一个消息平台适配器、一个记忆后端，都是同一套 `register(ctx)`

## 出处

- [[src:plugins-guide]] Build a Hermes Plugin — https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- [[src:plugins]] Plugins — https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- [[src:adding-tools]] Adding Tools — https://hermes-agent.nousresearch.com/docs/developer-guide/adding-tools
- [[src:middleware]] Middleware — https://hermes-agent.nousresearch.com/docs/developer-guide/middleware
