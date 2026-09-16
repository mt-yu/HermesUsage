# 贡献指南（人和 AI 用同一套流程）

本仓库的维护者既可能是人，也可能是 AI agent（Hermes / Claude Code / Codex …）。
所以流程写成**可执行的命令**，而不是“请注意规范”。

## 0. 一分钟速览

```bash
# 改内容
$EDITOR lessons/02-core/L21-xxx.md      # 或新建：cp templates/lesson.md lessons/...

# 自检（必须全绿）
python scripts/build_index.py            # 重建 llms.txt（AI 的导航入口）
python scripts/build_map.py              # 重建 docs/learning-map.html（学习者的可视化地图）
python scripts/verify.py                 # 11 条硬规则，0 错误才算完

# 归档并提交（自动写 journal + commit）
python scripts/journal.py commit --kind docs --title "新增 L21" --scope L21 \
    --summary "..." --learned "..."
```

## 1. 内容规范（写死在门禁里）

11 条硬规则由 [`scripts/verify.py`](scripts/verify.py) 执行，详细说明在
[`.hermes.md`](.hermes.md)。最容易踩的四条：

1. **8 个小节缺一不可**：你将学会 / 先动手 / 原理 / 亲手验证 / 常见坑 / 试一试 / 下一步 / 出处。
2. **引用三方绑定**：正文 `[[src:id]]` ⟷ frontmatter `sources:` ⟷ 文末 `## 出处`，必须完全一致。
3. **不凭记忆写 Hermes 的行为**。先读 `sources/cache/<id>.md`（官方文档快照）。
4. **编码 UTF-8 无 BOM + LF**。Windows 上用 Python 写文件要显式 `encoding="utf-8"`、`newline="\n"`。

## 2. 新增一课的标准流程

```bash
# ① 找/登记出处
grep -n "<关键词>" sources/registry.yaml
#   没有合适来源就在 registry.yaml 里加一行（id -> website/docs 下的相对路径）
python scripts/sync_sources.py && python scripts/sync_sources.py --list-missing

# ② 建文件
cp templates/lesson.md lessons/02-core/L21-do-something-real.md

# ③ 写（照模板的 8 小节；frontmatter 九项必填）

# ④ 门禁
python scripts/build_index.py && python scripts/verify.py

# ⑤ 归档
python scripts/journal.py commit --kind docs --title "新增 L21 ..." --scope L21
```

## 3. 更新官方文档快照

```bash
python scripts/sync_sources.py --check   # 先看有没有漂移
python scripts/sync_sources.py           # 有漂移则刷新快照（会带新 commit 与 sha256）
python scripts/verify.py                 # 快照哈希与 citations.yaml 必须一致
```

**不要手改 `sources/cache/` 里任何一个字节**。那是别人项目的原文，手改会破坏可考证性，
门禁会直接报错。

## 4. git 工作流

| 场景 | 命令 |
|---|---|
| 一次对话收尾 | `python scripts/journal.py commit --kind session --title "..." --with-session-digest` |
| 一个阶段完成 | `python scripts/journal.py commit --kind stage --title "..." --scope L00,L01` 然后 `git tag -a v0.2-orient -m "..."` |
| 只想看看做了什么 | `python scripts/journal.py log` / `python scripts/journal.py digest` |
| 回滚一个文件 | `git checkout <sha> -- lessons/xx/Lyy-*.md` |
| 安全回退一次提交 | `git revert <sha>` |
| 回到过去看看 | `git checkout <sha>`（回来用 `git switch -`） |

规则：

- 提交粒度 = **一个可独立回滚的语义单元**。宁可多切几次。
- commit message 前缀：`session:` / `stage:` / `docs:` / `fix:` / `release:`（journal.py 自动加）。
- 已归档的历史**不要**用 `git reset --hard` 或 force push 改写 —— journal 里记录的 commit 号会失效。
- 每次阶段完成必须打 tag。

## 5. 给 AI 维护者的入口

1. 读 [`.hermes.md`](.hermes.md)（Hermes 会自动注入，其他 agent 请手动读）。
2. 读本文件 + [`ROADMAP.md`](ROADMAP.md) 找 `⬜` 的工作队列。
3. `python scripts/verify.py` 确认当前状态健康，再动手。
4. 项目技能 [`.hermes/skills/`](.hermes/skills/) 里有两份可加载的操作手册：
   - `hermes-tutorial-authoring` —— 怎么写一课
   - `session-journal` —— 怎么归档一次会话
   安装：`hermes skills trust .`（项目级技能默认不加载，防投毒）
5. 不确定 Hermes 的行为时，优先查这三处（权威性从高到低）：
   `hermes <command> --help` → `sources/cache/` → `$HERMES_HOME/hermes-agent/website/docs/`。

## 6. 提交前自查清单

- [ ] `python scripts/verify.py` 输出“通过”，0 错误
- [ ] 新增课程已出现在 `llms.txt` 与 `ROADMAP.md`
- [ ] 所有命令我自己跑过，预期输出是**真实**输出
- [ ] 出处链接可点开，且与 `sources/cache/` 内容一致
- [ ] `python scripts/journal.py commit ...` 已归档
