#!/usr/bin/env python3
"""tests/test_build_roadmap_svg.py —— README 路线图 SVG 生成器的单元测试。

运行：python -m unittest discover -s tests -t . -p "test_*.py" -v

两条纪律：
1. 这些测试**不写 docs/roadmap.svg**（那是 CLI 的活）：纯函数一律直接调，
   需要碰文件的地方用临时文件 + `mock.patch.object(br, "OUT", ...)`。
2. 「生成物是否与课程同步」由 `check.py` 与 `python scripts/build_roadmap_svg.py --check` 负责；
   这里只钉住「同样的输入必然得到同样的字节」与「危险标记一个都不能有」。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_roadmap_svg as br  # noqa: E402
import tutorial_core as core  # noqa: E402


def fake_lesson(lid: str, stage: int, title: str, minutes: int = 25) -> dict:
    return {
        "id": lid, "title": title, "stage": stage, "minutes": minutes,
        "level": "入门", "prereq": [], "tags": [], "sources": [],
        "updated": "2026-09-16", "file": Path(f"{lid}-x.md"),
    }


class TestEscaping(unittest.TestCase):
    """SVG 是 XML：课程标题里出现 & 或 < 时，转义顺序错了整张图就解析不了。"""

    def test_amp_is_escaped_before_brackets(self):
        self.assertEqual(br.esc("A & B"), "A &amp; B")
        self.assertEqual(br.esc("<C>"), "&lt;C&gt;")

    def test_quotes_and_apostrophes_escaped(self):
        out = br.esc('说"引号" 和 \'单引号\'')
        self.assertIn("&quot;", out)
        self.assertNotIn('"', out.replace("&quot;", ""))

    def test_amp_does_not_double_escape(self):
        """& 若在 &lt; 之后才换，就会得到 &amp;lt; —— 顺序错了这里会红。"""
        self.assertNotIn("&amp;lt;", br.esc("<"))

    def test_title_with_markup_still_parses(self):
        svg = br.render([fake_lesson("L00", 0, "A & B <C>")], None)
        ET.fromstring(svg)  # 不转义 → ParseError
        self.assertIn("A &amp; B &lt;C&gt;", svg)


class TestTextMetrics(unittest.TestCase):
    """宽度估算决定了芯片会不会挤爆 —— 它是布局的判据，必须有测试。"""

    def test_cjk_counts_full_width(self):
        self.assertGreater(br.text_width("中文", 14), br.text_width("ab", 14))

    def test_clip_shortens_long_text(self):
        long_title = "技能系统：让它学会你的活法，而且这个标题长到放不进任何芯片里"
        clipped = br.clip(long_title, 100, 14)
        self.assertLess(len(clipped), len(long_title))
        self.assertTrue(clipped.endswith("…"))

    def test_clip_keeps_short_text_intact(self):
        self.assertEqual(br.clip("短", 100, 14), "短")


class TestRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lessons = core.load_lessons(REPO)
        cls.svg = br.render(cls.lessons, core.source_baseline(REPO))

    def test_parses_as_xml_and_is_1200_wide(self):
        root = ET.fromstring(self.svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(root.get("width"), "1200")

    def test_contains_every_lesson_id(self):
        for lesson in self.lessons:
            self.assertIn(lesson["id"], self.svg, lesson["id"])

    def test_contains_every_stage_name(self):
        for stage in core.group_by_stage(self.lessons):
            self.assertIn(stage["name"][:4], self.svg, stage["name"])

    def test_counts_match_tutorial_core(self):
        """图上的「32 课 / 7 个阶段 / N 分钟」必须来自课程本身，不能手抄。"""
        total_minutes = sum(l["minutes"] for l in self.lessons)
        self.assertIn(f"{total_minutes} 分钟", self.svg)
        self.assertIn(f"{len(self.lessons)} 课", self.svg)

    def test_deterministic_bytes(self):
        again = br.render(self.lessons, core.source_baseline(REPO))
        self.assertEqual(self.svg, again)

    def test_no_dangerous_markup(self):
        """GitHub 会消毒 SVG：外链脚本、foreignObject、filter 引用都会带来渲染风险。"""
        for bad in ("<script", "<foreignObject", "xlink:href", "url(#"):
            self.assertNotIn(bad, self.svg, bad)

    def test_only_external_url_is_the_xmlns(self):
        self.assertEqual(len(re.findall(r"https?://", self.svg)), 1)


class TestCommittedFile(unittest.TestCase):
    """真正被 README 引用的那个文件本身也得体检。"""

    def test_file_has_no_bom_and_no_crlf(self):
        raw = br.OUT.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "有 BOM")
        self.assertNotIn(b"\r\n", raw, "有 CRLF（跨平台门禁会红）")

    def test_file_is_utf8_and_parses(self):
        root = ET.fromstring(br.OUT.read_text(encoding="utf-8"))
        self.assertTrue(root.tag.endswith("svg"))


class TestCheckMode(unittest.TestCase):
    def test_check_returns_0_when_in_sync(self):
        with mock.patch.object(sys, "argv", ["build_roadmap_svg.py", "--check"]):
            self.assertEqual(br.main(), 0)

    def test_check_returns_1_when_file_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "roadmap.svg"
            stale.write_text("<svg>旧图</svg>", encoding="utf-8")
            with mock.patch.object(br, "OUT", stale), \
                 mock.patch.object(sys, "argv", ["build_roadmap_svg.py", "--check"]):
                self.assertEqual(br.main(), 1)
            self.assertEqual(stale.read_text(encoding="utf-8"), "<svg>旧图</svg>")

    def test_printed_size_is_bytes_not_characters(self):
        """回归：曾经报的是 len(str)（字符数）。中文在 UTF-8 里 3 字节，
        于是「20803 字节」比真实文件小了 2 KB —— 报尺寸必须 encode 之后算。"""
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "roadmap.svg"
            buf = io.StringIO()
            with mock.patch.object(br, "OUT", target), \
                 mock.patch.object(sys, "argv", ["build_roadmap_svg.py"]), \
                 redirect_stdout(buf):
                self.assertEqual(br.main(), 0)
            reported = int(re.search(r"(\d+) 字节", buf.getvalue()).group(1))
            self.assertEqual(reported, target.stat().st_size)

    def test_stdout_mode_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "roadmap.svg"
            with mock.patch.object(br, "OUT", target), \
                 mock.patch.object(sys, "argv", ["build_roadmap_svg.py", "--stdout"]):
                self.assertEqual(br.main(), 0)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
