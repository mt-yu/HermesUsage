#!/usr/bin/env python3
"""tests/test_release_probe.py —— release 探针的纯函数与两种模式。

真跑一遍 95 页的网络抓取不适合放进单测（慢、且依赖网络），所以这里只喂字节/字符串，
把「判据」钉住：tag 怎么选、LF 怎么归一化、什么算漂移、基线与 quiet 的语义。
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import release_probe as RP  # noqa: E402


class TestTagSelection(unittest.TestCase):
    LS_SAMPLE = (
        "aaa111\trefs/tags/v2026.9.14\n"
        "bbb222\trefs/tags/v2026.9.14^{}\n"
        "ccc333\trefs/tags/v2026.10.1\n"
        "ddd444\trefs/tags/v2026.10.1^{}\n"
        "eee555\trefs/tags/nightly\n"
        "fff666\trefs/heads/main\n"
        "ggg777\trefs/tags/v2026.9.9\n"
    )

    def test_parse_keeps_only_v_tags_and_drops_peeled_refs(self):
        self.assertEqual(RP.parse_ls_remote(self.LS_SAMPLE),
                         ["v2026.10.1", "v2026.9.14", "v2026.9.9"])

    def test_parse_tolerates_garbage(self):
        self.assertEqual(RP.parse_ls_remote(""), [])
        self.assertEqual(RP.parse_ls_remote("不是 ls-remote 的输出"), [])

    def test_latest_is_numeric_not_lexicographic(self):
        # 字符串比大小会把 v2026.10.1 排在 v2026.9.14 前面 —— 实测踩过这类排序坑
        self.assertEqual(RP.pick_latest(["v2026.9.14", "v2026.10.1"]), "v2026.10.1")
        self.assertEqual(RP.pick_latest(["v2026.9.9", "v2026.9.14"]), "v2026.9.14")

    def test_version_key_handles_short_and_odd_tags(self):
        self.assertEqual(RP.version_key("v2026.9.14"), (2026, 9, 14))
        self.assertGreater(RP.version_key("v2026.10.1"), RP.version_key("v2026.9.14"))


class TestClassify(unittest.TestCase):
    def test_lf_normalization_is_the_hash_basis(self):
        # 同一份内容 CRLF / LF 必须等价（否则 Windows 上全红，CI 上全绿）
        crlf = b"line1\r\nline2\r\n"
        lf = b"line1\nline2\n"
        self.assertEqual(RP.sha256(RP.lf_bytes(crlf)), RP.sha256(lf))

    def test_classify_splits_three_buckets(self):
        same = b"a\n"
        expected = {"same": RP.sha256(b"a\n"), "drifted": RP.sha256(b"b\n"),
                    "gone": RP.sha256(b"c\n")}
        got = RP.classify({"same": same, "drifted": b"something else\n", "gone": None}, expected)
        self.assertEqual(got["same"], ["same"])
        self.assertEqual(got["drifted"], ["drifted"])
        self.assertEqual(got["missing"], ["gone"])

    def test_classify_ignores_ids_without_expected_hash(self):
        got = RP.classify({"x": b"a\n"}, {})
        self.assertEqual((got["same"], got["drifted"], got["missing"]), ([], [], []))

    def test_has_drift_and_summary(self):
        clean = {"tag": "v1", "same": ["a"], "drifted": [], "missing": []}
        dirty = {"tag": "v1", "same": [], "drifted": ["a"], "missing": []}
        self.assertFalse(RP.has_drift(clean))
        self.assertTrue(RP.has_drift(dirty))
        self.assertIn("v1", RP.summary_line(dirty))


class TestBaseline(unittest.TestCase):
    def test_reads_baseline_comment(self):
        text = "# 说明\n# baseline-release: v2026.9.14\n\ngetting-started:\n  quickstart: a.md\n"
        self.assertEqual(RP.baseline_release(text), "v2026.9.14")

    def test_missing_baseline_is_none(self):
        self.assertIsNone(RP.baseline_release("# 只有说明\n"))

    def test_repo_registry_has_a_baseline(self):
        # 仓库里真的写了基线：没有它，哨兵只能报「判不了」
        self.assertRegex(RP.baseline_release() or "", r"^v\d")


class TestWatchMode(unittest.TestCase):
    def _run(self, argv, watch_result=None, error=None):
        saved = RP.watch
        try:
            if error:
                def boom(*a, **k):
                    raise error
                RP.watch = boom
            else:
                RP.watch = lambda **k: watch_result
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = RP.main(argv)
            return rc, buf.getvalue()
        finally:
            RP.watch = saved

    def test_no_new_release_is_quiet(self):
        rc, out = self._run(["--quiet"], {"baseline": "v1.0.0", "latest": "v1.0.0",
                                          "has_new_release": False, "note": ""})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_new_release_speaks_even_when_quiet(self):
        rc, out = self._run(["--quiet"], {"baseline": "v1.0.0", "latest": "v2.0.0",
                                          "has_new_release": True, "note": ""})
        self.assertEqual(rc, 1)
        self.assertIn("v2.0.0", out)
        self.assertIn("baseline-release", out)

    def test_watch_error_is_exit_2(self):
        rc, out = self._run([], error=RuntimeError("解析不出上游最新的 release tag"))
        self.assertEqual(rc, 2)

    def test_default_mode_is_watch_not_docs(self):
        # 默认必须是便宜的那个：--docs 会抓 95 页，绝不能是日常路径
        rc, out = self._run(["--json"], {"baseline": "v1.0.0", "latest": "v1.0.0",
                                         "has_new_release": False, "note": ""})
        payload = json.loads(out)
        self.assertIn("has_new_release", payload)
        self.assertNotIn("same", payload)


if __name__ == "__main__":
    unittest.main()
