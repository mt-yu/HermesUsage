#!/usr/bin/env python3
"""scripts/progress.py —— 学习进度打卡（本地状态，不进 git）。

和 ROADMAP.md 的分工
--------------------
  ROADMAP.md      “这门课存在吗、属于哪个阶段” —— 团队共享的事实，进 git
  .state.json     “我学到哪了、哪几课做完了” —— 每人本机不同，不进 git

用法
----
  python scripts/progress.py                      # 看进度
  python scripts/progress.py done L01             # 标记完成
  python scripts/progress.py done L01 --note "跑通了 cron"
  python scripts/progress.py undo L01
  python scripts/progress.py reset
  python scripts/progress.py next                 # 告诉我下一课学什么
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：python -m pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"
STATE = REPO / "progress" / ".state.json"
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def catalog() -> list[dict]:
    rows = []
    for p in sorted(LESSONS.rglob("*.md")):
        m = FM_RE.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        rows.append(
            {
                "id": str(fm.get("id", "")),
                "title": str(fm.get("title", "")),
                "stage": int(fm.get("stage", 0)),
                "level": str(fm.get("level", "")),
                "minutes": int(fm.get("minutes", 0)),
                "prereq": list(fm.get("prereq") or []),
            }
        )
    rows.sort(key=lambda r: (r["stage"], r["id"]))
    return rows


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"done": {}, "started": datetime.now().astimezone().isoformat()}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def show() -> None:
    rows, state = catalog(), load_state()
    done = state.get("done", {})
    total = len(rows)
    n_done = sum(1 for r in rows if r["id"] in done)
    mins = sum(r["minutes"] for r in rows if r["id"] not in done)
    bar_w = 28
    filled = int(bar_w * n_done / total) if total else 0
    print(f"进度：[{'█' * filled}{'░' * (bar_w - filled)}] {n_done}/{total} 课")
    if mins:
        print(f"剩余约 {mins} 分钟（按课程标注的耗时估算）")
    print()
    stage = None
    for r in rows:
        if r["stage"] != stage:
            stage = r["stage"]
            print(f"— 阶段 {stage} —")
        mark = "✅" if r["id"] in done else ("  " if all(p in done for p in r["prereq"]) else "🔒")
        note = done.get(r["id"], {}).get("note", "")
        print(f"  {mark} {r['id']:>4} {r['title'][:34]:<36} {r['minutes']:>3}min {('· ' + note) if note else ''}")
    print()


def next_lesson() -> int:
    rows, state = catalog(), load_state()
    done = state.get("done", {})
    for r in rows:
        if r["id"] in done:
            continue
        missing = [p for p in r["prereq"] if p not in done]
        if missing:
            print(f"下一课受阻：{r['id']} {r['title']}，请先完成前置：{', '.join(missing)}")
            return 1
        print(f"下一课学：{r['id']} · {r['title']}（{r['minutes']} 分钟，{r['level']}）")
        print(f"打开：lessons/ 下搜 {r['id']}- 开头的文件")
        return 0
    print("全部课程已完成 🎉  去 ROADMAP.md 看毕业项目（L90）。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="学习进度打卡")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("done", "undo"):
        p = sub.add_parser(name)
        p.add_argument("lesson")
        p.add_argument("--note", default="")
    sub.add_parser("reset")
    sub.add_parser("next")
    args = ap.parse_args()

    rows = {r["id"]: r for r in catalog()}

    if args.cmd in ("done", "undo"):
        lid = args.lesson.upper()
        if lid not in rows:
            print(f"没有这门课：{lid}（可用 python scripts/progress.py 查看全部）")
            return 1
        state = load_state()
        if args.cmd == "done":
            state.setdefault("done", {})[lid] = {
                "at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "note": args.note,
            }
            print(f"✅ {lid} {rows[lid]['title']} —— 完成后记得写 journal：")
            print(f'   python scripts/journal.py commit --kind session --title "完成 {lid}" --scope {lid}')
        else:
            state.get("done", {}).pop(lid, None)
            print(f"↩️  已撤销 {lid}")
        save_state(state)
        show()
        return 0

    if args.cmd == "reset":
        if STATE.exists():
            STATE.unlink()
        print("进度已清空。")
        return 0

    if args.cmd == "next":
        return next_lesson()

    show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
