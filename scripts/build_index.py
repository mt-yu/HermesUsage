#!/usr/bin/env python3
"""scripts/build_index.py —— 生成 llms.txt：让 AI（和读者）一次读全目录。

为什么不是手写目录
------------------
这套教程的维护者之一是 AI。AI 的自学习入口需要一个**机器可读、永远与内容同步**
的索引：给定一个任务（“我要学会用技能”），它能立刻找到该读哪个文件。

llms.txt 沿用 Hermes 官方文档自己的约定（是的，官方的 llms.txt 就是目录索引，
见 https://hermes-agent.nousresearch.com/docs/llms.txt —— 我们照抄这个思路）。

用法
----
  python scripts/build_index.py          # 生成/更新 llms.txt
  python scripts/build_index.py --check  # 只校验是否同步（CI / verify.py 用）
  python scripts/build_index.py --stdout # 打印到屏幕
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：python -m pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
LLMS = REPO / "llms.txt"
ROADMAP = REPO / "ROADMAP.md"

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

STAGE_TITLES = {
    0: "阶段 0 · 认识 Hermes（先建立正确的心智模型）",
    1: "阶段 1 · 会用 Hermes（核心五件事）",
    2: "阶段 2 · 日常威力（把 agent 当主力用）",
    3: "阶段 3 · 自动化与多代理（进阶）",
    4: "阶段 4 · 扩展与改造（进阶）",
    5: "阶段 5 · 运维与安全（进阶）",
    9: "毕业项目 · Capstone",
}


def rows_from_lessons(lessons: list[dict]) -> list[dict]:
    """把 verify.py 解析出的课程字典（含 'fm'）归一化成 render() 需要的行。

    两个模块共用渲染逻辑，就必须共用行结构；否则索引会出现“verify 算出来的文本”
    和“build_index 写出来的文本”不一致的假阳性。
    """
    rows = []
    for ls in lessons:
        fm = ls.get("fm", {})
        rows.append(
            {
                "id": str(fm.get("id", "")),
                "title": str(fm.get("title", "")),
                "stage": int(fm.get("stage", 0)),
                "level": str(fm.get("level", "")),
                "minutes": int(fm.get("minutes", 0)),
                "tags": list(fm.get("tags") or []),
                "sources": list(fm.get("sources") or []),
                "rel": ls["rel"].as_posix() if hasattr(ls["rel"], "as_posix") else str(ls["rel"]),
            }
        )
    rows.sort(key=lambda r: (r["stage"], r["id"]))
    return rows


def load_index_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(LESSONS_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = FM_RE.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            # 坏的 frontmatter 不能把索引生成器带崩：报出文件，让人（或 verify.py）去修
            print(f"[!] frontmatter 不是合法 YAML，已跳过：{path.relative_to(REPO)} — {e}", file=sys.stderr)
            continue
        rows.append(
            {
                "id": str(fm.get("id", "")),
                "title": str(fm.get("title", "")),
                "stage": int(fm.get("stage", 0)),
                "level": str(fm.get("level", "")),
                "minutes": int(fm.get("minutes", 0)),
                "tags": list(fm.get("tags") or []),
                "sources": list(fm.get("sources") or []),
                "rel": path.relative_to(REPO).as_posix(),
            }
        )
    rows.sort(key=lambda r: (r["stage"], r["id"]))
    return rows


def render(rows: list[dict]) -> str:
    total_min = sum(r["minutes"] for r in rows)
    beginner = [r for r in rows if r["level"] == "入门"]
    lines: list[str] = []
    lines.append("# Hermes Agent 初学者教程")
    lines.append("")
    lines.append(
        "> 一份可考证、可自维护、可回滚的 Hermes Agent 教程系统。"
        "每条事实性陈述都带 [[src:id]] 出处标记，可在 sources/citations.yaml 反查到"
        "官方文档 URL、版本与内容哈希。"
    )
    lines.append("")
    lines.append(
        f"课程总数：{len(rows)} 课（入门 {len(beginner)} 课 / 进阶 {len(rows) - len(beginner)} 课），"
        f"合计约 {total_min} 分钟。"
    )
    lines.append("")
    lines.append("## 怎么读这份索引（给 AI 维护者）")
    lines.append("")
    lines.append("- 想知道“这个仓库有什么内容”：读本文件即可，不需要遍历目录。")
    lines.append("- 想新增一课：复制 templates/lesson.md，改 frontmatter，然后跑")
    lines.append("  `python scripts/build_index.py && python scripts/verify.py`。")
    lines.append("- 想核对某条陈述的出处：`sources/cache/<src-id>.md` 是官方文档快照。")
    lines.append("- 想知道自己该改哪里：读 `.hermes.md`（项目宪章）与 `ROADMAP.md`（路线图）。")
    lines.append("")

    current_stage: int | None = None
    for r in rows:
        if r["stage"] != current_stage:
            current_stage = r["stage"]
            lines.append(f"## {STAGE_TITLES.get(current_stage, f'阶段 {current_stage}')}")
            lines.append("")
        tags = "、".join(r["tags"][:4]) if r["tags"] else "—"
        lines.append(
            f"- [{r['id']} {r['title']}]({r['rel']}) — "
            f"[{r['level']}] {r['minutes']} 分钟 · 标签：{tags} · 出处 {len(r['sources'])} 条"
        )
    lines.append("")
    lines.append("## 支撑文件")
    lines.append("")
    lines.append("- [README.md](README.md) — 人类入口：5 分钟上手 + 学习路线图")
    lines.append("- [ROADMAP.md](ROADMAP.md) — 阶段与进度（带勾选清单）")
    lines.append("- [.hermes.md](.hermes.md) — 项目宪章：写作规范、质量门禁、git 工作流（Hermes 自动注入）")
    lines.append("- [CONTRIBUTING.md](CONTRIBUTING.md) — 人和 AI 的贡献流程")
    lines.append("- [sources/README.md](sources/README.md) — 出处体系如何自证")
    lines.append("- [progress/checklist.md](progress/checklist.md) — 学习者进度清单")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 llms.txt 索引")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    rows = load_index_rows()
    if not rows:
        print("lessons/ 下还没有课程。")
        return 0
    content = render(rows)

    if args.stdout:
        print(content)
        return 0

    if args.check:
        current = LLMS.read_text(encoding="utf-8") if LLMS.exists() else ""
        if current == content:
            print(f"llms.txt 已同步（{len(rows)} 课）。")
            return 0
        print("llms.txt 与课程集合不同步：python scripts/build_index.py")
        return 1

    LLMS.write_text(content, encoding="utf-8", newline="\n")
    stages = len({r["stage"] for r in rows})
    print(f"写入 llms.txt：{len(rows)} 课 / {stages} 个阶段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
