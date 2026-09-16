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


class TestRenderMarkdownPrefix(unittest.TestCase):
    """v2.0：`render_markdown(body, prefix)` 让标题 id 带前缀。

    为什么需要它：单文件离线版把 32 课拼进**同一份 HTML**。默认前缀 `"s"` 下
    每课都从 `s1` 重新开始，同一份文档里就会出现 32 组重复 id —— 浏览器与
    `#s1` 式锚点只认第一个，读者点第 20 课的目录项会跳到第 1 课，而页面渲染
    得好好的，肉眼巡检 32 遍也未必看得出来。

    所以这里断言两件事：默认行为**一个字都不能变**（现有 42 个页面全靠它），
    以及传了前缀时每个标题 id 都真的带上了前缀。
    """

    MD = "# 标题不进目录\n\n## 你将学会\n\n正文\n\n### 子节\n\n## 出处\n"

    def test_default_prefix_keeps_old_behaviour(self):
        html, toc = R.render_markdown(self.MD)
        self.assertIn('<h2 id="s1">你将学会</h2>', html)
        self.assertIn('<h3 id="s2">子节</h3>', html)
        self.assertIn('<h2 id="s3">出处</h2>', html)
        self.assertEqual([t["id"] for t in toc], ["s1", "s2", "s3"])

    def test_prefix_is_concatenated_verbatim_before_the_counter(self):
        """`prefix` 是**原样**拼在编号前的，调用方怎么传决定了 id 长什么样。

        单文件离线版要的是 `L15-s1` 这种「课号 + 站内那套 `s<序号>`」的形态
        （一眼看出这是 L15 的第 2 节、且与课程页的 `s1/s2…` 对得上），所以它传
        `f"{id}-s"`；只传 `f"{id}-"` 会得到 `L15-1` —— 同样唯一，但少了后面的
        对号关系。两种写法都在这里钉住，免得以后有人以为 prefix 会自动补 `s`。
        """
        html, toc = R.render_markdown(self.MD, prefix="L15-")
        self.assertIn('<h2 id="L15-1">你将学会</h2>', html)
        self.assertEqual([t["id"] for t in toc], ["L15-1", "L15-2", "L15-3"])

        html, toc = R.render_markdown(self.MD, prefix="L15-s")
        self.assertIn('<h2 id="L15-s1">你将学会</h2>', html)
        self.assertIn('<h3 id="L15-s2">子节</h3>', html)
        self.assertIn('<h2 id="L15-s3">出处</h2>', html)
        self.assertEqual([t["id"] for t in toc], ["L15-s1", "L15-s2", "L15-s3"])
        self.assertNotIn('id="s1"', html)          # 默认前缀没被顺手带上

    def test_two_lessons_stop_colliding_when_each_gets_its_own_prefix(self):
        """同一份 HTML 里拼两课时，不传前缀必然撞 id；传课号前缀就不会。"""
        first, _ = R.render_markdown(self.MD)
        second, _ = R.render_markdown(self.MD)
        collided = set(re.findall(r'<h[23] id="([^"]+)"', first + second))
        self.assertLess(len(collided), 6)          # s1/s2/s3 各只出现一次 → id 撞车

        a, _ = R.render_markdown(self.MD, prefix="L15-")
        b, _ = R.render_markdown(self.MD, prefix="L16-")
        self.assertEqual(len(set(re.findall(r'<h[23] id="([^"]+)"', a + b))), 6)


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


class TestCountExercises(unittest.TestCase):
    """v2.0 `count_exercises`：把「这门课有几道练习」变成一个可断言的数字。

    它和 `preprocess_tasklist` 是最容易悄悄漂移的一对：一个把 `- [ ]` 变成复选框
    （渲染层），另一个数出练习总数写进 `data/index.json`（构建期的数据层）。
    两边对「围栏代码块里的示例算不算一题」的判断一旦不一致，读者就会看到
    「练习 3/5」的进度条对上 6 个方框 —— 这种错在浏览器里一点都看不出来。
    所以这里除了断言数字，还断言它与真实渲染出的方框数一致。
    """

    def test_empty_and_exercise_free_body_is_zero(self):
        self.assertEqual(R.count_exercises(""), 0)
        self.assertEqual(R.count_exercises("# 标题\n\n正文，这一课没有练习。\n"), 0)

    def test_counts_checked_and_unchecked_alike(self):
        self.assertEqual(R.count_exercises("- [ ] 一\n- [x] 二\n- [X] 三\n"), 3)

    def test_fenced_code_blocks_do_not_count(self):
        body = "- [ ] 真题一\n\n```markdown\n- [ ] 示例：怎么写练习清单\n- [x] 示例二\n```\n\n- [ ] 真题二\n"
        self.assertEqual(R.count_exercises(body), 2)

    def test_other_list_markers_and_prose_do_not_count(self):
        body = "- 普通条目\n* 星号条目\n1. 有序条目\n\n> - [ ] 引用里的\n\n正文里的 `- [ ]` 是行内代码。\n"
        self.assertEqual(R.count_exercises(body), 0)

    def test_match_rendered_boxes_one_to_one(self):
        """同一份正文：数出来的题数 == 渲染出的方框数 == 最大的 data-ex 编号。"""
        body = "- [ ] 一\n\n```text\n- [ ] 示例，不算一题\n```\n\n- [x] 二\n- [ ] 三\n"
        out = R.preprocess_tasklist(body)
        ids = [int(n) for n in re.findall(r'data-ex="(\d+)"', out)]
        self.assertEqual(len(ids), R.count_exercises(body))
        self.assertEqual(max(ids), R.count_exercises(body))
        self.assertEqual(out.count('class="task-box"'), R.count_exercises(body))

    def test_real_lessons_L15_and_L90(self):
        by_id = {l["id"]: l for l in core.load_lessons(REPO)}
        self.assertEqual(R.count_exercises(by_id["L15"]["body"]), 5)
        self.assertEqual(R.count_exercises(by_id["L90"]["body"]), 16)

    def test_every_real_lesson_has_a_plausible_count(self):
        """32 课全都要有练习；数字还要和正文里的任务行数对得上（防回归到「数了围栏里的」）。"""
        for lesson in core.load_lessons(REPO):
            self.assertGreater(R.count_exercises(lesson["body"]), 0, lesson["id"])
            self.assertLessEqual(
                R.count_exercises(lesson["body"]),
                len(R.TASKLIST_RE.findall(lesson["body"])),
                lesson["id"],
            )


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
