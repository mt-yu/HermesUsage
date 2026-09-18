---
name: source-drift-review
description: "Use when the docs-drift sentinel reports drift in the HermesUsage repo (sync_sources.py --check fails, or issue titled 官方文档漂移 exists). Classify each drifted page as released vs unreleased against the local Hermes source, then fix lessons or record."
version: 1.0.0
author: HermesUsage
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [citations, drift, official-docs, triage, quality-gate]
    related_skills: [hermes-tutorial-authoring, session-journal, hermes-agent]
---

# 官方文档漂移复核（sources 快照 vs 上游）

## 何时用

`python scripts/sync_sources.py --check` 报漂移、本机/CI 的「漂移哨兵」开了 issue、或者用户说
“官方文档更新了 / 快照要不要重刷 / issue #N 的漂移怎么处理”。

## 铁律（先记住这三条）

1. **定版判据只有一个：那个行为在「本机装的那个 Hermes 版本」的源码里有没有。**
   有 → 快照过时，改课程；没有 → 上游在写**未发布**内容，只登记，别写进课程（R3 要求可考证到
   读者装得到的版本）。
2. **两套哨兵比的对象不同，别混**：本机 cron 的 `drift_watch.py` 比「**本机装的** Hermes 源码 vs
   快照」（所以本机不升级就永远报无漂移）；CI 的 `.github/workflows/drift.yml` 比「**上游** docs
   vs 快照」（上游 main 永远领先于最新 release，所以几乎总会报漂移）。
3. **否定断言优先复核**。课程里「没有 X / 不会 Y / 只存在于 Z」这类句子最容易过时 —— 新代码往这些
   句子上加条件时，句子本身不会被门禁抓住。实测一次命中两处（L22「默认没有墙钟超时」、
   L32「`message_agent` 只存在于 Bot Chat 会话里」）。

## 步骤

### 1. 先看本机版本是不是最新 release

```bash
hermes --version    # Hermes Agent v0.21.3 (2026.9.14) · upstream <sha> · local <sha> (+N carried commits)
```

`local <sha>` 应等于 `sources/citations.yaml` 头部的文档提交。再用 GitHub API 确认它是不是最新
release（`repos/NousResearch/hermes-agent/releases/latest`）。**不是**最新 release 时，上游文档里
有一大堆你还没装上的内容，本次复核只能「登记 + 等下一次 release 对照」。

### 2. 稀疏克隆上游 docs（不要全克隆）

```bash
cd "$LOCALAPPDATA/Temp" && rm -rf hermes-docs-probe
git clone --depth 1 --filter=blob:none --sparse https://github.com/NousResearch/hermes-agent.git hermes-docs-probe
git -C hermes-docs-probe sparse-checkout set website/docs
git -C hermes-docs-probe rev-parse HEAD      # 记下这个 sha，写进 ROADMAP 与 issue 评论
```

### 3. 生成「逐页 diff + 这页被哪些课引用」

按 LF 归一化算 `sha256`（与 `sync_sources.py` 同口径），与 `sources/cache/<id>.md` 做
`difflib.unified_diff`，并从每课正文里正则抓 `[[src:...]]` 反向建映射。产物写到
`$LOCALAPPDATA/Temp/hermes-drift-review/`（**不进仓库**），按每块约 90 个变更行切片读，
避免一次灌爆上下文。分类时只读 `n=0` 的变更行就够。

### 4. 逐页定版（三种探针，按代价从低到高）

```bash
cd "$LOCALAPPDATA/hermes/hermes-agent"      # 本机安装树
# ① 存在性：有没有这个常量/键（0 命中 = 未发布）
rg -l --no-messages -g '!tests/**' -g '!*.md' -- "fake_ip_ranges" .
# ② 语义：看上下文，别只看命中（注释里常写着阈值与设计）
rg -n -A4 "bot_mode_protocol" agent/agent_init.py
# ③ A/B 实测：能直接调的纯函数用临时 HERMES_HOME 跑一次（最强证据）
python -c "import sys,os; sys.path.insert(0,os.getcwd()); from tools.bot_mode_probe import is_bot_mode_managed; print(is_bot_mode_managed('<临时 home>'))"
```

拿不准就按「未发布」登记 —— 反过来（未发布的写成已发布）会让课程指着一句读者装不到的行为。

### 5. 三类处置

| 桶 | 动作 |
|---|---|
| 与本机行为不符 | 改课程：改正文 + 把 frontmatter `updated` 改成今天 → `python scripts/check.py` → journal 提交 |
| 判定为上游未发布 | 不改课程，登记到 `ROADMAP.md` 的「官方文档漂移复核」小节（写清判据与本机证据），等下一个 release 再对照 |
| 已发布但课程未涉及 / 纯措辞 | 不用动课程；若值得讲，另开一课的待办，别顺手塞进本次复核 |

### 6. 收口

- `ROADMAP.md`「官方文档漂移复核（<日期> 首次）」小节：三分桶表格 + 诚实边界（哪些页只做了
  「课程是否涉及」的检查、没逐句定版）+ 重放方法。
- issue 评论分类结论后**手动关闭**（漂移哨兵只保证开一次，不会替你关）。
- `python scripts/check.py` 全绿 → `python scripts/journal.py commit --kind session ...` → push。

## 坑

- **别用 `search_files` 工具扫本机安装树**：命中目录里的 `AGENTS.md` 会被当成子目录提示注入上下文
  （实测一次灌进两份长 AGENTS.md）。用 `terminal` 里的 `rg`，并加 `-g '!tests/**'`。
- **别读 `$HERMES_HOME/hermes-agent/` 下的文档**当出处：那是安装树，不是快照；课程一律引
  `sources/cache/<id>.md`。
- 临时克隆/报告放 `$LOCALAPPDATA/Temp/` 并在收尾时删掉；仓库里只留 `ROADMAP` 的结论。
- 判据要写进记录：复核结论本身也要可考证（本机版本号 + 源码 `路径:行号` + 上游 sha），
  否则下一次复核无法判断上次为什么这么定。
- 改完课程记得同步 `updated` 字段并跑 `check.py`；只跑 `verify.py` 不足以覆盖站点与前端测试。
