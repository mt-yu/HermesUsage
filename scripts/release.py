#!/usr/bin/env python3
"""scripts/release.py —— 发布体系的唯一脚本：发布说明 / 变更日志 / 资产 / Release / 对账。

为什么四件事收在一个脚本里
--------------------------
写发布说明、维护 CHANGELOG、构建可校验的资产、在 GitHub 上建 Release —— 这四步共用
同一套「提交前缀 → Keep a Changelog 分类」映射（`CATEGORIES`）。任何一步换工具做
（`gh` CLI / 手点网页 / GitHub 的自动生成说明），另外三步就失去对照物：

  * 本仓库没有 `gh` CLI，也没装（脚本自己走 REST API）；
  * 提交全部直接落 main、不走 PR，所以 GitHub 的 "Generate release notes" 在这里是空的；
  * 自动生成的源码包不受我们控制，自有 zip + `SHA256SUMS` 才能被哈希校验、被 attestation 覆盖。

五个子命令
----------
  notes     --tag <tag> [--prev <tag>] [--json]        按模板渲染发布说明
  changelog [--write | --check]                        生成 / 校验 CHANGELOG.md（默认 --check）
  artifact  --tag <tag> [--out DIR] [--json]           构建确定性 zip + SHA256SUMS + 构建回执
  create    --tag <tag> [--prerelease|--no-prerelease] [--latest|--no-latest]
            [--body-only] [--dry-run]                  幂等建 / 更新 GitHub Release
  audit     [--tag <tag>] [--check] [--json]           远端 releases 与本地 tag 对账

退出码
------
  0   成功（含「该 tag 尚无站点，不产出资产」这种正常结论）
  1   校验失败（`changelog --check` 与磁盘不一致 / `audit --check` 有差异）
  2   用法或前置错误（未知 tag、无令牌、构建失败、网络失败、解析不出 owner/name）

确定性（这是本脚本最重要的性质）
--------------------------------
`artifact` 产出的 zip 必须「同一个 tag 在任何机器、任何时间构建，字节都相同」——
不然本机 `dist/SHA256SUMS` 与 CI 上传的资产哈希对不上，`audit --check` 永远红。
为此做了三件事：

  1. `zip_dir`：条目按名排序、`date_time` 固定 1980-01-01、`ZIP_DEFLATED`（compresslevel=6）、
     `create_system=3` 与固定的 `external_attr`（不然 Windows 与 Linux 打的包不一样）。
  2. `normalize_build_clock`：该 tag 树里的 `build_site.py` 会把**构建时刻**写进产物
     （`site/data/index.json` 的 `generated`、`site/data/manifest.json` 的 `built_at`，
     以及没有 `updated` 的课程在 `sitemap.xml` 里的 `lastmod` 兜底值）。
     构建完把这三处换成**该 tag 的 commit 时间**，于是产物只由 tag 决定。
  3. 临时树里跑的是**该 tag 自己的** `scripts/build_site.py`（不是工作区的），
     所以历史 tag 的站点按它当年的渲染逻辑重建，不会被后来的改动污染。

令牌与网络
----------
令牌顺序复用 `scripts/drift_watch.py` 的 `get_token()`（`GITHUB_TOKEN` → `git credential fill`），
**不打印、不写文件、不进提交**。一切 HTTP 都走 `ProxyHandler({})`（本机默认代理已挂，
`http://127.0.0.1:7897`，curl 会 schannel handshake 失败）。`--dry-run` 只打印将发出的请求，
**不取令牌、不触网**，没网也能跑。

已知限制
--------
  * 上游 `drift_watch.get_token()` 只认 `GITHUB_TOKEN` 与 `git credential fill`，
    不认 `GH_TOKEN`（计划里写的完整顺序是三者）。CI 传的是 `GITHUB_TOKEN`，不受影响；
    真要补 `GH_TOKEN` 应该改 `drift_watch.py`，本脚本不复制第二份实现。
  * zip 的 deflate 输出依赖 zlib 版本：本机（Windows Python 3.11）与 CI（ubuntu Python 3.11）
    都是 zlib，实测同 level 输出一致；换成 zlib-ng 之类实现需要重新验证。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
import zipfile
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

REPO = Path(__file__).resolve().parent.parent

# 令牌顺序与 git credential 读取都在这里（不复制第二份实现）：
# 先 sys.path 挂上 scripts/，再 from drift_watch import get_token。
sys.path.insert(0, str(REPO / "scripts"))

from drift_watch import get_token  # noqa: E402

CHANGELOG = REPO / "CHANGELOG.md"
DIST = REPO / "dist"
SITE_JSON_NAME = "scripts/build_site.py"

# 发布说明模板里的字面 URL（计划里逐字给定，不用运行时推断，免得输出随远端漂移）
GH_SLUG = "mt-yu/HermesUsage"
GH_URL = f"https://github.com/{GH_SLUG}"
SITE_URL = "https://mt-yu.github.io/HermesUsage/"

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
UA = "HermesUsage-release/1.0 (+https://github.com/mt-yu/HermesUsage)"
API_VERSION = "2022-11-28"

TITLE_MAX = 100
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
ZIP_LEVEL = 6

# 「提交前缀 → Keep a Changelog 分类」的唯一来源：notes 与 changelog 共用。
# 顺序即输出顺序（Keep a Changelog 的惯例：新增 → 修复 → 文档 → 变更 → 弃用 → 移除 → 安全 → 内部）。
CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("added", "新增", ("feat", "stage", "session")),
    ("fixed", "修复", ("fix",)),
    ("docs", "文档", ("docs",)),
    ("changed", "变更", ("refactor", "perf", "revert", "change")),
    ("deprecated", "弃用", ("deprecate",)),
    ("removed", "移除", ("remove",)),
    ("security", "安全", ("security",)),
    ("internal", "工程（内部）", ("ci", "chore", "release")),
)
CATEGORY_ORDER = tuple(key for key, _, _ in CATEGORIES)
CATEGORY_TITLES = {key: title for key, title, _ in CATEGORIES}
_PREFIX_TO_CATEGORY = {p: key for key, _, prefixes in CATEGORIES for p in prefixes}

# 提交前缀：`feat: xxx` / `fix：xxx` / 裸标题（无前缀）
RE_PREFIX = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*[:：]")
RE_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}")
RE_LAST_MOD = re.compile(r"<lastmod>([^<]*)</lastmod>")

# 构建期时间戳（该 tag 树的 build_site.py 写进产物的那几个字段）：
# rel 路径 → 顶层键名。只换这几个，不动课程内容里本来就有的日期。
BUILD_CLOCK_FIELDS = (("data/index.json", "generated"), ("data/manifest.json", "built_at"))


class ReleaseError(RuntimeError):
    """用法 / 前置错误 —— 一律对应退出码 2。"""


# --------------------------------------------------------------------------- 小工具

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def write_text(path: Path, text: str) -> None:
    """统一 UTF-8 + LF 落盘（项目铁律 R8：Windows 上最容易踩）。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def display_width(text: str) -> int:
    """终端列宽：CJK 全角算 2 列，不然中文表头会跟数据错位。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def _git(*args: str, check: bool = True) -> str:
    """跑一条只读 git 命令（发表这件事绝不需要写 git）。"""
    p = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if check and p.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)} 失败（退出码 {p.returncode}）：{(p.stderr or '').strip()[:500]}")
    return p.stdout or ""


# --------------------------------------------------------------------------- 纯函数：tag 与提交

def all_tags() -> list[str]:
    return [line.strip() for line in _git("tag", "-l").splitlines() if line.strip()]


def tag_depth(tag: str) -> int:
    """祖先深度：用「从这条 tag 能数到多少个提交」当排序键。

    tag 名不是 semver（`v0.2-orient` … `v3.3-topbar`），也不保证创建顺序与版本一致，
    所以按提交深度排 —— 它天然等于「谁的历史更长 = 谁更晚」，且不依赖机器时钟。
    """
    return int(_git("rev-list", "--count", f"{tag}^{{commit}}").strip() or 0)


def tag_creatordate(tag: str) -> str:
    return _git("for-each-ref", f"refs/tags/{tag}", "--format=%(creatordate:iso)").strip()


@lru_cache(maxsize=8)
def _ordered(tags: tuple[str, ...]) -> tuple[str, ...]:
    """排序本体（按值缓存：一次排序要跑 2N 条 git 命令，一个进程里会被问很多次）。"""
    return tuple(sorted(tags, key=lambda t: (tag_depth(t), tag_creatordate(t), t)))


def tag_order(tags: list[str]) -> list[str]:
    """按 tag 提交的祖先深度升序；深度相同再按 creatordate（最后用 tag 名兜底，保证全序）。"""
    return list(_ordered(tuple(tags)))


def tag_exists(tag: str) -> bool:
    p = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return p.returncode == 0


def previous_tag(tag: str) -> str | None:
    """`tag_order` 里该 tag 的前一个；第一个 tag → None（没有可对比的对象）。"""
    ordered = tag_order(all_tags())
    if tag not in ordered:
        raise ReleaseError(f"未知 tag：{tag}（本地 `git tag -l` 里没有它）")
    i = ordered.index(tag)
    return ordered[i - 1] if i else None


def tag_subject(tag: str) -> str:
    """tag 对象的 subject（注释 tag 的说明第一行）；轻量 tag 会退回 commit subject。"""
    return _git("for-each-ref", f"refs/tags/{tag}", "--format=%(contents:subject)").strip()


def tag_date(tag: str) -> str:
    """该 tag 指向的 commit 日期（YYYY-MM-DD）——发布说明与 CHANGELOG 的日期都用它。"""
    return _git("log", "-1", "--format=%cs", f"{tag}^{{commit}}").strip()


def commit_sha(tag: str) -> str:
    return _git("rev-parse", f"{tag}^{{commit}}").strip()


def commits_in(prev: str | None, tag: str) -> list[dict]:
    """`prev..tag` 的提交（prev 为 None 时取该 tag 的全部祖先）。subject 里的 tab 不会出现。"""
    rng = f"{prev}..{tag}" if prev else tag
    out = _git("log", "--format=%h%x09%s", rng)
    commits: list[dict] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append({"sha": sha.strip(), "subject": subject.strip()})
    return commits


def release_title(tag: str) -> str:
    subject = tag_subject(tag)
    title = f"{tag} · {subject}" if subject else tag
    if len(title) > TITLE_MAX:
        title = title[: TITLE_MAX - 1].rstrip() + "…"
    return title


def classify(subject: str) -> str:
    """提交前缀 → 分类键。未知前缀、无前缀 → `internal`（工程内部）。"""
    m = RE_PREFIX.match(subject or "")
    if not m:
        return "internal"
    return _PREFIX_TO_CATEGORY.get(m.group(1).lower(), "internal")


def is_noise(subject: str) -> bool:
    """归档镜像与自动提交：`journal:` 一律是噪声；`session:` 里只有「自动归档」那种才是。

    `session: 加一课` 是正经会话记录，不能当噪声吞掉。
    """
    m = RE_PREFIX.match((subject or "").strip())
    if not m:
        return False
    prefix = m.group(1).lower()
    if prefix == "journal":
        return True
    return prefix == "session" and "自动归档" in subject


def group_commits(commits: list[dict]) -> tuple[dict[str, list[dict]], int]:
    """按分类分组；返回 (分组, 噪声条数)。噪声只在统计行里报数量，不逐条列出。"""
    groups: dict[str, list[dict]] = {key: [] for key in CATEGORY_ORDER}
    noise = 0
    for c in commits:
        if is_noise(c.get("subject", "")):
            noise += 1
            continue
        groups[classify(c.get("subject", ""))].append(c)
    return groups, noise


def render_category_sections(commits: list[dict], level: int = 2) -> str:
    """分类小标题 + 条目；空分类不打印。notes 用 `##`，CHANGELOG 的 tag 节里用 `###`。"""
    groups, _ = group_commits(commits)
    hashes = "#" * level
    blocks: list[str] = []
    for key in CATEGORY_ORDER:
        items = groups[key]
        if not items:
            continue
        lines = [f"{hashes} {CATEGORY_TITLES[key]}"]
        lines += [f"- {c['subject']}（`{c['sha']}`）" for c in items]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- 纯函数：统计与资产名

def stats_at(tag: str) -> dict:
    """`{"lessons": N, "sources": M, "pages": P?}` —— 数的是**该 tag 的树**，不是工作区。

    `pages` 只在 `dist/<tag>-build.json`（artifact 写的构建回执）存在时给出：
    没有回执就没有可信的页数，宁可缺字段也不猜。
    """
    tree = _git("ls-tree", "-r", "--name-only", tag, "--", "lessons/")
    lessons = sum(1 for line in tree.splitlines() if line.strip().endswith(".md"))

    citations = _git("show", f"{tag}:sources/citations.yaml", check=False)
    sources = sum(1 for line in citations.splitlines() if line.startswith("- id:"))

    stats = {"lessons": lessons, "sources": sources}
    receipt = DIST / f"{tag}-build.json"
    if receipt.is_file():
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data.get("pages"), int):
            stats["pages"] = data["pages"]
    return stats


def tag_has_site(tag: str) -> bool:
    """该 tag 的树里有没有 `scripts/build_site.py`（v0.2-orient / v0.3-core / v1.0-tutorial 没有）。"""
    return bool(_git("ls-tree", "--name-only", tag, "--", SITE_JSON_NAME, check=False).strip())


def asset_name(tag: str) -> str:
    return f"hermesusage-site-{tag}.zip"


def sha256sums_line(digest: str, name: str) -> str:
    """GNU sha256sum 格式：**两个空格**分隔（`sha256sum -c` 认这个格式）。"""
    return f"{digest}  {name}"


def should_prerelease(tag: str) -> bool:
    """主版本 == 0 → 预发布（社区对 0.x 的通行口径）。"""
    m = re.match(r"^v?(\d+)", tag or "")
    return bool(m) and int(m.group(1)) == 0


def is_top_tag(tag: str) -> bool:
    """是不是版本最高的那个 tag —— 只有它显式 `make_latest: "true"`，免得 GitHub 按 semver 猜错。"""
    ordered = tag_order(all_tags())
    return bool(ordered) and ordered[-1] == tag


# --------------------------------------------------------------------------- 纯函数：发布说明与 CHANGELOG

def notes_content_line(stats: dict, noise: int) -> str:
    """模板里的 `<N> 课 · 出处 <M> 条[ · 站点 <P> 页]`（噪声条数只能报在统计行上）。"""
    parts = [f"{stats.get('lessons', 0)} 课", f"出处 {stats.get('sources', 0)} 条"]
    if isinstance(stats.get("pages"), int):
        parts.append(f"站点 {stats['pages']} 页")
    line = " · ".join(parts)
    if noise:
        line += f"（另有 {noise} 条归档/自动提交未列出）"
    return line


def build_notes(tag: str, prev: str | None, data: dict) -> str:
    """按计划里逐字给定的模板渲染发布说明。

    `data` 由 `collect_data()` 组装：`{"date", "commits", "stats"}`；缺项时回退到现场读 git，
    所以单测可以直接塞字典，不必先跑一遍 git。
    """
    stats = dict(data.get("stats") or {})
    commits = list(data.get("commits") or [])
    date = data.get("date") or tag_date(tag)
    groups, noise = group_commits(commits)
    listed = sum(len(items) for items in groups.values())

    lines = [
        f"# {release_title(tag)}",
        "",
        f"**发布日期**：{date}",
        f"**本版内容**：{notes_content_line(stats, noise)}",
        f"**完整变更日志**：{GH_URL}/blob/{tag}/CHANGELOG.md",
    ]
    if prev:
        lines.append(f"**对比**：{GH_URL}/compare/{prev}...{tag}")

    sections = render_category_sections(commits, level=2) if listed else "本版提交均为归档 / 自动提交，无逐条列出项。"

    footer = [
        "---",
        f"本发布说明由 `python scripts/release.py notes --tag {tag}` 生成（提交前缀 → Keep a Changelog 分类）。",
    ]
    if tag_has_site(tag):
        footer.append(f"资产：`{asset_name(tag)}`，校验 `sha256sum -c SHA256SUMS`")
    else:
        footer.append("本版尚未有站点，无构建资产")
    footer.append(f"站点在线版：{SITE_URL}")

    return "\n".join(lines) + "\n\n" + sections + "\n\n" + "\n".join(footer) + "\n"


def collect_data(tag: str, prev: str | None) -> dict:
    if not tag_exists(tag):
        raise ReleaseError(f"未知 tag：{tag}（本地 `git tag -l` 里没有它）")
    return {
        "tag": tag,
        "prev": prev,
        "date": tag_date(tag),
        "commits": commits_in(prev, tag),
        "stats": stats_at(tag),
    }


CHANGELOG_HEADER = f"""# 更新日志

本文件由脚本生成，**不要手改** —— 内容是 `python scripts/release.py changelog --write`
从 git 提交记录（提交前缀 → Keep a Changelog 分类）现算的；手改会在下一次
`python scripts/release.py changelog --check` 被判为「与 git 不一致」。

格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。
`journal:` 提交与 `session: 自动归档 …` 是归档/自动提交噪声，只在发布说明的统计行里计数，不逐条列出。
"""


def changelog_section(tag: str | None, date: str | None, commits: list[dict]) -> str:
    """一个版本节：`## [<tag>] - <YYYY-MM-DD>` + 分类小标题；没有条目写「无」。"""
    head = f"## [{tag}]" + (f" - {date}" if date else "")
    body = render_category_sections(commits, level=3)
    return f"{head}\n\n{body}" if body else f"{head}\n\n无"


def render_changelog(releases: list[dict], unreleased: list[dict] | None = None) -> str:
    """Keep a Changelog 1.1.0 正文：头部固定，**倒序**（最新 tag 在最上）。

    `releases` 按 tag 升序传入，函数内部反转；`unreleased` 是最后一个 tag 之后的提交
    （传 None 表示不渲染这一节）。
    """
    parts = [CHANGELOG_HEADER.rstrip("\n")]
    if unreleased is not None:
        parts.append(changelog_section("未发布", None, unreleased))
    for rel in reversed(list(releases)):
        parts.append(changelog_section(rel["tag"], rel.get("date"), list(rel.get("commits") or [])))
    return "\n\n".join(parts) + "\n"


def changelog_data() -> tuple[list[dict], list[dict]]:
    """(升序的 releases, 未发布提交)。releases 每项含 tag/date/commits。"""
    ordered = tag_order(all_tags())
    releases: list[dict] = []
    prev: str | None = None
    for tag in ordered:
        releases.append({"tag": tag, "date": tag_date(tag), "commits": commits_in(prev, tag)})
        prev = tag
    unreleased = commits_in(prev, "HEAD") if prev else commits_in(None, "HEAD")
    return releases, unreleased


def changelog_text() -> str:
    releases, unreleased = changelog_data()
    return render_changelog(releases, unreleased)


def first_difference(want: str, have: str) -> tuple[int, str, str]:
    """首个不同行：返回 (行号 1-based, 生成侧, 磁盘侧)；完全一致时行号为 0。"""
    wl, hl = want.splitlines(), have.splitlines()
    for i in range(max(len(wl), len(hl))):
        a = wl[i] if i < len(wl) else "<文件结束>"
        b = hl[i] if i < len(hl) else "<文件结束>"
        if a != b:
            return i + 1, a, b
    return 0, "", ""


# --------------------------------------------------------------------------- 纯函数：确定性 zip

def zip_dir(src: Path, dest: Path, root: str) -> None:
    """把 `src` 打成确定性的 zip：条目按名排序、时间戳固定、权限固定。

    `root` 是包内的顶层目录名（本项目用 `site`，解压后得到一个能直接托管的目录）。
    同一个目录打两次，两个文件的字节必须相同 —— 这是 `audit --check` 的前提。
    """
    src, dest = Path(src), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    entries = sorted(src.rglob("*"), key=lambda p: p.relative_to(src).as_posix())
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=ZIP_LEVEL) as zf:
        for path in entries:
            rel = path.relative_to(src).as_posix()
            arc = f"{root}/{rel}" if root else rel
            is_dir = path.is_dir()
            info = zipfile.ZipInfo(arc + ("/" if is_dir else ""), date_time=ZIP_TIME)
            # create_system=3（Unix）+ 固定 mode：不这么写，Windows 与 Linux 打的包字节不同
            info.create_system = 3
            info.external_attr = (0o40755 if is_dir else 0o100644) << 16
            if is_dir:
                info.external_attr |= 0x10
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, b"")
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, path.read_bytes())


def normalize_build_clock(site: Path, stamp_iso: str, stamp_date: str) -> list[str]:
    """把产物里的「构建时刻」换成 tag 的固定时间戳，让 zip 只由 tag 决定。

    只动三处（该 tag 树的 build_site.py 会写的那三处），课程正文里的日期一律不碰：
      1. `site/data/index.json` 的顶层 `generated`；
      2. `site/data/manifest.json` 的顶层 `built_at`；
      3. `sitemap.xml` 里等于「构建当天」的 `lastmod`（没有 `updated` 的课程的兜底值）。

    返回实际改动的文件清单（写进构建回执，便于人工复核）。
    """
    site = Path(site)
    changed: list[str] = []
    clocks: set[str] = set()

    for rel, key in BUILD_CLOCK_FIELDS:
        path = site / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        value = data.get(key)
        if not isinstance(value, str):
            continue
        clocks |= set(RE_ISO_TS.findall(value))
        data[key] = stamp_iso
        write_json(path, data)
        changed.append(f"{rel}#{key}")

    if not clocks:
        return changed

    build_dates = {ts[:10] for ts in clocks}
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:          # 图片等二进制产物：原样保留
            continue
        rel = path.relative_to(site).as_posix()
        new = text
        for ts in clocks:
            new = new.replace(ts, stamp_iso)
        for day in build_dates:
            new = new.replace(f"<lastmod>{day}</lastmod>", f"<lastmod>{stamp_date}</lastmod>")
        if new != text:
            path.write_bytes(new.encode("utf-8"))
            if rel not in changed:
                changed.append(rel)
    return changed


def write_sha256sums(out_dir: Path, name: str, digest: str) -> Path:
    """把一条记录并进 `out_dir/SHA256SUMS`（按 name 排序、GNU 两空格格式、UTF-8+LF）。

    为什么是「并进」而不是「覆盖」：`audit --check` 要拿它跟**每个** tag 的远端资产对账，
    覆盖式的话跑完 10 个 tag 只剩最后一行，前面 9 个就无从核对了。
    """
    path = Path(out_dir) / "SHA256SUMS"
    lines: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest_part, _, rest = line.partition("  ")
            key = rest.strip()
            if key:
                lines[key] = digest_part.strip()
    lines[name] = digest
    write_text(path, "".join(sha256sums_line(lines[n], n) + "\n" for n in sorted(lines)))
    return path


def read_sha256sums(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest_part, _, rest = line.partition("  ")
        key = rest.strip()
        if key:
            out[key] = digest_part.strip()
    return out


# --------------------------------------------------------------------------- 纯函数：请求体

def draft_payload(tag: str, name: str, body: str, prerelease: bool = False, latest: bool = False) -> dict:
    """新建草稿 release 的请求体。

    `draft: True` 是硬要求：资产必须传完再发布（顺序反了会留下一个没有资产的「已发布」版本）。
    `make_latest` 是**字符串**（GitHub 的 schema 要 `"true"`/`"false"`，传布尔会被拒）。
    """
    return {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": True,
        "prerelease": bool(prerelease),
        "make_latest": "true" if latest else "false",
    }


def update_payload(name: str, body: str, prerelease: bool | None = None, latest: bool | None = None) -> dict:
    """更新已有 release 的请求体；不可变发布时调用方只传 name/body（其余字段锁死）。

    ⚠️ **草稿上不许带 `make_latest`**：实测（2026-09-18）对一个草稿 PATCH
    `make_latest: "true"` 会被拒 —— HTTP 422 `Latest release cannot be draft or prerelease.`
    「是不是 latest」这件事只在该草稿**转正的那一刻**才有意义，所以它归 `publish_payload`。
    """
    payload: dict = {"name": name, "body": body}
    if prerelease is not None:
        payload["prerelease"] = bool(prerelease)
    if latest is not None:
        payload["make_latest"] = "true" if latest else "false"
    return payload


def publish_payload(latest: bool | None = None, tag: str | None = None) -> dict:
    """把草稿转正：`draft: false`（+ 可选 `make_latest`、`tag_name`），别的字段一个都不碰。

    `make_latest` 必须在这一步给：草稿阶段给的会被 422 拒（见 `update_payload`），
    而不给又会让 GitHub 按 semver 去猜我们这种 `v3.3-topbar` 形状的 tag —— 猜不对。

    `tag_name` 也必须在这一步**再给一次**：草稿在 GitHub 上先是挂在 `untagged-<hash>`
    这个占位名下（`html_url` 能看出来），实测有一个**搁置了几十分钟的旧草稿**转正后
    占位名被留了下来 —— release 建出来了，但 `tag_name` 仍是 `untagged-e51889b73d0a…`，
    既对不上 tag、也让 `audit` 判它「缺 release」。转正时显式带上 tag 名，这种状态就不会出现。
    """
    payload: dict = {"draft": False}
    if tag is not None:
        payload["tag_name"] = tag
    if latest is not None:
        payload["make_latest"] = "true" if latest else "false"
    return payload


def merge_body(generated: str, original: str) -> str:
    """保留原文：新 body = 生成说明 + 分隔线 + `## 原始发布说明` + 原 body。

    原文是读者面向的内容（手写的背景/迁移说明），不能被脚本的一次更新抹掉。
    """
    original = original or ""
    if not original.strip():
        return generated
    return generated.rstrip("\n") + "\n\n---\n\n## 原始发布说明\n\n" + original.lstrip("\n").rstrip("\n") + "\n"


def asset_plan(tag: str) -> list[tuple[str, str, int]]:
    """要不要上传、上传什么：(显示名, Content-Type, 字节数)。**不写任何文件**（dry-run 用它）。"""
    zip_path = DIST / asset_name(tag)
    if not zip_path.is_file():
        return []
    line = sha256sums_line(sha256_file(zip_path), zip_path.name) + "\n"
    return [
        (str(zip_path), "application/zip", zip_path.stat().st_size),
        (str(DIST / f"{tag}-SHA256SUMS"), "application/octet-stream", len(line.encode("utf-8"))),
    ]


def materialize_assets(tag: str) -> list[tuple[Path, str]]:
    """真正上传时用：写 `dist/<tag>-SHA256SUMS`（只含本版一行）并返回 [(文件, Content-Type)]。

    为什么 SHA256SUMS 只写**这一版**的资产行 —— 用户把 zip + SHA256SUMS 放进一个目录跑
    `sha256sum -c SHA256SUMS` 必须能过；把 `dist/SHA256SUMS`（累积清单，audit 用）原样传上去
    会因为缺其它版本的文件而报 FAILED。
    """
    zip_path = DIST / asset_name(tag)
    if not zip_path.is_file():
        return []
    sums = DIST / f"{tag}-SHA256SUMS"
    write_text(sums, sha256sums_line(sha256_file(zip_path), zip_path.name) + "\n")
    return [(zip_path, "application/zip"), (sums, "application/octet-stream")]


# --------------------------------------------------------------------------- git 仓库身份

def repo_slug() -> str | None:
    """`GH_REPO` 环境变量优先，否则从 `git remote get-url origin` 解析 `owner/name`。"""
    env = (os.environ.get("GH_REPO") or "").strip()
    if env:
        if re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", env):
            return env
        return None
    remote = _git("remote", "get-url", "origin", check=False).strip()
    m = re.search(r"github\.com[/:]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", remote)
    return f"{m.group(1)}/{m.group(2)}" if m else None


# --------------------------------------------------------------------------- HTTP

def _request(method: str, url: str, token: str, body: bytes | None = None,
             content_type: str = "application/json", timeout: float = 180.0) -> tuple[int, str]:
    """返回 (状态码, 响应文本)。传输层故障抛 ReleaseError；HTTP 错误码**不抛**（调用方要区分 404）。"""
    req = Request(url, method=method, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": UA,
        "Content-Type": content_type,
    })
    # ProxyHandler({}) 必须有：本机默认代理挂着，走系统代理会 schannel handshake 失败
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        e.close()
        return e.code, detail
    except URLError as e:
        raise ReleaseError(f"网络请求失败：{method} {url} —— {e.reason}") from None


def _api(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    status, text = _request(method, API + path, token, body)
    data: object = {}
    if text.strip():
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"raw": text[:2000]}
    return status, data


def upload_asset(repo: str, token: str, release_id: int, path: Path, content_type: str) -> dict:
    url = f"{UPLOADS}/repos/{repo}/releases/{release_id}/assets?name={quote(Path(path).name)}"
    status, text = _request("POST", url, token, Path(path).read_bytes(), content_type)
    if status not in (200, 201):
        raise ReleaseError(f"上传资产失败（HTTP {status}）：{path.name} —— {text[:500]}")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def fetch_releases(repo: str, token: str, per_page: int = 100, max_pages: int = 5) -> list[dict]:
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        status, data = _api("GET", f"/repos/{repo}/releases?per_page={per_page}&page={page}", token)
        if status != 200:
            raise ReleaseError(f"拉取 releases 失败（HTTP {status}）：{str(data)[:500]}")
        if not isinstance(data, list) or not data:
            break
        out += data
        if len(data) < per_page:
            break
    return out


def releases_for_tag(releases: list[dict], tag: str) -> tuple[dict | None, list[dict]]:
    """从一份 release 列表里挑出该 tag 的「正主」与「多余草稿」。

    「正主」优先**已发布**的那条（`draft == false`）；没有已发布的，取 id 最大的草稿
    （最后一次尝试建的）。返回 `(正主 | None, 多余草稿列表)`，多余草稿按 id 升序。

    为什么必须自己挑、不能用 `GET /releases/tags/<tag>`：那个端点**看不到草稿**（草稿在
    正式发布前不与 tag 关联），而带令牌的 `GET /releases` 列表**能看到**。2026-09-18 实测：
    v1.4-content 上传时 TLS 断，重跑 `create` 查不到那个草稿，于是又建一个 —— 一次事故
    留下两个谁也看不见的空草稿。残骸只能从列表里找回来。
    """
    mine = [r for r in releases if isinstance(r, dict) and r.get("tag_name") == tag]
    published = [r for r in mine if not r.get("draft")]
    if published:
        # 已发布的可能不止一条（历史上手工建过）：取 id 最大的一条当正主，其余如实报出来
        published.sort(key=lambda r: r.get("id") or 0)
        return published[-1], [r for r in mine if r is not published[-1]]
    drafts = sorted(mine, key=lambda r: r.get("id") or 0)
    if not drafts:
        return None, []
    return drafts[-1], drafts[:-1]


def fetch_latest_tag(repo: str, token: str) -> str | None:
    status, data = _api("GET", f"/repos/{repo}/releases/latest", token)
    if status == 200 and isinstance(data, dict):
        return data.get("tag_name")
    return None


def delete_release(repo: str, token: str, release_id: int, quiet: bool = False,
                   label: str = "草稿") -> bool:
    """删掉一条 release；成功返回 True。**只用于回滚本次新建的草稿、或清掉同 tag 的历史残骸。**

    为什么建草稿的脚本还得会删草稿：上传中断（本机 TLS 常年会抖）会留下一个
    **看不见的孤儿草稿** —— 草稿既不出现在 `GET /releases` 列表里，也不能用
    `GET /releases/tags/<tag>` 找到（草稿在正式发布前不与那个 tag 关联）。
    实测踩过（2026-09-18）：v1.4-content 上传时 `SSL: UNEXPECTED_EOF_WHILE_READING`，
    重跑 `create` 查不到那个草稿，于是又建了一个 —— 一次事故留下两个空壳。
    所以「建了草稿之后任何一步失败」就当场回滚，别留给下一个人。
    """
    status, detail = _api("DELETE", f"/repos/{repo}/releases/{release_id}", token)
    if status in (204, 200):
        info(f"已删除{label} release（id {release_id}）", quiet)
        return True
    info(f"删除失败：{label} release（id {release_id}）返回 HTTP {status} —— "
         f"请手工删：DELETE {API}/repos/{repo}/releases/{release_id}"
         f"（或在仓库 Releases 页的 Drafts 里删）", quiet)
    return False


# --------------------------------------------------------------------------- 构建资产

def build_artifact(tag: str, out_dir: Path, quiet: bool = False) -> dict:
    """`git archive` 取 tag 的树 → 跑**该树的** build_site.py → 确定性 zip + SHA256SUMS + 回执。

    没有站点的 tag（v0.2-orient / v0.3-core / v1.0-tutorial）直接在第一步返回：不建目录、不写文件。
    """
    if not tag_exists(tag):
        raise ReleaseError(f"未知 tag：{tag}（本地 `git tag -l` 里没有它）")
    if not tag_has_site(tag):
        return {"tag": tag, "skipped": True, "reason": "no-site",
                "message": f"{tag} 尚无站点（该版本还没有 web/ 与 build_site.py），不产出资产"}

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)

    stamp_iso = _git("log", "-1", "--format=%cI", f"{tag}^{{commit}}").strip()
    asset = asset_name(tag)
    zip_path = out_dir / asset

    with tempfile.TemporaryDirectory(prefix="hermesusage-release-") as tmp:
        tree = Path(tmp)
        proc = subprocess.Popen(["git", "archive", "--format=tar", tag], cwd=str(REPO),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
            if sys.version_info >= (3, 12):
                tf.extractall(tree, filter="data")
            else:
                tf.extractall(tree)
        _, tar_err = proc.communicate()
        if proc.returncode != 0:
            raise ReleaseError(f"git archive 失败（{tag}，退出码 {proc.returncode}）："
                               f"{(tar_err or b'').decode('utf-8', 'replace')[:500]}")

        if not (tree / SITE_JSON_NAME).is_file():
            raise ReleaseError(f"{tag} 的树里没有 {SITE_JSON_NAME}，无法构建站点")

        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        run = subprocess.run([sys.executable, SITE_JSON_NAME], cwd=str(tree), capture_output=True,
                             text=True, encoding="utf-8", errors="replace", env=env, timeout=1800)
        if run.returncode != 0:
            print(f"构建失败（{tag}，{SITE_JSON_NAME} 退出码 {run.returncode}）原始 stderr：", file=sys.stderr)
            print((run.stderr or "").strip() or "(stderr 为空)", file=sys.stderr)
            raise ReleaseError(f"{tag} 的站点构建失败")

        site = tree / "site"
        if not site.is_dir():
            raise ReleaseError(f"{tag} 构建成功但没有产出 site/ 目录")

        normalized = normalize_build_clock(site, stamp_iso, stamp_iso[:10])
        files = [p for p in site.rglob("*") if p.is_file()]
        pages = len(list(site.rglob("*.html")))
        site_bytes = sum(p.stat().st_size for p in files)

        zip_dir(site, zip_path, root="site")
        digest = sha256_file(zip_path)
        sums = write_sha256sums(out_dir, asset, digest)

        receipt = {
            "tag": tag,
            "commit": commit_sha(tag),
            "date": tag_date(tag),
            "lessons": stats_at(tag).get("lessons", 0),
            "pages": pages,
            "files": len(files),
            "bytes": site_bytes,
            "asset": asset,
            "asset_bytes": zip_path.stat().st_size,
            "sha256": digest,
            "sha256sums": sums.name,
            "deterministic_stamp": stamp_iso,
            "normalized": normalized,
        }
        write_json(DIST / f"{tag}-build.json", receipt)
        return {"tag": tag, "skipped": False, "receipt": receipt, "path": str(zip_path),
                "sha256sums": str(sums), "build_stdout": (run.stdout or "").strip(), "quiet": quiet}


def ensure_artifact(tag: str, quiet: bool = False) -> str | None:
    """确保本地有该 tag 的 zip（CI 只跑 `create`，没有单独的 artifact 步骤）。"""
    if not tag_has_site(tag):
        return None
    path = DIST / asset_name(tag)
    if path.is_file():
        return str(path)
    info(f"本地没有 {path.name}，先构建资产（等于跑一次 artifact --tag {tag}）", quiet)
    result = build_artifact(tag, DIST, quiet=quiet)
    return result.get("path")


# --------------------------------------------------------------------------- 输出

def info(message: str, quiet: bool = False) -> None:
    """过程性提示；`--quiet` 下不输出（主结果不受影响）。"""
    if not quiet:
        print(message)


# --------------------------------------------------------------------------- 子命令

def cmd_notes(args: argparse.Namespace) -> int:
    tag = args.tag
    if not tag_exists(tag):
        raise ReleaseError(f"未知 tag：{tag}（本地 `git tag -l` 里没有它）")
    prev = args.prev if args.prev is not None else previous_tag(tag)
    if prev is not None and not tag_exists(prev):
        raise ReleaseError(f"--prev 指定的 tag 不存在：{prev}")
    data = collect_data(tag, prev)
    body = build_notes(tag, prev, data)
    if args.json:
        groups, noise = group_commits(data["commits"])
        print(json.dumps({
            "tag": tag, "prev": prev, "title": release_title(tag), "date": data["date"],
            "stats": data["stats"], "noise": noise,
            "commits": data["commits"],
            "categories": {k: v for k, v in groups.items() if v},
            "body": body,
        }, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(body)
    return 0


def cmd_changelog(args: argparse.Namespace) -> int:
    if args.write:
        text = changelog_text()
        write_text(CHANGELOG, text)
        releases, unreleased = changelog_data()
        info(f"已写 {CHANGELOG.name}：{len(releases)} 个 tag 节"
             f"（倒序）+ 未发布 {len(unreleased)} 条提交", args.quiet)
        return 0

    if not CHANGELOG.is_file():
        print(f"{CHANGELOG.name} 不存在：先跑 `python scripts/release.py changelog --write` 生成。",
              file=sys.stderr)
        return 1
    want = changelog_text()
    have_bytes = CHANGELOG.read_bytes()
    if have_bytes == want.encode("utf-8"):
        releases, unreleased = changelog_data()
        info(f"{CHANGELOG.name} 与 git 记录一致（{len(releases)} 个 tag 节 + 未发布 {len(unreleased)} 条提交）",
             args.quiet)
        return 0
    have = have_bytes.decode("utf-8", "replace")
    lineno, want_line, have_line = first_difference(want, have)
    if lineno == 0:
        # 逐行相同但字节不同（多为 CRLF/BOM）
        print(f"{CHANGELOG.name} 与 git 记录不一致：逐行相同，但字节不同"
              f"（多半是换行或编码问题，应 UTF-8 + LF）", file=sys.stderr)
        return 1
    print(f"{CHANGELOG.name} 与 git 记录不一致：首个不同行在第 {lineno} 行", file=sys.stderr)
    print(f"  生成（脚本算出来）：{want_line}", file=sys.stderr)
    print(f"  磁盘（当前文件）  ：{have_line}", file=sys.stderr)
    print(f"跑 `python scripts/release.py changelog --write` 覆盖，或改回 git 记录里的事实。", file=sys.stderr)
    return 1


def cmd_artifact(args: argparse.Namespace) -> int:
    out_dir = Path(args.out) if args.out else DIST
    result = build_artifact(args.tag, out_dir, quiet=args.quiet)
    if result.get("skipped"):
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["message"])
        return 0
    receipt = result["receipt"]
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        info(f"已构建 {receipt['asset']}", args.quiet)
        info(f"  站点：{receipt['lessons']} 课 / {receipt['pages']} 页 / {receipt['files']} 文件 / "
             f"{receipt['bytes']} 字节", args.quiet)
        info(f"  zip ：{result['path']}（{receipt['asset_bytes']} 字节）", args.quiet)
        info(f"  sha256：{receipt['sha256']}", args.quiet)
        info(f"  清单：{result['sha256sums']}（GNU 两空格格式）", args.quiet)
        info(f"  回执：{DIST / (args.tag + '-build.json')}", args.quiet)
    return 0


def _planned_requests(tag: str, repo: str, title: str, body: str, prerelease: bool,
                      latest: bool, body_only: bool, plan: list[tuple[str, str, int]],
                      has_zip: bool) -> list[str]:
    """dry-run 的请求清单（方法 / URL / body 摘要 / 上传的文件名与字节数）。"""
    base = f"{API}/repos/{repo}/releases"
    draft = dict(draft_payload(tag, title, body, prerelease, latest))
    draft["body"] = f"<发布说明 {len(body)} 字符>"
    merged_len = len(merge_body(body, "<原 body，逐字保留>"))
    out = [
        f"[dry-run] tag={tag} repo={repo} prerelease={str(prerelease).lower()} "
        f"make_latest={'true' if latest else 'false'}",
        "（不解析令牌、不发任何请求；没网也能跑）",
        f"（发布说明 {len(body)} 字符，{len(body.splitlines())} 行；完整内容："
        f"python scripts/release.py notes --tag {tag}）",
        "",
        f"1) GET  {base}/tags/{tag}",
        f"   不存在 → POST {base}",
        f"      body: {json.dumps(draft, ensure_ascii=False)}",
        f"   已存在 → PATCH {base}/{{id}}",
        f"      body: {{\"name\": \"{title}\", \"body\": \"<生成说明 + 「## 原始发布说明」+ 原 body，"
        f"{merged_len} 字符>\"}}",
        "      immutable=true 时只发 name/body（资产与 tag 锁定，不动）",
        "",
    ]
    if body_only:
        out += ["2) --body-only：跳过资产上传（zip / SHA256SUMS 都不碰）", ""]
    else:
        out += [f"2) GET  {base}/{{id}}/assets",
                f"   DELETE {base}/assets/{{旧资产 id}}   # 仅同名资产且 release 非不可变时"]
        if plan:
            for name, ctype, size in plan:
                out.append(f"   POST {UPLOADS}/repos/{repo}/releases/{{id}}/assets?name={Path(name).name}")
                out.append(f"        Content-Type: {ctype}  body: {size} 字节（本地 {name}）")
        elif has_zip:
            out.append("   无资产可传：本地没有可上传文件")
        else:
            out.append(f"   本地还没有 {asset_name(tag)}：实跑时会先跑一次 artifact（离线构建，不触网）")
        out.append("")
    out += [f"3) PATCH {base}/{{id}}",
            f"      body: {json.dumps(publish_payload(), ensure_ascii=False)}",
            "      （发布前是草稿：资产传完才转正）"]
    return out


def cmd_create(args: argparse.Namespace) -> int:
    tag = args.tag
    if not tag_exists(tag):
        raise ReleaseError(f"未知 tag：{tag}（本地 `git tag -l` 里没有它）")
    repo = repo_slug()
    if not repo:
        raise ReleaseError("解析不出 owner/name：设 `GH_REPO=owner/name` 或修好 `git remote get-url origin`")

    prev = previous_tag(tag)
    data = collect_data(tag, prev)
    body = build_notes(tag, prev, data)
    title = release_title(tag)
    prerelease = args.prerelease if args.prerelease is not None else should_prerelease(tag)
    latest = args.latest if args.latest is not None else is_top_tag(tag)

    zip_path = DIST / asset_name(tag)
    has_zip = zip_path.is_file()

    if args.dry_run:
        plan = [] if args.body_only else asset_plan(tag)
        for line in _planned_requests(tag, repo, title, body, prerelease, latest,
                                      args.body_only, plan, has_zip):
            print(line)
        return 0

    token = get_token()
    if not token:
        raise ReleaseError("没找到令牌（GITHUB_TOKEN / git credential 都没有），无法建 release")

    # 列表（带令牌）能看到草稿；`GET /releases/tags/<tag>` 看不到 —— 见 releases_for_tag
    existing, extra_drafts = releases_for_tag(fetch_releases(repo, token), tag)
    immutable = False
    created_now = False
    if existing is None:
        payload = draft_payload(tag, title, body, prerelease, latest)
        status, release = _api("POST", f"/repos/{repo}/releases", token, payload)
        if status not in (200, 201) or not isinstance(release, dict):
            raise ReleaseError(f"建 release 失败（HTTP {status}）：{str(release)[:500]}")
        created_now = True
        info(f"已建草稿 release：{release.get('html_url')}", args.quiet)
    else:
        release = existing
        immutable = bool(release.get("immutable"))
        is_draft = bool(release.get("draft"))
        if is_draft:
            info(f"沿用上次留下的草稿 release（id {release['id']}）：{release.get('html_url')}", args.quiet)
        new_body = merge_body(body, str(release.get("body") or ""))
        # 草稿上不能带 make_latest（422），它归 publish_payload；不可变 release 只允许改 name/body
        payload = update_payload(title, new_body,
                                 None if immutable else prerelease,
                                 None if (immutable or is_draft) else latest)
        status, updated = _api("PATCH", f"/repos/{repo}/releases/{release['id']}", token, payload)
        if status not in (200, 201):
            raise ReleaseError(f"更新 release 失败（HTTP {status}）：{str(updated)[:500]}")
        release = updated if isinstance(updated, dict) else release
        info(f"已更新 release 说明（保留原文为「## 原始发布说明」）：{release.get('html_url')}", args.quiet)
        if immutable:
            info("该 release 已开启不可变发布（immutable=true）：只更新 name/body，"
                 "资产与 tag 已锁定，本次不动。", args.quiet)

    release_id = release["id"]

    # 从这一刻起，远端已经有「我们这次建出来的东西」了：任何一步失败都要回滚，
    # 否则会留下看不见的孤儿草稿（见 delete_release 的说明）。
    try:
        if args.body_only:
            info("--body-only：跳过资产上传。", args.quiet)
        elif not tag_has_site(tag):
            info(f"{tag} 尚无站点（该版本还没有 web/ 与 build_site.py），不附资产。", args.quiet)
        else:
            if not zip_path.is_file():
                ensure_artifact(tag, quiet=args.quiet)
            files = materialize_assets(tag)
            existing_status, existing = _api("GET", f"/repos/{repo}/releases/{release_id}/assets?per_page=100", token)
            existing_assets = existing if isinstance(existing, list) else []
            by_name = {a.get("name"): a for a in existing_assets if isinstance(a, dict)}
            for path, ctype in files:
                old = by_name.get(path.name)
                if old:
                    if immutable:
                        info(f"资产 {path.name} 已存在，且 release 不可变：跳过（不删不改）。", args.quiet)
                        continue
                    dstatus, detail = _api("DELETE", f"/repos/{repo}/releases/assets/{old.get('id')}", token)
                    if dstatus not in (204, 200):
                        raise ReleaseError(f"删除旧资产失败（HTTP {dstatus}）：{path.name} —— {str(detail)[:300]}")
                    info(f"已删除同名旧资产：{path.name}", args.quiet)
                uploaded = upload_asset(repo, token, release_id, path, ctype)
                info(f"已上传资产：{path.name}（{path.stat().st_size} 字节）"
                     f"{' → ' + str(uploaded.get('browser_download_url')) if uploaded.get('browser_download_url') else ''}",
                     args.quiet)

        status, published = _api("PATCH", f"/repos/{repo}/releases/{release_id}", token,
                                 publish_payload(None if immutable else latest,
                                                 None if immutable else tag))
        if status not in (200, 201):
            raise ReleaseError(f"发布 release 失败（HTTP {status}）：{str(published)[:500]}")
        if isinstance(published, dict):
            release = published
        info(f"已发布：{release.get('html_url')}", args.quiet)
    except BaseException:
        # 只回滚「本次新建的草稿」；已存在的 release 一个字节都不动（正文/资产是别人的东西）。
        if created_now:
            delete_release(repo, token, release_id, quiet=args.quiet,
                           label="本次新建的草稿（失败回滚）")
        raise

    # 顺手清掉同 tag 的多余草稿：都是这个脚本过去崩在半路留下的空壳（见 releases_for_tag）
    for draft in extra_drafts:
        delete_release(repo, token, draft["id"], quiet=args.quiet,
                       label="同 tag 的多余草稿")

    # 读回核对（远端状态才是事实）
    vstatus, verified = _api("GET", f"/repos/{repo}/releases/tags/{tag}", token)
    if vstatus == 200 and isinstance(verified, dict):
        assets = verified.get("assets") or []
        info(f"核验：draft={verified.get('draft')} prerelease={verified.get('prerelease')} "
             f"immutable={verified.get('immutable')} 资产 {len(assets)} 个"
             + ("：" + ", ".join(a.get("name", "?") for a in assets) if assets else ""), args.quiet)
    elif vstatus != 200:
        # `GET /releases/tags/<tag>` 看不到草稿；走到这里还查不到，说明这个 release 的 tag 没关联上
        print(f"⚠️ 发布后按 tag 查不到这条 release（HTTP {vstatus}）：tag_name 可能仍是 "
              f"`untagged-…` 占位名（GitHub 在搁置太久的旧草稿上有这个行为）。\n"
              f"   现在要做的：删掉这条 release 再重跑一次 `python scripts/release.py create --tag {tag}`"
              f"（删：DELETE {API}/repos/{repo}/releases/{release_id}）", file=sys.stderr)
        return 2
    return 0


def _local_digest(tag: str, sums: dict[str, str]) -> tuple[str | None, str]:
    """本地该 tag 的 zip 指纹：优先 SHA256SUMS 行，退回构建回执。返回 (digest, 来源)。"""
    name = asset_name(tag)
    if sums.get(name):
        return sums[name], "SHA256SUMS"
    receipt = DIST / f"{tag}-build.json"
    if receipt.is_file():
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data.get("sha256"), str):
            return data["sha256"], f"dist/{tag}-build.json"
    return None, ""


def audit_table(rows: list[dict]) -> str:
    headers = ("tag", "有 release", "资产", "本地 sha256 vs 远端", "immutable", "prerelease", "latest", "说明")
    columns = ["tag", "release", "assets", "digest", "immutable", "prerelease", "latest", "note"]
    widths = [display_width(h) for h in headers]
    for row in rows:
        for i, key in enumerate(columns):
            widths[i] = max(widths[i], display_width(str(row.get(key, ""))))
    out = ["  ".join(pad(h, widths[i]) for i, h in enumerate(headers)).rstrip(),
           "  ".join("-" * widths[i] for i in range(len(headers)))]
    for row in rows:
        out.append("  ".join(pad(str(row.get(k, "")), widths[i]) for i, k in enumerate(columns)).rstrip())
    return "\n".join(out)


def cmd_audit(args: argparse.Namespace) -> int:
    ordered = tag_order(all_tags())
    tags = [t for t in ordered if t == args.tag] if args.tag else ordered
    if not tags:
        raise ReleaseError(f"未知 tag：{args.tag}（本地 `git tag -l` 里没有它）")
    repo = repo_slug()
    if not repo:
        raise ReleaseError("解析不出 owner/name：设 `GH_REPO=owner/name` 或修好 `git remote get-url origin`")

    if args.dry_run:
        print(f"[dry-run] repo={repo} 要对账 {len(tags)} 个本地 tag：{'、'.join(tags)}")
        print("（不解析令牌、不发任何请求）")
        print(f"1) GET  {API}/repos/{repo}/releases?per_page=100&page=1..N")
        print(f"2) GET  {API}/repos/{repo}/releases/latest")
        print(f"3) 每个 release 的资产已在第 1 步的响应里（无需再请求）")
        return 0

    token = get_token()
    if not token:
        print("没找到令牌（GITHUB_TOKEN / git credential 都没有），无法对账远端 releases。", file=sys.stderr)
        return 2
    try:
        releases = fetch_releases(repo, token)
        latest_tag = fetch_latest_tag(repo, token)
    except ReleaseError as e:
        print(f"对账失败（原始错误）：{e}", file=sys.stderr)
        return 2

    by_tag: dict[str, dict] = {}
    extra_drafts: dict[str, list[dict]] = {}
    for tag_name in {r.get("tag_name") for r in releases if isinstance(r, dict)}:
        primary, extras = releases_for_tag(releases, tag_name)
        if primary is not None:
            by_tag[tag_name] = primary
        if extras:
            extra_drafts[tag_name] = extras
    sums = read_sha256sums(DIST / "SHA256SUMS")

    rows: list[dict] = []
    problems: list[str] = []
    for tag in tags:
        expected = asset_name(tag) if tag_has_site(tag) else None
        local_sha, local_src = _local_digest(tag, sums)
        rel = by_tag.get(tag)
        if rel is not None and rel.get("draft"):
            # 草稿不算「有 release」：它对读者还不存在，但它是一条**必须被清掉的残骸**
            extra_drafts.setdefault(tag, []).insert(0, rel)
            rel = None
        if not rel:
            drafts = extra_drafts.get(tag) or []
            note = "缺 release"
            if drafts:
                note += f"（有 {len(drafts)} 个未发布的草稿，id " + "、".join(str(d.get("id")) for d in drafts) + "）"
                problems.append(f"{tag}：有 {len(drafts)} 个草稿但一条都没发布")
            if expected:
                note += "；该版本有站点，应附资产"
            note += f"；远端共 {len(releases)} 个 release"
            rows.append({"tag": tag, "release": "草稿" if drafts else "缺", "assets": "—", "digest": "—",
                         "immutable": "—", "prerelease": "—", "latest": "—", "note": note})
            problems.append(f"{tag}：远端没有 release")
            continue

        assets = [a for a in (rel.get("assets") or []) if isinstance(a, dict)]
        names = [a.get("name", "?") for a in assets]
        note_parts: list[str] = []
        if expected and expected not in names:
            note_parts.append(f"缺资产 {expected}")
            problems.append(f"{tag}：release 里没有资产 {expected}")
        if names:
            note_parts.append("资产 " + "、".join(names))

        remote_sha = None
        for a in assets:
            digest = a.get("digest")
            if isinstance(digest, str) and ":" in digest:
                remote_sha = digest.split(":", 1)[1]
                break
        if expected:
            if not local_sha:
                digest_cell = "本地无"
                note_parts.append(f"本地未构建（没跑过 artifact --tag {tag}）")
                problems.append(f"{tag}：本地没有 sha256 记录（未构建）")
            elif not remote_sha:
                digest_cell = f"{local_sha[:12]} vs 远端无 digest"
                note_parts.append("远端没给 sha256（资产可能是旧的上传方式）")
            elif local_sha == remote_sha:
                digest_cell = f"{local_sha[:12]} = {remote_sha[:12]}"
                note_parts.append(f"哈希一致（来源 {local_src}）")
            else:
                digest_cell = f"{local_sha[:12]} ≠ {remote_sha[:12]}"
                note_parts.append(f"哈希不一致：本地 {local_sha} / 远端 {remote_sha}")
                problems.append(f"{tag}：sha256 不一致（本地 {local_sha[:12]}… / 远端 {remote_sha[:12]}…）")
        else:
            digest_cell = "—"
            if names:
                note_parts.append("该版本无站点，不该有资产")
                problems.append(f"{tag}：无站点的版本却挂了资产 {'、'.join(names)}")

        if extra_drafts.get(tag):
            ids = "、".join(str(d.get("id")) for d in extra_drafts[tag])
            note_parts.append(f"另有 {len(extra_drafts[tag])} 个未发布的草稿（id {ids}）")
            problems.append(f"{tag}：另有 {len(extra_drafts[tag])} 个未发布的草稿（id {ids}）—— "
                            f"删掉：DELETE {API}/repos/{repo}/releases/<id>")

        rows.append({
            "tag": tag,
            "release": "有",
            "assets": "、".join(names) or "无",
            "digest": digest_cell,
            "immutable": "真" if rel.get("immutable") else ("假" if rel.get("immutable") is not None else "未知"),
            "prerelease": "真" if rel.get("prerelease") else "假",
            "latest": "是" if latest_tag == tag else "否",
            "note": "；".join(note_parts) or "—",
        })

    if args.json:
        print(json.dumps({"repo": repo, "tags": rows, "problems": problems,
                          "ok": not problems, "remote_releases": len(releases)},
                         ensure_ascii=False, indent=2))
    else:
        print(audit_table(rows))
        print("")
        if problems:
            print(f"对账结论：{len(problems)} 处差异")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"对账结论：0 差异（本地 {len(tags)} 个 tag 与远端一致）")

    if args.check and problems:
        return 1
    return 0


# --------------------------------------------------------------------------- 入口

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="release.py",
                                 description="发布体系：发布说明 / 变更日志 / 构建资产 / GitHub Release / 远端对账")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true",
                        help="只打印将发出的请求，绝不触网（也不解析令牌）")
    common.add_argument("--quiet", action="store_true", help="只输出主结果，不输出过程提示")

    p = sub.add_parser("notes", parents=[common], help="按模板渲染某 tag 的发布说明")
    p.add_argument("--tag", required=True, help="tag 名（例如 v1.1-web）")
    p.add_argument("--prev", default=None, help="对比基准 tag（缺省用 previous_tag）")
    p.add_argument("--json", action="store_true", help="输出 JSON（含逐条提交）")
    p.set_defaults(func=cmd_notes)

    p = sub.add_parser("changelog", parents=[common], help="生成 / 校验 CHANGELOG.md")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="写 CHANGELOG.md")
    group.add_argument("--check", action="store_true", help="与磁盘比对（默认）")
    p.set_defaults(func=cmd_changelog)

    p = sub.add_parser("artifact", parents=[common], help="构建确定性 zip + SHA256SUMS + 构建回执")
    p.add_argument("--tag", required=True, help="tag 名")
    p.add_argument("--out", default=None, help=f"输出目录（默认 {DIST}）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_artifact)

    p = sub.add_parser("create", parents=[common], help="幂等建 / 更新 GitHub Release")
    p.add_argument("--tag", required=True, help="tag 名")
    p.add_argument("--prerelease", action=argparse.BooleanOptionalAction, default=None,
                   help="是否标记为预发布（缺省：主版本 == 0 → 是）")
    p.add_argument("--latest", action=argparse.BooleanOptionalAction, default=None,
                   help="是否标记为 latest（缺省：只有版本最高的 tag 是）")
    p.add_argument("--body-only", action="store_true", help="只更新说明，不碰资产")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("audit", parents=[common], help="远端 releases 与本地 tag 对账")
    p.add_argument("--tag", default=None, help="只对账这一个 tag")
    p.add_argument("--check", action="store_true", help="有差异就退出 1")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_audit)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ReleaseError as e:
        print(f"{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
