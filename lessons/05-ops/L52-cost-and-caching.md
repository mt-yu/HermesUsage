---
id: L52
title: "成本与缓存：prompt caching 心法"
stage: 5
level: 进阶
minutes: 20
prereq: [L10, L12]
tags: ["成本", "prompt-caching", "上下文压缩", "provider-routing"]
sources: [compression, tips, provider-routing]
updated: 2026-09-16
---

# L52 · 成本与缓存：prompt caching 心法

> **一句话**：每轮都重发的固定前缀（系统提示 + 工具 schema + 技能索引）是你最该保护的资产；换模型、换钥匙、改工具集都会让下一次按全价重读。

## 你将学会

- 用 `hermes prompt-size` 量出你每轮的固定开销（离线可跑，不花一分钱）
- 说出 prompt 缓存的三个断点、命中条件，以及哪四种操作会让它作废
- 用默认参数算出一个 200K 上下文模型的压缩触发点
- 解释为什么「摘要模型比主模型小」会让压缩后的细节被静默丢掉
- 判断 `provider_routing` 在什么 provider 上生效、什么情况下被忽略

**前置**：L10、L12 · **预计耗时**：20 分钟

## 先动手

```bash
hermes prompt-size
hermes config get compression
hermes config get prompt_caching
```

本机真实输出（节选）：

```
Prompt-size breakdown (platform=cli, model=deepseek-v4-pro)

  System prompt total :   22,206 B  (21.7 KB, 22,080 chars)

  Major blocks:
    skills index       :    8,217 B  (8.0 KB)
    memory             :        0 B  (0.0 KB)
    user profile       :        0 B  (0.0 KB)

  Tool schemas         :   41,186 B  (40.2 KB, 25 tools)
```

```
threshold: 0.5
tail_mode: lean
protect_last_n: 20
```

```
cache_ttl: 5m
```

**这三个数字就是你的底价**：`hermes prompt-size` 报告的是「一次全新会话、还没说一句话」时就要发出去的固定内容，官方把它叫做固定 prompt 预算，纯离线计算、不发 API 请求。[[src:tips]] 注意工具 schema 那 40.2 KB 是按 25 个工具算的 —— 你每关掉一个工具集，这里就会变小。

## 原理

### 你在为什么付费：每轮都重发的前缀

系统提示、上下文文件、技能索引这些内容**每一条消息都会重新发一遍**，所以每个字符都在吃你的 token 预算。[[src:tips]] 这笔固定开销分成三层：

| 层 | 本机实测 | 怎么让它变小 |
|---|---|---|
| 工具 schema | 41,186 B / 25 个工具 | 关掉用不到的 toolset（`hermes tools`） |
| 系统提示（身份/指引/技能） | 22,206 B | 精简技能索引与 `.hermes.md` |
| 记忆 / 用户画像 | 0 B（本机还没写） | 记忆有硬上限，见 [[L13]] |

### 缓存怎么记账：4 个断点，前缀必须逐字节一致

Hermes 用 Anthropic 的 `cache_control` 断点做缓存，策略叫 `system_and_3`：1 个断点打在系统提示上（整个会话稳定），另外 3 个打在最后三条非系统消息上，形成滚动窗口 —— 因为 Anthropic 一次请求最多 4 个断点。命中时多轮对话的输入成本大约降到 1/4。[[src:compression]]

命中要求**前缀完全匹配**：在中间增删消息，会让它之后的全部内容失效。[[src:compression]]

### 四种操作会让缓存作废（这是本课最贵的一段）

缓存键里包含**模型**和**账号 / API key**，所以下面四件事都会让下一次请求零命中、按原价重读整段对话：[[src:compression]] [[src:tips]]

1. 会话中途 `/model` 换模型；
2. 自动 fallback 到别的 provider；
3. 凭证池轮换到另一把钥匙（见 [[L51]]）；
4. 改了工具集（工具 schema 活在系统提示里，前缀一改就等于换了另一段前缀）——所以这类操作值得放在会话早期做。[[src:compression]]

推论：在长会话里反复横跳，比一开始就选对模型贵得多。[[src:tips]]

### 上下文压缩：两层，两个阈值

| 层 | 触发点 | 干什么 |
|---|---|---|
| Agent ContextCompressor | **50%**（`compression.threshold`，可配） | 主压缩：带真实 token 计数，剪掉中段、保留摘要与尾部 |
| Gateway Session Hygiene | **85%**（固定） | 兜底：防止会话在轮次之间（比如 Telegram 过夜）涨到 API 直接报错 |

[[src:compression]]

默认参数下的算法要点：先做一次**不用 LLM 的预剪枝**（把保护尾部之外、超过 200 字符的旧工具结果换成 `[Old tool output cleared to save context space]`）；然后定边界 —— 头部 `protect_first_n: 3` 固定保留，尾部按 token 预算走并至少保留 `protect_last_n: 20` 条；再让辅助模型出一份结构化摘要（Goal / Progress / Key Decisions / Relevant Files / Next Steps…）；最后拼装并清理孤立的 tool_call 配对。[[src:compression]]

算一下一个 200K 上下文模型的默认值：

```
context_length     = 200,000
threshold_tokens   = 200,000 × 0.50 = 100,000
tail_token_budget  = 100,000 × 0.20 = 20,000
max_summary_tokens = min(200,000 × 0.05, 12,000) = 10,000
```

[[src:compression]]

注意 `threshold_tokens` 永远由**主模型**的上下文窗口算出来，跟摘要模型无关；另外窗口小于 512K 的模型有一个 0.75 的地板阈值 —— 你在配置里写的更低的阈值会被抬到 0.75（只升不降）。[[src:compression]]

默认 `tail_mode: lean` 保留的尾部是按 `2.5% × 上下文窗口`（下限 10K、上限 25K）夹出来的，连续性靠摘要里的「保留标识符的会话日志 + 机械抽取的锚点索引（PR 号、SHA、路径、错误串）+ 逐字引用的用户消息 + `session_search` 恢复指针」来承担。[[src:compression]]

### 省钱四种做法（都很具体）

1. **在撞上限之前主动 `/compress`**，并用 `/usage` 观察位置 —— 别等到它开始变慢或被截断。[[src:tips]]
2. **并行研究交给 `delegate_task`**：子代理各自带上下文，只有摘要回主会话。[[src:tips]]
3. **批量操作写成脚本再跑**（`execute_code`），比一条条调用便宜。[[src:tips]]
4. **按任务选模型**：复杂推理用前沿模型，格式化 / 重命名这类活换快的模型 —— 但要记住换模型就清缓存，长会话里宁可在正确的模型上新开会话。[[src:tips]]

三个计量入口：`/usage`（token 用量）、`/insights`（近 30 天模式）、`hermes prompt-size`（任何对话之前的固定成本，离线）。[[src:tips]]

### 让 OpenRouter 替你选便宜的供方

`provider_routing` 只在使用 **OpenRouter** 时生效；Nous Portal 是集中路由、不接受调用方的偏好，直连 provider 也没有这个概念。[[src:provider-routing]]

```yaml
provider_routing:
  sort: "price"          # price / throughput / latency
  only: []               # 白名单
  ignore: []             # 黑名单
  order: []              # 显式优先级
  require_parameters: false
  data_collection: null  # "allow" / "deny"
```

- `sort: "price"` 按最便宜排序，`"throughput"` 按每秒 token 数，`"latency"` 按首 token 延迟。[[src:provider-routing]]
- `require_parameters: true` 只选支持你请求里**全部**参数的供方，避免参数被静默丢掉。[[src:provider-routing]]
- `data_collection: "deny"` 控制供方能不能拿你的 prompt 去训练 —— 它**不改变价格**，别指望它省钱。[[src:provider-routing]]
- 可以按模型覆盖（`models:` 段），但模型 id 里有点号，`hermes config set` 会把点当路径分隔符 —— 这几个键直接编辑 `config.yaml`。[[src:provider-routing]]
- 路由偏好是随 agent 聊天请求通过 `extra_body.provider` 传给 OpenRouter 的；压缩、起标题这些辅助任务由 `auxiliary.<task>.extra_body` 单独配置。[[src:provider-routing]]

## 亲手验证

### 验证一：自己把官方给的数字算出来（本机实测）

```bash
python -c "print('threshold_tokens =', 200000*0.5); print('tail_budget =', int(200000*0.5*0.2)); print('max_summary =', min(int(200000*0.05), 12000))"
```

真实输出：

```
threshold_tokens = 100000.0
tail_budget = 20000
max_summary = 10000
```

和文档里那组计算值一致 —— 说明「50% 触发、20% 尾部、摘要上限 10K」这些数字是你能自己复核的，不是玄学。[[src:compression]]

### 验证二：换一个平台，固定成本就变（本机实测）

```bash
hermes prompt-size --platform cli
hermes prompt-size --platform telegram
```

本机真实输出（第一行）：

```
Prompt-size breakdown (platform=cli, model=deepseek-v4-pro)
  System prompt total :   22,206 B  (21.7 KB, 22,080 chars)
```

```
Prompt-size breakdown (platform=telegram, model=unset)
  System prompt total :   13,987 B  (13.7 KB, 13,913 chars)
```

同一个模型、不同平台，系统提示相差 8KB 左右 —— 这解释了为什么「在哪个界面聊」也会影响每轮成本。[[src:tips]]

### 验证三：亲手制造一次缓存失效（需要一次真实会话）

```bash
hermes -c
#   ❯ 用一句话总结我们刚才在做什么        ← 记下这一轮的 input token
#   ❯ /model                              ← 中途换一个模型
#   ❯ 用一句话总结我们刚才在做什么        ← 对比这一轮
```

| 你观察到的 | 说明什么 |
|---|---|
| 换模型后的那一次 input token 陡增 | 缓存按模型 + 账号记账，切换等于全价重读 |
| 再后面几轮又降回来 | 新模型用自己的缓存重建了前缀 |
| `hermes prompt-size` 里 tool schemas 占大头 | 关掉不用的工具集，每轮都省 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 长会话越聊越贵，越聊越慢 | 每轮重发整段前缀，上下文只增不减 | `/compress` 或 `/new` 带着结论重开；用 `/usage` 盯着 |
| 压缩之后摘要很空、细节全丢 | 摘要模型上下文小于主模型 → 摘要调用失败，中段被**无摘要**丢弃（官方称为压缩质量下降的最常见原因） | 给 `auxiliary.compression` 配上下文不小于主模型的模型 |
| 半夜的 Telegram 会话自己触发了压缩 | gateway hygiene 在 85% 硬阈值兜底 | 正常行为；想少触发就在会话里主动 `/compress` |
| `/reload-mcp` 之后那一轮特别贵 | 工具集变了 → 系统提示前缀变了 → 缓存作废 | 在会话早期改 MCP；改完接受一次重建 |
| 配了 `provider_routing` 却毫无变化 | 它只对 OpenRouter 生效；Portal 与直连会忽略 | 换 provider，或改用对应 provider 自己的配置 |
| 以为 `data_collection: "deny"` 能省钱 | 它只管供方能否拿你的 prompt 训练 | 用 `sort` / `only` / `ignore` 控制价格与供方 |
| 用 `hermes config set` 写 `provider_routing.models."a.b"` 失败 | 模型 id 里的点号被当成路径分隔符 | 这几个键直接编辑 `config.yaml` |
| 阈值调低后没立刻生效 | 小于 512K 窗口的模型有 0.75 地板阈值（只升不降） | 记住地板规则，或换窗口更大的模型 |

## 试一试

- [ ] 跑 `hermes prompt-size --json`，把「系统提示 / 技能索引 / 工具 schema」三个数字记下来当基线
- [ ] 在一个长会话里做 A/B：`/usage` → `/compress` → `/usage`，比较压缩前后的占用
- [ ] 用 `hermes -c` 做一次「换模型 → 看 input token 跳变」的实验，把两个数字写进 `journal/`
- [ ] 关掉一个你从来不用的工具集，再跑 `hermes prompt-size`，看 tool schemas 那行降了多少
- [ ] 检查 `auxiliary.compression` 是否用了一个比主模型更弱的模型 —— 如果是，这就是你压缩质量的隐患

## 下一步

- [[L10]] —— 模型与 provider：辅助模型槽位怎么分开配
- [[L12]] —— 会话与斜杠命令：`/compress`、`/usage`、`/context` 的完整用法
- [[L23]] —— 定时与循环：无人值守任务怎么把成本控制住
- [[L51]] —— 凭证池轮换为什么会清缓存
- 想深入：[[src:compression]]（压缩算法与缓存断点实现）、[[src:provider-routing]]（路由字段逐个说明）

## 出处

- [[src:compression]] Context Compression and Caching — https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching
- [[src:tips]] Tips & Best Practices — https://hermes-agent.nousresearch.com/docs/guides/tips
- [[src:provider-routing]] Provider Routing — https://hermes-agent.nousresearch.com/docs/user-guide/features/provider-routing
