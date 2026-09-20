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

1. **定版判据只有一个：那个行为在「读者装得到的那个版本」的源码里有没有。**
   有 → 快照过时，改课程；没有 → 上游在写**未发布**内容，只登记，别写进课程（R3 要求可考证到
   读者装得到的版本）。**判据是「最新 release」，不是「本机源码」**：本机安装树可能跟踪 main
   （比 release 新几天到几周），这时「本机有」根本不能当判据 —— 会把未发布行为写进课程。
   实测（2026-09-20）：本机跟踪 main 时按「本机有」判定，20 处改动里有 14 条属于未发布，只能全部回滚。
   所以**先跑 `hermes --version` 看本机跟的是 release 还是 main**，再决定拿谁当判据；拿不准就按
   release tag 取原始文件验证（第 4 步的 ⓪ 号探针），或直接按「未发布」登记。
2. **两套哨兵比的对象不同，别混**：本机 cron 的 `drift_watch.py` 比「**本机装的** Hermes 源码 vs
   快照」（所以本机不升级就永远报无漂移）；CI 的 `.github/workflows/drift.yml` 比「**上游** docs
   vs 快照」（上游 main 永远领先于最新 release，所以几乎总会报漂移）。
3. **否定断言优先复核**。课程里「没有 X / 不会 Y / 只存在于 Z」这类句子最容易过时 —— 新代码往这些
   句子上加条件时，句子本身不会被门禁抓住。实测一次命中两处（L22「默认没有墙钟超时」、
   L32「`message_agent` 只存在于 Bot Chat 会话里」）。
4. **先剥掉「链接重写」再看 diff，否则 86 页漂移里有 27 页是噪音**。上游会把文档间链接从
   `](/user-guide/x)` 批量改成 `](../user-guide/x.md)`，这种改动只动链接目标、与课程无关。
   做法：每行的 `](...)` 归一化成 `](L)`（顺带 `href="..."`）之后再 diff，只有归一化后仍然不同的行
   才算「正文真变化」。实测（2026-09-20）：86 页漂移 = 27 页纯链接 + 59 页真变化。
5. **别一次应用再回滚**。改课之前逐条跑 ⓪ 号探针确认「这个 tag 里有」；先应用 20 处、再逐条核验、
   最后全部回滚是纯浪费（2026-09-20 真踩过）。

## 步骤

### 1. 先确认本机跟的是 release 还是 main

```bash
hermes --version     # v0.21.3 (2026.9.14) · upstream <sha>；还会打印「Update available: N commits behind」
git -C "$LOCALAPPDATA/hermes/hermes-agent" log -1 --format='%h %ad' -- website/docs   # 本机文档树走到哪
```

再用 GitHub API 取最新 release（`repos/NousResearch/hermes-agent/releases/latest`，本机是
`v2026.9.14` / 0.21.3）。

- 本机文档提交**等于** release 的文档提交 → 判据可以用本机源码（2026-09-17 首次复核就是这种状态）。
- 本机**领先** release（跟踪 main；本机树的 `website/docs` 提交比 release tag 新）→ **判据必须换成
  release tag**，按第 4 步的 ⓪ 号探针逐条验；「本机有、tag 里没有」的一律按未发布登记
  （2026-09-20 第二次复核就是这种状态：本机 main 比 release 新，20 处按「本机有」改的课程里 14 条要回滚）。

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

### 4. 逐页定版（四种探针，按代价从低到高）

```bash
# ⓪ 「这个 tag 里到底有没有」—— 判据探针，改课之前必须跑（本机没装 release 的树也能跑）
curl -s --noproxy '*' --max-time 60 \
  https://raw.githubusercontent.com/NousResearch/hermes-agent/v2026.9.14/hermes_cli/config_defaults.py \
  | grep -n 'failure_repeat_alert_hours'     # 0 命中 = release 里没有 → 按「未发布」登记
# 文档侧同理：**别拿快照当 release 文档** —— 快照取自主机安装树（跟踪 main），实测 95 页里
# 有 48 页比 v2026.9.14 的文档多出正文。要比 release 的文档就按 tag 取那一页：
#   curl -s --noproxy '*' --max-time 60 \
#     https://raw.githubusercontent.com/NousResearch/hermes-agent/v2026.9.14/website/docs/<rel> \
#     | diff - sources/cache/<id>.md
#   （`python scripts/release_probe.py --docs` 会一次性把 95 页全比一遍）

cd "$LOCALAPPDATA/hermes/hermes-agent"      # 本机安装树（先按第 1 步确认它跟的是 release 还是 main）
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

- `ROADMAP.md`「官方文档漂移复核（<日期> 第 N 次）」小节：三分桶表格 + **逐条列出待下一个 release
  对照的项**（页面 / 上游写了什么 / 你的 release 探针结果）+ 诚实边界 + 重放方法。
- **本机跟踪 main 时不要跑 `sync_sources.py`**：它读的是本机安装树，会把「未发布」的文档内容变成课程
  出处（违反 R3）。基线继续钉在 release 态，等下一个 release 出来再一次性刷快照 + 改课；漂移哨兵继续
  报是预期行为，在 ROADMAP 里写明理由即可。
- issue 评论分类结论后**手动关闭**（漂移哨兵只保证开一次，不会替你关）。
- `python scripts/check.py` 全绿 → `python scripts/journal.py commit --kind session ...` → push。

## 坑

- **别用 `search_files` 工具扫本机安装树**：命中目录里的 `AGENTS.md` 会被当成子目录提示注入上下文
  （实测一次灌进两份长 AGENTS.md）。用 `terminal` 里的 `rg`，并加 `-g '!tests/**'`。
- **别读 `$HERMES_HOME/hermes-agent/` 下的文档**当出处：那是安装树，不是快照；课程一律引
  `sources/cache/<id>.md`。
- 临时克隆/报告放 `$LOCALAPPDATA/Temp/` 并在收尾时删掉；仓库里只留 `ROADMAP` 的结论。
- 判据要写进记录：复核结论本身也要可考证（本机版本号 + 源码 `路径:行号` + 上游 sha），
  否则下一次复核无法判断上次为什么这么定。**本机跟的是 release 还是 main 必须一起写**。
- **别把「grep 0 命中」直接当成「未发布」**：文件可能在这个 tag 上压根不存在（模块是后来加的）或
  只是改了名字。先用 API 的 contents 端点确认文件存在（`?ref=<tag>`，看 HTTP 200/404），再多试几组
  候选词；确认「存在但 0 命中」才下结论。
- **别 grep `apps/desktop/dist/**`、`*.js`、`.asar` 这类打包产物**：压缩过的单文件一行几十万字符，
  实测一次搜索把输出灌到 65 KB 还超时。要查桌面端的字符串就限定 `--include="*.ts" --include="*.md"`。
- 改完课程记得同步 `updated` 字段并跑 `check.py`；只跑 `verify.py` 不足以覆盖站点与前端测试。
