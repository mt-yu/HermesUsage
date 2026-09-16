---
id: L02
title: 一次对话里到底发生了什么
stage: 0
level: 入门
minutes: 15
prereq: [L00, L01]
tags: [agent-loop, 消息格式, prompt-caching, 上下文压缩]
sources: [agent-loop, prompt-assembly, compression]
updated: 2026-09-16
---

# L02 · 一次对话里到底发生了什么

> **一句话**：每一轮都在重复同一件事 —— 把「系统提示 + 历史 + 你的话」发给模型，它要么回话，要么点名要工具；要了就把结果塞回去再来一轮。

## 你将学会

- 复述 agent loop 的一轮全部步骤（从收到你的话到返回答复）
- 读懂 Hermes 内部的消息格式，以及为什么有「角色必须交替」这条硬规则
- 解释系统提示为什么在整个会话里**字节不变**（以及违反它有多贵）
- 从自己的 `state.db` 里读出一段真实对话的消息序列并验证以上说法

**前置**：L00、L01 · **预计耗时**：15 分钟

## 先动手

先制造一次「它必须用工具」的对话：

```bash
hermes chat -q "看一下当前目录有哪些文件，然后告诉我哪个最像主入口文件"
```

然后**直接看它内部的消息序列**（这是本课的核心动作）：

```bash
python - <<'PY'
import sqlite3, os, pathlib
home = pathlib.Path(os.environ.get("HERMES_HOME") or (pathlib.Path.home() / ".hermes"))
con = sqlite3.connect(f"file:{home / 'state.db'}?mode=ro", uri=True)
for sid, title in con.execute(
        "select id, coalesce(title,'(无标题)') from sessions order by started_at desc limit 1"):
    print(f"会话 {sid}  「{title}」")
    for role, content, tool in con.execute(
        "select role, coalesce(content,''), coalesce(tool_name,'') "
        "from messages where session_id=? order by id limit 12", (sid,)):
        print(f"  {role:<9} {tool:<12} {content[:52]!r}")
PY
```

你应该看到类似下面的结构（本机真实输出，节选自我自己的一次会话）：

```
会话 20260916_102911_e50570  「Hermes agent 初学者教程与 Git 工作流」
  user                 '按照当前项目的思想, 制作Hermes agent 的初学者使用教程…'
  assistant            "I'll start by understanding the current project's st"
  tool      search_files '{"total_count": 1, "files": ["D:/Projects/ai_project'
  tool      skill_view   '{"success": true, "name": "hermes-agent", …'
  assistant            ''
  tool      read_file    '{"content": "1|这是一个关于初学者如何使用Hermes使用的项目…'
  tool      terminal     '{"output": "/d/Projects/ai_projects/HermesUsage…'
  assistant            'Project is a blank slate with just `IDEA.md`. Now gr'
```

**看懂这几行，你就看懂了 agent loop**：

1. `user` 是你的话；
2. `assistant` 后面跟着一串 `tool` —— 说明模型这一轮**没有回话，而是点名要工具**；
3. 每个 `tool` 行是**工具的执行结果**，被塞回上下文；
4. 模型再次被调用（又一条 `assistant`），直到它给出最终文字。

## 原理

### 一轮的完整步骤

```text
run_conversation()
  1. 生成 task_id（若未提供）
  2. 把你的消息追加进对话历史
  3. 组装或复用「已缓存的系统提示」
  4. 判断是否需要预压缩（上下文占用 > 50%）
  5. 把对话历史转成 API 消息
  6. 注入临时提示层（预算告警、上下文压力）
  7. 在 Anthropic 上打 prompt caching 标记
  8. 发起可中断的 API 调用
  9. 解析响应：
     - 有 tool_calls → 执行它们、回填结果、回到第 5 步
     - 是文字回复   → 落盘会话、必要时刷记忆、返回
```

**第 3 步和第 8 步之间的循环**就是全部秘密。[[src:agent-loop]]

### 消息格式（OpenAI 风格）

```python
{"role": "system",    "content": "..."}
{"role": "user",      "content": "..."}
{"role": "assistant", "content": "...", "tool_calls": [...]}
{"role": "tool",      "tool_call_id": "...", "content": "..."}
```

支持扩展思考的模型，其推理内容存在 `assistant_msg["reasoning"]`，可选地展示出来。[[src:agent-loop]]

### 为什么角色必须交替

循环强制遵守这些规则：

- 系统消息之后：`User → Assistant → User → Assistant → …`
- 工具调用期间：`Assistant(带 tool_calls) → Tool → Tool → … → Assistant`
- **绝不能**连续两条 `assistant`，**也绝不能**连续两条 `user`
- **只有** `tool` 角色可以连续出现（并行工具的结果）

供应商会校验这些序列，格式不合法直接拒收。[[src:agent-loop]]

**这解释了新手常见的两个现象**：

- 为什么「打断」是发一条新消息？因为两条连续 user 消息非法 —— 系统必须按规则插入位置。
- 为什么定时任务要跑在**独立会话**里？因为往一个正在跑的会话中途塞一条合成 user 消息，
  会破坏角色交替。

### 系统提示在整个会话里保持字节不变

这是 Hermes 最重要的工程约束，也是你**花钱多少**的直接决定因素：

> 系统提示在**一个会话的生命周期内字节稳定**，唯一被允许的上下文变更是**压缩**。

推论（值得背下来）：

| 你以为 | 实际 |
|---|---|
| 中途改 `.hermes.md` 会立刻生效 | 不会。上下文在会话开始时组装，要重开会话 |
| 让它记住东西，下一轮系统提示就更新 | 不会。记忆是冻结快照（见 [[L03]]） |
| 中途加个技能/工具无所谓 | 很贵：工具集变了，缓存前缀就作废，整段上下文按全价重算 |

任何必须在**会话中途**注入的内容，都走「user 消息」或「工具结果」这两条路，
而不是改系统提示。技能斜杠命令就是这样注入的。[[src:prompt-assembly]] [[src:compression]]

## 亲手验证

### 验证一：数出「模型被调用了几次」

上面那段脚本里，`assistant` 行数 ≈ 模型被调用的轮数（`tool_calls` 那一行内容可能是空的）。
再跑一次带 2-3 个步骤的任务，比较行数变化。

### 验证二：验证「角色交替」

```bash
python - <<'PY'
import sqlite3, os, pathlib
home = pathlib.Path(os.environ.get("HERMES_HOME") or (pathlib.Path.home() / ".hermes"))
con = sqlite3.connect(f"file:{home / 'state.db'}?mode=ro", uri=True)
sid = con.execute("select id from sessions order by started_at desc limit 1").fetchone()[0]
roles = [r for (r,) in con.execute(
    "select role from messages where session_id=? order by id", (sid,))]
bad = [(a, b) for a, b in zip(roles, roles[1:])
       if a == b and a in ("user", "assistant")]
print("消息序列:", " → ".join(roles[:12]), "…")
print("连续的 user/assistant 对:", bad or "无（符合硬规则）")
PY
```

| 你观察到的 | 说明什么 |
|---|---|
| `tool` 行可以连续出现 | 并行工具结果是唯一允许重复的角色 |
| 没有连续 `user` / `assistant` | 角色交替规则在真实数据里生效 |
| 一次提问对应多条 `assistant` | 因为有工具轮次 —— 这就是「循环」的证据 |

### 验证三：亲手制造一次缓存失效的代价感知

```bash
# 同一个会话里连续两问，对比第二轮的速度/用量
hermes -c      # 续上刚才的会话
#   ❯ 再看一下当前目录，这次只列出文件名
```

观察它第二轮明显更快（前缀复用了）。这就是「字节不变的系统提示」换来的钱和时间。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 长会话后期感觉它「变笨」 | 上下文压力 / 预压缩触发 | `/compress` 主动压缩，或开新会话接着干 |
| 改了配置/规则它却没反应 | 上下文只在会话开始时组装 | 重开会话 |
| 想在任务中途加技能 | 会破坏缓存前缀，成本跳升 | 接受成本或另起会话；工具的斜杠命令有 `--now` 变体专门处理这个 |
| 「打断」后行为怪 | 打断 = 发一条新 user 消息，需满足角色交替 | 明确说「停下，改成……」而不是自言自语 |
| 以为工具结果会永久留着 | 压缩会优先裁剪旧工具结果 | 关键结论让它写进文件或记忆，别只存在上下文里 |
| 模型不调工具、直接编答案 | 提示里没有可验证的判据 | 要求它「先读文件再回答」「给出证据」 |

## 试一试

- [ ] 跑一个需要 3 步以上的任务，用上面的脚本把完整消息序列打印出来，数出模型被调用了几次
- [ ] 在 `journal/` 里画一张你自己的 agent loop 图，标出「你的话」「工具结果」「系统提示」三者的位置
- [ ] 找一个你现在正在反复交代给 Hermes 的事情，判断它应该属于「技能」还是「记忆」（答案在 [[L13]] / [[L15]]）

## 下一步

- [[L12]] —— 会话的边界：`/new`、`/compress`、`/resume` 到底在做什么
- [[L13]] —— 冻结快照机制的完整后果：为什么记忆要等下个会话
- [[L14]] —— 系统提示里的项目规则从哪来、怎么改才有用
- 想深入：[[src:agent-loop]]（每个 turn 阶段的内部实现）、[[src:compression]]（压缩算法与缓存代价）

## 出处

- [[src:agent-loop]] Agent Loop Internals — https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop
- [[src:prompt-assembly]] Prompt Assembly — https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly
- [[src:compression]] Context Compression & Caching — https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching
