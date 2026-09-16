#!/usr/bin/env python3
"""scripts/tutorial_core.py —— 课程与出处解析层（唯一真相来源）。

为什么单独抽出这个文件
----------------------
在此之前，build_index.py / build_map.py / verify.py / progress.py 各自抄了一份
frontmatter 解析和阶段表。第五个消费者（静态站点构建器）出现时必须停下来：
再抄一份，必然出现「站点显示 31 课、门禁认为 32 课」这种自己骗自己的不一致。

本模块只做只读解析：不写文件、不打印日志、不 sys.exit。
构建器负责「怎么渲染」，门禁负责「合不合规」，这里只负责「仓库里到底有什么」。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("需要 PyYAML：python -m pip install -r requirements.txt")

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
SUMMARY_RE = re.compile(r"^>\s*\*\*一句话\*\*[：:]\s*(.+?)\s*$", re.M)

# 阶段表：站点首页、索引、学习地图都从这里取名字，别再各写一份
STAGES: dict[int, dict[str, str]] = {
    0: {"name": "认识 Hermes", "why": "先建立正确的心智模型"},
    1: {"name": "会用 Hermes", "why": "核心五件事：模型/工具/会话/记忆/技能"},
    2: {"name": "日常威力", "why": "把 agent 当主力用"},
    3: {"name": "自动化与多代理", "why": "它在你不在的时候也干活"},
    4: {"name": "扩展与改造", "why": "缺什么自己加"},
    5: {"name": "运维与安全", "why": "敢放在每天在用的机器上"},
    9: {"name": "毕业项目", "why": "自动化一件你真正在做的活"},
}


def stage_name(stage: int) -> str:
    return STAGES.get(stage, {}).get("name", f"阶段 {stage}")


def stage_why(stage: int) -> str:
    return STAGES.get(stage, {}).get("why", "")


def parse_frontmatter(text: str) -> dict[str, Any]:
    """解析 ---...--- 之间的 YAML；没有或坏掉都返回 {}（坏掉的由 verify.py 报错）。"""
    m = FM_RE.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """返回 (frontmatter, 正文)。渲染器只要正文。"""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    return parse_frontmatter(text), text[m.end():]


def lesson_summary(body: str) -> str:
    """抓「> **一句话**：…」—— 首页卡片与搜索结果用它，比截断正文可读。"""
    m = SUMMARY_RE.search(body)
    return m.group(1).strip() if m else ""


def lesson_slug(rel: str | Path) -> str:
    """lessons/01-core/L15-skills.md -> L15-skills（URL 用，稳定）。"""
    return Path(rel).stem


def lesson_page(rel: str | Path) -> str:
    """同级页面名：L15-skills.html（课程页里互相引用用这个）。"""
    return f"{lesson_slug(rel)}.html"


def lesson_url(rel: str | Path) -> str:
    """站点内绝对路径（相对站点根）：lessons/L15-skills.html。"""
    return f"lessons/{lesson_page(rel)}"


def load_lessons(repo: Path) -> list[dict[str, Any]]:
    """扫描 lessons/**/*.md，返回排序好的课程字典列表。

    没有 frontmatter 的文件直接跳过：它们要么是坏文件、要么不是课程，
    报错是 verify.py 的职责，构建器不该替它做判断。
    """
    rows: list[dict[str, Any]] = []
    for path in sorted((repo / "lessons").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        if not fm:
            continue
        rel = path.relative_to(repo).as_posix()
        rows.append(
            {
                "id": str(fm.get("id", "")),
                "title": str(fm.get("title", "")),
                "stage": int(fm.get("stage", 0)),
                "level": str(fm.get("level", "")),
                "minutes": int(fm.get("minutes", 0)),
                "prereq": [str(x) for x in (fm.get("prereq") or [])],
                "tags": [str(x) for x in (fm.get("tags") or [])],
                "sources": [str(x) for x in (fm.get("sources") or [])],
                "updated": str(fm.get("updated", "")),
                "summary": lesson_summary(body),
                "rel": rel,
                "slug": lesson_slug(rel),
                "page": lesson_page(rel),
                "url": lesson_url(rel),
                "path": path,
                "body": body,
            }
        )
    rows.sort(key=lambda r: (r["stage"], r["id"]))
    return rows


def group_by_stage(lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 stage 分组，保持传入顺序（load_lessons 已排好）。"""
    groups: list[dict[str, Any]] = []
    for lesson in lessons:
        if not groups or groups[-1]["stage"] != lesson["stage"]:
            groups.append(
                {
                    "stage": lesson["stage"],
                    "name": stage_name(lesson["stage"]),
                    "why": stage_why(lesson["stage"]),
                    "lessons": [],
                }
            )
        groups[-1]["lessons"].append(lesson)
    return groups


BASELINE_RE = re.compile(r"^#\s*生成时间:\s*(\S+)\s+hermes v(\S+)", re.M)
COMMIT_RE = re.compile(r"@\s*([0-9a-f]{7,40})")


def load_citations(repo: Path) -> dict[str, dict[str, Any]]:
    """读 sources/citations.yaml：id → 出处元数据（URL / 版本 / 快照哈希）。"""
    path = repo / "sources" / "citations.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return {str(entry["id"]): entry for entry in data if isinstance(entry, dict) and "id" in entry}


def source_baseline(repo: Path) -> dict[str, Any]:
    """从 citations.yaml 的头部注释里取出「出处基线」——站点页脚要展示它。

    这行信息本来就写在文件头（sync_sources.py 生成的），
    让站点复用它，读者点开页脚就知道整站的事实基线是哪一版官方文档。
    """
    path = repo / "sources" / "citations.yaml"
    if not path.exists():
        return {"version": "", "commit": "", "generated": "", "count": 0}
    head = path.read_text(encoding="utf-8")[:800]
    m_time = BASELINE_RE.search(head)
    m_commit = COMMIT_RE.search(head)
    return {
        "version": m_time.group(2) if m_time else "",
        "generated": m_time.group(1) if m_time else "",
        "commit": (m_commit.group(1)[:8] if m_commit else ""),
        "count": len(load_citations(repo)),
    }
