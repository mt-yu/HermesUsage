---
name: session-journal
description: "Use when wrapping up a work session or a stage in a project: summarize what happened and commit it as a resumable, revertable journal entry."
version: 1.0.0
author: HermesUsage
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [git, journal, session-summary, rollback, workflow]
    related_skills: [hermes-tutorial-authoring, hermes-agent]
---

# 会话/阶段归档：把“这段对话干了什么”变成一次可回滚的提交

## 何时用

- 一段对话结束、一个阶段完成、一次修复落地时；
- 用户说“总结一下”“提交一下”“记一下这次做的事”；
- 你自己判断“再往下做就该先存档了”（比如刚完成一个可独立验收的成果）。

**判据**：改动构成一个**可独立回滚的语义单元**时就归档。宁可多切几次，不要攒成一大坨。

## 核心动作（一条命令）

```bash
python scripts/journal.py commit \
    --kind session \
    --title "补完阶段2 日常威力（6课）" \
    --scope L20,L21,L22 \
    --summary "- 新增 3 课；修正 L20 的 frontmatter
- verify.py 全绿" \
    --learned "- state.db 里 sessions.cwd 能定位到本项目；tool_names 是 JSON 数组
- journal.py 建完文件后会用 --amend 把 journal 文件补进同一个提交"
```

它做四件事：① 建 `journal/<日期>-<序号>-<标题>.md`（套模板）② 更新
`journal/INDEX.md` 倒序索引 ③ `git add -A && git commit` ④ 把 journal 文件 amend 进同一提交。

### 带真实会话数据

```bash
python scripts/journal.py commit --kind session --title "..." --with-session-digest
```

`--with-session-digest` 会从 `$HERMES_HOME/state.db` 只读拉取**本仓库路径下**最近的
Hermes 会话（标题/消息数/工具调用数/token），避免了“凭印象写总结”。

### 只看看，不提交

```bash
python scripts/journal.py digest --hours 24
python scripts/journal.py log
python scripts/journal.py rollback --list
```

## 提交信息规范

`<kind>: <标题>`，kind 取 `session` / `stage` / `fix` / `docs` / `release`（journal.py 自动加前缀）。
正文自动带上 `scope:` 和 `journal:` 两行，方便 `git log --grep` 反查：

```bash
git log --grep "scope: L2" --oneline
git log --oneline -- journal/
```

## 阶段收尾要额外打 tag

```bash
git tag -a v0.2-workflow -m "阶段2 完成：日常威力 6 课"
git tag --sort=-creatordate
```

## 回滚

```bash
git checkout <sha> -- lessons/02-workflow/L20-xxx.md   # 只回滚一个文件
git revert <sha>                                        # 安全回退一次提交（保留历史）
git checkout <sha>                                      # 整体回到过去（用 git switch - 回来）
```

**不要**用 `git reset --hard` 或 force push 重写已归档的历史 —— 那会让 journal 里记录的
commit 号失效，而 journal 的价值就在于“每个记录都还能找回来”。

## 坑

- 提交失败常见原因：仓库没有 git identity。设一次即可
  （`git config user.name` / `git config user.email`），或让用户决定用哪个身份。
- 不要在没有改动时强行 `--allow-empty` 归档；没干活就别留journal噪音。
- `--scope` 里的课程 id 用逗号分隔且不加空格，便于 `--grep` 精确命中。
