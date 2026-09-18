---
id: L15
title: 技能系统：让它学会你的活法
stage: 1
level: 入门
minutes: 25
prereq: [L13, L14]
tags: [技能, SKILL.md, 渐进式披露, 项目技能, curator]
sources: [skills, creating-skills, curator, work-with-skills, slash-commands]
updated: 2026-09-16
---

# L15 · 技能系统：让它学会你的活法

> **一句话**：技能是「按需加载的说明书」—— 平时只占一行摘要的上下文，用到时才读全文；把重复交代的事写成技能，是你在这套系统里投入产出比最高的一件事。

## 你将学会

- 说出技能的存放位置、加载机制（渐进式披露）以及它与记忆的分工
- 把技能当斜杠命令用，并知道怎么一次叠多个技能
- 亲手写一个最小可用技能，并验证它被加载
- 说清「项目级技能」为什么默认不加载，以及两层开关（信任 + 扫描）分别防什么

**前置**：[[L13]]、[[L14]] · **预计耗时**：25 分钟

## 先动手

建一个最小技能（30 秒）：

```bash
mkdir -p "$HERMES_HOME/skills/say-hello"
cat > "$HERMES_HOME/skills/say-hello/SKILL.md" <<'EOF'
---
name: say-hello
description: "Use when the user greets you in Chinese. Reply in the house style: one line, no filler."
---
# 打招呼

回复必须满足：一句话、带一个可执行的下一步、不寒暄。
EOF
```

立刻在会话里用斜杠命令调用它：

```bash
hermes
#   ❯ /say-hello 你好
```

**你应该看到**：它按你写的风格回话，而不是套默认的客套。
（技能名就是斜杠命令名；`hermes skills list` 里也能看到它。）

## 原理

### 技能放在哪、谁在管

- **主目录**：`~/.hermes/skills/` —— 唯一的主目录与真相来源
- 全新安装会从仓库里拷一份内置技能目录进来；hub 安装的、agent 自己创建的也都放这里
- **agent 可以修改或删除任何技能**（这是它「自我改进」的实现方式）[[src:skills]]

### 渐进式披露：为什么装 50 个技能也不心疼

会话开始时，只有**名字 + 一句话描述**进入上下文（技能索引）；真正用到时才读 `SKILL.md` 全文。
这就是为什么技能数量可以很多，而上下文不会被撑爆。

**这条推论很重要**：技能描述（frontmatter 里的 `description`）是**唯一每轮都在花钱的部分**，
所以它必须写得又短又能让人（和模型）判断「什么时候该用我」。

### 技能即斜杠命令（还能叠加）

```bash
/gif-search funny cats                                     # 技能名 + 参数
/excalidraw                                                # 只写名字，让它反问你要什么

# 叠加多个（开头最多 5 个 /skill 标记会被加载，其余是给它的指令）：
/github-pr-workflow /test-driven-development fix issue #123 and open a PR
```

解析在遇到第一个「不是已安装技能」的 token 时停止，所以参数里以 `/` 开头的路径不会被吞掉。[[src:skills]]

### 项目级技能：默认不加载，且要过两道关

这是最适合「跟着仓库走」的技能形态 —— 把操作手册放进仓库，谁 clone 谁就有。
但它是个提示注入面，所以有两道防护：[[src:creating-skills]]

| 关口 | 防什么 | 怎么过 |
|---|---|---|
| **① 信任（人工，一次性）** | 防止「随便 clone 一个仓库就自动执行里面的指令」 | `hermes skills trust <路径>` |
| **② 扫描（每次内容变化，缓存哈希）** | 防止「已经信任的仓库，某次 `git pull` 塞进恶意技能」 | 由 hub 同款 skills_guard 扫描：判定 `dangerous` 则隔离（不进索引、不能 view、不能当斜杠命令）；`caution` 仍然加载；**扫描器崩了则 fail-closed 一并隔离** |

扫描缓存在 `$HERMES_HOME/cache/project_skill_scans`（**绝不写进你的仓库**），
所以代价是「每个技能每次内容变化扫一次」。

可信的项目技能目录只有两个：`<项目根>/.hermes/skills/`、`<项目根>/.agents/skills/`。
项目根 = **最近的含 `.git` 的祖先目录**。信任后，它们会**覆盖同名的 profile / 内置技能**。

### 与记忆的分工（一句话判据）

| 你要沉淀的东西 | 放哪 |
|---|---|
| 「**事实**」：我的偏好、环境、约定 | 记忆（MEMORY.md / USER.md），容量小 | [[L13]] |
| 「**流程**」：这类任务该怎么做，步骤、坑、判据 | **技能**（SKILL.md），按需加载，可无限多 | 本课 |

### 让技能自己长大：curator

装了技能之后会出现一个新问题：**哪些还有人用？哪些已经过时？** Hermes 用 curator
做后台维护 —— 使用统计、过期判断、归档，以及 LLM 驱动的复审。[[src:curator]]

你也可以手动触发一次自我改进复盘：

```
/refine save the deploy workflow as a skill
```

它会在**后台分叉**里对着会话快照跑，**不动**你的活会话与 prompt 缓存。[[src:slash-commands]]

### 不想要内置技能？

```bash
hermes skills opt-out          # 停止未来的种子投放（不动磁盘上已有的）
hermes skills opt-out --remove # 同时删除「未被修改过」的内置技能（会先确认）
hermes skills opt-in --sync    # 反悔：去掉标记并立刻重新投放
```

它只停未来的投放，**从不删除你已经改过/自己写的技能**。[[src:skills]]

## 亲手验证

### 验证一：技能就是斜杠命令，且能看清单

```bash
hermes skills list | head -8
hermes skills browse        # 逛仓库（分页）
hermes skills search csv    # 搜 hub
```

### 验证二：项目技能的两道关（本机实测）

本仓库自带两个项目技能（`.hermes/skills/hermes-tutorial-authoring` 与 `session-journal`）。
实测它们**不会**自动加载，而 `hermes skills trust` 后的行为如下：

```bash
hermes skills trust .
# 输出（本机真实）：
#   Trusted: D:\Projects\ai_projects\HermesUsage
#   2 project skill(s) will load in sessions started inside this repo
#   (they take precedence over same-named profile skills).

hermes config get skills.trusted_project_dirs
# 输出：- D:\Projects\ai_projects\HermesUsage
```

**但注意实测发现的坑**：仅仅信任还不够 —— 项目技能的解析依赖「**当前项目根**」，
而项目根的判定优先采用会话的工作目录（`TERMINAL_CWD`），其次才是进程 cwd。
如果你的会话工作目录落在项目之外（例如 home 目录），技能**不会**被加载。

可以直接用官方代码路径自查（本机实测输出）：

```bash
export HERMES_HOME="${HERMES_HOME:-$LOCALAPPDATA/hermes}"     # Windows；macOS/Linux 用 ~/.hermes
cd <你的项目>
"$HERMES_HOME/hermes-agent/venv/Scripts/python" - <<'PY'
import sys, os
sys.path.insert(0, os.path.join(os.environ["HERMES_HOME"], "hermes-agent"))
from agent.skill_utils import find_project_root, get_project_skills_dirs, is_quarantined_project_skill
print("project root:", find_project_root())
for d in get_project_skills_dirs():
    for p in d.rglob("SKILL.md"):
        print("  ", p.parent.name, "| quarantined:", is_quarantined_project_skill(p))
PY
```

| 你观察到的 | 说明什么 |
|---|---|
| `project root:` 是你项目的绝对路径 | 项目根解析到了；不在此路径内的技能不会被看到 |
| `quarantined: False` | 扫描通过（`True` 说明被判危险或扫描器失败，fail-closed） |
| 若 `project root: None` | 会话工作目录不在任何 git 仓库里 → 项目技能不加载 |

### 验证三：看渐进式披露的代价

```bash
hermes -c
#   ❯ /context all
```

`/context all` 会附上**每个技能与每个工具集的开销**（索引成本 vs 加载 `SKILL.md` 的成本、
每个工具集的 schema token）。这是「我能装多少技能」的实测依据。[[src:slash-commands]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 项目技能不加载（`hermes skills list` 里也没有） | ① 未信任；② 会话工作目录不在项目内 | `hermes skills trust .`；并确保从项目目录启动会话 |
| 信任过了还是不加载 | 项目根判定优先用 `TERMINAL_CWD` | 从项目目录启动；或用上面的自查脚本确认 `project root` |
| 技能被判 `dangerous` 而消失 | 内容命中 skills_guard（或扫描器崩了，fail-closed） | 改写命中内容；扫描缓存在 `$HERMES_HOME/cache/project_skill_scans` |
| 装了技能但模型不主动用 | `description` 没写清「什么时候用」 | 描述写成 `Use when <触发条件>. <一行行为>.` |
| 把所有知识塞进一个技能 | 没有按需加载的意义了 | 按「一类任务一个技能」拆；长内容用 `references/` 子文件 |
| 技能索引把上下文吃满 | 每个技能的 description 每轮都在花钱 | `/context all` 看成本，精简或禁用不常用的 |
| 以为记忆能代替技能 | 记忆有 3,575 字符上限 | 流程类知识一律进技能 |

## 试一试

- [ ] 写一个你自己的技能，把一件你反复交代的流程固化下来（模板见 [[L40]]）
- [ ] 用 `/skill-name` 直接调用它，再故意不写参数，看它是否会反问你
- [ ] 跑一次 `/refine`，让它把本次会话里学到的东西沉淀成技能或记忆
- [ ] 用 `hermes skills list` 数一下你现在有多少技能，挑三个写出它们各自的 `description` 并评估质量
- [ ] 判断：下面三件事分别该进**记忆**还是**技能**？① 我用 pnpm 不用 npm ② 部署前要跑三件事 ③ 我的时区是 UTC+8

## 下一步

- [[L40]] —— 写一个专业级技能：frontmatter 规范、`references/` 结构、常见失败模式
- [[L25]] —— 配方库：把技能与工具组合成工作流
- [[L41]] —— 技能不够用时：写插件扩展内核
- 想深入：[[src:creating-skills]]（官方创建规范）、[[src:curator]]（技能的生命周期管理）

## 出处

- [[src:skills]] Skills System — https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- [[src:creating-skills]] Creating Skills — https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills
- [[src:curator]] Curator — https://hermes-agent.nousresearch.com/docs/user-guide/features/curator
- [[src:work-with-skills]] Work with Skills — https://hermes-agent.nousresearch.com/docs/guides/work-with-skills
