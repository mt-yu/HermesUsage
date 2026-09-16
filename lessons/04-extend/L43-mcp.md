---
id: L43
title: "MCP 集成：接上外部工具服务器"
stage: 4
level: 进阶
minutes: 25
prereq: [L11, L41]
tags: ["MCP", "工具", "外部集成", "工具过滤"]
sources: [mcp, mcp-config, use-mcp-with-hermes, tools]
updated: 2026-09-16
---

# L43 · MCP 集成：接上外部工具服务器

> **一句话**：MCP 让你**不写任何 Hermes 代码**就给 agent 加上新工具 —— 代价是你要为「它到底暴露了哪些工具」负责。

## 你将学会

- 用 `hermes mcp` 发现、安装、测试一个 MCP 服务器，并读懂它的连接结果
- 用工具过滤（include/exclude）把几十个工具收窄成你要的那几个
- 解释 MCP 工具为什么以动态工具集 `mcp-<server>` 的形式出现
- 判断一个能力该用 MCP、该写插件、还是该用「终端 + 技能」

**前置**：L11、L41 · **预计耗时**：25 分钟

## 先动手

```bash
hermes mcp catalog                       # 逛官方审核过的目录
hermes mcp add fs1 --command npx --args -y @modelcontextprotocol/server-filesystem <一个你想让它读的目录>
```

本机真实输出：

```
✓ Connected! Found 14 tool(s)
✓ Saved 'fs1' (14/14 tools enabled)
```

**注意这个数字：14**。你只想要「列目录 + 读文件」两件事，却一次接进来 14 个工具。
这就是本课的重点：**接上很容易，收窄才是功夫**。

## 原理

### MCP 是什么、解决什么问题

MCP（Model Context Protocol）是一个「工具服务器」协议。Hermes 内置 MCP 客户端，
可以用 stdio 或 HTTP 传输连上任何 MCP 服务器，从而访问 GitHub、数据库、文件系统、
内部 API 提供的工具 —— **不用写原生 Hermes 工具**。[[src:mcp]]

判据（放哪儿最合适）：

| 你的需求 | 该用什么 |
|---|---|
| 已有现成的 MCP 服务器，或别人维护 | **MCP**（零代码） |
| 只是「跑几个命令 / 调一个 API」 | 终端 + 技能（最省事） |
| 需要结构化参数返回、且要融入 Hermes 内核流程 | 插件（[[L41]]） |
| 团队/社区要复用 | MCP 或插件仓库 |

**成本视角**：每个工具的定义都会随每次 API 调用一起发送，所以「多接 14 个工具」
是真金白银的开销，也是真的会稀释模型的注意力。[[src:tools]]

### 三个命令就够日常

```bash
hermes mcp catalog          # 浏览审核过的目录（可 install）
hermes mcp add NAME --command <cmd> [--args ...]     # stdio 传输
hermes mcp add NAME --url <https://...>              # HTTP 传输
hermes mcp list             # 看已配置的服务器与工具过滤状态
hermes mcp test NAME        # 只测连接与工具发现
hermes mcp configure NAME   # 交互式勾选要启用的工具
hermes mcp serve            # 反过来：把 Hermes 自己当成 MCP 服务器
```

### 工具过滤：`all` 与 `selected` 的区别

```bash
hermes mcp list
# 真实输出（节选）：fs1 | npx -y @modelcontextprotocol... | all | ✓ enabled
# 加了 tools.include 之后，同一列变成：2 selected
```

**一个必须知道的细节**：过滤只影响**注册进模型的工具**，不影响**发现**。
本机实测——只勾 2 个工具后，`hermes mcp test fs1` 仍然报
`✓ Tools discovered: 14`。所以「测试通过 14 个工具」不代表模型能看到 14 个。[[src:mcp-config]]

### 动态工具集 `mcp-<server>`

MCP 工具不是塞进某个固定工具集，而是以 `mcp-<服务器名>` 的形式动态出现。
所以你可以在 `--toolsets` 或平台配置里精确地只放行某个服务器的工具——
这是「按平台收窄权限」在 MCP 上的用法。[[src:mcp]]

## 亲手验证

### 验证一：连接失败长什么样（两种失败要分清）

```bash
# ① 命令根本不存在
hermes mcp add bogus --command definitely-not-a-real-binary
# 本机真实输出：✗ Failed to connect: [WinError 2] 系统找不到指定的文件。

# ② 名字不在配置里
hermes mcp test bogus
# 本机真实输出：✗ Server 'bogus' not found in config.
```

| 报错 | 含义 | 下一步 |
|---|---|---|
| `Failed to connect: [WinError 2]` | 启动命令找不到 | 检查 `--command` 是否正确、依赖是否装上 |
| `Server '…' not found in config` | 配置里没这个名字 | 先 `add`，或 `hermes mcp list` 确认拼写 |

### 验证二：过滤 ≠ 发现

```bash
hermes mcp test fs1
# 本机真实输出：✓ Connected (6000ms) / ✓ Tools discovered: 14
hermes mcp list
# 同一服务器显示：2 selected
```

**结论**：`discovered: 14` 和 `model sees: 2` 可以同时成立。看工具栏位要看 `list` 的过滤列。[[src:mcp-config]]

### 验证三：连不上时的排查顺序

```bash
hermes mcp test fs1          # 连接层
hermes mcp list              # 配置层：enabled？过滤？
hermes tools list | grep mcp # 工具集层：mcp-fs1 是否可用
```

**自下而上**：连接通不通 → 配置有没有 → 工具集放行没有。跳过前两步直接改工具集，
会白折腾半天。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 装上了但模型用不到这些工具 | 工具集没放行 / 平台配置限制 | 确认 `mcp-<server>` 在对应平台可用 |
| 上下文突然变贵 | 一次接进来几十个工具定义 | 用 `tools.include` 收窄到真正需要的几个 |
| `test` 显示工具很多，以为没过滤成功 | 过滤只影响注册，不影响发现 | 看 `hermes mcp list` 的 `N selected` |
| npx 类服务器首次连接很慢 | 现下载包 | 一次实测 `Connected (6000ms)`；后续会快 |
| Windows 上命令启动失败 | 可执行文件不在 PATH | 用绝对路径或 `npx`/`uvx` 这类不依赖 PATH 的入口 |
| 服务器提供了危险工具（写文件、删数据） | 默认全开 | 主动 exclude，或只 include 只读工具 |
| 想给 MCP 服务器加白名单校验 | 没有内置的策略层 | 用 hooks/中间件在工具调用前拦（[[L30]]、[[L41]]） |
| 不知道某个 MCP 服务器靠不靠谱 | 目录里的条目是审核过的，自加的未必 | 优先用 `hermes mcp catalog` 里的；自加的看完工具清单再启用 |

## 试一试

- [ ] 用 `hermes mcp catalog` 挑一个服务器装上，先看它暴露了多少工具，再收窄到你真正要用的
- [ ] 故意写错 `--command`，把两种报错的原因写进 `journal/`
- [ ] 给一个 MCP 服务器加 `tools.exclude`，把有写权限的工具全部排除，只留只读
- [ ] 判断：你要把公司内部 API 接给 agent，该用 MCP、插件，还是「终端 + 技能」？写下理由

## 下一步

- [[L41]] —— 插件：MCP 不够用时，怎么把逻辑写进内核流程
- [[L30]] —— 钩子：在 MCP 工具调用前后加护栏
- [[L11]] —— 工具与工具集：`mcp-<server>` 属于哪一层
- 想深入：[[src:use-mcp-with-hermes]]（实战组合与安全建议）、[[src:mcp-config]]（配置键与过滤语义）

## 出处

- [[src:mcp]] MCP (Model Context Protocol) — https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
- [[src:mcp-config]] MCP Config Reference — https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference
- [[src:use-mcp-with-hermes]] Use MCP with Hermes — https://hermes-agent.nousresearch.com/docs/guides/use-mcp-with-hermes
- [[src:tools]] Tools & Toolsets — https://hermes-agent.nousresearch.com/docs/user-guide/features/tools
