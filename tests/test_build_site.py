#!/usr/bin/env python3
"""tests/test_build_site.py —— 构建器集成测试：真的构建到临时目录，然后验收产物。"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_site  # noqa: E402
import design_matrix as D  # noqa: E402
import site_render as R  # noqa: E402
import tutorial_core as core  # noqa: E402


class TestBuildOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.stats = build_site.build(cls.out, build_site.load_config())

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_stats_match_repo(self):
        # 页数按**组成**断言，不留魔法数字：
        # 页数 = 课程页（= 课程数）+ 仓库规范页（= site.json 的 repo_docs 条数）
        #        + 站点根目录的页面（首页 / 学习地图 / 常见错误合集 / 404）
        n_lessons = len(core.load_lessons(REPO))
        lesson_pages = len(list((self.out / "lessons").glob("*.html")))
        repo_pages = len(list((self.out / "repo").glob("*.html")))
        root_pages = len(list(self.out.glob("*.html")))          # 只有站点根目录的页面，不含子目录
        cfg = build_site.load_config()

        self.assertEqual(self.stats["lessons"], n_lessons)
        self.assertEqual(lesson_pages, n_lessons)                # 每课一页
        self.assertEqual(repo_pages, len(cfg["repo_docs"]))      # 每个 repo_doc 一页
        # 站点根目录的页面：首页 / 学习地图 / 常见错误合集 / 设计对比 / 离线单文件版 / 404
        root_expected = ("index.html", "map.html", "pitfalls.html", "design.html",
                         "offline.html", "404.html")
        for rel in root_expected:
            self.assertTrue((self.out / rel).is_file(), f"缺 {rel}")
        self.assertEqual(root_pages, len(root_expected))
        self.assertEqual(self.stats["pages"], lesson_pages + repo_pages + root_pages)

        # 文件数也是组成式：页面 + 非页面文件（sitemap/robots/.nojekyll/data/*.json/assets/*）
        non_html = [p for p in self.out.rglob("*") if p.is_file() and p.suffix != ".html"]
        self.assertEqual(self.stats["files"], self.stats["pages"] + len(non_html))
        self.assertTrue(non_html, "产物里除了 .html 还应该有 sitemap/robots/data/资源文件")

    def test_index_and_data_files_exist(self):
        for rel in ("index.html", "404.html", "map.html", ".nojekyll",
                    "data/index.json", "data/citations.json", "data/search.json", "data/manifest.json",
                    "data/design.json", "assets/app.css", "assets/app.js"):
            self.assertTrue((self.out / rel).is_file(), f"缺 {rel}")

    def test_every_lesson_has_a_page(self):
        for lesson in core.load_lessons(REPO):
            self.assertTrue((self.out / "lessons" / lesson["page"]).is_file(), lesson["id"])

    def test_index_json_shape(self):
        data = json.loads((self.out / "data" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["lessons"]), len(core.load_lessons(REPO)))
        first = data["lessons"][0]
        for key in ("id", "title", "stage", "minutes", "level", "prereq", "summary", "url"):
            self.assertIn(key, first)

    def test_search_json_shape(self):
        data = json.loads((self.out / "data" / "search.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["docs"]), len(core.load_lessons(REPO)))
        l23 = next(d for d in data["docs"] if d["id"] == "L23")
        self.assertIn("hermes cron", l23["text"])

    def test_lesson_page_contains_citation_link_and_toc(self):
        page = (self.out / "lessons" / "L01-first-conversation.html").read_text(encoding="utf-8")
        self.assertIn('class="cite"', page)
        self.assertIn('class="page-toc"', page)
        self.assertIn("hermes-agent.nousresearch.com", page)

    def test_prereq_is_clickable_on_lesson_page_and_offline(self):
        """两处「前置」都要是链接：正文行（渲染期）与页脚（构建期由 frontmatter 生成）。"""
        page = (self.out / "lessons" / "L11-tools-and-toolsets.html").read_text(encoding="utf-8")
        self.assertIn('<p class="lesson-meta">前置：'
                      '<a class="xref" href="L02-what-happens-in-a-turn.html">L02</a>、'
                      '<a class="xref" href="L10-models-and-providers.html">L10</a>', page)
        self.assertIn('<a class="xref" href="L02-what-happens-in-a-turn.html">L02</a>', page)
        self.assertIn('href="L02-what-happens-in-a-turn.html"', page)

        offline = (self.out / "offline.html").read_text(encoding="utf-8")
        self.assertIn('<a class="xref" href="#L02">L02</a>', offline)   # 单文件里是文档内锚点
        self.assertIn('<p class="lesson-meta">前置：无', offline)        # L00 无前置仍是纯文字

    def test_every_lesson_page_has_linkable_prereq(self):
        """所有课程页一起去查：有前置的课，页脚「前置：」后面必须紧跟 <a>。"""
        lessons = core.load_lessons(REPO)
        for lesson in lessons:
            page = (self.out / "lessons" / lesson["page"]).read_text(encoding="utf-8")
            if lesson["prereq"]:
                self.assertIn('<p class="lesson-meta">前置：<a class="xref"',
                              page, lesson["id"])
            else:
                self.assertIn('<p class="lesson-meta">前置：无 ·', page, lesson["id"])

    def test_repo_doc_pages_rendered(self):
        self.assertTrue((self.out / "repo" / "hermes-md.html").is_file())
        self.assertTrue((self.out / "repo" / "sources-readme.html").is_file())

    def test_manifest_records_source_hashes(self):
        manifest = json.loads((self.out / "data" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["lessons"]), len(core.load_lessons(REPO)))
        self.assertEqual(len(manifest["lessons"][0]["sha256"]), 64)
        self.assertTrue(manifest["baseline"]["version"])

    def test_no_broken_links(self):
        self.assertEqual(build_site.check_links(self.out), [])

    def test_no_unfilled_layout_placeholders_reach_a_page(self):
        """页面的**模板骨架**（`<main>` 之外：head / 顶栏 / 侧栏 / 目录 / 页脚）不许残留占位符。

        为什么把 `<main>` 排除在外：正文里会**讨论**占位符 —— `.hermes.md` 的坑表写了
        `{{footer}}`、`ROADMAP.md` 写了 `{{github}}`，那是原文，出现在页面正文里是对的。
        早先的宽判据（「页面里还有没有 `{{`」）把这种正文当成「模板没填」，整站构建直接停下
        （实测踩过一次，见 `site_render.render_template` 的注释）。
        正文里的 `{{content}}` 要是真没被填，`render_template` 在构建期就抛错了
        （`tests/test_site_render.py` 有专门用例），所以这一条不必再管正文。
        """
        names = set(R.PLACEHOLDER_RE.findall(
            (REPO / "web" / "partials" / "layout.html").read_text(encoding="utf-8")
        ))
        self.assertGreaterEqual(len(names), 5, "布局模板里没扫到占位符（选择器或结构变了？）")
        for page in self.out.rglob("*.html"):
            chrome = re.sub(r"<main\b.*?</main>", "", page.read_text(encoding="utf-8"), flags=re.S)
            for name in names:
                self.assertNotIn("{{" + name + "}}", chrome, page.as_posix())


LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')
# 只认 <meta property="og:…">。**不能用 html.count("og:")**：规范页正文里就有
# 「每页加 5 个 og 标签（`og:site_name` …）」这种句子，字符串计数会把正文算进来。
OG_META_RE = re.compile(r'<meta property="(og:[a-z_]+)" content="([^"]*)"')

OG_NAMES = {"og:site_name", "og:type", "og:title", "og:description", "og:url"}


def main_region(html: str) -> str:
    """取出 `<main>` 里的正文。

    为什么需要它：`data-lesson` 在整页里出现三次来源 —— layout 的 `<body data-lesson>`、
    全局侧栏的 32 条课程行、以及正文里的课程行。要断言「地图页有 32 行」，
    必须只看正文，否则数的其实是「侧栏 + 正文」（64）。
    """
    m = re.search(r"<main\b[^>]*>(.*)</main>", html, re.S)
    assert m, "页面里没有 <main>"
    return m.group(1)


def sidebar_region(html: str) -> str:
    """取出 `<aside class="sidebar">` 里的侧栏（全站每一页都是同一份）。"""
    m = re.search(r'<aside class="sidebar"[^>]*>(.*?)</aside>', html, re.S)
    assert m, "页面里没有侧栏"
    return m.group(1)


def topbar_region(html: str) -> str:
    """取出 `<header class="topbar">` 里的顶栏（全站每一页都是同一份）。"""
    m = re.search(r'<header class="topbar">(.*?)</header>', html, re.S)
    assert m, "页面里没有顶栏"
    return m.group(1)


# 会被折进「14px 第一列」的文字 = `<a>` 元素的**直接文本子节点**。
# 用 html.parser 而不是正则：文字归属跟着 `<a>` 的深度变，正则数不清嵌套。
VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img",
                       "input", "link", "meta", "source", "track", "wbr"})


class SidebarAnchorTextCollector(HTMLParser):
    """收集侧栏 `<li><a>` 的直接文本子节点（裸文本 = 会变成竖排的那种）。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[str] = []
        self._aside_left: int | None = None      # 侧栏起点所处的深度
        self._anchor_depth: int | None = None    # <a> 外面的深度
        self.anchors = 0
        self.bare: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        if tag == "aside" and "sidebar" in (dict(attrs).get("class") or "").split():
            self._aside_left = len(self._stack)
        elif self._aside_left is not None and tag == "a":
            self.anchors += 1
            self._anchor_depth = len(self._stack)
        self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or not self._stack or self._stack[-1] != tag:
            return
        self._stack.pop()
        if self._aside_left is not None and len(self._stack) == self._aside_left:
            self._aside_left = None
        if self._anchor_depth is not None and len(self._stack) == self._anchor_depth:
            self._anchor_depth = None

    def handle_data(self, data):
        if (data.strip() and self._anchor_depth is not None
                and len(self._stack) == self._anchor_depth + 1):
            self.bare.append(data.strip())


# 侧栏普通条目里那一枚内联图标的完整形状（见 build_site.nav_icon）：
# 14×14、线稿跟随 currentColor、对读屏隐藏。**外链一律不许有** ——
# offline.html 断网也要能读，图标字体/CDN 在无网时就是一个空方块。
NAV_ICON_RE = re.compile(
    r'\A<svg class="nav-icon" viewBox="0 0 14 14" width="14" height="14" fill="none" '
    r'stroke="currentColor" stroke-width="[\d.]+" stroke-linejoin="round" '
    r'stroke-linecap="round" aria-hidden="true" focusable="false">.+?</svg>'
    r'<span class="nav-title">([^<]+)</span>\Z',
    re.S,
)


def assert_sidebar_entry(case: unittest.TestCase, page: str, href: str, label: str, where: str = "") -> None:
    """断言侧栏里指向 `href` 的那一条是「图标 + 文字」。

    为什么连标记形状一起断言：**布局靠它撑着**。课程行是
    `grid-template-columns: 14px 34px 1fr auto`（列数是按 ○ / 课号 / 标题 / 分钟
    四个 span 定的），普通条目要是只剩一个裸文本节点，文字就落进 14px 的第一列被
    逐字折行 —— 浏览器里看起来是「竖排」，而构建、门禁、链接自检全绿。
    所以这里的断言必须落在 `<svg>` 与 `<span class="nav-title">` 上，不能只对 href。
    """
    m = re.search(
        rf'<li><a href="{re.escape(href)}">(.*?)</a></li>', sidebar_region(page), re.S
    )
    case.assertIsNotNone(m, f"{where}: 侧栏里没有指向 {href} 的条目")
    inner = m.group(1)
    icon = NAV_ICON_RE.match(inner)
    case.assertIsNotNone(
        icon,
        f'{where}: 侧栏条目 {href} 必须是「图标 + <span class="nav-title">」'
        f"（裸文本会被折成竖排；实际是 {inner[:90]!r}）",
    )
    case.assertEqual(icon.group(1), label, where)


class TestMapPage(unittest.TestCase):
    """v1.3 学习地图页 `/map.html`：与桌面部件同源，但用站点自己的模板渲染。

    这一页最容易坏的地方是**链接前缀**（它和首页一样在站点根目录），
    而前缀错了在构建期只有 check_links 能发现 —— 所以这里连前缀一起断言。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        cls.base = cls.cfg["base_url"]
        build_site.build(cls.out, cls.cfg)
        cls.page = (cls.out / "map.html").read_text(encoding="utf-8")
        cls.lessons = core.load_lessons(REPO)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_map_page_exists_and_has_one_row_per_lesson(self):
        self.assertTrue((self.out / "map.html").is_file())
        stat = (self.out / "map.html").stat()
        self.assertGreater(stat.st_size, 0)
        rows = re.findall(r'<li data-lesson="(L\d+)"', main_region(self.page))
        self.assertEqual(len(rows), len(core.load_lessons(REPO)))       # 每课一行
        self.assertEqual(set(rows), {l["id"] for l in self.lessons})   # 不重复、也没有多余的

    def test_map_rows_link_to_the_lesson_pages(self):
        links = re.findall(r'<li data-lesson="(L\d+)"><a href="([^"]+)"', main_region(self.page))
        self.assertEqual(len(links), len(self.lessons))
        for lesson in self.lessons:
            self.assertIn((lesson["id"], lesson["url"]), links, lesson["id"])
        for _, href in links:
            self.assertTrue(href.startswith("lessons/"), href)
            self.assertTrue((self.out / href).is_file(), f"地图页指向不存在的页面：{href}")

    def test_map_page_reuses_existing_classes_only(self):
        """不新增视觉类：只用站点已有的 card / stage-h / lesson-grid / nav-check / lc-*。"""
        for cls_name in ("card", "stage-h", "stage-why", "lesson-grid", "nav-check", "lc-head", "lc-summary"):
            self.assertIn(cls_name, self.page, cls_name)
        # 桌面部件的样式与 data-hermes-send 不许出现在站点页里
        self.assertNotIn("humap", self.page)
        self.assertNotIn("data-hermes-send", self.page)

    def test_map_page_is_in_the_sitemap(self):
        locs = LOC_RE.findall((self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn(self.base + "map.html", locs)
        # 组成式：sitemap 条目数 == 产物 .html 数 - 不进 sitemap 的页面数
        # （404.html 是错误页、offline.html 是同一批内容的离线形态，都不收录）
        self.assertEqual(
            len(locs),
            len(list(self.out.rglob("*.html"))) - len(build_site.EXCLUDED_FROM_SITEMAP),
        )

    def test_map_page_has_canonical_and_five_og_tags(self):
        self.assertEqual(CANONICAL_RE.findall(self.page), [self.base + "map.html"])
        metas = dict(OG_META_RE.findall(self.page))
        self.assertEqual(len(OG_META_RE.findall(self.page)), 5)
        self.assertEqual(set(metas), OG_NAMES)
        self.assertEqual(metas["og:type"], "website")
        self.assertEqual(metas["og:url"], self.base + "map.html")
        self.assertTrue(metas["og:description"], "og:description 不能为空")

    def test_sidebar_links_to_the_map_from_root_and_subpages(self):
        """首页 `map.html`，课程/规范页 `../map.html`，地图页自己也是 `map.html`。"""
        for rel, href in (
            ("index.html", "map.html"),
            ("map.html", "map.html"),
            ("lessons/L15-skills.html", "../map.html"),
            ("repo/roadmap.html", "../map.html"),
        ):
            page = (self.out / rel).read_text(encoding="utf-8")
            assert_sidebar_entry(self, page, href, "学习地图", rel)

    def test_sidebar_prefix_is_explicit_and_still_right_for_other_groups(self):
        """前缀改成显式参数后，其余三组页面的侧栏链接必须和以前一样。

        三类页面的课程链接本来就不同（首页从根、课程页同级、规范页往上一级），
        这正是 `link_for` 的职责；`prefix` 只管「入口」与「规范与出处」两组。
        """
        root = (self.out / "map.html").read_text(encoding="utf-8")
        home = (self.out / "index.html").read_text(encoding="utf-8")
        lesson = (self.out / "lessons" / "L15-skills.html").read_text(encoding="utf-8")
        repo = (self.out / "repo" / "roadmap.html").read_text(encoding="utf-8")

        for page in (home, root):                     # 站点根目录的页面
            self.assertIn('href="repo/hermes-md.html"', page)
            self.assertIn('href="lessons/L15-skills.html"', page)
            self.assertIn('href="map.html"', page)
        self.assertIn('href="../repo/hermes-md.html"', lesson)
        self.assertIn('href="L15-skills.html"', lesson)          # 课程页之间是同级引用
        self.assertIn('href="../map.html"', lesson)
        self.assertIn('href="../repo/hermes-md.html"', repo)
        self.assertIn('href="../lessons/L15-skills.html"', repo)
        self.assertIn('href="../map.html"', repo)
        self.assertNotIn('href="repo/', lesson)          # 课程页的前缀必须是 ../


class TestSidebarEntriesAreNotVertical(unittest.TestCase):
    """侧栏条目不许退回「竖排」—— 纯渲染层的坑，构建期全绿也照样踩。

    `.nav-stage li a` 原先是 `display: grid; grid-template-columns: 14px 34px 1fr auto`：
    列数是按**课程行**的四个 span（○ / 课号 / 标题 / 分钟）定的。普通条目
    （「入口」三条、「规范与出处」六条）只有一个文本节点，落进 14px 的第一列就被
    **逐字折行** —— 真实浏览器里「学习地图」占 4 行 / 103px 高、「常见错误合集」占
    6 行 / 150px 高，看起来像竖排。而门禁、单测、链接自检全绿：它们只看链接与文本，
    不看谁落在哪一列。

    所以这一组断言必须落在**标记与 CSS 的契约**上：
    - 四列网格只许出现在 `li[data-lesson]` 的规则里；
    - 侧栏每个 `<li><a>` 内不许有裸文本子节点（文字一律包进 span）。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        build_site.build(cls.out, cls.cfg)
        cls.css = (REPO / "web" / "assets" / "app.css").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @staticmethod
    def css_block(css: str, selector: str) -> str:
        """取某条选择器的声明块（够用即可：这两条规则都没有嵌套）。"""
        m = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", css)
        assert m, f"样式表里没有 `{selector}` 规则"
        return m.group(1)

    def test_grid_columns_are_scoped_to_lesson_rows(self):
        """四列网格属于课程行；普通条目必须是「图标 + 一行文字」的 flex。"""
        plain = self.css_block(self.css, ".nav-stage li a")
        self.assertIn("display: flex", plain)
        self.assertNotIn(
            "grid-template-columns", plain,
            "普通条目（只有一个 span）套四列网格 → 文字落进 14px 的第一列被逐字折行",
        )
        rows = self.css_block(self.css, ".nav-stage li[data-lesson] a")
        self.assertIn("grid-template-columns: 14px 34px minmax(0, 1fr) auto", rows)
        self.assertEqual(
            self.css.count("grid-template-columns: 14px 34px"), 1,
            "四列网格只该有一份定义（两份就是又要走偏了）",
        )

    def test_no_bare_text_inside_a_sidebar_anchor(self):
        """侧栏条目的文字必须全在 span 里：裸文本就是网格的第一列（14px 宽）。"""
        for rel in ("index.html", "map.html", "pitfalls.html", "design.html",
                    "lessons/L15-skills.html", "repo/roadmap.html"):
            page = (self.out / rel).read_text(encoding="utf-8")
            collector = SidebarAnchorTextCollector()
            collector.feed(page)
            self.assertGreaterEqual(
                collector.anchors, 40, f"{rel}: 没扫到侧栏条目（选择器或结构变了？）"
            )
            self.assertEqual(
                collector.bare, [],
                f"{rel}: 侧栏条目里有裸文本（会落进 14px 的第一列被逐字折行）",
            )

    def test_plain_entry_icons_are_inline_theme_aware_and_offline_safe(self):
        """图标是内联 SVG：跟随主题色、对读屏隐藏、**不引任何外链**。

        外链很重要：`offline.html` 是内联同一份样式表的单文件版，断网也要能读；
        图标字体/CDN 在无网时就是一个空方块，而页面看起来「只是少了个小图形」。
        """
        page = (self.out / "index.html").read_text(encoding="utf-8")
        icons = re.findall(r'<svg class="nav-icon".*?</svg>', sidebar_region(page), re.S)
        expected = len(self.cfg["repo_docs"]) + 3          # 规范与出处 + 入口三条
        self.assertEqual(len(icons), expected, "侧栏每个普通条目都该有一枚图标")
        for svg in icons:
            self.assertIn('stroke="currentColor"', svg)
            self.assertIn('aria-hidden="true"', svg)
            self.assertNotIn("http", svg, "图标不许引外链（离线版会变成空方块）")


class TestGithubEntrypoint(unittest.TestCase):
    """顶栏右端的 GitHub 标识（v3.3）：全站每页一枚、指向仓库、新标签页打开。

    为什么这些细节都要断言：图标是最容易在「改样式 / 换模板」时被顺手弄坏的东西，
    而坏掉之后**在联网的浏览器里看着完全正常** —— 换成 `<img src>` 断网才变成空方块、
    href 写成相对地址或漏掉 `rel="noopener"` 也照样「点了能跳」。
    所以断言落在标记形状与属性上，逐页查一遍（顶栏是全站同一份，但模板填值各页不同）。
    """

    PAGES = ("index.html", "map.html", "pitfalls.html", "design.html",
             "lessons/L15-skills.html", "repo/roadmap.html")

    # 一整块：<a class="icon-btn github-link" …>内联 SVG</a>
    LINK_RE = re.compile(
        r'<a class="icon-btn github-link" href="([^"]+)" target="_blank" rel="noopener"'
        r' aria-label="([^"]+)" title="([^"]+)">(<svg class="github-icon".*?</svg>)</a>',
        re.S,
    )

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        build_site.build(cls.out, cls.cfg)
        cls.pages = {rel: (cls.out / rel).read_text(encoding="utf-8") for rel in cls.PAGES}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_page_has_one_github_link_in_the_topbar(self):
        for rel, page in self.pages.items():
            hits = self.LINK_RE.findall(topbar_region(page))
            self.assertEqual(len(hits), 1, f"{rel}: 顶栏该有且只有一枚 GitHub 标识")
            href, aria, title, svg = hits[0]
            self.assertEqual(href, self.cfg["repo_url"], rel)
            self.assertIn("GitHub", aria, f"{rel}: 可访问名要说清点了去哪")
            self.assertTrue(title, rel)
            self.assertTrue(svg, rel)

    def test_icon_is_inline_svg_and_fetches_nothing(self):
        """内联 SVG、跟随主题色、对读屏隐藏、不含任何外链。

        与侧栏图标同一条硬约束：`offline.html` 把同一份标记内联进单文件，断网也要能读；
        `<img src>` / 图标字体在无网时就是一个空方块，而页面看起来「只是少了个小图形」。
        """
        svg = self.LINK_RE.findall(topbar_region(self.pages["index.html"]))[0][3]
        self.assertIn('fill="currentColor"', svg)
        self.assertIn('aria-hidden="true"', svg)
        self.assertIn("<path d=", svg)
        self.assertNotIn("http", svg)
        for bad in ("<img", "<use", "xlink:href"):
            self.assertNotIn(bad, svg, bad)

    def test_link_is_the_rightmost_topbar_control(self):
        """位置：在主题按钮之后（顶栏最右端）—— 开源项目的通行位置，读者会去那儿找。"""
        page = self.pages["index.html"]
        bar = topbar_region(page)
        self.assertIn('id="theme-toggle"', bar)
        self.assertLess(bar.index('id="theme-toggle"'), bar.index("github-link"))
        self.assertLess(bar.index('class="search-btn"'), bar.index("github-link"))
        # 尾随的下划线只对文字有意义，图标上是一条凭空多出来的线
        css = (REPO / "web" / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn(".github-link, .github-link:hover { text-decoration: none; }", css)

    def test_narrow_viewports_shed_the_progress_pill(self):
        """480px 以下收掉进度胶囊 —— 这是「顶栏多了一枚按钮」的配套决定。

        单测量不出布局，所以这条断言落在样式表文本上；真实浏览器实测的数字记在
        `ROADMAP.md` 的 v3.3 一节：480px 视口下站名会从 1 行折成 2 行、顶栏 50.3 → 73px，
        收掉胶囊后回到 1 行；360/400px 下站名本来就是 2 行（改这一版之前也是），
        所以那一档不做别的处理。谁把这条规则删了，480px 上的折行会悄悄回来。
        """
        css = (REPO / "web" / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 480px) {", css)
        self.assertIn(".progress-pill { display: none; }", css)

    def test_footer_reuses_the_same_mark(self):
        """页脚那条「在 GitHub 上查看仓库」用同一枚标识、同一个地址。"""
        page = self.pages["lessons/L15-skills.html"]
        m = re.search(
            r'<a class="footer-repo" href="([^"]+)" target="_blank" rel="noopener">'
            r'(<svg class="github-icon".*?</svg>)在 GitHub 上查看仓库</a>',
            page, re.S,
        )
        self.assertIsNotNone(m, "页脚的仓库链接该带同一枚 GitHub 标识")
        self.assertEqual(m.group(1), self.cfg["repo_url"])
        self.assertIn('fill="currentColor"', m.group(2))

    def test_offline_page_carries_the_mark_and_stays_self_contained(self):
        """单文件离线版没有顶栏，但页脚的那枚标识必须在，且仍然是纯内联标记。"""
        offline = (self.out / "offline.html").read_text(encoding="utf-8")
        self.assertIn('class="footer-repo" href="' + self.cfg["repo_url"] + '"', offline)
        self.assertNotIn("<img", offline)

    def test_missing_repo_url_renders_nothing_instead_of_a_dead_icon(self):
        """site.json 没配仓库地址时不放图标 —— 点了没反应的控件比没有更糟。"""
        self.assertEqual(build_site.github_link({"repo_url": ""}), "")
        self.assertEqual(build_site.topbar_values({"repo_url": ""}), {"github": ""})


class TestPitfallsPage(unittest.TestCase):
    """v1.4 常见错误合集 `/pitfalls.html`：32 课「常见坑」的全量聚合页。

    这一页最容易坏的地方是**链接前缀**：它和首页同在站点根目录，而 `[[Lxx]]`
    在课程页里的映射是「同级页面」（`L15-skills.html`）。照抄那份映射，读者点课号
    就会跳到 `site/L15-skills.html`（不存在）——构建期只有 check_links 会发现，
    所以这里先把它断言死。

    第二处容易坏的是**行数**：表头行 / 分隔行没被解析层跳掉时，页面上会多出
    32 行「现象/真实原因/怎么解决」，看着仍然像一张表。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        cls.base = cls.cfg["base_url"]
        cls.stats = build_site.build(cls.out, cls.cfg)
        cls.page = (cls.out / "pitfalls.html").read_text(encoding="utf-8")
        cls.main = main_region(cls.page)
        cls.lessons = core.load_lessons(REPO)
        cls.groups = core.group_by_stage(cls.lessons)
        cls.expected_rows = sum(len(core.pitfall_rows(l)) for l in cls.lessons)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # --- 内容 --------------------------------------------------------------

    def test_page_exists_and_holds_all_pitfall_rows(self):
        self.assertTrue((self.out / "pitfalls.html").is_file())
        self.assertGreater((self.out / "pitfalls.html").stat().st_size, 0)

        # 数据行 = `<tr>` 后面直接跟着 `<td>` 的行；表头行是 `<th>`，天然被排除。
        data_rows = re.findall(r"<tr>\s*<td>", self.main)
        self.assertEqual(len(data_rows), 334)
        # 与解析层对账（**不是**数 `[[src:` 的出现次数：一个单元格里可能有两个标记）
        self.assertEqual(self.expected_rows, 334)
        self.assertEqual(len(data_rows), self.expected_rows)
        # 表头行另算：每个阶段一张表 → 一行 `<th>`
        self.assertEqual(len(re.findall(r"<tr>", self.main)), len(data_rows) + len(self.groups))
        self.assertEqual(len(self.groups), 8)          # 0/1/2/3/4/5/6/9

    def test_table_columns_are_lesson_symptom_cause_fix(self):
        heads = re.findall(r"<th>([^<]+)</th>", self.main)
        self.assertEqual(heads, ["课", "现象", "真实原因", "怎么解决"] * len(self.groups))

    def test_every_lesson_id_appears(self):
        ids = re.findall(r'<a class="xref" href="[^"]+">(L\d+)</a>', self.main)
        self.assertEqual(set(ids), {l["id"] for l in self.lessons})
        self.assertEqual(len(set(ids)), 40)

    def test_cell_content_is_rendered_not_left_as_markers(self):
        self.assertNotIn("[[", self.main)              # 出处与交叉引用标记都该变成链接
        self.assertIn('class="cite"', self.main)
        self.assertIn("hermes-agent.nousresearch.com", self.main)
        self.assertIn("<code>hermes cron list</code>", self.main)   # 行内代码照常渲染

    # --- 那个坑：课程链接必须带 lessons/ 前缀 -------------------------------

    def test_links_back_to_lessons_carry_the_lessons_prefix(self):
        # 课号总数 = 每行「课」列一个 + 有些格子正文里自己也带交叉引用（本文里 13 处）
        joined = "".join(
            r["symptom"] + r["cause"] + r["fix"]
            for l in self.lessons for r in core.pitfall_rows(l)
        )
        markers = re.findall(r"\[\[(L\d+)\]\]", joined)
        self.assertEqual(len(markers), 13)          # 格子正文里自带的交叉引用（如「见 [[L24]]」）

        hrefs = re.findall(r'<a class="xref" href="([^"]+)"', self.main)
        self.assertEqual(len(hrefs), 334 + len(markers))   # 每行「课」列一个 + 格子里的
        self.assertEqual(set(hrefs), {l["url"] for l in self.lessons})   # 只指向 40 个课程页
        for href in hrefs:
            self.assertTrue(href.startswith("lessons/"), f"合集页在站点根目录，课号必须带前缀：{href}")
            self.assertTrue((self.out / href).is_file(), f"指向不存在的页面：{href}")
        self.assertNotIn('href="L15-skills.html"', self.main)      # 「同级页面」映射的典型错法
        self.assertNotIn('href="../lessons/', self.main)           # 前缀多一层也是死链

    def test_no_broken_links_from_this_page(self):
        self.assertEqual(
            [p for p in build_site.check_links(self.out) if p.startswith("pitfalls.html")], []
        )

    # --- sitemap / canonical / og / 侧栏 ------------------------------------

    def test_page_is_in_the_sitemap(self):
        locs = LOC_RE.findall((self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn(self.base + "pitfalls.html", locs)
        # 组成式：sitemap = 课程页 + 规范页 + 站点根目录的四个可收录页面
        # （首页 / 学习地图 / 常见错误合集 / 设计对比；离线版与 404 不收录）
        self.assertEqual(len(locs), len(self.lessons) + len(self.cfg["repo_docs"]) + 4)
        self.assertEqual(
            len(locs),
            len(list(self.out.rglob("*.html"))) - len(build_site.EXCLUDED_FROM_SITEMAP),
        )

    def test_page_has_canonical_and_five_og_tags(self):
        self.assertEqual(CANONICAL_RE.findall(self.page), [self.base + "pitfalls.html"])
        metas = dict(OG_META_RE.findall(self.page))
        self.assertEqual(len(OG_META_RE.findall(self.page)), 5)
        self.assertEqual(set(metas), OG_NAMES)
        self.assertEqual(metas["og:url"], self.base + "pitfalls.html")
        self.assertTrue(metas["og:title"].startswith("常见错误合集"), metas["og:title"])
        self.assertTrue(metas["og:description"], "og:description 不能为空")

    def test_sidebar_links_the_page_from_root_and_subpages(self):
        for rel, href in (
            ("index.html", "pitfalls.html"),
            ("map.html", "pitfalls.html"),
            ("pitfalls.html", "pitfalls.html"),
            ("lessons/L15-skills.html", "../pitfalls.html"),
            ("repo/roadmap.html", "../pitfalls.html"),
        ):
            page = (self.out / rel).read_text(encoding="utf-8")
            assert_sidebar_entry(self, page, href, "常见错误合集", rel)

    def test_build_fails_loudly_when_a_pitfall_cites_an_unregistered_source(self):
        """未登记的出处必须让构建报错，而不是渲染成一个点了就 404 的标记。

        这一页用到的 `[[src:]]` id 全部已登记；这里用一个假的正文验
        「报错这条路真的通」——绕过去（静默留字面量）才是真的坏。
        """
        fake_groups = [{
            "stage": 9, "name": "毕业项目", "why": "",
            "lessons": [{
                "id": "L99", "title": "假课", "stage": 9,
                "body": "## 常见坑\n\n| 现象 | 真实原因 | 怎么解决 |\n|---|---|---|\n"
                        "| a | b | [[src:not-registered]] |\n",
            }],
        }]
        md = build_site.render_pitfalls_markdown(fake_groups)
        html, _ = R.render_markdown(md)
        with self.assertRaises(R.SiteError) as ctx:
            R.linkify_citations(html, core.load_citations(REPO), "pitfalls.html")
        self.assertIn("not-registered", str(ctx.exception))


class TestExerciseCountsAndReportButton(unittest.TestCase):
    """v2.0 学习报告导出的构建期部分：`data/index.json` 里的练习数 + 导出按钮。

    这一节的关键是**双路对账**：`exercises` 走的是构建期数正文（count_exercises），
    而读者看到的是渲染出来的方框（`<span class="task-box">`）。两条路算的是
    「同一门课有几道练习」这一件事，只要有一边改变了口径（比如以后有人在围栏里
    写示例练习题），数字就会分叉 —— 而分叉之后读者的进度会显示成 3/5 却看到 6 个方框。
    浏览器里看不出这种错，所以在这里把它焊死。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        build_site.build(cls.out, cls.cfg)
        cls.lessons = core.load_lessons(REPO)
        cls.index = json.loads((cls.out / "data" / "index.json").read_text(encoding="utf-8"))
        cls.by_id = {l["id"]: l for l in cls.index["lessons"]}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def boxes_on_page(self, lesson: dict) -> int:
        """该课页面正文里渲染出的练习方框数（只看 <main>，不含侧栏）。"""
        html = (self.out / "lessons" / lesson["page"]).read_text(encoding="utf-8")
        return len(re.findall(r'<span class="task-box"', main_region(html)))

    def test_index_json_has_exercises_for_every_lesson(self):
        self.assertEqual(len(self.index["lessons"]), len(self.lessons))
        for lesson in self.lessons:
            value = self.by_id[lesson["id"]]["exercises"]
            self.assertIsInstance(value, int, lesson["id"])
            self.assertGreater(value, 0, lesson["id"])

    def test_L15_has_five_exercises(self):
        self.assertEqual(self.by_id["L15"]["exercises"], 5)

    def test_L90_has_sixteen_exercises(self):
        self.assertEqual(self.by_id["L90"]["exercises"], 16)

    def test_index_count_equals_rendered_boxes_for_every_lesson(self):
        """双路对账：index.json 的数字 == 页面里真实方框的个数（32 课全查）。"""
        for lesson in self.lessons:
            self.assertEqual(
                self.by_id[lesson["id"]]["exercises"], self.boxes_on_page(lesson),
                f"{lesson['id']}：index.json 与页面方框数不一致",
            )

    def test_total_exercises_agrees_across_both_paths(self):
        total_index = sum(l["exercises"] for l in self.index["lessons"])
        total_pages = sum(self.boxes_on_page(l) for l in self.lessons)
        self.assertEqual(total_index, total_pages)
        # 首页/地图页的进度卡要能报「练习 Z/W」：W 就是这里的总数
        self.assertEqual(total_index, sum(R.count_exercises(l["body"]) for l in self.lessons))

    def test_home_and_map_page_have_the_export_report_button(self):
        for rel in ("index.html", "map.html"):
            html = (self.out / rel).read_text(encoding="utf-8")
            self.assertIn('class="btn export-report" type="button">导出学习报告</button>', html, rel)
            # 用 class 选择器而不是 id：同一个按钮会出现两处，重复 id 是无效 HTML
            self.assertEqual(html.count("export-report"), 1, f"{rel} 应该只有一个导出报告按钮")
            self.assertIn("导出学习报告", main_region(html), rel)

    def test_report_button_does_not_break_the_progress_card_actions(self):
        """首页原有的三个控件必须一个不少（新按钮是**追加**，不是替换）。"""
        home = (self.out / "index.html").read_text(encoding="utf-8")
        for needle in ('id="next-lesson"', 'id="export-progress"', 'id="import-progress"',
                       'id="import-file"', 'class="btn export-report"'):
            self.assertIn(needle, home)
        self.assertEqual(home.count('class="pc-actions"'), 1)

    def test_export_report_buttons_live_in_the_progress_card(self):
        """按钮要落在进度卡里：它是「把这份进度交出去」，不是独立功能。"""
        for rel in ("index.html", "map.html"):
            html = (self.out / rel).read_text(encoding="utf-8")
            card = re.search(r'<section class="card progress-card"[^>]*>(.*?)</section>', html, re.S)
            self.assertIsNotNone(card, rel)
            self.assertIn('class="btn export-report"', card.group(1), rel)

    def test_app_js_downloads_the_report(self):
        """接线留在 app.js：报告文件名与 download 调用都要在产物里。"""
        app = (self.out / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("hermes-usage-report.md", app)
        self.assertIn("buildReport", app)
        report = (self.out / "assets" / "lib" / "report.js").read_text(encoding="utf-8")
        self.assertIn("export function buildReport", report)
        self.assertIn("export function summarize", report)


class TestDesignPage(unittest.TestCase):
    """v3.1 设计对比 `/design.html`：10 套 UI 方案 × 10 个维度的评分矩阵。

    这一页最容易坏的地方**不是样式**，而是「页面上的数字与数据源脱钩」：
    有人手改一句结论、或者改了 `web/assets/app.css` 却没重算 token 表，
    页面照样渲染得好好的，只是开始说假话。所以这一组断言全部是**双路对账**：

    - 页面上的赢家 ⟷ `design_matrix.winner()`
    - 页面上印的 token 取值链 ⟷ 从 app.css `:root` 现读出来的链
    - 页面上那 8 行对比度结论 ⟷ 现算的 WCAG 比值（必须全部通过）
    - `data/design.json` ⟷ 同一份数据源（同一个赢家、同一个字节数）
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        cls.base = cls.cfg["base_url"]
        build_site.build(cls.out, cls.cfg)
        cls.page = (cls.out / "design.html").read_text(encoding="utf-8")
        cls.main = main_region(cls.page)
        cls.css = (REPO / "web" / "assets" / "app.css").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # --- 内容与数据源 -------------------------------------------------------

    def test_page_exists_and_is_not_empty(self):
        self.assertTrue((self.out / "design.html").is_file())
        self.assertGreater((self.out / "design.html").stat().st_size, 0)

    def test_winner_named_on_the_page_is_the_computed_winner(self):
        winners = re.findall(r"<td><strong>([^<]+)</strong> ← 赢家</td>", self.main)
        self.assertEqual(winners, [D.winner()["name"]])
        self.assertIn(f"{D.score(D.winner()):.2f}", self.main)
        # 结论句里的平均分也必须与现算值一致（正文里没有任何手写数字）
        self.assertIn(f"**{D.score(D.winner()):.2f}**", D.render_markdown(self.css))

    def matrix_table_html(self) -> str:
        """页面里那张**矩阵表**的 HTML。

        判据是「包含『← 赢家』」而不是「第三张表」或者「第一个 <table>」：页面上共有
        五张表（方案清单 / 维度说明 / 矩阵 / 赢家与差距 / 改造前后），其中「赢家与差距」
        与「改造前后」的行也以 **加粗** 或 *斜体* 开头 —— 不限定范围去数行数，
        数出来的是「所有表格里首格加粗的行」（实测 23 行而不是 12 行）。
        """
        for table in re.findall(r"<table[^>]*>.*?</table>", self.main, re.S):
            if "← 赢家" in table:
                return table
        raise AssertionError("页面里找不到矩阵表（没有带「← 赢家」的表格）")

    def test_wide_tables_are_wrapped_so_they_can_scroll_on_a_phone(self):
        """12 列的矩阵在手机上必须能横向滚动，而不是被挤成竖条。

        做法是给这一页的每张表套一层 `.table-wrap`（真正的滚动容器），
        并给矩阵表本身一个最小宽度（`table.matrix`）。包没包上在浏览器里
        一眼能看出来，但「漏包了哪一张」在构建期只有断言能发现。
        """
        tables = len(re.findall(r"<table[^>]*>", self.main))
        # 八张表：方案清单 / 维度说明 / 矩阵 / 赢家与差距 / 采纳清单 / 令牌表 / 对比度 / 改造前后
        self.assertEqual(tables, 8)
        self.assertEqual(self.main.count('<div class="table-wrap">'), tables)
        self.assertEqual(self.main.count('class="matrix"'), 1)
        self.assertIn('<table class="matrix">', self.main)
        # 矩阵表是那张宽表：其余表格不该拿到最小宽度（那会让手机上也出现滚动条）
        for table in re.findall(r"<table[^>]*>", self.main):
            if "matrix" not in table:
                self.assertEqual(table, "<table>", table)

    def test_matrix_has_a_row_per_system_plus_two_reference_rows(self):
        rows = re.findall(r"<tr>\s*<td>(?:<strong>|<em>)", self.matrix_table_html())
        self.assertEqual(len(rows), len(D.SYSTEMS) + 2)
        for system in D.SYSTEMS:
            self.assertIn(system["name"], self.main, system["key"])
        self.assertIn("改造前", self.main)
        self.assertIn("改造后", self.main)

    def test_every_dimension_header_is_rendered(self):
        self.assertEqual(
            re.findall(r"<th>([^<]+)</th>", self.matrix_table_html()),
            ["方案"] + [D.SHORT[k] for k in D.DIM_KEYS] + ["平均"],
        )

    def test_token_table_matches_app_css(self):
        for item in D.APPLIED_TOKENS:
            with self.subTest(token=item["token"]):
                steps = D.token_chain(self.css, item["token"])
                cell = " → ".join(f"<code>{step}</code>" for step in steps)
                self.assertIn(f"<td>{cell}</td>", self.main)

    def test_contrast_table_is_fully_passing_and_matches_the_css(self):
        self.assertNotIn("❌", self.main)
        self.assertEqual(self.main.count("✅ 通过"), len(D.CONTRAST_PAIRS))
        for fg, bg, _, _ in D.CONTRAST_PAIRS:
            ratio = D.contrast_ratio(D.hex_of(self.css, fg), D.hex_of(self.css, bg))
            self.assertIn(f"<strong>{ratio}:1</strong>", self.main)

    def test_stylesheet_size_on_the_page_matches_the_file(self):
        stats = build_site.D.css_stats(self.css)
        self.assertEqual(stats["bytes"], (REPO / "web" / "assets" / "app.css").stat().st_size)
        self.assertIn(f"{stats['bytes']:,} 字节", self.main)

    def test_chart_svg_is_embedded_with_one_bar_per_row(self):
        self.assertIn("chart-figure", self.main)
        self.assertEqual(self.main.count("<svg"), 1)
        self.assertEqual(self.main.count("<rect"), len(D.SYSTEMS) + 2)
        self.assertIn('role="img"', self.main)

    def test_chart_placeholder_never_reaches_the_reader(self):
        # 占位符必须已被换成 SVG；页面上任何一处都不该残留 {{…}} 形态的模板标记
        self.assertNotIn(D.CHART_PLACEHOLDER, self.page)
        self.assertNotIn("{{", self.page)
        self.assertIn("<svg", self.main)

    def test_no_markdown_markers_left_in_the_body(self):
        self.assertNotIn("[[", self.main)
        self.assertNotIn("**", self.main)          # markdown 加粗必须已经变成 <strong>
        for source in D.SOURCES:
            self.assertIn(source["url"], self.main, source["url"])

    def test_sources_and_systems_links_are_absolute_https(self):
        hrefs = re.findall(r'<a[^>]+href="([^"]+)"', self.main)
        external = [h for h in hrefs if h.startswith("http")]
        self.assertGreaterEqual(len(external), len(D.SOURCES))
        for href in external:
            self.assertTrue(href.startswith("https://"), href)

    # --- 机器可读版本 -------------------------------------------------------

    def test_design_json_matches_the_module(self):
        data = json.loads((self.out / "data" / "design.json").read_text(encoding="utf-8"))
        self.assertEqual(data["winner"], D.winner()["key"])
        self.assertEqual(len(data["systems"]), len(D.SYSTEMS))
        self.assertEqual(len(data["dimensions"]), len(D.DIMENSIONS))
        self.assertEqual(data["stylesheet"]["bytes"], (REPO / "web" / "assets" / "app.css").stat().st_size)
        self.assertTrue(all(row["pass"] for row in data["contrast"]), data["contrast"])
        self.assertEqual([s["rank"] for s in data["systems"]], list(range(1, len(D.SYSTEMS) + 1)))

    # --- sitemap / canonical / og / 侧栏 ------------------------------------

    def test_page_is_in_the_sitemap(self):
        locs = LOC_RE.findall((self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn(self.base + "design.html", locs)
        self.assertEqual(
            len(locs),
            len(list(self.out.rglob("*.html"))) - len(build_site.EXCLUDED_FROM_SITEMAP),
        )

    def test_page_has_canonical_and_five_og_tags(self):
        self.assertEqual(CANONICAL_RE.findall(self.page), [self.base + "design.html"])
        metas = dict(OG_META_RE.findall(self.page))
        self.assertEqual(len(OG_META_RE.findall(self.page)), 5)
        self.assertEqual(set(metas), OG_NAMES)
        self.assertEqual(metas["og:type"], "article")
        self.assertEqual(metas["og:url"], self.base + "design.html")
        self.assertTrue(metas["og:title"].startswith("设计对比"), metas["og:title"])
        self.assertTrue(metas["og:description"], "og:description 不能为空")

    def test_sidebar_links_the_page_from_root_and_subpages(self):
        for rel, href in (
            ("index.html", "design.html"),
            ("map.html", "design.html"),
            ("pitfalls.html", "design.html"),
            ("design.html", "design.html"),
            ("lessons/L15-skills.html", "../design.html"),
            ("repo/roadmap.html", "../design.html"),
        ):
            page = (self.out / rel).read_text(encoding="utf-8")
            assert_sidebar_entry(self, page, href, "设计对比", rel)

    def test_no_broken_links_from_this_page(self):
        self.assertEqual(
            [p for p in build_site.check_links(self.out) if p.startswith("design.html")], []
        )

    # --- 与离线版的关系 -----------------------------------------------------

    def test_offline_page_stays_self_contained_and_does_not_inline_this_page(self):
        offline = (self.out / "offline.html").read_text(encoding="utf-8")
        for needle in ("<link ", "<script", 'src="', 'href="design.html"'):
            self.assertNotIn(needle, offline, f"离线版不该出现 {needle}")
        # 它内联的那份样式表里当然**有** .chart 那几条规则、注释里也提了 /design.html
        # （逐字内联就是这个意思），但它自己不含这张图，也没有指向这一页的链接：
        # 离线版是「40 课正文」，不是整站。
        # 唯一的例外是页脚那一枚 GitHub 标识（内联 SVG，v3.3）：它不属于任何一页的正文，
        # 而是全站页脚的一部分，单文件版也该带着它。所以断言写成「这张图表不在、侧栏图标
        # 也不在、内联 SVG 只有那一枚」，而不是「一个 svg 都没有」——后者会把
        # 「页脚长出一枚图标」误报成「离线版开始内联整站」。
        self.assertNotIn('<svg class="chart"', offline)
        self.assertNotIn('<svg class="nav-icon"', offline)
        self.assertEqual(offline.count("<svg"), 1, "离线版里只该有页脚那一枚 GitHub 标识")


class TestSiteReachability(unittest.TestCase):
    """v1.2 站点可达性：canonical / og / sitemap / robots / skip-link。

    这些元信息错了在浏览器里**完全看不出来**（页面照常渲染），只能靠断言。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        cls.base = cls.cfg["base_url"]
        cls.stats = build_site.build(cls.out, cls.cfg)
        cls.sitemap = (cls.out / "sitemap.xml").read_text(encoding="utf-8")
        cls.locs = LOC_RE.findall(cls.sitemap)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # --- sitemap -----------------------------------------------------------

    def test_sitemap_lists_every_html_page_except_the_excluded_ones(self):
        # 组成式：产物里的 .html 减掉明确不进 sitemap 的那几个（错误页 + 离线单文件版）
        excluded = build_site.EXCLUDED_FROM_SITEMAP
        listed = [
            p for p in self.out.rglob("*.html")
            if p.relative_to(self.out).as_posix() not in excluded
        ]
        self.assertEqual(len(self.locs), len(listed))
        self.assertEqual(len(self.locs), len(list(self.out.rglob("*.html"))) - len(excluded))
        for name in excluded:
            self.assertFalse([loc for loc in self.locs if loc.endswith(name)], self.locs)

    def test_sitemap_covers_every_lesson(self):
        for lesson in core.load_lessons(REPO):
            self.assertIn(self.base + lesson["url"], self.locs, lesson["id"])

    def test_sitemap_locs_are_absolute_https_under_base_url(self):
        for loc in self.locs:
            self.assertTrue(loc.startswith("https://"), loc)
            self.assertTrue(loc.startswith(self.base), loc)

    def test_sitemap_entries_have_lastmod(self):
        self.assertEqual(self.sitemap.count("<lastmod>"), len(self.locs))
        # 课程 frontmatter 的 updated 要真的被用上（而不是全站一个日期）
        lesson = next(l for l in core.load_lessons(REPO) if l["id"] == "L01")
        i = self.locs.index(self.base + lesson["url"])
        entry = self.sitemap.split("<url>")[i + 1]
        self.assertIn(f"<lastmod>{lesson['updated']}</lastmod>", entry)

    # --- canonical / og ----------------------------------------------------

    def test_lesson_page_has_five_og_tags_and_canonical(self):
        page = (self.out / "lessons" / "L15-skills.html").read_text(encoding="utf-8")
        self.assertEqual(CANONICAL_RE.findall(page), [self.base + "lessons/L15-skills.html"])
        metas = dict(OG_META_RE.findall(page))
        self.assertEqual(len(OG_META_RE.findall(page)), 5)
        self.assertEqual(set(metas), OG_NAMES)
        self.assertEqual(metas["og:type"], "article")
        self.assertEqual(metas["og:url"], self.base + "lessons/L15-skills.html")
        self.assertTrue(metas["og:title"].startswith("「L15"), metas["og:title"])
        self.assertTrue(metas["og:description"], "og:description 不能为空")

    def test_home_page_canonical_is_base_url_itself(self):
        page = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertEqual(CANONICAL_RE.findall(page), [self.base])
        metas = dict(OG_META_RE.findall(page))
        self.assertEqual(len(OG_META_RE.findall(page)), 5)
        self.assertEqual(set(metas), OG_NAMES)
        self.assertEqual(metas["og:type"], "website")
        self.assertEqual(metas["og:url"], self.base)
        self.assertEqual(metas["og:title"], self.cfg["title"])
        self.assertEqual(metas["og:site_name"], self.cfg["title"])

    def test_repo_page_has_five_og_tags_and_canonical(self):
        page = (self.out / "repo" / "roadmap.html").read_text(encoding="utf-8")
        self.assertEqual(CANONICAL_RE.findall(page), [self.base + "repo/roadmap.html"])
        self.assertEqual(len(OG_META_RE.findall(page)), 5)
        self.assertEqual(dict(OG_META_RE.findall(page))["og:type"], "article")
        # 这个页面的正文里出现 "og:" 字样好几个（ROADMAP 自己在描述这条需求），
        # 所以上面那两行必须按 <meta property="og:"> 数，不能按字符串数。
        self.assertGreater(page.count("og:"), 5)

    # --- robots / skip-link / 自检 -----------------------------------------

    def test_robots_txt_points_to_sitemap(self):
        robots = (self.out / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("User-agent: *", robots)
        self.assertIn("Allow: /", robots)
        self.assertIn(f"Sitemap: {self.base}sitemap.xml", robots)

    def test_skip_link_is_first_in_body_and_search_button_labelled(self):
        for rel in ("index.html", "lessons/L15-skills.html", "repo/roadmap.html"):
            page = (self.out / rel).read_text(encoding="utf-8")
            self.assertIn('<a class="skip-link" href="#main">跳到正文</a>', page, rel)
            self.assertIn('aria-label="搜索课程（Ctrl+K）"', page, rel)
            self.assertLess(page.index("skip-link"), page.index('<header class="topbar"'), rel)
        css = (self.out / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn(".skip-link", css)
        self.assertIn(".skip-link:focus", css)

    def test_check_seo_is_clean(self):
        self.assertEqual(build_site.check_seo(self.out, self.cfg), [])

    # --- 主题：首帧不闪白 + 键名只有一份 -----------------------------------

    def test_theme_bootstrap_runs_before_the_stylesheet(self):
        """暗色用户在首帧不该看到白屏：主题脚本必须在样式表**之前**、且同步执行。

        这不是「感觉更快」的问题：`<link rel=stylesheet>` 一到，浏览器就可能
        画出第一帧。主题脚本排在它后面，暗色用户就会先看到一帧白底再跳黑（FOUC）。
        内联脚本不能带 `src`/`defer`/`async` —— 那三样都会把执行时机推到解析之后，
        等于没修。
        """
        for rel in ("index.html", "lessons/L15-skills.html", "design.html", "repo/roadmap.html"):
            html = (self.out / rel).read_text(encoding="utf-8")
            script_at = html.index('localStorage.getItem("hermes-usage:theme:v1")')
            sheet_at = html.index('<link rel="stylesheet"')
            self.assertLess(script_at, sheet_at, rel)
            script_tag = html[:script_at].rsplit("<script", 1)[1]
            for needle in ("defer", "async", "src="):
                self.assertNotIn(needle, script_tag, rel)
            # 浏览器 UI 也跟着主题走（地址栏/状态栏配色）
            self.assertEqual(html.count('<meta name="theme-color"'), 2, rel)

    def test_theme_storage_key_is_the_same_string_in_both_places(self):
        """内联脚本必须与 storage.js 用同一个键名。

        键名写错的表现是「切了主题、刷新回到默认」——而页面不会报任何错。
        所以直接拿 storage.js 里的 THEME_KEY 去比对（它是唯一权威）。
        """
        storage = (REPO / "web" / "assets" / "lib" / "storage.js").read_text(encoding="utf-8")
        key = re.search(r'export const THEME_KEY = "([^"]+)"', storage)
        self.assertIsNotNone(key, "storage.js 里找不到 THEME_KEY")
        for rel in ("index.html", "lessons/L15-skills.html", "design.html"):
            html = (self.out / rel).read_text(encoding="utf-8")
            self.assertIn(f'localStorage.getItem("{key.group(1)}")', html, rel)
            app = (self.out / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertGreaterEqual(app.count("THEME_CYCLE"), 2)      # 常量 + 使用处
        self.assertNotIn("THEME_CYCLE = [", app.split("boot();")[1].split("\n")[0])  # 别搬回后面

    def test_theme_toggle_is_labelled_for_screen_readers(self):
        """切主题的按钮要说清「现在是什么、按下去会变成什么」。"""
        html = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('aria-label="切换主题"', html)      # 无 JS 时的静态标签
        app = (self.out / "assets" / "app.js").read_text(encoding="utf-8")
        for label in ("跟随系统", "亮色", "暗色"):
            self.assertIn(label, app, label)

    def test_check_seo_flags_a_page_missing_its_meta(self):
        """自检本身要能抓到问题：把一个页面的 og 标签删掉，它必须报出来。"""
        victim = self.out / "lessons" / "L15-skills.html"
        original = victim.read_text(encoding="utf-8")
        try:
            victim.write_text(re.sub(r'<meta property="og:[^>]*>\n', "", original), encoding="utf-8", newline="\n")
            problems = build_site.check_seo(self.out, self.cfg)
        finally:
            victim.write_text(original, encoding="utf-8", newline="\n")
        self.assertTrue(problems)
        self.assertTrue(any("L15-skills.html" in p for p in problems), problems)

    def test_build_refuses_empty_base_url(self):
        cfg = dict(self.cfg)
        cfg["base_url"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(R.SiteError) as ctx:
                build_site.build(Path(tmp) / "site", cfg)
        self.assertIn("base_url", str(ctx.exception))

    def test_base_url_is_normalised_to_a_trailing_slash(self):
        self.assertEqual(build_site.site_base(self.cfg), self.base)
        self.assertEqual(
            build_site.site_base({"base_url": "https://example.com/x"}),
            "https://example.com/x/",   # 少了斜杠会拼成 /xlessons/L01….html
        )

    def test_sitemap_and_robots_text_shape(self):
        xml = build_site.build_sitemap([(self.base, "2026-01-02")])
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>\n'))
        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', xml)
        self.assertIn(f"<url><loc>{self.base}</loc><lastmod>2026-01-02</lastmod></url>", xml)
        self.assertTrue(xml.endswith("</urlset>\n"))
        self.assertEqual(
            build_site.build_robots(self.cfg),
            f"User-agent: *\nAllow: /\n\nSitemap: {self.base}sitemap.xml\n",
        )


OFFLINE_ARTICLE_RE = re.compile(r'<article class="lesson offline-lesson" id="(L\d+)"')
OFFLINE_ID_RE = re.compile(r'\sid="([^"]+)"')
OFFLINE_TOC_RE = re.compile(r'<nav class="page-toc"[^>]*id="offline-toc"[^>]*>(.*?)</nav>', re.S)
STYLE_BLOCK_RE = re.compile(r"<style>(.*?)</style>", re.S)
XREF_ANCHOR_RE = re.compile(r'<a class="xref" href="([^"]+)"')
HREF_RE = re.compile(r'href="([^"]+)"')


class TestOfflineSingleFile(unittest.TestCase):
    """v2.0 单文件离线版 `/offline.html`：整套课程压进一个 HTML，双击就能读。

    这一页的形态与站点其它页面**相反**：零外部依赖、零 JS、所有课程链接都是页内
    锚点。三处最容易静默坏掉的地方，这里逐个焊死：

    1. **标题 id 前缀**：32 课拼进同一份文档，`render_markdown` 默认给 `s1/s2…`，
       不传课号前缀就会在同一份文件里出现 32 组重复 id。浏览器只认第一个匹配，
       于是「点第 20 课的目录项跳到第 1 课」—— 而页面本身渲染得好好的，
       `check_links` 也抓不到（锚点不是文件链接）。所以这里直接数 `id=`。
    2. **课程链接必须是 `#L15`，不是 `lessons/L15-skills.html`**：单文件旁边没有
       `lessons/` 目录，课程页那份「同级页面」映射照抄过来就是 32 条死链。
       这与 pitfalls 页那个「必须带 `lessons/` 前缀」的坑是同一件事的镜像，
       也是本项目里已经踩过一次的错法。
    3. **零外部/相对资源**：出现任何 `<script>` / `<link rel="stylesheet">` /
       `src="…"` / 相对 href，这个文件就不再是「拷到 U 盘、双击可读」的了。

    另外把「体积」也钉住：离线版的卖点就是能当附件发出去。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.cfg = build_site.load_config()
        cls.base = cls.cfg["base_url"]
        build_site.build(cls.out, cls.cfg)
        cls.path = cls.out / "offline.html"
        cls.html = cls.path.read_text(encoding="utf-8")
        cls.lessons = core.load_lessons(REPO)
        cls.ids = [l["id"] for l in cls.lessons]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # --- 结构与目录 ---------------------------------------------------------

    def test_page_exists_with_one_article_per_lesson(self):
        self.assertTrue(self.path.is_file())
        self.assertGreater(self.path.stat().st_size, 0)
        self.assertEqual(self.html.count('class="lesson offline-lesson"'), len(self.lessons))
        articles = OFFLINE_ARTICLE_RE.findall(self.html)
        self.assertEqual(len(articles), len(self.lessons))
        self.assertEqual(articles, self.ids)          # 顺序 = 学习顺序，不重不漏

    def test_toc_groups_lessons_by_stage_and_links_in_page_anchors(self):
        m = OFFLINE_TOC_RE.search(self.html)
        self.assertIsNotNone(m, "离线版缺少 id=offline-toc 的目录")
        toc = m.group(1)
        self.assertEqual(re.findall(r'<a href="#(L\d+)">', toc), self.ids)
        for lid in self.ids:
            self.assertIn(f'<a href="#{lid}">', toc, lid)
        # 目录按阶段分组：组数 == 阶段数（每个阶段一个 <ol class="toc-l2">）
        self.assertEqual(len(re.findall(r'<ol class="toc-l2">', toc)),
                         len(core.group_by_stage(self.lessons)))

    def test_header_says_what_this_file_is_and_how_to_search(self):
        head = self.html[: self.html.index('id="offline-toc"')]
        for needle in ("离线", "Ctrl+F", f"{len(self.lessons)} 课", "src:"):
            self.assertIn(needle, head, needle)
        # 出处徽标悬停能看到版本与哈希这条事实，要在说明里讲清楚
        self.assertIn("哈希", head)

    # --- 自包含（本任务的核心断言）------------------------------------------

    def test_no_external_or_relative_resource_references(self):
        for needle in ('<link rel="stylesheet"', "<link ", "<script", 'src="', 'href="../'):
            self.assertNotIn(needle, self.html, f"离线版不该出现 {needle}")
        for tag in ("<img", "<iframe", "<video", "<audio"):
            self.assertNotIn(tag, self.html, tag)
        # 每一个 href 要么是站外绝对地址，要么是页内锚点；没有第三种可能
        hrefs = HREF_RE.findall(self.html)
        self.assertTrue(hrefs)
        for href in hrefs:
            self.assertTrue(href.startswith(("https://", "#")), href)

    def test_stylesheet_is_inlined_verbatim(self):
        css = (REPO / "web" / "assets" / "app.css").read_text(encoding="utf-8")
        blocks = STYLE_BLOCK_RE.findall(self.html)
        self.assertEqual(len(blocks), 1, "离线版应该恰好内联一份样式表")
        self.assertEqual(blocks[0], css)              # 逐字内联，不是精简/改写版
        self.assertEqual(len(blocks[0].encode("utf-8")), len(css.encode("utf-8")))
        self.assertGreater(len(blocks[0]), 5_000)

    def test_file_is_small_enough_to_attach(self):
        size = len(self.html.encode("utf-8"))
        self.assertLess(size, 2 * 1024 * 1024, "离线版超过 2MB 就不再适合当附件发了")
        # 下限也要有：比 32 课 markdown 原文 + 样式表总和大，说明正文真的都在里面
        floor = sum(len(l["body"].encode("utf-8")) for l in self.lessons) + \
            (REPO / "web" / "assets" / "app.css").stat().st_size
        self.assertGreater(size, floor)

    # --- 那个坑：同文档 id 不许重复 -----------------------------------------

    def test_every_id_in_the_document_is_unique(self):
        found = OFFLINE_ID_RE.findall(self.html)
        self.assertTrue(found)
        duplicates = sorted({v for v in found if found.count(v) > 1})
        self.assertEqual(duplicates, [], f"同一份文档里 id 重复：{duplicates}")
        for lid in self.ids:
            self.assertIn(lid, found, lid)

    def test_heading_ids_carry_the_lesson_prefix(self):
        heading_ids = re.findall(r'<h[23] id="([^"]+)"', self.html)
        self.assertTrue(heading_ids)
        for hid in heading_ids:
            self.assertRegex(hid, r"^L\d{2}-s\d+$")
        self.assertNotIn('id="s1"', self.html)        # 默认前缀在单文件里必然撞车

    def test_lesson_cross_references_stay_inside_the_file(self):
        hrefs = XREF_ANCHOR_RE.findall(self.html)
        self.assertTrue(hrefs, "32 课正文里应该有 [[Lxx]] → 页内锚点")
        allowed = {f"#{lid}" for lid in self.ids}
        for href in hrefs:
            self.assertIn(href, allowed, f"离线版的课号必须指向页内锚点：{href}")
        for href in HREF_RE.findall(self.html):
            self.assertNotIn("lessons/", href, "单文件旁边没有 lessons/ 目录，这种链接是死链")

    def test_citation_badges_keep_absolute_provenance(self):
        cites = re.findall(r'<a class="cite" href="([^"]+)"', self.html)
        self.assertTrue(cites)
        for href in cites:
            self.assertTrue(href.startswith("https://hermes-agent.nousresearch.com/docs/"), href)
        self.assertIn("hermes v", self.html)          # title 里有版本
        self.assertRegex(self.html, r"快照 sha256 [0-9a-f]{12}")
        # 与 32 个课程页对账：正文里有几个徽标，离线版就该有几个（不多不少）
        page_total = sum(
            len(re.findall(r'<a class="cite"',
                           main_region((self.out / "lessons" / l["page"]).read_text(encoding="utf-8"))))
            for l in self.lessons
        )
        self.assertEqual(len(cites), page_total)

    # --- sitemap / 链接自检 -------------------------------------------------

    def test_offline_page_and_404_are_excluded_from_the_sitemap(self):
        locs = LOC_RE.findall((self.out / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertEqual(build_site.EXCLUDED_FROM_SITEMAP, {"404.html", "offline.html"})
        self.assertNotIn(self.base + "offline.html", locs)
        self.assertNotIn(self.base + "404.html", locs)
        self.assertEqual(
            len(locs),
            len(list(self.out.rglob("*.html"))) - len(build_site.EXCLUDED_FROM_SITEMAP),
        )

    def test_no_broken_links_from_this_page(self):
        self.assertEqual(
            [p for p in build_site.check_links(self.out) if p.startswith("offline.html")], []
        )

    def test_home_offers_the_single_file_download(self):
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn('<a class="btn" href="offline.html" download>下载离线版（单文件）</a>', home)
        card = re.search(r'<section class="card progress-card"[^>]*>(.*?)</section>', home, re.S)
        self.assertIsNotNone(card)
        self.assertIn('href="offline.html"', card.group(1), "下载入口要落在进度卡的按钮组里")

    def test_lesson_bodies_contain_no_resource_markup_today(self):
        """把上面那条「零外部资源」断言的**前提**钉住。

        离线版是 32 课正文的拼接，所以「文件里没有 `<script` / `src="`」这条断言
        其实同时在断言**课程正文**里没有这些字样。今天确实没有；哪天有人在围栏
        代码里写 `<script>` 示例（阶段 4 讲插件时很容易），这条会先红，失败信息
        直接指向那一课 —— 而不是让离线版无声地不再自包含。
        """
        for lesson in self.lessons:
            for needle in ("<script", 'src="', 'href="../', '<link rel="stylesheet"'):
                self.assertNotIn(needle, lesson["body"], f"{lesson['id']} 正文含 {needle}")


if __name__ == "__main__":
    unittest.main()

class TestLinkRewriterIgnoresCode(unittest.TestCase):
    """文档里**讨论** href 时（写在反引号/代码块里）不能被当成真链接——否则构建会报假错。"""

    def test_repo_doc_link_rewriter_skips_code(self):
        import build_site as B, tutorial_core as core
        lesson = next(l for l in core.load_lessons(REPO) if l["id"] == "L00")
        html = (
            '<p>反引号里的 <code>href="../x"</code> 是给人看的</p>'
            '<pre><code>href="../../y.py"</code></pre>'
            '<p>真链接：<a href="CONTRIBUTING.md">CONTRIBUTING.md</a></p>'
        )
        out = B.rewrite_repo_doc_links(html, ".hermes.md", B.load_config())
        self.assertIn('href="../x"', out)                     # 代码区原样保留
        self.assertEqual(out.count('href="../x"'), 1)
        self.assertIn('href="contributing.html"', out)        # 真链接被改写成规范页
        # 取链接也必须跳过代码区，否则文档里讨论 href 就会变成假断链
        self.assertEqual(B.link_targets(html), ["CONTRIBUTING.md"])
