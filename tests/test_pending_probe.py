#!/usr/bin/env python3
"""tests/test_pending_probe.py —— 「待发布清单」脚本的判据与数据表。

真跑 19 条网络探针不适合进单测（慢、依赖网络），这里钉三件事：
  1. 纯函数（evaluate/summarize/render）的语义；
  2. 数据表的完整性（编号唯一、doc 类必须写 doc_id 且它在 registry.yaml 里）；
  3. **needle 必须是「main 侧独有」的字符串** —— 这条最值钱：第一版里 #8 的 needle
     选了 `Follow-up messages do not cancel`，而 release 版里**也有**这句话，探针于是假阳性。
     现在每条 needle 都必须在「本机安装树 / 快照」里命中、同时（不该）在 release 里命中。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import pending_probe as P  # noqa: E402
import release_probe as RP  # noqa: E402

LOCAL_TREE = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "hermes-agent"


class TestEvaluate(unittest.TestCase):
    def test_any_needle_counts(self):
        self.assertTrue(P.evaluate("x schema_valid y", ("schema_valid",)))
        self.assertTrue(P.evaluate("a\nb coalesce c", ("nope", "coalesce")))

    def test_missing_file_is_not_landed(self):
        self.assertFalse(P.evaluate(None, ("anything",)))

    def test_absent_symbol_is_not_landed(self):
        self.assertFalse(P.evaluate("nothing here", ("coalesce",)))


class TestSummarizeAndRender(unittest.TestCase):
    def _rows(self):
        return [
            {"n": 1, "claim": "甲", "course": "", "landed": True, "evidence": "f.py:1 x"},
            {"n": 2, "claim": "乙", "course": "L31", "landed": False, "evidence": "0 命中"},
        ]

    def test_counts(self):
        s = P.summarize(self._rows())
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["landed_count"], 1)
        self.assertEqual(s["still_missing_count"], 1)

    def test_render_names_the_landed_item_and_its_evidence(self):
        out = P.render(self._rows(), "v2026.10.1")
        self.assertIn("#1", out)
        self.assertIn("f.py:1 x", out)
        self.assertIn("v2026.10.1", out)
        self.assertIn("baseline-release", out)     # 有落地才提示「换基线」

    def test_render_omits_the_baseline_advice_when_nothing_landed(self):
        rows = [{"n": 1, "claim": "甲", "course": "", "landed": False, "evidence": "-"},
                {"n": 2, "claim": "乙", "course": "", "landed": False, "error": "boom",
                 "evidence": "<没核成>"}]
        out = P.render(rows, "v1")
        self.assertNotIn("baseline-release", out)  # 一条都没落地：别叫人去改基线
        self.assertIn("#2", out)                   # 没核成的要说出来

    def test_quiet_is_silent_only_when_nothing_landed(self):
        all_missing = [{"n": 1, "claim": "甲", "course": "", "landed": False, "evidence": "-"}]
        self.assertEqual(P.render(all_missing, "v1", quiet=True), "")
        self.assertNotEqual(P.render(self._rows(), "v1", quiet=True), "")


class TestDataTable(unittest.TestCase):
    def test_numbers_are_unique_and_contiguous(self):
        ns = [i["n"] for i in P.ITEMS]
        self.assertEqual(ns, list(range(1, len(ns) + 1)))

    def test_doc_items_declare_a_registered_doc_id(self):
        reg = P.load_doc_paths()
        for it in P.ITEMS:
            if it["kind"] == "doc":
                with self.subTest(item=it["n"]):
                    self.assertTrue(it["doc_id"], f"#{it['n']} 是 doc 类却没写 doc_id")
                    self.assertIn(it["doc_id"], reg, f"#{it['n']} 的 doc_id 不在 registry.yaml 里")

    def test_code_items_declare_a_path_and_needles(self):
        for it in P.ITEMS:
            if it["kind"] == "code":
                with self.subTest(item=it["n"]):
                    self.assertTrue(it["path"].endswith((".py", ".md", ".ts")))
                    self.assertTrue(it["needles"])

    def test_every_item_is_still_traceable_in_the_roadmap(self):
        # 数据表与 ROADMAP 是两份拷贝：这条钉住「改了脚本别忘了文档」
        roadmap = (REPO / "ROADMAP.md").read_text(encoding="utf-8")
        for it in P.ITEMS:
            with self.subTest(item=it["n"]):
                self.assertIn(it["roadmap_token"], roadmap,
                              f"#{it['n']} 的 token {it['roadmap_token']!r} 在 ROADMAP.md 里找不到")

    def test_needles_are_main_side_only(self):
        """needle 必须在 main 侧（本机安装树）命中 —— 否则探针永远假阴性/假阳性。

        注意 main 侧 = **本机安装树的 website/docs**（不是 sources/cache：那是 2026-09-15
        的快照，比 main 落后好几天，有些新写法那时还没进快照 —— 第一版就是这么写错的）。
        """
        docs = LOCAL_TREE / "website" / "docs"
        reg = P.load_doc_paths()
        for it in P.ITEMS:
            with self.subTest(item=it["n"]):
                if it["kind"] == "doc":
                    rel = reg.get(it["doc_id"] or "")
                    p = docs / (rel or "")
                    if not p.is_file():
                        self.skipTest(f"本机没有 {rel}（换机器时跳过这半条）")
                    text = p.read_text(encoding="utf-8", errors="replace")
                else:
                    p = LOCAL_TREE / it["path"]
                    if not p.is_file():
                        self.skipTest(f"本机没有 {it['path']}（换机器时跳过这半条）")
                    text = p.read_text(encoding="utf-8", errors="replace")
                self.assertTrue(P.evaluate(text, it["needles"]),
                                f"#{it['n']} 的 needle {it['needles']} 在 main 侧都找不到 —— "
                                "它多半是两版都有的普通句子，换成新写法里独有的短语")


if __name__ == "__main__":
    unittest.main()
