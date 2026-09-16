#!/usr/bin/env python3
"""tests/test_drift_watch.py —— 漂移输出解析（parse_drift）单元测试。

运行：python -m unittest discover -s tests -t . -p "test_*.py" -v
parse_drift 是纯函数（字符串进、字典出），所以这里不跑 sync_sources.py，
也不碰 GitHub API —— 样本就是 scripts/sync_sources.py --check 的真实输出格式。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import drift_watch as dw  # noqa: E402

# 与 sync_sources.py --check 的 stdout 完全同构（含头几行噪声）
REAL_SAMPLE = """docs 源码 : C:\\Users\\28189\\.hermes\\hermes-agent\\website\\docs
commit    : 05fac10a758c  (2026-09-15)
hermes    : v0.21.3
登记来源  : 91 条

漂移检查：发现 5 处变化
    ~ context-references  7e626dd05f91 -> ada9b7f98c08
    ~ creating-skills  39159c033ada -> 8c02803ab101
    新增未登记快照 2 条：browser, web-search
    路径失效 3 条：old-id -> user-guide/old.md
"""


class TestParseDriftRealSample(unittest.TestCase):
    def setUp(self):
        self.parsed = dw.parse_drift(REAL_SAMPLE)

    def test_drifted_ids(self):
        self.assertEqual(self.parsed["drifted"], ["context-references", "creating-skills"])

    def test_added_ids(self):
        self.assertEqual(self.parsed["added"], ["browser", "web-search"])

    def test_missing_ids_strip_path(self):
        # 行里是 `old-id -> user-guide/old.md`，只取箭头左边的 id。
        self.assertEqual(self.parsed["missing"], ["old-id"])

    def test_header_line_not_captured(self):
        # `漂移检查：发现 5 处变化` 不该被当成一个 id。
        for key in ("drifted", "added", "missing"):
            self.assertNotIn("发现", self.parsed[key])
            self.assertNotIn("漂移检查", self.parsed[key])


class TestParseDriftEdges(unittest.TestCase):
    def test_no_change(self):
        self.assertEqual(
            dw.parse_drift("登记来源  : 91 条\n\n漂移检查：无变化\n"),
            {"drifted": [], "added": [], "missing": []},
        )

    def test_empty_string(self):
        self.assertEqual(dw.parse_drift(""), {"drifted": [], "added": [], "missing": []})

    def test_only_added(self):
        out = "漂移检查：无变化\n    新增未登记快照 2 条：browser, web-search\n"
        got = dw.parse_drift(out)
        self.assertEqual(got["added"], ["browser", "web-search"])
        self.assertEqual(got["drifted"], [])
        self.assertEqual(got["missing"], [])

    def test_only_missing_multiple(self):
        out = "漂移检查：无变化\n    路径失效 2 条：aaa -> x/y.md, bbb -> z.md\n"
        got = dw.parse_drift(out)
        self.assertEqual(got["missing"], ["aaa", "bbb"])
        self.assertEqual(got["added"], [])

    def test_tilde_lines_only(self):
        out = "    ~ context-references  7e626dd05f91 -> ada9b7f98c08\n"
        self.assertEqual(dw.parse_drift(out)["drifted"], ["context-references"])

    def test_drift_header_with_count(self):
        self.assertEqual(dw.parse_drift("漂移检查：发现 1 处变化\n")["drifted"], [])

    def test_has_drift_helper(self):
        self.assertFalse(dw.has_drift(dw.parse_drift("漂移检查：无变化\n")))
        self.assertTrue(dw.has_drift(dw.parse_drift(REAL_SAMPLE)))


class TestIssueHelpers(unittest.TestCase):
    """issue 标题/正文/去重前缀 —— 同样不发请求。"""

    def test_repo_from_remote(self):
        self.assertEqual(dw.repo_from_remote("https://github.com/mt-yu/HermesUsage.git"), "mt-yu/HermesUsage")
        self.assertEqual(dw.repo_from_remote("git@github.com:mt-yu/HermesUsage.git"), "mt-yu/HermesUsage")

    def test_title_uses_prefix(self):
        title = dw.issue_title(dw.parse_drift(REAL_SAMPLE))
        self.assertTrue(title.startswith(dw.ISSUE_PREFIX))
        self.assertIn("5", title)

    def test_body_lists_all_three_groups(self):
        body = dw.issue_body(dw.parse_drift(REAL_SAMPLE))
        self.assertIn("context-references", body)
        self.assertIn("creating-skills", body)
        self.assertIn("browser", body)
        self.assertIn("old-id", body)
        self.assertIn("scripts/sync_sources.py", body)
        self.assertIn("scripts/check.py", body)

    def test_body_handles_empty_groups(self):
        body = dw.issue_body({"drifted": [], "added": [], "missing": []})
        self.assertIn("无", body)


class TestDryRunSafety(unittest.TestCase):
    """--dry-run 的硬保证：不取令牌、不发任何请求、照样报漂移（退出码 1）。

    这是本脚本最该被钉住的行为 —— 一个"以为在 dry-run 结果真开了 issue"的
    哨兵，比没有哨兵危险得多。
    """

    def setUp(self):
        self._saved = (dw.run_check, dw.get_token, dw._api, dw._git_remote)

        def boom(*a, **k):  # pragma: no cover - 被调用即测试失败
            raise AssertionError("dry-run 不该走到这里")

        dw.run_check = lambda timeout=180.0: (1, REAL_SAMPLE, "")
        dw.get_token = boom
        dw._api = boom
        dw._git_remote = boom

    def tearDown(self):
        dw.run_check, dw.get_token, dw._api, dw._git_remote = self._saved

    def test_dry_run_returns_1_and_touches_nothing(self):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = dw.main(["--dry-run"])
        out = buf.getvalue()
        self.assertEqual(rc, 1)
        self.assertIn(dw.ISSUE_PREFIX, out)
        self.assertIn("context-references", out)
        self.assertIn("scripts/sync_sources.py", out)

    def test_dry_run_json_action(self):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dw.main(["--dry-run", "--json"])
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["action"], "dry-run")
        self.assertTrue(payload["has_drift"])
        self.assertEqual(payload["drift"]["drifted"], ["context-references", "creating-skills"])


class TestIssueFlow(unittest.TestCase):
    """新建 / 去重跳过两条分支 —— 用假的 _api 拦住，绝不真开 issue。"""

    def setUp(self):
        self._saved = (dw.run_check, dw.get_token, dw._api, dw._git_remote)
        self.calls: list[tuple] = []
        self.existing: list[dict] = []

        def fake_api(method, path, token, payload=None, timeout=30.0):
            self.calls.append((method, path, payload))
            if method == "GET":
                return 200, self.existing
            return 201, {"number": 42, "html_url": "https://github.com/mt-yu/HermesUsage/issues/42"}

        dw.run_check = lambda timeout=180.0: (1, REAL_SAMPLE, "")
        dw.get_token = lambda: "fake-token"
        dw._git_remote = lambda: "https://github.com/mt-yu/HermesUsage.git"
        dw._api = fake_api

    def tearDown(self):
        dw.run_check, dw.get_token, dw._api, dw._git_remote = self._saved

    def _run(self, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = dw.main(argv)
        return rc, buf.getvalue()

    def test_creates_issue_when_none_exists(self):
        rc, out = self._run(["--json"])
        payload = json.loads(out)
        self.assertEqual(rc, 1)
        self.assertEqual(payload["action"], "created")
        posts = [c for c in self.calls if c[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0][2]["title"].startswith(dw.ISSUE_PREFIX))
        self.assertIn("sync_sources.py", posts[0][2]["body"])

    def test_skips_when_same_prefix_issue_is_open(self):
        self.existing = [{
            "number": 9,
            "title": dw.ISSUE_PREFIX + "旧的一条",
            "html_url": "https://github.com/mt-yu/HermesUsage/issues/9",
        }]
        rc, out = self._run(["--json"])
        payload = json.loads(out)
        self.assertEqual(rc, 1)
        self.assertEqual(payload["action"], "skipped-existing")
        self.assertEqual(payload["issue"]["number"], 9)
        self.assertEqual([c for c in self.calls if c[0] == "POST"], [])

    def test_pull_requests_are_not_treated_as_issues(self):
        # /repos/{repo}/issues 会把 PR 也列出来，去重时不能拿 PR 当已有 issue
        self.existing = [{
            "number": 11,
            "title": dw.ISSUE_PREFIX + "看起来像",
            "html_url": "https://github.com/mt-yu/HermesUsage/pull/11",
            "pull_request": {"url": "https://api.github.com/repos/mt-yu/HermesUsage/pulls/11"},
        }]
        rc, out = self._run(["--json"])
        self.assertEqual(json.loads(out)["action"], "created")


if __name__ == "__main__":
    unittest.main()
