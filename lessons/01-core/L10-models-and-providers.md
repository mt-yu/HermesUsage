---
id: L10
title: 模型与 Provider：你到底在跟谁说话
stage: 1
level: 入门
minutes: 20
prereq: [L00, L01]
tags: [模型, provider, 配置, 辅助模型, 缓存]
sources: [configuring-models, providers, quickstart]
updated: 2026-09-16
---

# L10 · 模型与 Provider：你到底在跟谁说话

> **一句话**：Hermes 里跑的不止一个模型 —— 一个「主模型」负责思考，一堆「辅助模型」负责杂活；而换模型最贵的时刻，是中途换。

## 你将学会

- 区分主模型（main model）与辅助模型（auxiliary models），说出至少四个辅助模型的用途
- 用 `hermes model` / `hermes setup --portal` 配置 provider，并知道配置写进了哪个文件
- 解释「中途换模型」为什么可能让下一条消息的成本翻好几倍
- 用命令查出当前的主模型配置，并读懂它的结构

**前置**：[[L00]]、[[L01]] · **预计耗时**：20 分钟

## 先动手

```bash
hermes config get model
hermes model          # 交互式选择 provider / 模型
```

本机真实输出（`hermes config get model`）：

```
default: deepseek-v4-pro
provider: mac-provider
base_url: ''
```

**看到这三行，你就知道自己在跟谁说话了**：

| 字段 | 含义 |
|---|---|
| `default` | 主模型的名字 |
| `provider` | 用哪个供应商（决定走哪个 API、用哪个密钥） |
| `base_url` | 自定义端点（空 = 用 provider 的官方地址） |

新装的机器上，`model:` 可能是一个**空字符串** —— 那是「尚未配置」的哨兵值。
只要你跑一次 `hermes setup` 或 `hermes model`，它就会被就地升级成上面这种
带 `provider` / `default` / `base_url` / `api_mode` 的映射结构。[[src:configuring-models]]

## 原理

### 一个「主模型」+ 一堆「辅助模型」

这是新手最容易漏掉的一层：

| 角色 | 干什么 | 谁在用它 |
|---|---|---|
| **主模型 Main model** | 你的每条消息、每次工具循环、每次流式回复 | 你的日常对话 |
| **辅助模型 Auxiliary models** | 上下文压缩、视觉（图像分析）、网页摘要、审批打分、MCP 工具路由、会话标题生成、技能搜索 | 系统在后台偷偷用 |

**关键**：每个辅助任务都有**自己独立的槽位**，可以单独覆盖。所以你可以用便宜快的模型
跑压缩和标题，用贵的模型只做主思考。[[src:configuring-models]]

**实践建议**：先把主模型选对（能力够、上下文 ≥ 64K），再去调辅助模型。
顺序反了会让你在错的模型上做精细优化。

### 供应商不是「选一个就锁死」

`hermes model` 随时可换。官方列出的常见档位大致是三类：

| 类型 | 例子 | 特点 |
|---|---|---|
| 订阅制（OAuth 登录，无需 API key） | Nous Portal、OpenAI Codex、Anthropic(OAuth)、xAI Grok、Qwen、MiniMax | 一个订阅覆盖很多模型 |
| API key 直连 | OpenRouter、DeepSeek、Google AI Studio、xAI… | 按 token 计费，自己管密钥 |
| 本地 / 自建端点 | Ollama、LM Studio、vLLM、SGLang、llama.cpp | 数据不出本机；上下文要自己调够 |

Nous Portal 是一条省事的路：一个订阅覆盖 300+ 模型，还含工具网关（网页搜索、
图像生成、TTS、云浏览器），且订阅者对 token 计费的 provider 有 **10% 折扣**。[[src:providers]] [[src:configuring-models]]

### 最贵的一刀：中途换模型

> Prompt 缓存是按「正在服务的模型」来记账的。任何**会话中途**的模型变化 ——
> 手动 `/model`、自动 fallback、凭证池轮换到另一个账号 —— 都意味着下一条消息
> 要**按全价重读整段对话**，而不是走缓存那 ~75–90% 的折扣价。
> 在一个长会话上，这一次重读的开销可能远超过两个模型之间的单价差。

Hermes 因此在「活动会话已持有大上下文」时（默认阈值 **100,000 tokens**，
以最近一次供应商计费的 prompt 大小计）会**明确要求确认**才应用中途切换。[[src:configuring-models]]

**结论（值得当纪律）**：要么在对话早期换，要么新开会话再换。

### 密钥与设置分家（这条会反复出现）

```bash
hermes config set model anthropic/claude-opus-4.6    # 设置 → config.yaml
hermes config set OPENROUTER_API_KEY sk-or-...       # 密钥 → .env
```

`hermes config set` 会自动把值送进正确的文件。**手改 `config.yaml` 是高危动作**。[[src:quickstart]]

## 亲手验证

### 验证一：确认「主模型 vs 辅助模型」是两个层面

```bash
hermes config get model                                   # 主模型
hermes config show | grep -n -A8 -i "auxiliary"           # 辅助模型的槽位
```

| 你观察到的 | 说明什么 |
|---|---|
| 主模型只有一个 `default` | 它决定你的对话质量上限 |
| 辅助任务有多个可覆盖的槽位 | 你可以用便宜模型干杂活，不必全家最贵 |

### 验证二：亲手感受「中途换模型清缓存」的代价

```bash
hermes -c                # 续上一个已有一定长度的会话
#   ❯ 总结一下我们前面聊了什么
#   （观察第一轮的耗时/用量）
#   ❯ /model
#   （换一个模型，再问一次同样的问题）
#   （对比这一次的 input token 数 —— 大概率明显变大）
```

| 你观察到的 | 说明什么 |
|---|---|
| 切换后的那一次 input token 陡增 | 缓存失效，整段对话按全价重读 |
| 后续轮次又降下来 | 新模型建了自己的缓存 |

### 验证三：本地模型这条路的硬门槛

```bash
# 如果你在用 Ollama
ollama run <你的模型>
#   >>> /set parameter num_ctx 65536     # 或启动时 -c 65536
```

上下文小于 64K 的模型会在启动时被直接拒绝 —— 多步工具调用装不下工作记忆。[[src:quickstart]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `config.yaml` 里 `model:` 是空字符串 | 新装未配置（哨兵值） | 跑一次 `hermes model`，它会写成映射结构 |
| 长会话中途换模型后账单跳了一次 | 缓存按模型记账，切换即全价重读 | 早换或新开会话再换 |
| 启动被拒「上下文不足」 | 模型窗口 < 64K | 换模型，或本地模型调大 `num_ctx` / `--ctx-size` |
| 把模型名写进 `.env` | 以为 `.env` 是通用配置 | `.env` 只放密钥；设置一律 `hermes config set` |
| 明明换了模型但新会话才生效 | 模型变更只对新会话生效 | 当前会话用 `/model` 热切（并接受一次缓存重建） |
| 压缩/标题这些杂活也在烧钱 | 不知道有辅助模型 | 给辅助槽位配便宜模型 |

## 试一试

- [ ] 用 `hermes config get model` 记下当前配置，再 `hermes model` 换一个，对比 `config.yaml` 的变化
- [ ] 列出你能用上的 2-3 个 provider，判断哪个最适合「长期高频用」（考虑订阅 vs 按量）
- [ ] 找出一条你经常重复的长上下文场景，评估「改用便宜辅助模型是否可行」
- [ ] 把本课的「辅助模型清单」抄进 `journal/`，标注哪些你打算单独配置

## 下一步

- [[L11]] —— 模型决定「它多聪明」，工具集决定「它能做多少事」，两者是分开的两把旋钮
- [[L12]] —— 会话边界：什么时候该 `/new`，以及会话到底存在哪
- [[L52]] —— 成本与缓存的完整心法（本课只讲了最要命的那一刀）
- 想深入：[[src:configuring-models]]（辅助槽位逐个说明）、[[src:providers]]（全部供应商与密钥）

## 出处

- [[src:configuring-models]] Configuring Models — https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models
- [[src:providers]] Providers — https://hermes-agent.nousresearch.com/docs/integrations/providers
- [[src:quickstart]] Hermes Agent Quickstart — https://hermes-agent.nousresearch.com/docs/getting-started/quickstart
