#!/usr/bin/env python3
"""tests/test_site_render.py —— 渲染层纯函数单元测试 + 全仓库内容回归。"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import site_render as R  # noqa: E402
import tutorial_core as core  # noqa: E402


class TestPreprocess(unittest.TestCase):
    def test_strips_template_comments(self):
        src = "前<!-- 这是给作者看的（含 [[src:xxx]]） -->后"
        self.assertEqual(R.strip_template_comments(src).strip(), "前后")

    def test_tasklist_becomes_visual_box(self):
        out = R.preprocess_tasklist("- [ ] 练习一\n- [x] 练习二\n")
        self.assertIn('<span class="task-box" data-ex="1" data-checked="0" aria-hidden="true"></span> 练习一', out)
        self.assertIn('<span class="task-box" data-ex="2" data-checked="1" aria-hidden="true"></span> 练习二', out)
        self.assertNotIn("[ ]", out)

    def test_tasklist_ignores_normal_bullets_and_code(self):
        out = R.preprocess_tasklist("- 普通条目\n\n```bash\n- [ ] 这不是练习\n```\n")
        self.assertNotIn("task-box", out)

    def test_tasklist_numbers_boxes_in_lesson_order(self):
        """课内编号必须稳定地从 1 递增，已勾选/未勾选一视同仁地参与编号。"""
        out = R.preprocess_tasklist("- [ ] 一\n- [ ] 二\n\n- [x] 三\n")
        self.assertIn('data-ex="1" data-checked="0"', out)
        self.assertIn('data-ex="2" data-checked="0"', out)
        self.assertIn('data-ex="3" data-checked="1"', out)
        self.assertLess(out.index('data-ex="1"'), out.index('data-ex="2"'))
        self.assertLess(out.index('data-ex="2"'), out.index('data-ex="3"'))

    def test_tasklist_numbering_restarts_for_each_lesson(self):
        """一次调用 = 一课正文，所以第二次调用必须又从 1 开始。"""
        first = R.preprocess_tasklist("- [ ] 一课第一题\n- [ ] 一课第二题\n")
        second = R.preprocess_tasklist("- [ ] 下一课第一题\n")
        self.assertIn('data-ex="2"', first)
        self.assertIn('data-ex="1"', second)
        self.assertNotIn('data-ex="3"', second)

    def test_tasklist_numbering_skips_fenced_code_but_counts_rest(self):
        out = R.preprocess_tasklist("- [ ] 一\n\n```text\n- [ ] 示例，不算一题\n```\n\n- [ ] 二\n")
        self.assertIn("- [ ] 示例，不算一题", out)
        self.assertIn('data-ex="2"', out)
        self.assertNotIn('data-ex="3"', out)


class TestHeadingIdsAndToc(unittest.TestCase):
    MD = "# 标题不进目录\n\n## 你将学会\n\n正文\n\n### 子节\n\n正文\n\n## 出处\n"

    def test_ids_are_sequential_and_language_free(self):
        html, toc = R.add_heading_ids("<h1>标题</h1>\n<h2>你将学会</h2>\n<h3>子节</h3>\n<h2>出处</h2>")
        self.assertIn('<h2 id="s1">你将学会</h2>', html)
        self.assertIn('<h3 id="s2">子节</h3>', html)
        self.assertIn('<h2 id="s3">出处</h2>', html)
        self.assertEqual([t["level"] for t in toc], [2, 3, 2])

    def test_toc_items_carry_text(self):
        _, toc = R.add_heading_ids("<h2>你将学会</h2>")
        self.assertEqual(toc, [{"id": "s1", "level": 2, "text": "你将学会"}])

    def test_toc_html_nests_by_level(self):
        toc = [{"id": "s1", "level": 2, "text": "A"}, {"id": "s2", "level": 3, "text": "A1"}]
        html = R.build_toc_html(toc)
        self.assertIn('<a href="#s1">A</a>', html)
        self.assertIn('<a href="#s2">A1</a>', html)
        self.assertLess(html.index("A</a>"), html.index("A1</a>"))

    def test_empty_toc_renders_empty_string(self):
        self.assertEqual(R.build_toc_html([]), "")


CITES = {
    "quickstart": {
        "title": "Quickstart",
        "url": "https://hermes-agent.nousresearch.com/docs/getting-started/quickstart",
        "hermes_version": "0.21.3",
        "sha256": "a" * 64,
    }
}


class TestMarkers(unittest.TestCase):
    def test_citation_becomes_link_with_provenance(self):
        out = R.linkify_citations("<p>跑一次 [[src:quickstart]] 就知道</p>", CITES, "L01")
        self.assertIn('class="cite"', out)
        self.assertIn('href="https://hermes-agent.nousresearch.com/docs/getting-started/quickstart"', out)
        self.assertIn("hermes v0.21.3", out)
        self.assertIn("aaaaaaaaaaaa", out)          # 哈希前缀，可核对
        self.assertNotIn("[[src:", out)

    def test_unknown_citation_raises_with_context(self):
        with self.assertRaises(R.SiteError) as ctx:
            R.linkify_citations("[[src:nope]]", CITES, "L01")
        self.assertIn("L01", str(ctx.exception))
        self.assertIn("nope", str(ctx.exception))

    def test_marker_inside_code_is_not_rewritten(self):
        html = '<pre><code>[[src:quickstart]]</code></pre><p>[[src:quickstart]]</p>'
        out = R.linkify_citations(html, CITES, "L01")
        self.assertIn("<code>[[src:quickstart]]</code>", out)
        self.assertIn('class="cite"', out)
        self.assertEqual(out.count('class="cite"'), 1)

    def test_xref_links_to_sibling_page(self):
        out = R.linkify_xrefs("<p>顺路看 [[L13]]</p>", {"L13": "L13-memory.html"}, "L15")
        self.assertIn('<a class="xref" href="L13-memory.html">L13</a>', out)

    def test_unknown_xref_raises(self):
        with self.assertRaises(R.SiteError):
            R.linkify_xrefs("[[L99]]", {"L13": "L13-memory.html"}, "L15")

    def test_render_template_fills_and_rejects_leftovers(self):
        out = R.render_template("<title>{{title}}</title><p>{{body}}</p>",
                                {"title": "T", "body": "B"}, "index.html")
        self.assertEqual(out, "<title>T</title><p>B</p>")
        with self.assertRaises(R.SiteError) as ctx:
            R.render_template("<p>{{whoops}}</p>", {}, "index.html")
        self.assertIn("whoops", str(ctx.exception))


class TestRepoDocSlug(unittest.TestCase):
    def test_slug_is_ascii_and_readable(self):
        self.assertEqual(R.repo_doc_slug(".hermes.md"), "hermes-md")
        self.assertEqual(R.repo_doc_slug("sources/README.md"), "sources-readme")
        self.assertEqual(R.repo_doc_slug("templates/lesson.md"), "templates-lesson")


class TestLessonContentIsRenderable(unittest.TestCase):
    """课程正文本该是纯 Markdown：除代码围栏与行内反引号外，不该有裸 HTML 标签。"""

    RAW_HTML_RE = re.compile(r"<[a-zA-Z][a-zA-Z0-9_:-]*")

    def test_no_raw_html_outside_code(self):
        offenders = []
        for lesson in core.load_lessons(REPO):
            in_fence = False
            for lineno, line in enumerate(lesson["body"].split("\n"), 1):
                if line.lstrip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                stripped = re.sub(r"`[^`]*`", "", line)
                stripped = re.sub(r"<!--.*?-->", "", stripped)
                if self.RAW_HTML_RE.search(stripped):
                    offenders.append(f"{lesson['rel']}:{lineno}: {stripped.strip()[:80]}")
        self.assertEqual(offenders, [], "把尖括号内容放进反引号里，否则浏览器里会消失")

    def test_every_lesson_renders_sections(self):
        for lesson in core.load_lessons(REPO):
            html, toc = R.render_markdown(lesson["body"])
            self.assertGreaterEqual(len(toc), 8, f"{lesson['id']} 的目录少于 8 节")
            self.assertIn("<h1", html)


if __name__ == "__main__":
    unittest.main()
