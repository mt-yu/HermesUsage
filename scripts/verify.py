#!/usr/bin/env python3
"""scripts/verify.py —— 质量门禁：这套教程能不能“自己检查自己”。

为什么要有这个文件
------------------
如果维护者是 AI（或者半年后的你自己），最需要的东西不是文档规范，而是
**一条命令告诉它“你这次改的对不对”**。所以规则不写在散文里，写在代码里：

  R1  frontmatter 字段齐全且取值合法
  R2  每个 [[src:id]] 都能在 sources/citations.yaml 找到出处
  R3  frontmatter 的 sources: 与实际引用一致（不多不少）
  R4  8 个必备小节齐全，且开头有「一句话」摘要
  R5  课程 id 全局唯一、可排序，文件名与 id 一致
  R6  交叉引用 [[Lxx]] 必须指向真实存在的课程
  R7  相对链接指向的文件真实存在
  R8  llms.txt 与课程集合同步（由 scripts/build_index.py 生成）
  R9  ROADMAP.md 覆盖全部课程
  R10 sources/cache 快照与 citations.yaml 的 sha256 一致（且工作区必须是 LF——CRLF 会让 CI 上的哈希对不上）
  R11 文件是 UTF-8 且无 BOM、无 CRLF（Windows 上的老坑）

用法
----
  python scripts/verify.py            # 有问题就退出码 1
  python scripts/verify.py --quiet    # 只打印结论
  python scripts/verify.py --fix-hint # 额外打印每条规则的修复建议
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：python -m pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
TEMPLATES = REPO / "templates"
CITATIONS = REPO / "sources" / "citations.yaml"
CACHE = REPO / "sources" / "cache"
LLMS = REPO / "llms.txt"
ROADMAP = REPO / "ROADMAP.md"

LEVELS = {"入门", "进阶"}
REQUIRED_SECTIONS = ["你将学会", "先动手", "原理", "亲手验证", "常见坑", "试一试", "下一步", "出处"]
REQUIRED_FM = ["id", "title", "stage", "level", "minutes", "prereq", "tags", "sources", "updated"]

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
SRC_RE = re.compile(r"\[\[src:([A-Za-z0-9_.\-]+)\]\]")
XREF_RE = re.compile(r"\[\[(L\d{2,})\]\]")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+\.(?:md|yaml|json|py|html))\)")
ID_RE = re.compile(r"^L\d{2,}$")

errors: list[str] = []
warnings: list[str] = []
fix_hints: list[str] = []


def err(rule: str, path: Path | str, msg: str, hint: str = "") -> None:
    errors.append(f"[{rule}] {path}: {msg}")
    if hint:
        fix_hints.append(f"[{rule}] {hint}")


def warn(rule: str, path: Path | str, msg: str, hint: str = "") -> None:
    warnings.append(f"[{rule}] {path}: {msg}")
    if hint:
        fix_hints.append(f"[{rule}] {hint}")


# --------------------------------------------------------------------------- 载入

def load_citations() -> dict[str, dict]:
    if not CITATIONS.exists():
        err("R2", CITATIONS.relative_to(REPO), "缺失，先跑 python scripts/sync_sources.py")
        return {}
    data = yaml.safe_load(CITATIONS.read_text(encoding="utf-8")) or []
    return {e["id"]: e for e in data}


def load_lessons() -> list[dict]:
    lessons: list[dict] = []
    if not LESSONS_DIR.is_dir():
        err("R5", "lessons/", "目录不存在")
        return lessons
    for path in sorted(LESSONS_DIR.rglob("*.md")):
        raw = path.read_bytes()
        rel = path.relative_to(REPO)
        # R11 编码
        if raw.startswith(b"\xef\xbb\xbf"):
            err("R11", rel, "文件带 UTF-8 BOM", "用 Python 的 encoding='utf-8'（非 utf-8-sig）重写该文件")
        if b"\r\n" in raw:
            err("R11", rel, "含 CRLF 换行", "git config core.autocrlf false 后重新 checkout，或统一转成 LF")
        text = raw.decode("utf-8", errors="replace")

        m = FM_RE.match(text)
        if not m:
            err("R1", rel, "缺少 YAML frontmatter（文件必须以 --- 开头）")
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            err("R1", rel, f"frontmatter 不是合法 YAML：{e}")
            continue

        body = text[m.end():]
        lessons.append({"path": path, "rel": rel, "fm": fm, "body": body, "text": text})
    return lessons


# --------------------------------------------------------------------------- 规则

def check_frontmatter(ls: dict) -> None:
    rel, fm = ls["rel"], ls["fm"]
    for key in REQUIRED_FM:
        if key not in fm:
            err("R1", rel, f"frontmatter 缺字段：{key}", f"补上 {key}:（见 templates/lesson.md）")
            return
    if not ID_RE.match(str(fm["id"])):
        err("R1", rel, f"id 必须形如 L00/L10/L90，实际：{fm['id']}")
    if fm["level"] not in LEVELS:
        err("R1", rel, f"level 只能是 {LEVELS}，实际：{fm['level']}")
    if not isinstance(fm["stage"], int) or not 0 <= fm["stage"] <= 9:
        err("R1", rel, f"stage 应为 0~9 的整数，实际：{fm['stage']}")
    if not isinstance(fm["minutes"], int) or fm["minutes"] <= 0:
        err("R1", rel, f"minutes 应为正整数，实际：{fm['minutes']}")
    for listy in ("prereq", "tags", "sources"):
        if fm.get(listy) is None:
            fm[listy] = []
        if not isinstance(fm[listy], list):
            err("R1", rel, f"{listy} 应为列表，实际：{type(fm[listy]).__name__}")
    if not isinstance(fm.get("updated"), str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(fm.get("updated"))):
        # PyYAML 会把裸写的 2026-09-16 解析成 datetime.date —— 两类都接受，但格式必须对
        upd = fm.get("updated")
        if not (hasattr(upd, "isoformat") and re.match(r"^\d{4}-\d{2}-\d{2}$", upd.isoformat())):
            err("R1", rel, f"updated 应为 YYYY-MM-DD，实际：{upd}")
    # 文件名与 id 一致性
    if not ls["path"].name.startswith(f"{fm['id']}-"):
        err("R5", rel, f"文件名应以 {fm['id']}- 开头", f"重命名为 {fm['id']}-<slug>.md")
    # 标题
    if f"# {fm['id']} · " not in ls["text"]:
        err("R4", rel, f"正文缺少一级标题 `# {fm['id']} · <标题>`")


def check_sections(ls: dict) -> None:
    rel, body = ls["rel"], ls["body"]
    heads = re.findall(r"^##\s+(.+)$", body, re.M)
    for section in REQUIRED_SECTIONS:
        if not any(section in h for h in heads):
            err("R4", rel, f"缺少必备小节：## {section}", f"参考 templates/lesson.md 的 8 小节结构")
    # 「一句话」摘要
    head_zone = "\n".join(body.splitlines()[:20])
    if not re.search(r"^>\s*\*\*一句话\*\*", head_zone, re.M):
        err("R4", rel, "开头 20 行内缺少 `> **一句话**：...` 摘要", "入门读者只看这一行决定是否继续读")


def check_sources(ls: dict, citations: dict[str, dict]) -> None:
    rel, fm, text = ls["rel"], ls["fm"], ls["text"]
    used = SRC_RE.findall(text)
    declared = list(fm.get("sources") or [])

    if not declared:
        err("R3", rel, "frontmatter 的 sources 为空：课程必须给出可考证出处")
    for sid in used:
        if sid not in citations:
            err("R2", rel, f"引用了未登记的出处 [[src:{sid}]]",
                f"在 sources/registry.yaml 里登记 {sid}，或改用已有 id")
        if sid not in declared:
            err("R3", rel, f"正文用了 [[src:{sid}]] 但 frontmatter 没声明",
                f"把它加进 frontmatter: sources: [{sid}]")
    for sid in declared:
        if sid not in citations:
            err("R2", rel, f"frontmatter 声明的出处未登记：{sid}",
                "在 sources/registry.yaml 里登记后跑 sync_sources.py")
        if sid not in used:
            warn("R3", rel, f"frontmatter 声明了 {sid} 但正文没用到", "删掉它，或补上引用位置")
    # 出处小节里应该有真实 URL，读者能点开
    tail = text.split("## 出处", 1)[-1] if "## 出处" in text else ""
    if tail and "http" not in tail:
        warn("R4", rel, "「出处」小节里没有出现任何 http 链接", "至少列出官方 URL，方便读者核对")


def check_cross_refs(ls: dict, ids: set[str], planned: set[str]) -> None:
    """交叉引用要么指向已存在的课程，要么指向 ROADMAP 里已声明的计划课程。

    允许“前向引用”是刻意的：教程分阶段写作时，阶段 0 会引用阶段 1 的课。
    ROADMAP 是这些课的声明处，所以“悬空 id”仍然能被抓到 —— 只是判定依据
    从“文件存在”放宽成“ROADMAP 里有名有姓”。
    """
    for target in set(XREF_RE.findall(ls["text"])):
        if target in ids:
            continue
        if target in planned:
            warn("R6", ls["rel"], f"交叉引用 [[{target}]] 指向 ROADMAP 中尚未编写的课程")
            continue
        err("R6", ls["rel"], f"交叉引用 [[{target}]] 既不存在也没在 ROADMAP.md 里声明",
            "确认课程 id；要么先写它，要么在 ROADMAP.md 里登记")


def check_links(ls: dict) -> None:
    for target in set(LINK_RE.findall(ls["text"])):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        candidate = (ls["path"].parent / target).resolve()
        if not candidate.exists():
            err("R7", ls["rel"], f"相对链接指向的文件不存在：{target}")


def check_global(lessons: list[dict], citations: dict[str, dict]) -> None:
    # R5 唯一性
    seen: dict[str, str] = {}
    for ls in lessons:
        lid = str(ls["fm"].get("id", ""))
        if lid in seen:
            err("R5", ls["rel"], f"课程 id 与 {seen[lid]} 重复：{lid}")
        seen[lid] = str(ls["rel"])

    # R8 llms.txt 同步
    if not LLMS.exists():
        err("R8", "llms.txt", "缺失，跑 python scripts/build_index.py")
    else:
        generated = build_index_preview(lessons)
        current = LLMS.read_text(encoding="utf-8")
        if current != generated:
            err("R8", "llms.txt", "与课程集合不同步（新增/删除课程后未重建）",
                "python scripts/build_index.py")

    # R9 ROADMAP 覆盖
    if not ROADMAP.exists():
        err("R9", "ROADMAP.md", "缺失")
    else:
        roadmap = ROADMAP.read_text(encoding="utf-8")
        for ls in lessons:
            lid = str(ls["fm"].get("id", ""))
            if lid and lid not in roadmap:
                err("R9", ls["rel"], f"ROADMAP.md 未收录 {lid}", "把课程加进 ROADMAP.md 对应阶段")

    # R10 快照哈希
    if not CACHE.is_dir():
        err("R10", "sources/cache/", "目录缺失，跑 python scripts/sync_sources.py")
    else:
        for sid, entry in citations.items():
            f = CACHE / f"{sid}.md"
            if not f.is_file():
                err("R10", f"sources/cache/{sid}.md", "快照缺失", "python scripts/sync_sources.py")
                continue
            raw = f.read_bytes()
            if b"\r\n" in raw:
                err("R10", f"sources/cache/{sid}.md",
                    "快照在工作区里是 CRLF，而 git 存的是 LF：Linux/CI 上 checkout 出来的字节不同，哈希必然对不上",
                    "python scripts/sync_sources.py 会统一按 LF 重算哈希")
            actual = hashlib.sha256(raw).hexdigest()
            if actual != entry.get("sha256"):
                err("R10", f"sources/cache/{sid}.md", "快照哈希与 citations.yaml 不一致",
                    "不要手改快照；重新跑 python scripts/sync_sources.py")


def build_index_preview(lessons: list[dict]) -> str:
    """与 scripts/build_index.py 保持一致的 llms.txt 渲染（避免循环 import）。"""
    sys.path.insert(0, str(REPO / "scripts"))
    import build_index  # noqa: E402

    return build_index.render(build_index.rows_from_lessons(lessons))


# --------------------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="教程仓库质量门禁")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--fix-hint", action="store_true", help="打印每条规则的修复建议")
    args = ap.parse_args()

    citations = load_citations()
    lessons = load_lessons()
    ids = {str(ls["fm"].get("id", "")) for ls in lessons}
    planned = set(re.findall(r"\bL\d{2,}\b", ROADMAP.read_text(encoding="utf-8"))) if ROADMAP.exists() else set()

    for ls in lessons:
        check_frontmatter(ls)
        check_sections(ls)
        check_sources(ls, citations)
        check_cross_refs(ls, ids, planned)
        check_links(ls)
    check_global(lessons, citations)

    if not args.quiet:
        print(f"课程数：{len(lessons)}    出处数：{len(citations)}")
        for w in warnings:
            print(f"  warn  {w}")
        for e in errors:
            print(f"  ERROR {e}")
        if args.fix_hint and fix_hints:
            print("\n修复建议：")
            for h in fix_hints:
                print(f"  - {h}")

    if errors:
        print(f"\n未通过：{len(errors)} 个错误，{len(warnings)} 个警告")
        print("修好后再提交。规则速查：python scripts/verify.py --fix-hint")
        return 1
    print(f"\n通过：{len(lessons)} 课全部合规（{len(warnings)} 个警告）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
