#!/usr/bin/env python3
"""scripts/build_site.py —— 把 lessons/ + web/ 编译成可部署的静态站点 site/。

设计取舍（读之前先看这三条）
----------------------------
1. **构建期渲染，不在浏览器里渲染 Markdown。** 产物是一堆真 HTML：JS 关掉也能读，
   搜索引擎能收录，而且 verify 那一套「用脚本检查产物」才有对象可查。
2. **不用打包器、不装 npm 依赖。** 前端是原生 ES 模块，浏览器直接吃；
   Node 只用来跑单元测试（node --test），所以部署机器上不需要 node_modules。
3. **构建失败要给得出人话。** 未登记的出处、指向不存在课程的交叉引用、
   模板占位符没填、链接指向不存在的文件 —— 全部 exit 1 并指出是哪一课哪一行。

用法
----
  python scripts/build_site.py              # 构建到 site/
  python scripts/build_site.py --check      # 构建到临时目录并做链接/数量自检（不碰 site/）
  python scripts/build_site.py --out D:/x   # 指定输出目录
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import site_render as R  # noqa: E402
import tutorial_core as core  # noqa: E402

WEB = REPO / "web"
SITE = REPO / "site"
CONFIG = REPO / "site.json"

DEFAULT_CONFIG: dict = {
    "title": "Hermes Agent 初学者教程",
    "tagline": "",
    "repo_url": "",
    "repo_docs": [],
    "base_url": "",
}


# --------------------------------------------------------------------------- 配置与数据

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    return cfg


def site_base(cfg: dict) -> str:
    """site.json 的 base_url → 归一化后的站点根地址（末尾一定带斜杠）。

    留空直接报错而不是「静默跳过」：canonical / og:url / sitemap 全靠它拼绝对地址，
    拼错的后果（搜索引擎和分享卡片指向 404 或别人的域名）在浏览器里一点都看不出来。
    """
    base = str(cfg.get("base_url", "")).strip()
    if not base:
        raise R.SiteError(
            "site.json 里没填 base_url（站点部署地址），构建停下。"
            "canonical / og:url / sitemap 要用它拼绝对地址：留空会让它们指向错误地址，"
            "搜索引擎与社交平台收录的就是错的页面。"
            "GitHub Pages 的形态是 https://<用户名>.github.io/<仓库名>/"
        )
    return base if base.endswith("/") else base + "/"


def page_meta(base: str, rel: str, og_type: str, og_title: str, og_desc: str) -> dict[str, str]:
    """一页的 canonical / og 值。rel 是页面在站点内的相对路径（首页传 ""）。

    首页的 canonical 就是 base_url 本身：写成 base_url + "index.html" 会让
    「/」和「/index.html」被搜索引擎当成两个页面，各收一份。
    """
    url = base + rel
    return {
        "canonical": R.escape(url),
        "og_type": og_type,
        "og_title": R.escape(og_title),
        "og_desc": R.escape(og_desc),
        "og_url": R.escape(url),
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def index_data(lessons: list[dict]) -> dict:
    return {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "lessons": [
            {
                "id": l["id"],
                "title": l["title"],
                "stage": l["stage"],
                "stage_name": core.stage_name(l["stage"]),
                "level": l["level"],
                "minutes": l["minutes"],
                "prereq": l["prereq"],
                "tags": l["tags"],
                "sources": l["sources"],
                "summary": l["summary"],
                "updated": l["updated"],
                "url": l["url"],
            }
            for l in lessons
        ],
        "stages": [
            {"stage": s, "name": v["name"], "why": v["why"]} for s, v in sorted(core.STAGES.items())
        ],
    }


def citations_data(citations: dict) -> dict:
    return {
        "count": len(citations),
        "items": {
            sid: {
                "title": e.get("title", ""),
                "url": e.get("url", ""),
                "hermes_version": str(e.get("hermes_version", "")),
                "sha256": str(e.get("sha256", "")),
                "local": e.get("local", ""),
                "retrieved_at": str(e.get("retrieved_at", "")),
            }
            for sid, e in sorted(citations.items())
        },
    }


def search_data(lessons: list[dict]) -> dict:
    return {
        "docs": [
            {
                "id": l["id"],
                "title": l["title"],
                "stage": l["stage"],
                "minutes": l["minutes"],
                "tags": l["tags"],
                "summary": l["summary"],
                "url": l["url"],
                "text": R.search_text(l["body"]),
            }
            for l in lessons
        ]
    }


def manifest_data(lessons: list[dict], baseline: dict) -> dict:
    """构建清单：让「这个站点是哪次内容构建出来的」这件事可核对。"""
    return {
        "built_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "baseline": baseline,
        "lessons": [
            {"id": l["id"], "rel": l["rel"], "url": l["url"], "sha256": sha256_file(l["path"])}
            for l in lessons
        ],
    }


# --------------------------------------------------------------------------- 页面片段

def link_sibling(lesson: dict) -> str:
    """课程页 → 另一课（同级目录）。"""
    return lesson["page"]


def link_from_root(lesson: dict) -> str:
    """首页 → 课程。"""
    return lesson["url"]


def link_from_repo(lesson: dict) -> str:
    """规范页 → 课程。

    规范页在 `site/repo/`，课程在 `site/lessons/` —— 这里**不能**用 link_sibling，
    否则侧栏 32 条课程链接会指向 `site/repo/L01-….html`（全是死链，而且肉眼在
    浏览器里点侧栏第一条就能发现，构建期不检查的话没人会发现）。
    """
    return "../lessons/" + lesson["page"]


def render_sidebar(groups: list[dict], current_id: str, link_for, cfg: dict) -> str:
    out = ['<nav class="nav-lessons" aria-label="课程导航">']
    for g in groups:
        out.append('<section class="nav-stage">')
        out.append(
            f'<h2 class="nav-stage-title"><span class="nav-stage-no">阶段 {g["stage"]}</span>'
            f'<span>{R.escape(g["name"])}</span></h2>'
            f'<p class="nav-stage-why">{R.escape(g["why"])}</p><ul>'
        )
        for ls in g["lessons"]:
            current = ' class="is-current"' if ls["id"] == current_id else ""
            out.append(
                f'<li data-lesson="{ls["id"]}"{current}>'
                f'<a href="{link_for(ls)}">'
                f'<span class="nav-check" aria-hidden="true">○</span>'
                f'<span class="nav-id">{ls["id"]}</span>'
                f'<span class="nav-title">{R.escape(ls["title"])}</span>'
                f'<span class="nav-min">{ls["minutes"]}′</span></a></li>'
            )
        out.append("</ul></section>")
    if cfg.get("repo_docs"):
        out.append('<section class="nav-stage nav-repo"><h2 class="nav-stage-title">'
                   '<span>规范与出处</span></h2><ul>')
        for rel in cfg["repo_docs"]:
            slug = R.repo_doc_slug(rel)
            href = ("../repo/" if current_id else "repo/") + f"{slug}.html"
            out.append(f'<li><a href="{href}"><span class="nav-title">{R.escape(rel)}</span></a></li>')
        out.append("</ul></section>")
    out.append("</nav>")
    return "".join(out)


def render_home(groups: list[dict], lessons: list[dict], cfg: dict, link_for, baseline: dict) -> str:
    total_min = sum(l["minutes"] for l in lessons)
    hours = total_min // 60
    out = [
        f'<h1>{R.escape(cfg["title"])}</h1>',
        f'<p class="lead">{R.escape(cfg.get("tagline", ""))}</p>',
        '<section class="card progress-card" id="progress-card">',
        f'<p class="pc-line"><b id="done-count">0</b> / {len(lessons)} 课完成'
        f'<span class="muted"> · 全量约 {hours} 小时 · <span id="min-left">{total_min} 分钟</span> 待学</span></p>',
        '<div class="bar"><i id="bar-fill" style="width:0%"></i></div>',
        '<p class="muted pc-note">进度只存在你这台机器的浏览器里（localStorage），不上传任何数据；'
        '也可以导出 JSON 与 <code>python scripts/progress.py</code> 的本地状态对照。</p>',
        '<p class="pc-actions">'
        '<button class="btn primary" id="next-lesson">我该学哪一课？</button>'
        '<button class="btn" id="export-progress">导出进度 JSON</button>'
        '<button class="btn" id="import-progress">导入进度 JSON</button>'
        '<input type="file" id="import-file" accept="application/json,.json" hidden>'
        '</p>',
        '<p class="muted pc-out" id="pc-out" hidden></p>',
        "</section>",
    ]
    for g in groups:
        out.append('<section class="card">')
        out.append(
            f'<h2 class="stage-h">阶段 {g["stage"]} · {R.escape(g["name"])}'
            f'<span class="muted"> {len(g["lessons"])} 课 · {sum(l["minutes"] for l in g["lessons"])} 分钟</span></h2>'
            f'<p class="stage-why">{R.escape(g["why"])}</p><ul class="lesson-grid">'
        )
        for ls in g["lessons"]:
            out.append(
                f'<li data-lesson="{ls["id"]}"><a href="{link_for(ls)}">'
                f'<span class="nav-check" aria-hidden="true">○</span>'
                f'<span class="lc-head"><b>{ls["id"]} {R.escape(ls["title"])}</b>'
                f'<span class="muted">{ls["minutes"]} 分钟 · {R.escape(ls["level"])}</span></span>'
                f'<span class="lc-summary">{R.escape(ls["summary"])}</span></a></li>'
            )
        out.append("</ul></section>")
    out.append(
        f'<p class="muted site-note">出处基线：hermes v{baseline["version"]} · 文档提交 {baseline["commit"]}'
        f' · {baseline["count"]} 条官方来源。站点的每一课都能在 '
        f'<code>sources/cache/&lt;src-id&gt;.md</code> 里找到原文快照。</p>'
    )
    return "".join(out)


def render_lesson_article(ls: dict, html: str, toc_html: str, prev, nxt, link_for) -> str:
    prereq = "、".join(ls["prereq"]) if ls["prereq"] else "无"
    nav = ['<nav class="prevnext">']
    nav.append(
        f'<a class="btn" href="{link_for(prev)}">← {prev["id"]} {R.escape(prev["title"])}</a>'
        if prev else "<span></span>"
    )
    nav.append(
        f'<a class="btn" href="{link_for(nxt)}">{nxt["id"]} {R.escape(nxt["title"])} →</a>'
        if nxt else "<span></span>"
    )
    nav.append("</nav>")
    return "".join([
        f'<article class="lesson" data-lesson="{ls["id"]}">',
        html,
        '<p class="lesson-meta">'
        f'前置：{R.escape(prereq)} · {ls["minutes"]} 分钟 · {R.escape(ls["level"])} · '
        f'更新于 {R.escape(ls["updated"])} · 源码 <code>{R.escape(ls["rel"])}</code></p>',
        '<p class="lesson-actions">'
        f'<button class="btn primary" id="mark-done" data-lesson="{ls["id"]}">标记本课完成</button>'
        '<a class="btn" href="../index.html">回首页</a></p>',
        "</article>",
        "".join(nav),
    ])


def rewrite_repo_links(html: str, lesson: dict, cfg: dict) -> str:
    """把课程里指向仓库文件的相对链接改写到站点内的规范页。

    现在仓库里只有一处这样的链接（`../../.hermes.md`），但规则要立住：
    指向未收录文件的链接直接报错，否则读者会点到一个 404 却没人发现。
    """
    whitelist = {R.repo_doc_slug(rel): rel for rel in cfg.get("repo_docs", [])}

    def repl(m: re.Match[str]) -> str:
        href = m.group(1)
        if href.startswith(("http://", "https://", "mailto:", "#", "/")):
            return m.group(0)
        target = href.split("#", 1)[0]
        if not target.endswith((".md", ".txt")):
            return m.group(0)
        resolved = (lesson["path"].parent / target).resolve()
        try:
            rel = resolved.relative_to(REPO).as_posix()
        except ValueError:
            raise R.SiteError(f"{lesson['rel']}: 相对链接指到仓库之外：{href}")
        slug = R.repo_doc_slug(rel)
        if slug not in whitelist:
            raise R.SiteError(
                f"{lesson['rel']}: 相对链接指向未收录的仓库文件 {rel}"
                f"（要么把它加进 site.json 的 repo_docs，要么改掉这个链接）"
            )
        return f'href="../repo/{slug}.html"'

    return re.sub(r'href="([^"]+)"', repl, html)


def rewrite_repo_doc_links(html: str, rel: str, cfg: dict) -> str:
    """规范页正文里指向仓库文件的相对链接 → 站点内能解析的目标。

    规范页（CONTRIBUTING.md、ROADMAP.md…）写的是仓库内路径：`scripts/verify.py`、
    `.hermes/skills/`、`../CONTRIBUTING.md`。这些文件在静态站点上根本不存在，
    原样渲染出来就是一堆 404。规则：

    - 目标已登记在 `site.json` 的 repo_docs → 对应的规范页；
    - 目标是一门课程（`lessons/**/*.md`）→ 对应的课程页；
    - 其余（脚本、目录）：配了 `repo_url` 就指回 GitHub，没配就把 href 去掉
      —— 留可读的文字，不留一个点了就 404 的链接。

    与 rewrite_repo_links 的分工：那个管「课程正文」，这个管「规范页正文」，
    两者都在构建期把断链消灭掉，而不是等读者踩到。
    """
    whitelist = {R.repo_doc_slug(doc): doc for doc in cfg.get("repo_docs", [])}
    lessons = core.load_lessons(REPO)
    lesson_by_rel = {l["rel"]: l for l in lessons}
    here = (REPO / rel).parent

    def repl(m: re.Match[str]) -> str:
        raw = m.group(1)
        if raw.startswith(("http://", "https://", "mailto:", "#", "/")):
            return m.group(0)
        target, _, frag = raw.partition("#")
        if not target:
            return m.group(0)
        resolved = (here / target).resolve()
        try:
            target_rel = resolved.relative_to(REPO).as_posix()
        except ValueError:
            raise R.SiteError(f"{rel}: 相对链接指到仓库之外：{raw}")
        anchor = f"#{frag}" if frag else ""
        if target_rel in lesson_by_rel:
            return f'href="../lessons/{lesson_by_rel[target_rel]["page"]}{anchor}"'
        slug = R.repo_doc_slug(target_rel)
        if slug in whitelist:
            return f'href="{slug}.html{anchor}"'
        if cfg.get("repo_url"):
            return (f'href="{cfg["repo_url"].rstrip("/")}/blob/main/{target_rel}{anchor}"'
                    ' target="_blank" rel="noopener"')
        return "data-repo-path=\"%s\"" % R.escape(target_rel)

    return re.sub(r'href="([^"]+)"', repl, html)


# --------------------------------------------------------------------------- 主流程

def render_repo_doc(rel: str, cfg: dict, layout: str, groups: list[dict]) -> tuple[str, str]:
    """仓库规范页：.hermes.md / CONTRIBUTING.md 等，用同一套渲染管线。

    返回 (slug, 页面 HTML)。这些文件没有 frontmatter，标题取第一个 H1。
    """
    path = REPO / rel
    if not path.is_file():
        raise R.SiteError(f"site.json 里登记的仓库文档不存在：{rel}")
    slug = R.repo_doc_slug(rel)
    html, toc = R.render_markdown(path.read_text(encoding="utf-8"))
    html = rewrite_repo_doc_links(html, rel, cfg)
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else rel
    page = R.render_template(
        layout,
        {
            "title": f"{title} · {cfg['title']}",
            "desc": f"仓库文件 {rel}",
            **page_meta(site_base(cfg), f"repo/{slug}.html", "article", title, f"仓库文件 {rel}"),
            "prefix": "../",
            "site_title": R.escape(cfg["title"]),
            "lesson_id": "",
            "sidebar": render_sidebar(groups, "__repo__", link_from_repo, cfg),
            "content": f'<article class="lesson repo-doc">{html}</article>',
            "toc": R.build_toc_html(toc),
            "footer": render_footer(cfg),
        },
        rel,
    )
    return slug, page


def render_footer(cfg: dict) -> str:
    parts = [f'<span>{R.escape(cfg["title"])}</span>',
             '<span class="muted">内容 CC BY 4.0 · 代码 MIT</span>']
    if cfg.get("repo_url"):
        parts.append(f'<a href="{R.escape(cfg["repo_url"])}" target="_blank" rel="noopener">在 GitHub 上查看仓库</a>')
    return '<div class="footer-inner">' + "".join(parts) + "</div>"


def build_sitemap(entries: list[tuple[str, str]]) -> str:
    """[(绝对 URL, lastmod)] → sitemap.xml 文本。

    只列能被搜索引擎收录的页面：404.html 不在其中（它既是错误页，也是给站内
    跳转兜底的页面，收录它等于把「页面不存在」摆到搜索结果里）。
    lastmod 用课程 frontmatter 的 updated —— 全站统一写构建当天，等于告诉搜索引擎
    「今天 39 个页面全变了」，反而谁也不信。
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in entries:
        lines.append(f"  <url><loc>{R.escape(loc)}</loc><lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_robots(cfg: dict) -> str:
    """robots.txt：全站可抓，并指明 sitemap 的位置。

    教程站没有任何需要屏蔽的东西（只有课程、数据和一份可下载的 JSON），
    所以规则是「全放行」——但 sitemap 那一行必须有，否则发现路径就只剩爬链接。
    """
    return f"User-agent: *\nAllow: /\n\nSitemap: {site_base(cfg)}sitemap.xml\n"


def build(out: Path, cfg: dict) -> dict:
    base = site_base(cfg)   # base_url 没填就在这里停下，别产出「看着没问题」的站
    today = datetime.now().strftime("%Y-%m-%d")
    lessons = core.load_lessons(REPO)
    if not lessons:
        raise R.SiteError("lessons/ 下没有课程，先写课再建站")
    citations = core.load_citations(REPO)
    baseline = core.source_baseline(REPO)
    groups = core.group_by_stage(lessons)
    id_to_page = {l["id"]: l["page"] for l in lessons}

    layout = (WEB / "partials" / "layout.html").read_text(encoding="utf-8")

    site = Path(out)
    if site.exists():
        shutil.rmtree(site)
    (site / "lessons").mkdir(parents=True)
    (site / "repo").mkdir()
    (site / "data").mkdir()
    shutil.copytree(WEB / "assets", site / "assets")
    (site / ".nojekyll").write_text("", encoding="utf-8", newline="\n")

    sitemap_entries: list[tuple[str, str]] = []

    # 课程页
    for i, ls in enumerate(lessons):
        where = ls["rel"]
        html, toc = R.render_markdown(ls["body"])
        html = rewrite_repo_links(html, ls, cfg)
        html = R.linkify_citations(html, citations, where)
        html = R.linkify_xrefs(html, id_to_page, where)
        page = R.render_template(
            layout,
            {
                "title": f'{ls["id"]} · {ls["title"]} · {cfg["title"]}',
                "desc": ls["summary"] or ls["title"],
                **page_meta(
                    base, ls["url"], "article",
                    f'「{ls["id"]} · {ls["title"]}」', ls["summary"] or ls["title"],
                ),
                "prefix": "../",
                "site_title": R.escape(cfg["title"]),
                "lesson_id": ls["id"],
                "sidebar": render_sidebar(groups, ls["id"], link_sibling, cfg),
                "content": render_lesson_article(
                    ls, html, "", lessons[i - 1] if i else None,
                    lessons[i + 1] if i + 1 < len(lessons) else None, link_sibling,
                ),
                "toc": R.build_toc_html(toc),
                "footer": render_footer(cfg),
            },
            where,
        )
        (site / "lessons" / ls["page"]).write_text(page, encoding="utf-8", newline="\n")
        sitemap_entries.append((base + ls["url"], ls["updated"] or today))

    # 首页
    home = R.render_template(
        layout,
        {
            "title": cfg["title"],
            "desc": cfg.get("tagline", ""),
            **page_meta(base, "", "website", cfg["title"], cfg.get("tagline", "")),
            "prefix": "",
            "site_title": R.escape(cfg["title"]),
            "lesson_id": "",
            "sidebar": render_sidebar(groups, "", link_from_root, cfg),
            "content": render_home(groups, lessons, cfg, link_from_root, baseline),
            "toc": "",
            "footer": render_footer(cfg),
        },
        "index.html",
    )
    (site / "index.html").write_text(home, encoding="utf-8", newline="\n")

    # 仓库规范页
    repo_pages = [render_repo_doc(rel, cfg, layout, groups) for rel in cfg.get("repo_docs", [])]
    for slug, page in repo_pages:
        (site / "repo" / f"{slug}.html").write_text(page, encoding="utf-8", newline="\n")
        sitemap_entries.append((base + f"repo/{slug}.html", today))

    # sitemap / robots：首页一条 + 每课一条 + 每个规范页一条。
    # 404.html 不在其中 —— 它是错误兜底页，不该出现在搜索结果里（check_seo 会盯着这点）。
    (site / "sitemap.xml").write_text(
        build_sitemap([(base, today)] + sitemap_entries), encoding="utf-8", newline="\n",
    )
    (site / "robots.txt").write_text(build_robots(cfg), encoding="utf-8", newline="\n")

    # 数据
    write_json(site / "data" / "index.json", index_data(lessons))
    write_json(site / "data" / "citations.json", citations_data(citations))
    write_json(site / "data" / "search.json", search_data(lessons))
    write_json(site / "data" / "manifest.json", manifest_data(lessons, baseline))

    # 404
    (site / "404.html").write_text(
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<title>页面不存在 · {R.escape(cfg["title"])}</title>'
        '<style>body{font:16px/1.6 system-ui,sans-serif;margin:4rem auto;max-width:36rem;padding:0 1rem}'
        'a{color:#3b5bdb}</style></head><body><h1>页面不存在</h1>'
        '<p>你要找的课程可能改了名字。</p><p><a href="/index.html">回课程首页</a></p></body></html>\n',
        encoding="utf-8",
        newline="\n",
    )

    files = [p for p in site.rglob("*") if p.is_file()]
    return {
        "lessons": len(lessons),
        "pages": len(list(site.rglob("*.html"))),
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "baseline": baseline,
    }


LINK_ATTR_RE = re.compile(r'(?:href|src)="([^"]+)"')
SITEMAP_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
# canonical / og 一律用「标签级」正则来数：规范页的正文里就有 `og:site_name`、
# 「5 个 og: 标签」这类字样，用 html.count("og:") 会把正文算成元信息。
OG_META_RE = re.compile(r'<meta property="(og:[a-z_]+)"')
CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')


def check_links(out: Path) -> list[str]:
    """站内自检：每个 href/src 都要能在产物里找到对应文件。

    站内链接断一条，读者的体验就是「点了个 404」，而作者在自己的浏览器里
    往往正好点不到那一条。所以交给脚本，在 CI 里跑。
    """
    problems: list[str] = []
    for page in sorted(out.rglob("*.html")):
        for raw in LINK_ATTR_RE.findall(page.read_text(encoding="utf-8")):
            if raw.startswith(("http://", "https://", "mailto:", "data:", "//", "#", "/")):
                continue
            target = raw.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            if not (page.parent / target).resolve().exists():
                problems.append(f"{page.relative_to(out).as_posix()} → {raw}")
    return problems


def check_seo(out: Path, cfg: dict) -> list[str]:
    """可达性自检：sitemap 覆盖、canonical/og 齐不齐、robots 指不指得到 sitemap。

    与 check_links 的分工：断链读者点一下就能发现，而这些「给机器看的」元信息
    错在浏览器里完全看不见 —— 页面照样渲染，只有搜索引擎和分享卡片会看到那个
    视角（而且是错的）。所以只能靠断言，静态构建期就要断言。
    """
    problems: list[str] = []
    base = site_base(cfg)

    sitemap_path = out / "sitemap.xml"
    if not sitemap_path.is_file():
        return ["产物里没有 sitemap.xml（搜索引擎发现课程页的唯一入口就没了）"]
    locs = SITEMAP_LOC_RE.findall(sitemap_path.read_text(encoding="utf-8"))

    # 1) 条目数 == 产物页面数 - 404.html
    pages = sorted(p for p in out.rglob("*.html") if p.name != "404.html")
    if len(locs) != len(pages):
        problems.append(
            f"sitemap 条目数 {len(locs)} != 非 404 页面数 {len(pages)}"
            f"（产物共 {len(list(out.rglob('*.html')))} 个 .html，应排除 404.html）"
        )

    url_to_page: dict[str, Path] = {}
    for p in pages:
        rel = p.relative_to(out).as_posix()
        url_to_page[base + ("" if rel == "index.html" else rel)] = p

    # 2) 每个 loc 都是 https 绝对地址、落在 base_url 下、且对应真实页面
    for loc in locs:
        if not loc.startswith("https://"):
            problems.append(f"sitemap 里有非 https 的地址：{loc}")
        elif not loc.startswith(base):
            problems.append(f"sitemap 地址不在 base_url（{base}）之下：{loc}")
        elif loc not in url_to_page:
            problems.append(f"sitemap 指向产物里不存在的页面：{loc}")

    # 3) 每门课都要在里面
    for lesson in core.load_lessons(REPO):
        if base + lesson["url"] not in locs:
            problems.append(f"sitemap 少了课程页：{lesson['id']} → {base + lesson['url']}")

    # 4) 404.html 不许出现
    for loc in locs:
        if loc.endswith("404.html"):
            problems.append(f"404.html 不该出现在 sitemap 里：{loc}")

    # 5) 每个 sitemap 页面：恰好 5 个 og: 标签 + 有 canonical；反向也要查（页面漏进 sitemap）
    for loc, page in url_to_page.items():
        rel = page.relative_to(out).as_posix()
        if loc not in locs:
            problems.append(f"sitemap 少了页面：{rel} → {loc}")
            continue
        html = page.read_text(encoding="utf-8")
        og = OG_META_RE.findall(html)
        if len(og) != 5:
            problems.append(f"{rel}：og 标签 {len(og)} 个（应为 5 个：{', '.join(sorted(og)) or '无'}）")
        if not CANONICAL_RE.search(html):
            problems.append(f'{rel}：缺 <link rel="canonical" href="…">')

    # 6) robots.txt
    robots = out / "robots.txt"
    if not robots.is_file():
        problems.append("产物里没有 robots.txt")
    elif f"Sitemap: {base}sitemap.xml" not in robots.read_text(encoding="utf-8"):
        problems.append(f"robots.txt 里没有指向 {base}sitemap.xml 的 Sitemap 行")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="构建教程静态站点")
    ap.add_argument("--out", default=str(SITE), help="输出目录（默认 site/）")
    ap.add_argument("--check", action="store_true", help="构建到临时目录并自检，不写 site/")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    cfg = load_config()

    try:
        if args.check:
            with tempfile.TemporaryDirectory() as tmp:
                stats = build(Path(tmp) / "site", cfg)
                problems = check_links(Path(tmp) / "site")
                problems += check_seo(Path(tmp) / "site", cfg)
        else:
            stats = build(Path(args.out), cfg)
            problems = check_links(Path(args.out))
            problems += check_seo(Path(args.out), cfg)
    except R.SiteError as e:
        print(f"构建失败：{e}", file=sys.stderr)
        return 1

    if problems:
        print(f"站点自检失败：{len(problems)} 条（站内链接 / sitemap / canonical / og / robots）")
        for p in problems[:30]:
            print(f"  - {p}")
        return 1

    if not args.quiet:
        print(
            f"站点自检通过：{stats['lessons']} 课 / {stats['pages']} 页 / "
            f"{stats['files']} 文件 / {stats['bytes'] / 1024:.0f} KB"
            f"（出处基线 hermes v{stats['baseline']['version']}）"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
