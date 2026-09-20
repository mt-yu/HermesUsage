#!/usr/bin/env python3
"""scripts/journal.py —— 把“每个对话/每个阶段”自动变成一次可回滚的 git 提交。

设计目标
--------
1. **零记忆负担**：会话结束时不需要自己想“我改了啥”，跑一条命令就归档。
2. **可考证**：归档内容来自 Hermes 自己的会话数据库（state.db），不是凭印象写的。
3. **可回滚**：每次归档 = 一个独立 commit，配合 tag 形成一条能倒着走回去的路。
4. **AI 友好**：参数全部显式，无交互提示，适合 agent 直接调用（见 CONTRIBUTING.md）。

三个动作
--------
  digest   只读 Hermes 会话库，生成本仓库相关的会话摘要（不提交）
  new      新建一条 journal 记录（可带正文），更新 journal/INDEX.md
  commit   new + git add -A + git commit，一步完成“总结并提交”

常用姿势
--------
  # 阶段收尾：写总结 + 提交 + 打 tag
  python scripts/journal.py commit --kind stage --scope L00,L01 --title "阶段0 认识 Hermes" \
      --summary "新增 4 课；建立出处体系" --learned "官方文档源码在本机 website/docs，可离线核对"

  # 对话收尾：把本次 Hermes 会话摘要一起写进去
  python scripts/journal.py commit --kind session --title "补 3 门进阶课" --with-session-digest

  # 只想看看这次会话发生了啥
  python scripts/journal.py digest

  # 回滚（这是纯 git 操作，脚本只帮你查）
  python scripts/journal.py rollback --list
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JOURNAL = REPO / "journal"
INDEX = JOURNAL / "INDEX.md"
TEMPLATE = REPO / "templates" / "journal.md"
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE_DB = HERMES_HOME / "state.db"

KINDS = ("session", "stage", "fix", "docs", "release")


# --------------------------------------------------------------------------- 工具

def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """跑一条命令并把 cwd 默认设为仓库根。

    cwd 必须**可被调用方覆盖**（`kw.setdefault`）：写成 `subprocess.run(cwd=REPO, **kw)`
    时，任何调用方再传 cwd 都会 TypeError —— 实测踩过（闸门在真仓库上一跑就崩，
    而 mock 掉 run 的单元测试完全看不见）。
    """
    kw.setdefault("cwd", REPO)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", **kw)


def now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def slugify(text: str, maxlen: int = 40) -> str:
    """中文标题也要能进文件名：去掉路径非法字符，保留中文。"""
    s = re.sub(r"[\\/:*?\"<>|\s]+", "-", text.strip())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen] or "entry"


def next_seq(day: str) -> int:
    seqs = [int(m.group(1)) for p in JOURNAL.glob(f"{day}-[0-9][0-9]-*.md")
            if (m := re.match(rf"{day}-(\d{{2}})-", p.name))]
    return (max(seqs) + 1) if seqs else 1


# --------------------------------------------------------------------------- 会话摘要

def session_digest(hours: int = 72, limit: int = 12) -> tuple[str, dict]:
    """从 Hermes state.db 读出与本仓库相关的会话，生成确定性摘要（不做 LLM 概括）。"""
    if not STATE_DB.is_file():
        return ("（未找到 Hermes 会话库，跳过）", {"sessions": 0, "messages": 0})

    repo_key = str(REPO).replace("\\", "/").lower()
    rows: list[tuple] = []
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=8)
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, COALESCE(title,'(无标题)'), source, COALESCE(cwd,''),
                   COALESCE(started_at,0), COALESCE(message_count,0),
                   COALESCE(tool_call_count,0), COALESCE(model,''),
                   COALESCE(input_tokens,0), COALESCE(output_tokens,0),
                   COALESCE(cache_read_tokens,0), COALESCE(tool_names,'')
            FROM sessions
            WHERE lower(replace(COALESCE(cwd,''),'\\','/')) LIKE ?
              AND COALESCE(started_at,0) > strftime('%s','now') - ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (f"%{repo_key}%", hours * 3600, limit),
        )
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error as e:
        return (f"（读取会话库失败：{e}）", {"sessions": 0, "messages": 0})

    if not rows:
        return (f"（最近 {hours} 小时内本仓库没有 Hermes 会话记录）", {"sessions": 0, "messages": 0})

    stats = {
        "sessions": len(rows),
        "messages": sum(r[5] for r in rows),
        "tool_calls": sum(r[6] for r in rows),
        "in_tokens": sum(r[8] for r in rows),
        "out_tokens": sum(r[9] for r in rows),
        "cache_read": sum(r[10] for r in rows),
    }

    lines = [
        f"| 时间 | 会话 | 来源 | 消息 | 工具调用 | 输入/输出 token |",
        "|---|---|---|---:|---:|---|",
    ]
    for r in rows:
        ts = datetime.fromtimestamp(r[4]).astimezone().strftime("%m-%d %H:%M") if r[4] else "—"
        title = r[1].replace("|", "／")[:40]
        lines.append(f"| {ts} | {title} | {r[2]} | {r[5]} | {r[6]} | {r[8]:,}/{r[9]:,} |")

    tools: dict[str, int] = {}
    for r in rows:
        try:
            for t in json.loads(r[11] or "[]"):
                tools[str(t)] = tools.get(str(t), 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_tools = "、".join(f"{k}({v})" for k, v in sorted(tools.items(), key=lambda x: -x[1])[:10])

    return ("\n".join(lines), stats | {"top_tools": top_tools})


# --------------------------------------------------------------------------- journal 文件

def write_entry(kind: str, title: str, scope: str, summary: str, learned: str,
                extra: str = "", do_commit: bool = False, message: str | None = None) -> Path:
    """写一条 journal 记录；do_commit 时额外把它提交成一个独立提交。

    两段式提交（这是关键设计）
    --------------------------
    记录里要写“这次工作的提交号”，可是提交号在提交之前不存在。用 --amend 回填
    会让 SHA 再次变化，形成追不上的循环。所以：

      提交 1 = 工作提交（不含 journal 文件）   -> 得到真实 SHA
      journal 文件里写 提交 1 的 SHA
      提交 2 = 只包含 journal 文件与索引       -> 历史干净、引用准确

    语义也更对：一条 journal 说的是“它前面那个工作提交干了什么”。
    """
    JOURNAL.mkdir(exist_ok=True)
    stamp = now()
    day = stamp.strftime("%Y-%m-%d")
    path = JOURNAL / f"{day}-{next_seq(day):02d}-{slugify(title)}.md"
    rel = path.relative_to(REPO)

    work_sha = ""
    if do_commit:
        # 先提交工作内容，把新的 journal 文件排除在外
        run(["git", "add", "-A"])
        run(["git", "reset", "-q", "--", str(rel)])
        msg = message or f"{kind}: {title}"
        res = run(["git", "commit", "-m", msg, "-m",
                   f"scope: {scope or '—'}\njournal: {path.name}\n\n由 scripts/journal.py 归档。"])
        if res.returncode == 0:
            work_sha = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
        else:
            head = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
            if "nothing to commit" in (res.stdout + res.stderr):
                work_sha = head
                print(f"  · 没有新的工作改动，记录指向当前提交 {head}")
            else:
                print("  [!] git commit 失败：")
                print("      " + (res.stderr or res.stdout).strip().replace("\n", "\n      "))
                print("      常见原因：未配置 git user.name/user.email。")
                return path

    body = render_entry(title, kind, scope, summary, learned, extra, day, work_sha)
    path.write_text(body, encoding="utf-8", newline="\n")
    append_index(path, kind, scope, title, work_sha)
    print(f"journal 记录：{rel}")

    if do_commit:
        run(["git", "add", str(rel), str(INDEX.relative_to(REPO))])
        res = run(["git", "commit", "-m", f"journal: {title}",
                   "-m", f"范围: {scope or '—'}\n描述工作提交: {work_sha or '—'}"])
        if res.returncode == 0:
            print("已提交：")
            print(run(["git", "log", "--oneline", "-3"]).stdout)
        else:
            print("  [!] journal 提交失败：" + (res.stderr or res.stdout).strip())
    return path


def render_entry(title: str, kind: str, scope: str, summary: str, learned: str,
                 extra: str, day: str, work_sha: str) -> str:
    body = TEMPLATE.read_text(encoding="utf-8") if TEMPLATE.exists() else DEFAULT_ENTRY
    body = body.replace("2026-01-01", day)
    body = body.replace("一句话说明本次会话干了什么", title)
    body = body.replace("kind: session", f"kind: {kind}")
    body = body.replace("scope: L00", f"scope: {scope or '—'}")
    body = body.replace("commit: (由 scripts/journal.py 自动回填)",
                        f"commit: {work_sha or '(工作区无改动)'}")
    if summary:
        # 别把 summary 插进替换串：它会和前面的 \1 粘成 \186 这种非法组引用
        # （实测：summary 以数字开头时报 "invalid group reference 18"）。用函数式替换。
        body = re.sub(r"(## 实际做了什么\n\n)(?:.*?)(\n## )",
                      lambda m: m.group(1) + summary + "\n" + m.group(2),
                      body, flags=re.S)
    if learned:
        body = re.sub(r"(> 什么踩坑了、什么反直觉、哪条命令救了我。\n\n)(?:.*?)(\n## )",
                      lambda m: m.group(1) + learned + "\n" + m.group(2),
                      body, flags=re.S)
    if extra:
        body = body.replace("## 下一步", f"{extra}\n\n## 下一步")
    return body


DEFAULT_ENTRY = """---
date: 2026-01-01
kind: session
scope: L00
title: 一句话说明本次会话干了什么
commit: (由 scripts/journal.py 自动回填)
---

# 2026-01-01 · 一句话说明本次会话干了什么

## 实际做了什么

## 学到的东西

## 下一步
"""


def append_index(path: Path, kind: str, scope: str, title: str, sha: str) -> None:
    header = (
        "# Journal 索引\n\n"
        "> 每次对话 / 每个阶段的自我总结。**倒序排列，最新的在最上面。**\n"
        "> 这是回滚时的作战地图：先在这里找到“改坏之前那一次”，再按文件里的回滚指引操作。\n\n"
        "| 日期 | 类型 | 范围 | 标题 | 提交 |\n|---|---|---|---|---|\n"
    )
    if INDEX.exists():
        content = INDEX.read_text(encoding="utf-8")
        rows = [ln for ln in content.splitlines() if ln.startswith("| ") and not ln.startswith("| 日期")]
    else:
        rows = []
    entry = f"| {path.stem[:10]} | {kind} | {scope or '—'} | [{title}]({path.name}) | `{sha or '—'}` |"
    rows.insert(0, entry)
    INDEX.write_text(header + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- 回滚辅助

def rollback_list() -> None:
    print("== 最近的提交（回滚目标） ==")
    print(run(["git", "log", "--oneline", "--decorate", "-20"]).stdout)
    print("== tag（里程碑） ==")
    print(run(["git", "tag", "--sort=-creatordate"]).stdout or "（还没有 tag）")
    print(
        "回滚姿势：\n"
        "  只回滚某个文件  git checkout <sha> -- path/to/file\n"
        "  安全回退一次提交 git revert <sha>\n"
        "  完全回到过去    git checkout <sha>   （看完记得 git switch - 回来）\n"
        "  打里程碑        git tag -a v0.2 -m '阶段1完成' && git push --tags\n"
    )


# --------------------------------------------------------------------------- main

# --- 自动归档的闸门：别把「在途改动」卷进自动提交 ---------------------------
# 实测踩过 4 次（2026-09-16/17）：cron 的小时级自动归档见到什么就提交什么，
# 于是子代理写到一半的课/脚本被卷进一个 `session:` 提交 —— 历史里多出
# 「未验收状态」的提交，而人精心写的那条信息反而落不了地。
# 两道判据都很便宜，任一命中就静默跳过这一轮（下次 tick 再来）。
IN_FLIGHT_GRACE_S = 120          # 文件刚被改过多少秒内视为「有人正在写」
MANIFEST_STALE_S = 6 * 3600      # manifest 这么久还没收工就视为残留，不再阻塞
TERMINAL_TASK_STATUS = {"completed", "failed", "stopped", "cancelled"}


def hermes_home() -> Path:
    """$HERMES_HOME 优先，否则按平台默认（Windows 是 %LOCALAPPDATA%\\hermes）。"""
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "hermes"
    return Path.home() / ".hermes"


def changed_paths(repo: Path | None = None) -> list[str]:
    """工作区变化的路径（用 `-z` 输出，中文与空格路径不会被 git 加引号转义）。

    `repo` 默认在**调用时**解析成 REPO：写成 `repo=REPO` 会让默认值在导入时就绑定，
    patch 模块级 REPO 就失效了（测试会因此测了个寂寞）。
    """
    repo = repo or REPO
    out = run(["git", "status", "--porcelain", "-z"], cwd=repo).stdout
    paths: list[str] = []
    skip_next = False
    for rec in out.split("\0"):
        if not rec:
            continue
        if skip_next:            # 改名/复制在 -z 里紧跟一条旧路径记录
            skip_next = False
            continue
        if len(rec) < 4:
            continue
        status, path = rec[:2], rec[3:]
        if status[0] in "RC" or status[1] in "RC":
            skip_next = True
        paths.append(path)
    return paths


def delegation_in_flight(home: Path | None = None) -> str | None:
    """有子代理还在跑就返回它的 delegation_id，否则 None。"""
    live = (home or hermes_home()) / "cache" / "delegation" / "live"
    if not live.is_dir():
        return None
    now_ts = time.time()
    for manifest in sorted(live.glob("*/manifest.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("completed"):
            continue
        statuses = [str((t or {}).get("status", "")).lower() for t in (data.get("tasks") or [])]
        if statuses and all(st in TERMINAL_TASK_STATUS for st in statuses):
            continue             # 任务都收工了（有些收尾路径不写 completed 字段）
        try:
            age = now_ts - manifest.stat().st_mtime
        except OSError:
            continue
        if age > MANIFEST_STALE_S:
            continue             # 残留 manifest 不该把归档永久卡死
        return str(data.get("delegation_id") or manifest.parent.name)
    return None


def freshest_change_age(paths: list[str], repo: Path | None = None,
                        now_ts: float | None = None) -> float | None:
    """工作区里最近被改过的那个文件是多少秒前（都没有/都不存在则 None）。"""
    repo = repo or REPO
    now_ts = time.time() if now_ts is None else now_ts
    ages: list[float] = []
    for rel in paths:
        try:
            ages.append(now_ts - (repo / rel).stat().st_mtime)
        except OSError:
            continue
    return min(ages) if ages else None


def skip_reason(paths: list[str], repo: Path | None = None, home: Path | None = None,
                now_ts: float | None = None) -> str | None:
    """该跳过这轮自动归档吗？返回原因字符串（该跳）或 None（可以提交）。"""
    repo = repo or REPO
    who = delegation_in_flight(home)
    if who:
        return f"有子代理还在跑（{who}）—— 在途改动不自动提交"
    age = freshest_change_age(paths, repo=repo, now_ts=now_ts)
    if age is not None and age < IN_FLIGHT_GRACE_S:
        return f"工作区刚被改过（{age:.0f} 秒前）—— 等写完再归档"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="会话/阶段总结 → git 提交")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("digest", help="输出本仓库相关 Hermes 会话摘要")
    d.add_argument("--hours", type=int, default=72)
    d.add_argument("--limit", type=int, default=12)

    n = sub.add_parser("new", help="新建 journal 记录")
    c = sub.add_parser("commit", help="新建 journal 记录并提交")
    for p in (n, c):
        p.add_argument("--kind", choices=KINDS, default="session")
        p.add_argument("--title", required=True)
        p.add_argument("--scope", default="", help="涉及的课程 id，逗号分隔，如 L00,L01")
        p.add_argument("--summary", default="")
        p.add_argument("--learned", default="")
        p.add_argument("--message", default=None, help="覆盖 git commit 信息")
    c.add_argument("--with-session-digest", action="store_true", help="自动附加 state.db 会话摘要")
    n.add_argument("--with-session-digest", action="store_true")

    r = sub.add_parser("rollback", help="列出回滚目标")
    r.add_argument("--list", action="store_true")

    l = sub.add_parser("log", help="显示 journal 索引与最近提交")
    l.add_argument("-n", type=int, default=10)

    ac = sub.add_parser("autocommit", help="无人值守归档：有改动才提交（适合 cron）")
    ac.add_argument("--hours", type=int, default=24, help="会话摘要回溯窗口")
    ac.add_argument("--title", default="", help="覆盖自动标题")
    ac.add_argument("--verbose", action="store_true",
                    help="被闸门跳过时说明原因（cron 下不要加，静默才是对的）")

    args = ap.parse_args()

    if args.cmd == "autocommit":
        # 设计给 cron / hook 调用：静默、幂等、只在真有改动时才落一条记录。
        # 关键：没有改动时**不输出任何东西**，这样 cron 的 no_agent 模式就不会产生噪音投递。
        changed = run(["git", "status", "--porcelain"]).stdout.strip()
        if not changed:
            return 0
        # 闸门：有子代理在跑、或文件刚被改过 -> 这轮静默跳过（下次 tick 再说）
        if os.environ.get("HERMESUSAGE_AUTOCOMMIT_FORCE") != "1":
            reason = skip_reason(changed_paths(), now_ts=time.time())
            if reason:
                if getattr(args, "verbose", False):
                    print(f"[跳过本轮自动归档] {reason}")
                return 0
        files = len([ln for ln in changed.splitlines() if ln.strip()])
        text, stats = session_digest(args.hours)
        title = args.title or f"自动归档 {now().strftime('%Y-%m-%d %H:%M')}（{files} 个文件变动）"
        write_entry(
            kind="session",
            title=title,
            scope="(自动)",
            summary=f"- 本次自动归档检测到 **{files}** 个文件变动：\n\n"
                    + "\n".join(f"  - `{ln.strip()}`" for ln in changed.splitlines()[:20])
                    + "\n\n（由 `python scripts/journal.py autocommit` 生成；无人值守，未做人工总结）",
            learned="- （自动归档：无人工总结。想补的话直接编辑这条记录并提交）",
            extra="## 本次 Hermes 会话摘要（来自 state.db）\n\n" + text,
            do_commit=True,
            message=f"session: 自动归档 {files} 个文件变动",
        )
        return 0

    if args.cmd == "digest":
        text, stats = session_digest(args.hours, args.limit)
        print(text)
        if stats.get("sessions"):
            print(f"\n合计：{stats['sessions']} 个会话 / {stats['messages']} 条消息 / "
                  f"{stats.get('tool_calls', 0)} 次工具调用 / 缓存读 {stats.get('cache_read', 0):,} tokens")
            if stats.get("top_tools"):
                print(f"最常用工具：{stats['top_tools']}")
        return 0

    if args.cmd in ("new", "commit"):
        extra = ""
        if getattr(args, "with_session_digest", False):
            text, _ = session_digest()
            extra = "## 本次 Hermes 会话摘要（来自 state.db）\n\n" + text
        write_entry(
            kind=args.kind, title=args.title, scope=args.scope,
            summary=args.summary, learned=args.learned, extra=extra,
            do_commit=(args.cmd == "commit"), message=getattr(args, "message", None),
        )
        if args.cmd == "commit":
            print(run(["git", "log", "--oneline", "-3"]).stdout)
        return 0

    if args.cmd == "rollback":
        rollback_list()
        return 0

    if args.cmd == "log":
        if INDEX.exists():
            print(INDEX.read_text(encoding="utf-8"))
        print(run(["git", "log", "--oneline", "--decorate", f"-{args.n}"]).stdout)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
