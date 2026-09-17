---
id: L64
title: 把这次劳动固化成技能，下次一句话复用
stage: 6
level: 进阶
minutes: 30
prereq: [L15, L40]
tags: ["技能", "SKILL.md", "description", "触发", "复用"]
sources: [creating-skills, work-with-skills, skills, context-files, curator]
updated: 2026-09-16
---

# L64 · 把这次劳动固化成技能，下次一句话复用

> **一句话**：同一个流程做到第三遍就该停下来写技能 —— 本课教你写一个最小可用的 SKILL.md，并用「跑三次数命中」的实测法确认它真的会被自动选中。

## 你将学会

- 用三条判据判断「这次劳动值不值得写成技能」，以及该进技能还是进上下文文件 / 记忆
- 写出一个最小可用 SKILL.md，并指出其中哪几行决定它会不会被自动选中
- 在 3 分钟内验证技能「被看见了」：`hermes skills list` 与会话里的 `/skills`
- 用同一提示跑三次、数命中次数的方法，实测含糊描述与具体描述的差别
- 说明项目技能为什么 `trust` 过了仍然可能不加载

**前置**：L15、L40 · **预计耗时**：30 分钟

## 先动手

把「每周把 git 提交整理成周报」这件事写成技能（3 分钟内能看到结果）：

```bash
# Windows git-bash：默认 profile 在 $LOCALAPPDATA/hermes
# macOS / Linux：把下面这行换成 SKILLS="$HOME/.hermes/skills"
SKILLS="${HERMES_HOME:-$LOCALAPPDATA/hermes}/skills"
echo "$SKILLS"        # 先确认这是你自己的 profile 目录（见「常见坑」第 2 条）

mkdir -p "$SKILLS/weekly-report"
cat > "$SKILLS/weekly-report/SKILL.md" <<'EOF'
---
name: weekly-report
description: "用户要「把本周的 git 提交整理成周报」时使用。"
version: 1.0.0
---

# 周报

输出必须以 `【周报·简短版】` 开头，列三条要点，不加寒暄。
EOF

hermes skills list | grep weekly-report
```

你应该看到（本机真实输出）：

```
│ weekly-report          │                      │ local   │ local   │ enabled │
```

这里有两个关键列：`Source`/`Trust` 都是 `local`，说明它是你自己写的、在你本机 profile 里。

再确认它在**会话**里也能被看见 —— 会话里的 `/skills` 打的就是「名字 — 一句描述」：

```bash
hermes chat -Q -q "/skills" | grep weekly-report
```

```
  weekly-report — 把本周 git 提交整理成周报
```

> 这一行是 Hermes 给你看的描述（措辞可能与 SKILL.md 里的原文略有出入，本机实测如此）。
> 真正进到模型面前的，是技能索引里的「名字 + 描述」这一行 —— 会话开始时只加载这份紧凑清单，`SKILL.md` 全文要等它真的要用才读。[[src:work-with-skills]]
> 不想留痕：`rm -rf "$SKILLS/weekly-report"`，之后重来即可。

## 原理

### 1. 什么时候值得写：三条触发 + 一条「第三遍」经验

官方给的「agent 该自己写技能」的场合有三个，你自己动手时照抄这三条判据就行：[[src:skills]]

- 一套多步骤流程，你**还会再做**；
- 一条**踩过坑才找到**的可行路径（坑本身也是内容）；
- 你**纠正过它**的做法（这是一条别人不知道的偏好）。

本课再加一条操作性的：**同一个流程你口述到第三遍**，就该停手写技能。第一遍是探索，第二遍是复现，第三遍开始你付的都是重复成本。

### 2. 该写技能，还是该写常驻上下文？

同一个「规矩」，放错地方的成本差别很大：

| 放哪 | 什么时候进上下文 | 适合放什么 |
|---|---|---|
| `.hermes.md` / `AGENTS.md` / `SOUL.md` | **每轮都注入**，全文都在系统提示里 [[src:context-files]] | 每轮都必须知道的规矩、路径、约定 |
| 技能（SKILL.md） | 平时只占索引一行，用到才读全文 [[src:skills]] | 一类任务的**流程**：步骤、命令、坑、验收判据 |

```
系统提示（每轮都进上下文，按 token 付费）
├── .hermes.md / AGENTS.md / SOUL.md 全文     ← 「每轮都必须说的话」放这儿 [[src:context-files]]
└── 技能索引：<name> — <description>          ← 每个技能只占一行
         │  模型判断：「这一行和我现在要干的事有关吗」
         ▼
    skill_view("<name>")  →  SKILL.md 全文     ← 真的用上才读，用不上不花钱 [[src:skills]]
```

判断口诀（官方原文意思）：**会写进参考文档的东西 → 技能；会写在便利贴上的东西 → 记忆。** [[src:work-with-skills]]

### 3. 决定「会不会被自动选中」的，只有这几行

frontmatter 能写的键很多，但只有三处影响「被选中」：

| 位置 | 作用 | 判据 |
|---|---|---|
| `name` | 同时是斜杠命令名（`/weekly-report`）[[src:skills]] | 短、能看出干什么 |
| `description` | 索引里唯一的一句话，模型据此判断相关性 [[src:work-with-skills]] | 写成 `Use when <触发场景>. <一行行为>.`，把**你真会说的那句原话里的词**塞进去（周报、对账、Excel、PR……） |
| `platforms` / `requires_toolsets` / `requires_tools` / `fallback_for_*` | 决定它**出不出现在**索引里：平台或工具集不匹配时整个隐藏 [[src:creating-skills]] | 不确定就别写；从别处抄来的 frontmatter 是重灾区 |

`tags` / `category` 管的是归类与检索，不决定这一次用不用它 [[src:creating-skills]]。

本仓库自带的技能就是现成例子 —— `.hermes/skills/hermes-tutorial-authoring/SKILL.md` 的 frontmatter：

```yaml
description: "Use when adding or editing a lesson in the HermesUsage tutorial repo. Enforces the 8-section template, citation binding, and the verify gate before commit."
```

一句话里同时给了「什么时候用（加/改一课）」和「用了会怎样（守 8 节模板 + 出处绑定 + 过 verify 门禁）」。

### 4. 正文照抄四节，不要自由发挥

官方模板给的是固定骨架：`When to Use` → `Quick Reference` / `Procedure` → `Pitfalls` → `Verification`。[[src:creating-skills]]
把「最常用的那条路」放最前面，边角情况放最后 —— 这样常用任务的 token 成本最低。[[src:creating-skills]]

### 5. 写完不会烂掉：谁在动你的技能

| 技能来源 | curator 会动它吗 |
|---|---|
| 你自己手写的 `SKILL.md` | **不会**：它的记录里没有「agent 创建」标记，不在 curator 辖区 [[src:curator]] |
| 你让前台 agent 建的（含 `/learn`） | 不会：记为「你说要的」，curator 有意放手 [[src:curator]] |
| 后台自我改进复审建的 | 会：长期没人看就走 `active → stale → archived`，可 `hermes curator restore <name>` 找回 [[src:curator]] |

想确认自己的技能在不在辖区：`hermes curator status` 会分别给出 managed / unmanaged 的数量。[[src:curator]]

## 亲手验证

### 验证一：只改 `description` 这一行，看它会不会被自动选中

先做**判据**：让技能正文里有一个「只有加载了才会出现」的标记 —— 上面先动手的正文要求输出以 `【周报·简短版】` 开头，这就是标记。

① 把描述改成含糊的 :

```bash
SKILLS="${HERMES_HOME:-$LOCALAPPDATA/hermes}/skills"
cat > "$SKILLS/weekly-report/SKILL.md" <<'EOF'
---
name: weekly-report
description: "处理各种杂事"
version: 1.0.0
---

# 周报

输出必须以 `【周报·简短版】` 开头，列三条要点，不加寒暄。
EOF

for i in 1 2 3; do
  printf '含糊 run%s 命中: ' "$i"
  hermes chat -t skills --max-turns 4 -Q -q "把这周的 git 提交整理成周报发我" | grep -c "简短版"
done
```

本机实测输出（0 = 回答里没出现标记 = 没加载这个技能）：

```
含糊 run1 命中: 0
含糊 run2 命中: 0
含糊 run3 命中: 0
```

② 只把 `description:` 换成具体的（其余一个字不动），同样跑三次：

```bash
cat > "$SKILLS/weekly-report/SKILL.md" <<'EOF'
---
name: weekly-report
description: "Use when the user asks to turn this week's git commits into a weekly report (周报)."
version: 1.0.0
---

# 周报

输出必须以 `【周报·简短版】` 开头，列三条要点，不加寒暄。
EOF

for i in 1 2 3; do
  printf '具体 run%s 命中: ' "$i"
  hermes chat -t skills --max-turns 4 -Q -q "把这周的 git 提交整理成周报发我" | grep -c "简短版"
done
```

本机实测输出：

```
具体 run1 命中: 0
具体 run2 命中: 2
具体 run3 命中: 1
```

| 你观察到的 | 说明什么 |
|---|---|
| 含糊描述：本机累计 **0/5** 次命中 | 索引里那一行不含「周报」「git 提交」这类词 → 模型没有理由去读它 |
| 具体描述：本机累计 **3/5** 次命中（不是 5/5） | 描述写对只**提高**被选中的概率，不保证每次 —— 所以用「跑三次数命中」而不是「跑一次下结论」 |
| 命中时回答里会出现 `【周报·简短版】` | 判据是技能正文独有的标记，不是感觉 |
| 换成 `/weekly-report 把本周提交整理成周报` | 斜杠命令是**强制加载**，与描述写得好不好无关 [[src:skills]] |

`-t skills`（等价写法 `--toolsets skills`）只给技能工具集，命令里没有终端，所以「命中」只看它有没有读你的技能。[[src:creating-skills]]

### 验证二：项目技能不是 `trust` 了就一定加载

本仓库自带两个项目技能（`.hermes/skills/hermes-tutorial-authoring`、`session-journal`），并且本机已经执行过 `hermes skills trust .`。在仓库目录里分别跑这两条：

```bash
# ① 会话工作目录 = 你 shell 的当前位置（本机是 home 目录）
hermes chat -Q -q "/skills" | grep hermes-tutorial-authoring

# ② 显式把会话工作目录指向仓库
hermes chat --in D:/Projects/ai_projects/HermesUsage -Q -q "/skills" | grep hermes-tutorial-authoring
```

本机实测：

```
（① 没有任何输出 —— 项目技能不加载）
（② 输出）
  - hermes-tutorial-authoring — 增改 HermesUsage 教程课程：8 节模板、出处硬绑定、提交前过 verify 门禁
```

| 你观察到的 | 说明什么 |
|---|---|
| ① 无输出 | `hermes chat -q` 的会话工作目录**不是**你 shell 的 `cd`，项目根按会话工作目录解析 → 解析不到仓库，项目技能整批不加载 |
| ② 出现了 | 加上 `--in <仓库路径>` 后项目根解析到了，同一套信任立刻生效 |
| 在仓库目录跑 `hermes skills list` 也看不到项目技能 | CLI 的列表只列 profile / hub / 内置；项目技能要看**会话里**的 `/skills`（本机实测）[[src:skills]] |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `SKILL.md` 就在磁盘上，`hermes skills list` 里没有 | 只有被扫描的目录才算数：`$HERMES_HOME/skills/`、`external_dirs`、以及项目根的 `.hermes/skills/`。放在别的目录（例如临时目录）不会被扫描 | `mkdir -p "$HERMES_HOME/skills/<name>"` 后重放。本机实测：同一份文件在 `…/Temp/skilldemo/weekly-report/SKILL.md` 时列表里 0 条，移到 profile 的 `skills/` 下立刻出现 [[src:skills]] |
| 列表整片空着，可你的技能都在 | 当前 shell 的 `HERMES_HOME` 指向了另一个 profile 或临时目录 | `echo "$HERMES_HOME"`；用绝对路径或 `HERMES_HOME=<你的profile目录> hermes skills list` 固定下来。本机实测：同一个 shell 里 `HERMES_HOME` 指到空目录后，`hermes skills list --source local` 从 33 条变 0 条 |
| 项目技能里 trust 也执行了，还是没出现 | 「项目根」按**会话工作目录**解析，不看你的 shell `cd` | 从仓库目录启动会话，或用 `hermes chat --in <仓库路径>`；自查脚本见 [[L15]] 的「亲手验证」 [[src:skills]] |
| 技能写了，模型很少主动用 | `description` 太含糊 | 改写成 `Use when <你真会说的那句话>. <一行行为>.`，把触发词放进描述。本机实测含糊 0/5、具体 3/5（用法见「亲手验证」）[[src:work-with-skills]] |
| 在 macOS 上好好的，Windows 上根本没这个技能 | 抄来的 frontmatter 里带 `platforms:` 限制 | 删掉 `platforms:`，或写全 `[macos, linux, windows]`。不兼容平台上技能会从系统提示、`skills_list()`、斜杠命令里一起消失 [[src:skills]] |
| 技能时有时无，换台机器更明显 | `requires_toolsets` / `requires_tools` / `fallback_for_toolsets` / `fallback_for_tools` 会按当前会话的工具集把它藏起来 | 逐个自查这几个键，不确定就别写 [[src:creating-skills]] |
| 技能索引把上下文吃满 | `description` 是**每轮都在花钱**的部分 | 一句话、约 60 字符以内，别写段落 [[src:skills]] |

## 试一试

- [ ] 挑一个你已经做过三遍的流程，写成 `$HERMES_HOME/skills/<name>/SKILL.md`，用 `hermes skills list | grep <name>` 确认它被看见
- [ ] 对刚写的技能做一次「跑三次数命中」的对照实验（含糊描述 3 次 / 具体描述 3 次），把两组命中数记到 `journal/` 里
- [ ] 用 `hermes chat -t skills -Q -q "/<技能名> <一句任务>"` 强制调用一次，对比「自动选中」和「斜杠命令」的区别
- [ ] 把一个技能放进你某个 git 仓库的 `.hermes/skills/`，`hermes skills trust .` 之后从仓库目录开会话，确认 `/skills` 里能看到它
- [ ] 数一下你现在有多少技能（`hermes chat -Q -q "/skills"`），挑三个抄下它们的 `description`，各改写成 `Use when …` 一句

## 下一步

- [[L15]] —— 技能系统基础：渐进式披露、项目技能的两道关（本课的前置）
- [[L40]] —— 写一个专业级技能：frontmatter 全字段与 `references/` 结构（本课的前置）
- [[L14]] —— 上下文文件：哪些规矩该写成「每轮都在」的常驻文件，而不是技能
- [[L25]] —— 配方库：把技能和工具拼成可直接抄的工作流
- 想深入：[[src:creating-skills]]（官方 SKILL.md 规范与条件激活）、[[src:curator]]（技能的生命周期与归档回滚）

## 出处

- [[src:creating-skills]] Creating Skills — https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills
- [[src:work-with-skills]] Working with Skills — https://hermes-agent.nousresearch.com/docs/guides/work-with-skills
- [[src:skills]] Skills System — https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- [[src:context-files]] Context Files — https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
- [[src:curator]] Curator — https://hermes-agent.nousresearch.com/docs/user-guide/features/curator
