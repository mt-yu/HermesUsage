#!/usr/bin/env python3
"""tests/test_tutorial_core.py —— 解析层单元测试。

运行：python -m unittest discover -s tests -t . -p "test_*.py" -v
为什么不用 pytest：仓库只承诺 PyYAML + Markdown 两个依赖，pytest 不在其中（本机也没装）。
标准库 unittest 够用，且不增加任何安装步骤。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import tutorial_core as core  # noqa: E402

SAMPLE = """---
id: L99
title: 示例课
stage: 3
level: 进阶
minutes: 20
prereq: [L10]
tags: ["@引用", "示例"]
sources: [quickstart, agent-loop]
updated: 2026-09-16
---

# L99 · 示例课

> **一句话**：这一课用来验证解析层。

## 你将学会

- 解析 frontmatter
"""


class TestFrontmatter(unittest.TestCase):
    def test_parse_frontmatter_fields(self):
        fm = core.parse_frontmatter(SAMPLE)
        self.assertEqual(fm["id"], "L99")
        self.assertEqual(fm["stage"], 3)
        self.assertEqual(fm["prereq"], ["L10"])
        self.assertEqual(fm["sources"], ["quickstart", "agent-loop"])

    def test_parse_frontmatter_without_frontmatter_returns_empty(self):
        self.assertEqual(core.parse_frontmatter("# 只有正文\n"), {})

    def test_parse_frontmatter_with_broken_yaml_returns_empty(self):
        broken = "---\nid: L99\ntitle: [未闭合\n---\n\n# x\n"
        self.assertEqual(core.parse_frontmatter(broken), {})

    def test_split_frontmatter_returns_body(self):
        fm, body = core.split_frontmatter(SAMPLE)
        self.assertEqual(fm["id"], "L99")
        self.assertTrue(body.startswith("\n# L99 · 示例课"))


class TestDerivedFields(unittest.TestCase):
    def test_lesson_summary(self):
        _, body = core.split_frontmatter(SAMPLE)
        self.assertEqual(core.lesson_summary(body), "这一课用来验证解析层。")

    def test_lesson_summary_missing(self):
        self.assertEqual(core.lesson_summary("## 正文\n没有一句话摘要\n"), "")

    def test_slug_and_urls(self):
        rel = "lessons/01-core/L15-skills.md"
        self.assertEqual(core.lesson_slug(rel), "L15-skills")
        self.assertEqual(core.lesson_page(rel), "L15-skills.html")
        self.assertEqual(core.lesson_url(rel), "lessons/L15-skills.html")

    def test_slug_accepts_path_object(self):
        self.assertEqual(core.lesson_slug(Path("lessons/06-capstone/L90-capstone.md")), "L90-capstone")

    def test_stage_names(self):
        self.assertEqual(core.stage_name(3), "自动化与多代理")
        self.assertEqual(core.stage_name(42), "阶段 42")
        self.assertTrue(core.stage_why(1))


class TestLoadLessonsOnRealRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lessons = core.load_lessons(REPO)

    def test_count_matches_repo(self):
        self.assertEqual(len(self.lessons), 32)

    def test_sorted_by_stage_then_id(self):
        keys = [(l["stage"], l["id"]) for l in self.lessons]
        self.assertEqual(keys, sorted(keys))

    def test_every_lesson_has_answerable_fields(self):
        for l in self.lessons:
            self.assertRegex(l["id"], r"^L\d{2,}$")
            self.assertTrue(l["title"])
            self.assertTrue(l["summary"], f"{l['id']} 缺「一句话」摘要")
            self.assertTrue(l["sources"], f"{l['id']} 没有出处")
            self.assertTrue(l["url"].startswith("lessons/"))
            self.assertTrue(l["body"].startswith("\n#"), f"{l['id']} 正文异常")

    def test_first_and_last(self):
        self.assertEqual(self.lessons[0]["id"], "L00")
        self.assertEqual(self.lessons[-1]["id"], "L90")


class TestCitations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.citations = core.load_citations(REPO)

    def test_all_registered(self):
        self.assertGreaterEqual(len(self.citations), 89)

    def test_entry_shape(self):
        entry = self.citations["quickstart"]
        self.assertTrue(entry["url"].startswith("https://hermes-agent.nousresearch.com/docs"))
        self.assertEqual(len(str(entry["sha256"])), 64)
        self.assertTrue(entry["title"])

    def test_every_lesson_source_is_registered(self):
        for lesson in core.load_lessons(REPO):
            for sid in lesson["sources"]:
                self.assertIn(sid, self.citations, f"{lesson['id']} 引用了未登记的 {sid}")

    def test_baseline(self):
        b = core.source_baseline(REPO)
        self.assertEqual(b["version"], "0.21.3")
        self.assertTrue(b["commit"].startswith("05fac10a"))
        self.assertGreaterEqual(b["count"], 89)


class TestTutorPrompt(unittest.TestCase):
    """「带我学」提示语只有一份：桌面部件（build_map）与站点地图页共用它。

    这句话会被塞进 data-hermes-send / data-hermes-prompt，用户在桌面应用里
    看到的字面量就是它 —— 所以断言按**逐字**比较，不按「包含关键词」比较。
    """

    @classmethod
    def setUpClass(cls):
        cls.by_id = {l["id"]: l for l in core.load_lessons(REPO)}

    def test_tutor_prompt_matches_expected_sentence_for_real_lesson(self):
        lesson = self.by_id["L15"]
        self.assertEqual(
            core.tutor_prompt(lesson),
            "带我学 L15「技能系统：让它学会你的活法」：先读 lessons/01-core/L15-skills.md，"
            "然后按课里的「先动手」一步步带我走，每步都等我确认",
        )

    def test_tutor_prompt_uses_fullwidth_brackets_and_commas(self):
        """全角括号「」/「，」/「：」是刻意的：半角版本在中文排版里挤成一团。"""
        prompt = core.tutor_prompt(self.by_id["L15"])
        self.assertNotIn('"', prompt)
        self.assertIn("「", prompt)
        self.assertIn("」", prompt)
        self.assertEqual(prompt.count("「"), 2)
        self.assertEqual(prompt.count("」"), 2)
        self.assertIn("：先读 ", prompt)
        self.assertIn("，然后按课里的", prompt)

    def test_tutor_prompt_is_built_from_lesson_fields(self):
        lesson = self.by_id["L90"]
        prompt = core.tutor_prompt(lesson)
        self.assertIn(lesson["id"], prompt)
        self.assertIn(lesson["title"], prompt)
        self.assertIn(lesson["rel"], prompt)

    def test_tutor_prompt_for_every_lesson_reads_back_its_own_fields(self):
        for lesson in self.by_id.values():
            prompt = core.tutor_prompt(lesson)
            self.assertTrue(prompt.startswith(f"带我学 {lesson['id']}「{lesson['title']}」：先读 "))
            self.assertTrue(prompt.endswith("每步都等我确认"), lesson["id"])
            self.assertIn(lesson["rel"], prompt, lesson["id"])


class TestMapRows(unittest.TestCase):
    """站点地图页与桌面部件共用的行数据（单一来源）。"""

    KEYS = {"id", "title", "stage", "minutes", "rel", "url", "done", "prompt"}

    @classmethod
    def setUpClass(cls):
        cls.lessons = core.load_lessons(REPO)
        cls.rows = core.map_rows(cls.lessons)

    def test_row_count_matches_lessons(self):
        self.assertEqual(len(self.rows), len(self.lessons))
        self.assertEqual(len(self.rows), 32)

    def test_row_shape(self):
        for row in self.rows:
            self.assertEqual(set(row), self.KEYS, row["id"])
            self.assertIsInstance(row["done"], bool)
            self.assertIsInstance(row["minutes"], int)
            self.assertIsInstance(row["stage"], int)
            self.assertTrue(row["url"].startswith("lessons/"))
            self.assertTrue(row["url"].endswith(".html"))

    def test_rows_sorted_by_stage_then_id(self):
        keys = [(r["stage"], r["id"]) for r in self.rows]
        self.assertEqual(keys, sorted(keys))

    def test_url_matches_lesson_page(self):
        by_id = {l["id"]: l for l in self.lessons}
        for row in self.rows:
            self.assertEqual(row["url"], by_id[row["id"]]["url"])

    def test_prompt_comes_from_tutor_prompt(self):
        by_id = {l["id"]: l for l in self.lessons}
        for row in self.rows:
            self.assertEqual(row["prompt"], core.tutor_prompt(by_id[row["id"]]))

    def test_done_defaults_to_all_false(self):
        self.assertFalse(any(r["done"] for r in self.rows))

    def test_done_flags_only_named_lessons(self):
        rows = core.map_rows(self.lessons, done={"L15", "L90"})
        flagged = {r["id"] for r in rows if r["done"]}
        self.assertEqual(flagged, {"L15", "L90"})


class TestGrouping(unittest.TestCase):
    def test_groups_cover_all_stages(self):
        groups = core.group_by_stage(core.load_lessons(REPO))
        self.assertEqual([g["stage"] for g in groups], [0, 1, 2, 3, 4, 5, 9])
        self.assertEqual(sum(len(g["lessons"]) for g in groups), 32)
        self.assertEqual(groups[-1]["name"], "毕业项目")

    def test_group_keeps_lesson_order(self):
        groups = core.group_by_stage(core.load_lessons(REPO))
        stage1 = next(g for g in groups if g["stage"] == 1)
        self.assertEqual([l["id"] for l in stage1["lessons"]], ["L10", "L11", "L12", "L13", "L14", "L15"])


if __name__ == "__main__":
    unittest.main()
