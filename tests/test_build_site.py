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
        # lessons/pages 的组成写清楚，不留魔法数字：
        # 页数 = 课程页（= 课程数）+ 仓库规范页（= site.json 的 repo_docs 条数）+ 首页 + 404
        self.assertEqual(self.stats["lessons"], 32)

        lesson_pages = len(list((self.out / "lessons").glob("*.html")))
        repo_pages = len(list((self.out / "repo").glob("*.html")))
        cfg = build_site.load_config()

        self.assertEqual(lesson_pages, 32)                      # 每课一页
        self.assertEqual(repo_pages, len(cfg["repo_docs"]))     # 每个 repo_doc 一页
        self.assertTrue((self.out / "index.html").is_file())     # 首页
        self.assertTrue((self.out / "404.html").is_file())       # 404
        self.assertEqual(self.stats["pages"], lesson_pages + repo_pages + 2)

    def test_index_and_data_files_exist(self):
        for rel in ("index.html", "404.html", ".nojekyll",
                    "data/index.json", "data/citations.json", "data/search.json", "data/manifest.json",
                    "assets/app.css", "assets/app.js"):
            self.assertTrue((self.out / rel).is_file(), f"缺 {rel}")

    def test_every_lesson_has_a_page(self):
        for lesson in core.load_lessons(REPO):
            self.assertTrue((self.out / "lessons" / lesson["page"]).is_file(), lesson["id"])

    def test_index_json_shape(self):
        data = json.loads((self.out / "data" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["lessons"]), 32)
        first = data["lessons"][0]
        for key in ("id", "title", "stage", "minutes", "level", "prereq", "summary", "url"):
            self.assertIn(key, first)

    def test_search_json_shape(self):
        data = json.loads((self.out / "data" / "search.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["docs"]), 32)
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
        self.assertEqual(len(manifest["lessons"]), 32)
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
