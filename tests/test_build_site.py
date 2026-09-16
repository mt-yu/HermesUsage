#!/usr/bin/env python3
"""tests/test_build_site.py —— 构建器集成测试：真的构建到临时目录，然后验收产物。"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_site  # noqa: E402
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
        for rel in ("index.html", "map.html", "pitfalls.html", "404.html"):
            self.assertTrue((self.out / rel).is_file(), f"缺 {rel}")
        self.assertEqual(root_pages, 4)                          # 首页 / 地图 / 合集 / 404
        self.assertEqual(self.stats["pages"], lesson_pages + repo_pages + root_pages)

        # 文件数也是组成式：页面 + 非页面文件（sitemap/robots/.nojekyll/data/*.json/assets/*）
        non_html = [p for p in self.out.rglob("*") if p.is_file() and p.suffix != ".html"]
        self.assertEqual(self.stats["files"], self.stats["pages"] + len(non_html))
        self.assertTrue(non_html, "产物里除了 .html 还应该有 sitemap/robots/data/资源文件")

    def test_index_and_data_files_exist(self):
        for rel in ("index.html", "404.html", "map.html", ".nojekyll",
                    "data/index.json", "data/citations.json", "data/search.json", "data/manifest.json",
                    "assets/app.css", "assets/app.js"):
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

    def test_no_unfilled_placeholders_in_pages(self):
        for page in self.out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("{{", text, page.as_posix())


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
        # 组成式：sitemap 条目数 == 产物 .html 数 - 1（404 不收录）
        self.assertEqual(len(locs), len(list(self.out.rglob("*.html"))) - 1)

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
            self.assertIn(f'<li><a href="{href}">学习地图</a></li>', page, rel)

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

    def test_page_exists_and_holds_all_253_pitfall_rows(self):
        self.assertTrue((self.out / "pitfalls.html").is_file())
        self.assertGreater((self.out / "pitfalls.html").stat().st_size, 0)

        # 数据行 = `<tr>` 后面直接跟着 `<td>` 的行；表头行是 `<th>`，天然被排除。
        data_rows = re.findall(r"<tr>\s*<td>", self.main)
        self.assertEqual(len(data_rows), 253)
        # 与解析层对账（**不是**数 `[[src:` 的出现次数：一个单元格里可能有两个标记）
        self.assertEqual(self.expected_rows, 253)
        self.assertEqual(len(data_rows), self.expected_rows)
        # 表头行另算：每个阶段一张表 → 一行 `<th>`
        self.assertEqual(len(re.findall(r"<tr>", self.main)), len(data_rows) + len(self.groups))
        self.assertEqual(len(self.groups), 7)          # 0/1/2/3/4/5/9

    def test_table_columns_are_lesson_symptom_cause_fix(self):
        heads = re.findall(r"<th>([^<]+)</th>", self.main)
        self.assertEqual(heads, ["课", "现象", "真实原因", "怎么解决"] * len(self.groups))

    def test_every_lesson_id_appears(self):
        ids = re.findall(r'<a class="xref" href="[^"]+">(L\d+)</a>', self.main)
        self.assertEqual(set(ids), {l["id"] for l in self.lessons})
        self.assertEqual(len(set(ids)), 32)

    def test_cell_content_is_rendered_not_left_as_markers(self):
        self.assertNotIn("[[", self.main)              # 出处与交叉引用标记都该变成链接
        self.assertIn('class="cite"', self.main)
        self.assertIn("hermes-agent.nousresearch.com", self.main)
        self.assertIn("<code>hermes cron list</code>", self.main)   # 行内代码照常渲染

    # --- 那个坑：课程链接必须带 lessons/ 前缀 -------------------------------

    def test_links_back_to_lessons_carry_the_lessons_prefix(self):
        # 课号总数 = 每行「课」列一个 + 有些格子正文里自己也带交叉引用（本文里 10 处）
        joined = "".join(
            r["symptom"] + r["cause"] + r["fix"]
            for l in self.lessons for r in core.pitfall_rows(l)
        )
        markers = re.findall(r"\[\[(L\d+)\]\]", joined)
        self.assertEqual(len(markers), 10)          # 格子正文里自带的交叉引用（如「见 [[L24]]」）

        hrefs = re.findall(r'<a class="xref" href="([^"]+)"', self.main)
        self.assertEqual(len(hrefs), 253 + len(markers))   # 每行「课」列一个 + 格子里的
        self.assertEqual(set(hrefs), {l["url"] for l in self.lessons})   # 只指向 32 个课程页
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
        # 组成式：sitemap = 课程页 + 规范页 + 首页/地图/合集（404 不收录）
        self.assertEqual(len(locs), len(self.lessons) + len(self.cfg["repo_docs"]) + 3)
        self.assertEqual(len(locs), len(list(self.out.rglob("*.html"))) - 1)

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
            self.assertIn(f'<li><a href="{href}">常见错误合集</a></li>', page, rel)

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

    def test_sitemap_lists_every_html_page_except_404(self):
        html_pages = [p for p in self.out.rglob("*.html") if p.name != "404.html"]
        self.assertEqual(len(self.locs), len(html_pages))
        self.assertEqual(len(self.locs), len(list(self.out.rglob("*.html"))) - 1)
        self.assertFalse([loc for loc in self.locs if loc.endswith("404.html")], self.locs)

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


if __name__ == "__main__":
    unittest.main()
