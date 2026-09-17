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
    6: {"name": "真实工作流案例", "why": "把前面学的拼成能交付的活"},
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


TUTOR_PROMPT_TAIL = "然后按课里的「先动手」一步步带我走，每步都等我确认"


def tutor_prompt(lesson: dict[str, Any]) -> str:
    """「带我学这一课」的提示语 —— 桌面部件与站点地图页共用的唯一一份。

    例：`带我学 L15「技能系统：让它学会你的活法」：先读 lessons/01-core/L15-skills.md，`
    `然后按课里的「先动手」一步步带我走，每步都等我确认`

    这句话是**给 agent 的指令**，不是给人看的摘要，所以三处细节都是刻意的：
    - 课程 id + 标题：agent 要知道学哪一课；
    - 仓库相对路径 `rel`：agent 要能直接读文件，而不是先自己做一次模糊搜索；
    - 结尾「每步都等我确认」：把「先动手」的节奏钉死，防止它一口气跑完 8 步。

    全角「」与「，」也是刻意的（中文排版）。改这句话前先想清楚：
    桌面应用里用户点「开始」看到的就是它，站点地图页点圆圈看到的也是它。
    """
    return (f"带我学 {lesson['id']}「{lesson['title']}」：先读 {lesson['rel']}，"
            f"{TUTOR_PROMPT_TAIL}")


def map_rows(lessons: list[dict[str, Any]], done: set[str] | None = None) -> list[dict[str, Any]]:
    """把课程列表压成「学习地图」的行数据：桌面部件与站点地图页共用。

    行结构：{id, title, stage, minutes, rel, url, done: bool, prompt}。
    `done` 由调用方传入（桌面部件读 progress/.state.json，站点读 localStorage），
    解析层不碰任何状态文件 —— 它只回答「仓库里有什么」。

    注意这里**不出** `level` / `summary`：地图模板两者都不用，
    多传一份就多一处将来会各自漂移的字段。
    """
    mark = done or set()
    rows = [
        {
            "id": lesson["id"],
            "title": lesson["title"],
            "stage": lesson["stage"],
            "minutes": lesson["minutes"],
            "rel": lesson["rel"],
            "url": lesson["url"],
            "done": lesson["id"] in mark,
            "prompt": tutor_prompt(lesson),
        }
        for lesson in lessons
    ]
    rows.sort(key=lambda r: (r["stage"], r["id"]))
    return rows


PITFALL_HEADING_RE = re.compile(r"^#{1,6}\s*常见坑\s*$", re.M)
SECTION_RE = re.compile(r"^##\s", re.M)
# 分隔行：|---|---| / |:--|--:|。整行都是横线，没有任何内容。
SEP_CELL_RE = re.compile(r"^:?-+:?$")
PITFALL_HEADER = ("现象", "真实原因", "怎么解决")


def pitfall_section(body: str) -> str:
    """取出正文里 `## 常见坑` 小节的原文（到下一个二级标题为止）。

    单独抽出来是因为「小节边界」是这一段最容易出错的地方：
    用「下一个 ## 」当右边界，才不会把「试一试」「动手练」里的表格也算进来
    —— 那些表是练习，不是坑。
    """
    m = PITFALL_HEADING_RE.search(body or "")
    if not m:
        return ""
    rest = body[m.end():]
    nxt = SECTION_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _table_cells(line: str) -> list[str]:
    """一行 markdown 表格 → 单元格列表（按未转义的 `|` 切，`\\|` 不是分隔符）。"""
    inner = line.strip().strip("|")
    return [c.strip() for c in re.split(r"(?<!\\)\|", inner)]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(SEP_CELL_RE.match(c) for c in cells)


def pitfall_rows(lesson: dict[str, Any]) -> list[dict[str, str]]:
    """抽取该课 `## 常见坑` 小节里所有 markdown 表格的数据行 → [{symptom, cause, fix}]。

    规则（站点「常见错误合集」页全部 253 行都从这里来，所以每条都要说清）：

    - 只在该小节内找表格；「试一试」等别的小节里的表格不算；
    - 跳过表头行（紧挨着分隔行的那行）与 `|---|---|` 分隔行 ——
      否则页面上会凭空多出 32 行「现象/真实原因/怎么解决」；
    - 单元格数不为 3 的行跳过（两列的行是写坏的表，宁可少一行也不要把
      半个单元格渲染成表格里的错位格子）；
    - 单元格**原文保留**（行内代码、`[[src:id]]`、`[[Lxx]]` 都留着）：
      渲染层要拿它们去连出处与课程页，这里先做一次替换就等于把标记吃掉了。

    没有该小节、或小节里没有表格，返回 []。
    """
    raw_rows = [
        _table_cells(line)
        for line in pitfall_section(lesson.get("body", "")).split("\n")
        if line.strip().startswith("|")
    ]
    rows: list[dict[str, str]] = []
    for i, cells in enumerate(raw_rows):
        if _is_separator_row(cells):
            continue
        # 表头 = 紧挨着分隔行上面的那一行（markdown 表格的唯一合法表头位置）
        if i + 1 < len(raw_rows) and _is_separator_row(raw_rows[i + 1]):
            continue
        if tuple(cells) == PITFALL_HEADER:
            continue
        if len(cells) != 3:
            continue
        rows.append({"symptom": cells[0], "cause": cells[1], "fix": cells[2]})
    return rows


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
