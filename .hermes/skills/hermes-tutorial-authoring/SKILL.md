---
name: hermes-tutorial-authoring
description: "Use when adding or editing a lesson in the HermesUsage tutorial repo. Enforces the 8-section template, citation binding, and the verify gate before commit."
version: 1.0.0
author: HermesUsage
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tutorial, documentation, hermes, citations, quality-gate]
    related_skills: [session-journal, source-drift-review, hermes-agent]
---

# 在 HermesUsage 仓库里写一课

## 何时用

当你要在这个仓库里**新增、改写、翻译、校订一门课程**，或者用户说
“补一课 / 更新课程 / 同步官方文档”时。

## 铁律（先记住这四条，其余都是细节）

1. **不凭记忆写 Hermes 的行为。** 先读 `sources/cache/<id>.md`（官方文档快照），
   或者直接读 `$HERMES_HOME/hermes-agent/website/docs/` 下的原文。
2. **每个事实性断言后面跟 `[[src:<id>]]`**，且该 id 必须同时出现在
   frontmatter 的 `sources:` 与文末 `## 出处`。三处不一致 = 门禁失败。
3. **先动手，后原理。** `## 先动手` 必须 3 分钟内跑出可见结果。
4. **没跑 `python scripts/verify.py` 且全绿的改动，不算改完。**

## 步骤

### 1. 定位主题对应的官方来源

```bash
# 已有登记来源里找
grep -n "<关键词>" sources/registry.yaml
# 官方文档全量索引（一份文件看全部页面）
grep -n "<关键词>" "$HERMES_HOME/hermes-agent/website/docs/../" 2>/dev/null
# 或者直接看官方索引页
# https://hermes-agent.nousresearch.com/docs/llms.txt
```

找不到合适来源时，在 `sources/registry.yaml` 里按分组登记一行：

```yaml
core:
  <新id>: user-guide/features/<页面>.md     # 相对 website/docs/ 的路径
```

然后刷新快照（会自动回填 URL、版本、sha256）：

```bash
python scripts/sync_sources.py
python scripts/sync_sources.py --list-missing   # 确认路径没写错
```

### 2. 复制模板

```bash
cp templates/lesson.md lessons/<阶段目录>/<ID>-<slug>.md
```

阶段目录与 ID 前缀的对应（阶段目录名不要自创）：

| 阶段 | 目录 | ID |
|---|---|---|
| 0 认识 | `lessons/00-orient/` | L00–L0x |
| 1 会用 | `lessons/01-core/` | L10–L1x |
| 2 日常威力 | `lessons/02-workflow/` | L20–L2x |
| 3 自动化 | `lessons/03-automation/` | L30–L3x |
| 4 扩展 | `lessons/04-extend/` | L40–L4x |
| 5 运维 | `lessons/05-ops/` | L50–L5x |
| 6 真实工作流案例 | `lessons/06-realwork/` | L60–L6x |
| 毕业项目 | `lessons/06-capstone/` | L90+ |

### 3. 填 frontmatter

必填九项：`id, title, stage, level, minutes, prereq, tags, sources, updated`。
`level` 只能是 `入门` 或 `进阶`；`minutes` 是你实测的阅读+动手时间，别拍脑袋写 5。

### 4. 写正文的 8 节

顺序固定：`你将学会` → `先动手` → `原理` → `亲手验证` → `常见坑` → `试一试` → `下一步` → `出处`。

各节的判据：

| 小节 | 判据（达不到就别提交） |
|---|---|
| 你将学会 | 每条都是「动词 + 可验证结果」，不写“了解/熟悉/掌握” |
| 先动手 | 复制粘贴一条命令就能看到东西；附真实输出片段 |
| 原理 | 读者不动手、只读这一节，也能向别人解释这个机制 |
| 亲手验证 | 让读者主动制造一次**失败或边界情况**并观察反应 |
| 常见坑 | 表格：现象（照抄报错原文） / 真实原因 / 解决命令 |
| 试一试 | 可自我判断对错的练习，至少一条 |
| 下一步 | 用 `[[Lxx]]` 交叉引用（会被门禁校验是否存在） |
| 出处 | 列出 `[[src:id]]` + 标题 + 可点击官方 URL |

### 5. 通过门禁

```bash
python scripts/build_index.py    # 新增课程必须重建索引
python scripts/verify.py         # 全绿才算完
python scripts/verify.py --fix-hint
```

### 5.5 顺带确认站点能重建

课程是站点唯一的内容源，改完课必须确认站点还能编译：

```bash
python scripts/build_site.py     # 期望：站点自检通过：32 课 / 40 页 / 52 文件
```

站点源码在 `web/`（模板与前端），产物在 `site/`（gitignore，别手改）。
出处标记、交叉引用、仓库内相对链接写错时，构建会直接失败并指出是哪一课。

### 6. 归档并提交

```bash
python scripts/journal.py commit --kind docs --title "新增 L2x <标题>" \
    --scope L2x --summary "新增一课：<一句话>" --learned "<这次学到的 Hermes 事实>"
```

## 坑

- **`sources/cache/` 和 `citations.yaml` 是自动生成的**，手改会被门禁的哈希校验抓到。
  要更新内容就重跑 `sync_sources.py`。
- **引用 id 拼错**是最常见的失败：门禁会报“引用了未登记的出处”，跑一次
  `python scripts/verify.py` 就知道是哪个。
- **课程里写 `hermes chat -q` 的例子必须带 `--in <目录>`**：实测它的工作目录**不是**你 shell 的
  当前目录（`terminal.cwd: .` 是相对**会话基目录**解析的，`-q` 还会沿用/恢复会话记录的目录），
  不加 `--in` 时 agent 在用户主目录里跑 —— 贴进课程的输出会与实际不符。`--no-restore-cwd` 实测不够。
- **Windows 写文件**：Python 里必须 `encoding="utf-8"` + `newline="\n"`，
  否则 BOM/CRLF 触发 R11。
- **不要占位**：写不完的课不要建文件，在 `ROADMAP.md` 里标 `⬜` 待建即可。
- **`site/` 是产物，不是源码**：要么改 `lessons/`，要么改 `web/`；
  手改 `site/` 会在下次构建时丢失。
- **练习（`- [ ]`）只许在末尾追加**：站点按课内位置给练习编号（`data-ex`）来存读者的打勾，
  在中间插删或重排会让读者已做的勾错位到别的题上（静默错，不报错）。
- **练习一律写 `- [ ]`，不要用 `- [x]`**：站点会用读者的本地存储覆盖初始勾选状态，
  预勾等于给读者一个会被抹掉的假状态。
- **官方文档更新了、快照却还没刷**：`sync_sources.py --check` 报漂移时**不要直接 sync 了事** ——
  上游 main 常常在写未发布内容。按 `source-drift-review` 技能逐页定版（判据：本机装的版本有没有
  这个行为），再决定改课还是只登记。
- 官方文档页面的**路径与 llms.txt 里的 URL 一一对应**，但 `index.md` 的 URL 是目录本身
  （`/docs/user-guide/messaging` 而不是 `.../messaging/index`）——`sync_sources.py` 已处理。
