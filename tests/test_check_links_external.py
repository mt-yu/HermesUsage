#!/usr/bin/env python3
"""tests/test_check_links_external.py —— 外链检测的分类/汇总纯函数单元测试。

运行：python -m unittest discover -s tests -t . -p "test_*.py" -v
这些测试**不发任何网络请求**：只测 classify / summarize 这两个纯函数，
以及 URL 过滤（--only / --limit）。真正打外网的只有 CLI 全量跑那一次。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_links_external as cl  # noqa: E402


class TestClassify(unittest.TestCase):
    """四分类必须互斥且覆盖 None：None 来自超时/连接错误，不是 HTTP 状态码。"""

    def test_none_is_network(self):
        # 没有状态码 = 压根没连上（DNS/超时/代理），这类不该算“坏链”。
        self.assertEqual(cl.classify(None), "network")

    def test_2xx_is_ok(self):
        for code in (200, 204, 299):
            self.assertEqual(cl.classify(code), "ok")

    def test_3xx_is_ok(self):
        # 跟随重定向后的最终状态码；裸 301 说明请求器没跟，也仍然不算坏。
        for code in (301, 302, 308):
            self.assertEqual(cl.classify(code), "ok")

    def test_403_is_blocked_not_broken(self):
        # Cloudflare 之类的机器人拦截：链接本身是好的，不能报成坏链。
        self.assertEqual(cl.classify(403), "blocked")

    def test_429_is_blocked(self):
        self.assertEqual(cl.classify(429), "blocked")

    def test_404_is_broken(self):
        self.assertEqual(cl.classify(404), "broken")

    def test_410_is_broken(self):
        self.assertEqual(cl.classify(410), "broken")

    def test_500_is_broken(self):
        self.assertEqual(cl.classify(500), "broken")

    def test_400_is_broken(self):
        # 401/400 之类既不是拦截也不是成功，归 broken（需要人看一眼）。
        self.assertEqual(cl.classify(400), "broken")

    def test_categories_are_exactly_four(self):
        self.assertEqual(
            {cl.classify(s) for s in (None, 200, 403, 404, 500)},
            {"ok", "blocked", "broken", "network"},
        )


class TestSummarize(unittest.TestCase):
    def _r(self, rid: str, status):
        return {"id": rid, "url": f"https://example.com/{rid}", "status": status,
                "category": cl.classify(status)}

    def test_empty_list(self):
        self.assertEqual(
            cl.summarize([]),
            {"ok": 0, "blocked": 0, "broken": 0, "network": 0, "broken_ids": []},
        )

    def test_mixed_counts(self):
        results = [
            self._r("a", 200),
            self._r("b", 301),
            self._r("c", 403),
            self._r("d", 429),
            self._r("e", 404),
            self._r("f", 500),
            self._r("g", None),
            self._r("h", 200),
        ]
        summary = cl.summarize(results)
        self.assertEqual(summary["ok"], 3)
        self.assertEqual(summary["blocked"], 2)
        self.assertEqual(summary["broken"], 2)
        self.assertEqual(summary["network"], 1)

    def test_broken_ids_keep_input_order(self):
        results = [self._r("zeta", 404), self._r("alpha", 200), self._r("mid", 500)]
        self.assertEqual(cl.summarize(results)["broken_ids"], ["zeta", "mid"])

    def test_blocked_and_network_are_not_broken(self):
        # 最容易写错的地方：把 403/超时也算成坏链，结果每周都误报。
        results = [self._r("c", 403), self._r("g", None)]
        self.assertEqual(cl.summarize(results)["broken_ids"], [])
        self.assertEqual(cl.summarize(results)["broken"], 0)

    def test_has_broken_helper(self):
        self.assertFalse(cl.has_broken(cl.summarize([self._r("a", 200)])))
        self.assertTrue(cl.has_broken(cl.summarize([self._r("a", 404)])))


class TestSelect(unittest.TestCase):
    """--only / --limit 的过滤逻辑（纯函数，不碰网络）。"""

    ENTRIES = [
        {"id": "acp", "url": "https://example.com/acp"},
        {"id": "quickstart", "url": "https://example.com/quickstart"},
        {"id": "web-search", "url": "https://example.com/web-search"},
    ]

    def test_limit(self):
        self.assertEqual([e["id"] for e in cl.select(self.ENTRIES, limit=2)], ["acp", "quickstart"])

    def test_only(self):
        got = cl.select(self.ENTRIES, only="web-search,acp")
        self.assertEqual([e["id"] for e in got], ["web-search", "acp"])

    def test_only_ignores_unknown_without_crashing(self):
        got = cl.select(self.ENTRIES, only="acp,nope")
        self.assertEqual([e["id"] for e in got], ["acp"])

    def test_limit_none_means_all(self):
        self.assertEqual(len(cl.select(self.ENTRIES)), 3)


class TestFakeStatus(unittest.TestCase):
    """容错：还没分类的结果也能被 summarize 处理（防手写 dict 漏字段）。"""

    def test_summarize_classifies_missing_category(self):
        results = [{"id": "x", "url": "https://example.com/x", "status": 404}]
        self.assertEqual(cl.summarize(results)["broken_ids"], ["x"])


if __name__ == "__main__":
    unittest.main()


class TestHealthy(unittest.TestCase):
    """--quiet 的静默判据：只有「全部可达」才算健康（没验成 != 通过）。"""

    def _sum(self, **kw):
        base = {"total": 91, "ok": 91, "blocked": 0, "broken": 0, "network": 0, "broken_ids": []}
        base.update(kw)
        return base

    def test_all_ok_is_healthy(self):
        self.assertTrue(cl.healthy(self._sum()))

    def test_broken_is_not_healthy(self):
        self.assertFalse(cl.healthy(self._sum(ok=90, broken=1)))

    def test_network_is_not_healthy(self):
        """连不上是「没查成」，不能算过 —— 否则 cron 会静默吞掉一次没验成的检查。"""
        self.assertFalse(cl.healthy(self._sum(ok=89, network=2)))

    def test_blocked_is_not_healthy(self):
        self.assertFalse(cl.healthy(self._sum(ok=90, blocked=1)))

    def test_exit_code_still_only_on_broken(self):
        """退出码与静默判据刻意不同：blocked/network 不该让 CI 红，但该让人看见。"""
        self.assertFalse(cl.has_broken(self._sum(blocked=3, network=3)))
        self.assertTrue(cl.has_broken(self._sum(broken=1)))
