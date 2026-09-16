---
id: L40
title: 写一个技能：SKILL.md 规范与实战
stage: 4
level: 进阶
minutes: 25
prereq: [L15]
tags: ["技能", "SKILL.md", "frontmatter", "platforms", "渐进式披露"]
sources: [creating-skills, skills, work-with-skills]
updated: 2026-09-16
---

# L40 · 写一个技能：SKILL.md 规范与实战

> **一句话**：技能是最低成本的扩展方式 —— 一个 `SKILL.md` 写清「什么时候用、怎么做、怎么自查」，放进技能目录就能用，一行 Hermes 的源码都不用改。

## 你将学会

- 按官方规范写全 `SKILL.md` 的 frontmatter：`name` / `description` / `version` / `metadata.hermes`
- 用 `platforms` 和 `requires_*` / `fallback_for_*` 控制技能在什么环境下出现
- 用 `references/`、`scripts/`、`templates/` 拆分长内容，并用 `${HERMES_SKILL_DIR}` 让 SKILL.md 里的命令可以直接粘
- 分清技能的三种外部依赖：密钥（env）、非敏感配置（config）、凭证文件
- 亲手触发一次「技能写好了却在列表里消失」并定位原因

**前置**：L15 · **预计耗时**：25 分钟

## 先动手

写一个能用的技能：把「整理 git 提交成 CHANGELOG」这件事固化下来。目录结构是固定的，`SKILL.md` 是唯一必需文件 [[src:creating-skills]]：

```bash
mkdir -p "$HERMES_HOME/skills/repo-changelog"     # Windows 上 $HERMES_HOME 默认是 %LOCALAPPDATA%\hermes

cat > "$HERMES_HOME/skills/repo-changelog/SKILL.md" <<'EOF'
---
name: repo-changelog
description: "Use when the user asks for a changelog or release notes for a git repository. Groups commits by type and writes CHANGELOG entry text."
version: 1.0.0
metadata:
  hermes:
    tags: [git, release, documentation]
---
# Repo changelog

把一段提交历史整理成可直接粘贴的 CHANGELOG 条目。

## When to Use

用户要求「写更新日志 / release notes / 这个版本改了什么」，并且当前目录是 git 仓库。

## Procedure

1. 确认范围：有 tag 就用 `<上一个 tag>..HEAD`，没有就问用户从哪个提交开始。
2. 拉提交列表（`git log --oneline --no-merges`），按 feat / fix / docs / chore 分组。
3. 每组按时间正序输出；每条写成「做了什么 + 影响谁」。
4. 结尾给出 BREAKING CHANGE 段落，没有就明确写「无」。

## Pitfalls

- 合并提交会污染列表：加 `--no-merges`。
- 只看 `--oneline` 会丢掉动机，需要时用 `--pretty=fuller` 补详情。

## Verification

输出的每一条都必须能对应到一条真实提交哈希；抽查两条：`git show <hash> --stat`。
EOF
```

确认它被系统认出来了：

```bash
hermes skills list
```

**你应该看到**（本机实测输出，技能名就是上面这个）：

```
                    Installed Skills
┌────────────────┬──────────┬────────┬───────┬─────────┐
│ Name           │ Category │ Source │ Trust │ Status  │
├────────────────┼──────────┼────────┼───────┼─────────┤
│ repo-changelog │          │ local  │ local │ enabled │
└────────────────┴──────────┴────────┴───────┴─────────┘
0 hub-installed, 0 builtin, 1 local — 1 enabled, 0 disabled
```

技能**不需要注册**：文件放进技能目录，下次开会话就在索引里了 [[src:work-with-skills]]。

## 原理

### SKILL.md 的骨架

官方给出的字段全貌如下，只有 `name` 和 `description` 是真正必填的，其余按需加 [[src:creating-skills]]：

| 字段 | 作用 |
|---|---|
| `name` | 技能名，同时是调用名 |
| `description` | 一句话说明「什么时候用我」。技能索引里每轮都会进上下文，所以它写得越准，模型越不会漏用或误用 |
| `version` / `author` / `license` | 元数据，发布到 hub 时用得上 |
| `platforms` | 限定操作系统：`macos` / `linux` / `windows`，省略即全平台 |
| `metadata.hermes.tags` | 分类标签，方便 `hermes skills search` |
| `metadata.hermes.requires_toolsets` / `requires_tools` | 这些工具/工具集**不在**时，技能隐藏 |
| `metadata.hermes.fallback_for_toolsets` / `fallback_for_tools` | 这些工具/工具集**在**时，技能隐藏（用来写「替代方案」技能） |
| `metadata.hermes.config` | 非敏感设置，落到 `config.yaml` 的 `skills.config.<key>` |
| `metadata.hermes.blueprint` | 给技能挂一个 cron 表达式，让技能同时是一个可运行的自动化 |
| `required_environment_variables` | 技能需要的密钥，值存 `~/.hermes/.env`，不展示给模型 |
| `required_credential_files` | 以文件形式存在的凭证（OAuth token、service account JSON） |

正文部分官方推荐的五个小节是 `When to Use` / `Quick Reference` / `Procedure` /
`Pitfalls` / `Verification` —— 注意最后一个：**技能要写「怎么自查」**，否则模型没法判断自己有没有做完 [[src:creating-skills]]。

### 平台门控与条件激活：让技能只在合适的时候出现

`platforms` 写死平台后，技能会在**系统提示、`skills_list()`、斜杠命令**三处同时消失（下一个实验你会看到它连 `hermes skills list` 的计数都不进）[[src:creating-skills]]。

条件激活管的是「有没有对应工具」，判据是一张四行表 [[src:creating-skills]]：

| 字段 | 行为 |
|---|---|
| `requires_toolsets` | 列表里任何一个工具集**不可用** → 隐藏 |
| `requires_tools` | 列表里任何一个工具**不可用** → 隐藏 |
| `fallback_for_toolsets` | 列表里任何一个工具集**可用** → 隐藏 |
| `fallback_for_tools` | 列表里任何一个工具**可用** → 隐藏 |

典型用法：写一个 `duckduckgo-search` 技能并声明 `fallback_for_tools: [web_search]`，它只在没配 web search 的机器上冒出来 [[src:creating-skills]]。

### 长技能怎么拆：渐进式披露

技能全文是按需加载的，但加载之后它是**整篇**进上下文。所以官方给的写法是：把最常见的流程放最前面，边角情况放最后；解析类逻辑不要指望模型当场写，放进 `scripts/`；参考资料放 `references/`，让模型需要时自己读 [[src:creating-skills]]。

```text
repo-changelog/
├── SKILL.md              # 主文档：什么时候用 + 怎么做 + 怎么自查
├── references/
│   ├── commit-types.md   # 参考资料，按需读
│   └── examples.md
├── templates/
│   └── changelog.md
└── scripts/
    └── group_log.py      # 解析/统计类脚本
```

SKILL.md 里引用它们不用写死路径：加载时 `${HERMES_SKILL_DIR}` 会被替换成技能目录的绝对路径，`${HERMES_SESSION_ID}` 换成当前会话 id [[src:creating-skills]]：

```markdown
统计提交分组，运行：

    python ${HERMES_SKILL_DIR}/scripts/group_log.py <since-tag>..HEAD
```

模型看到的就是一条可以直接粘进 `terminal` 的绝对路径命令，不用先 `skill_view` 再拼路径。

### 三种外部依赖，别放错地方

| 你要提供的东西 | 写在哪 | 存在哪 | 模型能看到值吗 |
|---|---|---|---|
| API key、token 这类**密钥** | `required_environment_variables` | `~/.hermes/.env` | 不能，且声明过、已存在的变量会自动透传进 `terminal` / `execute_code` 沙箱 [[src:creating-skills]] |
| 路径、偏好这类**非敏感设置** | `metadata.hermes.config` | `config.yaml` 的 `skills.config.<key>` | 能，加载时追加在技能消息末尾 [[src:creating-skills]] |
| OAuth token 文件、证书这类**文件凭证** | `required_credential_files` | `~/.hermes/` 下，路径相对于它 | 文件会被挂进 Docker（只读）/ Modal 沙箱；本地后端直接可用 [[src:creating-skills]] |

### 技能放哪里

- `skills/`：随 Hermes 一起装，要求「对大多数人有普遍用处」（文档处理、常见开发流程）
- `optional-skills/`：官方出品但比较重（要付费服务、额外依赖），`hermes skills browse` 里标 official，安装自带信任
- Skills Hub：小众、社区贡献的，用 `hermes skills install` 分发
- `~/.hermes/skills/`：**你自己的技能放这里**，是本地唯一的主目录 [[src:skills]]

技能目录是 Hermes 的自我改进面：agent 可以自己创建、修改、删除技能（`skill_manage`），也可以在解决一个复杂问题后主动问你要不要存成技能 [[src:work-with-skills]]。

## 亲手验证

### 验证一：平台门控是「静默消失」，不是报错

在同一个技能目录里再加一个**只给 macOS** 的技能：

```bash
mkdir -p "$HERMES_HOME/skills/mac-only-demo"
cat > "$HERMES_HOME/skills/mac-only-demo/SKILL.md" <<'EOF'
---
name: mac-only-demo
description: "Use when the user asks about macOS-only tooling (Keychain, AppleScript). Declares platforms: [macos]."
platforms: [macos]
---
# macOS only demo

声明了 platforms: [macos]，在 Windows 上不应出现在技能列表里。
EOF

hermes skills list
```

**本机实测输出**（Windows 11）：

```
                    Installed Skills
┌────────────────┬──────────┬────────┬───────┬─────────┐
│ Name           │ Category │ Source │ Trust │ Status  │
├────────────────┼──────────┼────────┼───────┼─────────┤
│ repo-changelog │          │ local  │ local │ enabled │
└────────────────┴──────────┴────────┴───────┴─────────┘
0 hub-installed, 0 builtin, 1 local — 1 enabled, 0 disabled
```

| 你观察到的 | 说明什么 |
|---|---|
| 表里没有 `mac-only-demo`，也**没有任何警告** | 平台不匹配是设计行为，不是错误 |
| 最后一行仍然是 `1 local` | 它连计数都不进 —— 技能被当成了「不存在」，而不是「被禁用的技能」 |
| 把 `platforms: [macos]` 那一行删掉，再跑一次 `hermes skills list` | 它会立刻出现。**技能名不复用、目录不改**，唯一变化就是那一行 |

这个实验的用处：以后遇到「我明明写了这个技能，为什么它不见了」，第一件事是 `grep platforms` 自己的 frontmatter。

### 验证二：技能同时是斜杠命令

技能装好后，名字就是斜杠命令 [[src:skills]]：

```bash
hermes chat -q "/repo-changelog 从 v0.3-core 到 HEAD 的改动"
# 输出：按 feat / fix / docs 分组的 CHANGELOG 草稿（内容取决于你仓库的提交历史）
```

只写技能名、不带任务时，它会反过来问你想要什么 —— 这是判断「技能到底加载了没有」最快的方法 [[src:work-with-skills]]。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 技能写好了，`hermes skills list` 里却没有 | frontmatter 的 `platforms` 与当前系统不匹配（本机实测：Windows 上 `platforms: [macos]` 的技能完全不出现，也无警告） | 删掉 `platforms` 或改成当前平台；用 `hermes skills list --source local` 只看本地技能 |
| 技能在列表里，模型却从不主动用它 | `description` 只写了「是什么」，没写「什么时候用」 | 改成 `Use when <触发条件>. <一行行为>.`，它是每轮都进上下文的那一行 [[src:creating-skills]] |
| 技能里的脚本读不到 API key | 变量没进 `~/.hermes/.env`，或没在 frontmatter 里声明 | 写到 `required_environment_variables`，值放 `~/.hermes/.env`；加载后已存在的变量会自动透传进沙箱 [[src:creating-skills]] |
| 一加载技能，上下文就满了 | 所有内容都塞在 `SKILL.md` 正文里 | 常用流程前置，细节拆到 `references/`，解析逻辑拆到 `scripts/` [[src:creating-skills]] |
| 技能里的命令要写一长串绝对路径才能跑 | 没用模板变量 | 写 `${HERMES_SKILL_DIR}/scripts/x.py`，加载时自动替换成绝对路径 [[src:creating-skills]] |
| 技能里的 `` !`date` `` 内联片段不执行 | 内联 shell 默认关闭（防投毒） | 确认来源可信后，在 `config.yaml` 里 `skills.inline_shell: true` [[src:creating-skills]] |

## 试一试

- [ ] 把 `repo-changelog` 改成你自己仓库能用的版本（换成你的分组规则），再用 `/repo-changelog` 跑一次，检查每条是否都能对应到真实提交
- [ ] 给技能加上 `templates/changelog.md`，并在 Procedure 里用 `${HERMES_SKILL_DIR}` 指它
- [ ] 写一个声明 `required_environment_variables` 的技能，观察加载时它怎么向你要密钥（值不会展示给模型）
- [ ] 用 `hermes skills list --enabled-only` 确认这个技能会在哪个 profile 加载
- [ ] 把结果记到 `journal/` 里并提交（见项目宪章的会话总结流程）

## 下一步

- [[L15]] —— 技能系统的基础机制：渐进式披露、项目技能的两道关
- [[L41]] —— 一个 SKILL.md 不够用时：写插件、注册工具与中间件
- [[L42]] —— 改外观与交互：桌面插件、TUI、皮肤、宠物
- [[L25]] —— 配方库：把技能和工具组合成能直接抄的工作流
- 想深入：[[src:creating-skills]] 的 blueprints 一节 —— 给技能加 `metadata.hermes.blueprint.schedule`，它就同时是一个能被 cron 调度的自动化

## 出处

- [[src:creating-skills]] Creating Skills — https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills
- [[src:skills]] Skills System — https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- [[src:work-with-skills]] Working with Skills — https://hermes-agent.nousresearch.com/docs/guides/work-with-skills
