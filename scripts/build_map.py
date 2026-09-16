#!/usr/bin/env python3
"""scripts/build_map.py —— 生成 docs/learning-map.html：给初学者的可视化学习地图。

为什么要有这个
--------------
`llms.txt` 是给 AI 看的索引，`ROADMAP.md` 是给维护者看的状态表。
初学者需要的是第三种东西：**一眼看到自己站在哪、下一步点什么**。
所以这张图是可点击的：点课程就把「带我学这一课」发回给 Hermes（`data-hermes-send`）。

它同时是 Hermes 桌面应用的**行内部件**，所以样式必须遵守桌面框架的约定：
用框架注入的 CSS 变量上色、不要自带背景色/字体/外边距、左对齐不居中。
（框架会注入 --foreground / --muted-foreground / --accent / --border / --card。）

课程解析不在这里：frontmatter 解析与阶段表统一走 `scripts/tutorial_core.py`
（它是全仓库唯一的解析入口）。本文件只负责「怎么渲染」。

用法
----
  python scripts/build_map.py            # 写 docs/learning-map.html
  python scripts/build_map.py --stdout   # 打到屏幕（贴进聊天预览）
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

# 同目录的解析层：显式入栈，脚本被以任何方式启动都能找到 tutorial_core
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tutorial_core as core  # noqa: E402 —— 必须在 sys.path 调整之后导入

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "progress" / ".state.json"
OUT = REPO / "docs" / "learning-map.html"


def load_rows() -> list[dict]:
    """把解析层的课程列表压成学习地图需要的字段。

    ⚠️ `summary` 故意写死空串，别改成 `lesson["summary"]`：
    迁移前这里取的是 frontmatter 的 `summary` 键，而课程的 frontmatter 里
    根本没有这个键，所以实际取到的永远是空串（地图模板当前也不显示摘要）。
    解析层的 `summary` 是从正文「**一句话**：…」抽出来的真摘要，直接透传
    会改变输出字节 —— 那不是本任务（DRY 收口）该带来的变化。
    """
    rows = [
        {
            "id": lesson["id"],
            "title": lesson["title"],
            "stage": lesson["stage"],
            "level": lesson["level"],
            "minutes": lesson["minutes"],
            "rel": lesson["rel"],
            "summary": "",  # 见 docstring：保持与迁移前一致的空串
        }
        for lesson in core.load_lessons(REPO)
    ]
    rows.sort(key=lambda r: (r["stage"], r["id"]))
    return rows


def done_set() -> set[str]:
    if STATE.exists():
        try:
            return set(json.loads(STATE.read_text(encoding="utf-8")).get("done", {}))
        except json.JSONDecodeError:
            return set()
    return set()


def render(rows: list[dict], done: set[str]) -> str:
    total = len(rows)
    n_done = sum(1 for r in rows if r["id"] in done)
    total_min = sum(r["minutes"] for r in rows)
    parts: list[str] = []
    A = parts.append

    A('<div class="humap">')
    A("<style>")
    A("""
.humap { width: 680px; max-width: 100%; color: var(--foreground); font-size: 13px; line-height: 1.5; }
.humap .bar { height: 6px; border-radius: 3px; background: var(--border); overflow: hidden; margin: 6px 0 14px; }
.humap .bar > i { display: block; height: 100%; background: var(--accent); }
.humap .head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.humap .head b { font-size: 14px; }
.humap .muted { color: var(--muted-foreground); }
.humap .stage { margin: 14px 0 6px; padding: 8px 10px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; }
.humap .stage > .top { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.humap .stage .name { font-weight: 600; }
.humap .stage .why { color: var(--muted-foreground); }
.humap ul { list-style: none; margin: 8px 0 0; padding: 0; }
.humap li { display: flex; align-items: baseline; gap: 8px; padding: 4px 0; border-top: 1px solid var(--border); }
.humap li:first-child { border-top: none; }
.humap .id { flex: 0 0 40px; font-variant-numeric: tabular-nums; color: var(--muted-foreground); }
.humap .t { flex: 1 1 auto; min-width: 0; }
.humap .min { flex: 0 0 46px; text-align: right; color: var(--muted-foreground); }
.humap .go { flex: 0 0 72px; text-align: right; }
.humap button { font: inherit; cursor: pointer; color: var(--foreground);
  background: transparent; border: 1px solid var(--border); border-radius: 6px; padding: 2px 8px; }
.humap button:hover { border-color: var(--accent); color: var(--accent); }
.humap .ok { color: var(--accent); }
.humap .lock { color: var(--muted-foreground); }
""".strip())
    A("</style>")

    A('<div class="head">')
    A(f"<b>Hermes 学习地图</b><span class='muted'>{n_done}/{total} 课完成 · 全量约 {total_min} 分钟</span>")
    A("</div>")
    pct = int(n_done / total * 100) if total else 0
    A(f'<div class="bar"><i style="width:{pct}%"></i></div>')

    current_stage = None
    for r in rows:
        if r["stage"] != current_stage:
            if current_stage is not None:
                A("</ul></div>")
            current_stage = r["stage"]
            # 阶段名与「为什么」来自唯一解析层（旧的本地 STAGES 三元组里第三项
            # level 从未被使用，直接不取，输出不变）
            name = core.stage_name(current_stage)
            why = core.stage_why(current_stage)
            stage_rows = [x for x in rows if x["stage"] == current_stage]
            s_done = sum(1 for x in stage_rows if x["id"] in done)
            tag = "入门" if current_stage in (0, 1) else "进阶"
            A('<div class="stage">')
            A('<div class="top">')
            A(f'<span><span class="name">阶段 {current_stage} · {html.escape(name)}</span> '
              f'<span class="why">— {html.escape(why)}</span></span>')
            A(f'<span class="muted">{s_done}/{len(stage_rows)} · {tag}</span>')
            A("</div>")
            A("<ul>")
        mark = '<span class="ok">✓</span>' if r["id"] in done else '<span class="lock">○</span>'
        prompt = (f"带我学 {r['id']}「{r['title']}」：先读 {r['rel']}，"
                  f"然后按课里的「先动手」一步步带我走，每步都等我确认")
        A("<li>")
        A(f'<span class="id">{mark} {r["id"]}</span>')
        A(f'<span class="t">{html.escape(r["title"])}</span>')
        A(f'<span class="min">{r["minutes"]}min</span>')
        A(f'<span class="go"><button data-hermes-send="{html.escape(prompt, quote=True)}">开始</button></span>')
        A("</li>")
    if current_stage is not None:
        A("</ul></div>")

    A('<div style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap;">')
    A('<button data-hermes-send="python scripts/progress.py next">我该学哪一课？</button>')
    A('<button data-hermes-send="python scripts/verify.py 并告诉我这个仓库当前是否健康">检查仓库健康度</button>')
    A('<button data-hermes-send="python scripts/journal.py commit --kind session '
      '--title \'本次学习会话\' --with-session-digest">归档这次学习</button>')
    A('<button data-hermes-send="python scripts/sync_sources.py --check">官方文档有没有改版？</button>')
    A("</div>")
    A("</div>")
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="生成可视化学习地图")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    rows = load_rows()
    if not rows:
        print("lessons/ 下还没有课程。")
        return 0
    out = render(rows, done_set())
    if args.stdout:
        print(out)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out, encoding="utf-8", newline="\n")
    print(f"写入 {OUT.relative_to(REPO)}：{len(rows)} 课")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
