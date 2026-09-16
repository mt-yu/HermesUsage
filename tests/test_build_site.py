#!/usr/bin/env python3
"""tests/test_build_site.py —— 构建器集成测试：真的构建到临时目录，然后验收产物。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_site  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
