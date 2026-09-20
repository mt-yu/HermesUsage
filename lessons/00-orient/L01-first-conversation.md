---
id: L01
title: 五分钟装好并说第一句话
stage: 0
level: 入门
minutes: 15
prereq: [L00]
tags: [安装, provider, 第一次对话, 验收]
sources: [quickstart, installation, platform-support]
updated: 2026-09-16
---

# L01 · 五分钟装好并说第一句话

> **一句话**：装 + 选 provider + 跑通一次「它用了工具」的对话，这三步做完，最难的部分就已经过去了。

## 你将学会

- 用官方脚本在你的系统上装好 Hermes，并让 `hermes` 命令可用
- 用 `hermes setup` / `hermes model` 选好 provider，知道「设置该写进哪个文件」
- 跑通一次**它真的用了工具**的对话，并用官方验收清单自我确认
- 判断一个模型能不能用（最小 64K 上下文这条硬门槛）

**前置**：[[L00]] · **预计耗时**：15 分钟

## 先动手

### 已经装好了？直接跳到第 2 步

```bash
hermes --version          # 有输出就不用装
```

### 第 1 步：安装（没装才需要）

| 系统 | 命令 |
|---|---|
| Linux / macOS / WSL2 / Android(Termux) | `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` |
| Windows（原生） | 在 **PowerShell** 里跑 `iex (irm https://hermes-agent.nousresearch.com/install.ps1)` |
| 想要图形界面 | 下载 [Hermes Desktop 安装包](https://hermes-agent.nousresearch.com/) 直接运行 |

装完重载 shell（Windows 直接重开 Git Bash）：

```bash
source ~/.bashrc      # zsh 用 ~/.zshrc
```

### 第 2 步：选 provider

```bash
hermes setup          # 全新安装会问你要走哪条路
hermes model          # 之后想换模型/换供应商，随时用这条
```

**最省事的一条路**：一个订阅覆盖 300+ 模型 + 工具网关（网页搜索、图像生成、TTS、云浏览器）：

```bash
hermes setup --portal
```

### 第 3 步：说第一句话（可验证的那种）

```bash
hermes chat -q "用三句话说明你能替我做什么，每句不超过 30 字"
```

我在本机跑出来的真实输出（耗时约 12 秒）：

```
我能帮你查资料、写文档、改代码，并把结果直接跑出来验证。

我能自动操作浏览器和终端，替你执行搜索、抓取、安装和排障。

我能长期记住你的偏好和常用流程，还能定时执行任务或调用多种工具协作。
```

**成功了。** 注意 `hermes chat -q` 只打印最终回复、不进入交互界面 —— 适合写进脚本。

想进去聊：

```bash
hermes                 # 经典 CLI
hermes --tui           # 新版 TUI（鼠标友好，推荐试试）
```

## 原理

### 三条安装路径，怎么选

`hermes setup` 在全新安装时给你三种模式：[[src:quickstart]]

| 模式 | 内容 | 适合谁 |
|---|---|---|
| **Quick Setup (Nous Portal)** | OAuth 登录，无 API key，包含模型 + 工具网关 | 不想折腾密钥的人（推荐） |
| **Full Setup** | 逐个走 provider、工具、选项（自备密钥） | 已有各家的 API key |
| **Blank Slate** | 只留 provider/model + 文件操作 + 终端，其余**全关** | 想要最小可控、自己按需开启 |

**Blank Slate 的隐藏价值**：它会写入显式白名单（`platform_toolsets.cli` 加
`agent.disabled_toolsets`），所以**你选过什么就一直是什么，连 `hermes update` 之后也不会
偷偷多出一堆工具**。之后想开回来用 `hermes tools`、想补技能用 `hermes skills opt-in --sync`。

### 设置写在哪：secrets 与 settings 的分家

这是新手最容易搞错、后续最难纠的一件事：

| 内容 | 文件 | 谁管 |
|---|---|---|
| **密钥 / token**（API key 等） | `~/.hermes/.env` | 只有密钥 |
| **普通设置**（模型名、后端、显示项） | `~/.hermes/config.yaml` | 永远不要放密钥 |

**不要手改 `config.yaml`**（一个缩进错误就能让整个 gateway 起不来）。用命令写：

```bash
hermes config set model anthropic/claude-opus-4.6
hermes config set terminal.backend docker
hermes config set OPENROUTER_API_KEY sk-or-...      # 这一条会自动进 .env
```

`hermes config set` 会把值自动送去正确的文件。[[src:quickstart]]

### 硬门槛：最小 64,000 tokens 上下文

模型上下文小于 **64K** 会被启动时直接拒绝 —— 因为多步工具调用需要的工作记忆装不下。
主流托管模型（Claude / GPT / Gemini / Qwen / DeepSeek）都远超这个数；

**跑本地模型要注意手动调大**：llama.cpp 用 `--ctx-size 65536`，Ollama 用 `-c 65536`。[[src:quickstart]]

## 亲手验证

### 验证一：会话能不能续上（官方验收清单第 4 条）

```bash
hermes --continue     # 简写：hermes -c
```

应该回到你刚才那次会话。如果没回来，先确认你在同一个 profile 下。

### 验证二：设置确实落在正确的文件里

```bash
hermes config path        # config.yaml 的位置
hermes config env-path    # .env 的位置
grep -c . "$(hermes config path)"     # 配置文件非空（能数出行数）
```

| 你观察到的 | 说明什么 |
|---|---|
| 两个路径指向不同文件 | secrets / settings 分家的设计确实生效了 |
| `--continue` 回到了上次会话 | 会话是持久化的，不是一关就没 |

### 验证三：自己跑一遍官方验收清单

- [ ] 启动横幅里显示了你选定的模型与 provider
- [ ] Hermes 正常回复、不报错
- [ ] 它**用了至少一个工具**（读文件 / 跑终端 / 搜网页）
- [ ] 对话能连续进行不止一轮

四条全中，你已经越过了最难的部分。[[src:quickstart]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `hermes: command not found` | 装完没重载 shell | `source ~/.bashrc` / `~/.zshrc`；Windows 重开 Git Bash |
| 启动时报「模型上下文不足」被拒 | 模型窗口 < 64K | 换模型，或给本地模型加 `--ctx-size 65536` / `-c 65536` |
| 把模型名写进了 `.env` | 以为 `.env` 是万能配置 | `.env` 只放密钥；设置用 `hermes config set` |
| 手改 `config.yaml` 后 gateway 起不来 | YAML 缩进被破坏 | 用 `hermes config set`；已坏了就 `hermes config check` |
| 急着接 Telegram/定时任务，结果哪都不通 | 跳过了「先跑通一次干净对话」 | 先回到第 3 步，跑通再加层 |

**官方那条规矩值得单独记住**：如果 Hermes 连一次正常对话都完不成，就别加任何功能。
先让一次干净的对话跑通，再往上叠 gateway、cron、skills、voice、routing。[[src:quickstart]]

## 试一试

- [ ] 用 `hermes chat -q` 让它做一件**需要读文件**的事，例如：`hermes chat -q "看一下当前目录，告诉我这里有哪些文件，并猜猜哪个最像主入口"`
- [ ] 跑 `hermes doctor`，把输出里的每个 `✓` 和任何 `✗` 记到 `journal/` 里
- [ ] 用 `hermes config get model` 查当前模型，再用 `hermes model` 换成另一个，观察 `config.yaml` 的变化

## 下一步

- [[L02]] —— 第一句话已经说出去了，下一课拆开看这一轮内部发生了什么
- [[L03]] —— 弄清 `config.yaml` / `.env` / `SOUL.md` / 记忆文件各自的职责，避免踩错文件
- 想深入：[[src:installation]] 里有各系统的详细前置条件与排障

## 出处

- [[src:quickstart]] Hermes Agent Quickstart — https://hermes-agent.nousresearch.com/docs/getting-started/quickstart
- [[src:installation]] Installation — https://hermes-agent.nousresearch.com/docs/getting-started/installation
- [[src:platform-support]] Platform Support — https://hermes-agent.nousresearch.com/docs/getting-started/platform-support
