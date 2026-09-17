#!/usr/bin/env python3
"""tests/test_design_matrix.py —— 设计对比矩阵的单元测试。

这一页的**全部卖点就是「数字不是手抄的」**，所以测试的重点不是「渲染出了字符串」，
而是「同一条事实只有一份来源、并且被现算」：

1. 平均分 == 那个方案各维度分数的算术平均（不是手写的数字）；
2. 页面上的赢家 == 现算的最高分（改分数表，结论自动跟着改）；
3. 页面印的 token 值与对比度 == 从 web/assets/app.css 现读现算的值；
4. 对比度**每一行都达标**（无障碍是这个项目的硬约束，不能只画个表）；
5. 每个方案/维度/出处都有可点的官方地址，且没有重复的方案 key。

最后一条是与 app.css 的**双路对账**：token 在页面上与在样式表里必须是同一份。
样式表里删掉一个 token 而忘了改 APPLIED_TOKENS，构建会报错；这一层测试则证明
「报错那条路真的通」。
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import design_matrix as D  # noqa: E402

CSS_PATH = REPO / "web" / "assets" / "app.css"


class TestMatrixData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = CSS_PATH.read_text(encoding="utf-8")

    # --- 数据自检 ---------------------------------------------------------

    def test_validate_passes(self):
        D.validate()          # 维度齐全、分数 1~5、key 不重复

    def test_dimensions_are_unique_and_non_empty(self):
        keys = [d["key"] for d in D.DIMENSIONS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreaterEqual(len(D.DIMENSIONS), 8)      # 「多维度」不能是三种维度
        for d in D.DIMENSIONS:
            self.assertTrue(d["why"].strip(), d["key"])

    def test_every_system_has_scores_for_every_dimension(self):
        for system in D.SYSTEMS:
            self.assertEqual(sorted(system["scores"]), sorted(D.DIM_KEYS), system["key"])

    def test_scores_are_in_range(self):
        for system in D.SYSTEMS + [D.BEFORE, D.AFTER]:
            for key, value in system["scores"].items():
                self.assertIsInstance(value, int)
                self.assertGreaterEqual(value, 1)
                self.assertLessEqual(value, D.MAX_SCORE)

    def test_validate_rejects_out_of_range_score(self):
        """坏数据必须让 validate() 报错，而不是默默渲染上台。"""
        original = D.SYSTEMS[:]
        broken = dict(original[0])
        broken["scores"] = dict(broken["scores"], reading=9)
        try:
            D.SYSTEMS[:] = [broken] + original[1:]
            with self.assertRaises(D.MatrixError) as ctx:
                D.validate()
        finally:
            D.SYSTEMS[:] = original
        self.assertIn("reading", str(ctx.exception))

    def test_validate_rejects_a_missing_dimension(self):
        original = D.SYSTEMS[:]
        broken = dict(original[0])
        broken["scores"] = {k: v for k, v in broken["scores"].items() if k != "a11y"}
        try:
            D.SYSTEMS[:] = [broken] + original[1:]
            with self.assertRaises(D.MatrixError) as ctx:
                D.validate()
        finally:
            D.SYSTEMS[:] = original
        self.assertIn("a11y", str(ctx.exception))

    # --- 计算 -------------------------------------------------------------

    def test_score_is_the_arithmetic_mean(self):
        for system in D.SYSTEMS:
            values = [system["scores"][k] for k in D.DIM_KEYS]
            self.assertAlmostEqual(D.score(system), round(sum(values) / len(values), 2), places=2)

    def test_ranking_is_descending_and_deterministic(self):
        rows = D.ranking()
        scores = [D.score(s) for s in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([s["key"] for s in rows], [s["key"] for s in D.ranking()])
        self.assertEqual(len(rows), len(D.SYSTEMS))

    def test_winner_is_the_highest_mean(self):
        top = max(D.SYSTEMS, key=D.score)
        self.assertEqual(D.winner()["key"], top["key"])

    def test_reference_rows_do_not_compete(self):
        keys = {s["key"] for s in D.SYSTEMS}
        for ref in (D.BEFORE, D.AFTER):
            self.assertNotIn(ref.get("key"), keys)
            self.assertIn("参考", ref["name"])

    def test_every_self_check_names_a_verifiable_action(self):
        """「改造后」每一格都必须给出核验方式：不许出现无法验证的自评。"""
        for key in D.DIM_KEYS:
            check = D.AFTER["checks"][key]
            self.assertTrue(check.strip(), key)
            self.assertGreater(len(check), 8, check)

    # --- 与 app.css 的双路对账 ---------------------------------------------

    def test_root_block_is_found(self):
        tokens = D.css_root_tokens(self.css)
        self.assertGreater(len(tokens), 40)     # 令牌层是这套视觉的地基

    def test_every_applied_token_exists_in_the_stylesheet(self):
        for item in D.APPLIED_TOKENS:
            with self.subTest(token=item["token"]):
                self.assertIn(item["token"], D.css_root_tokens(self.css))

    def test_missing_token_raises_instead_of_printing_a_stale_value(self):
        with self.assertRaises(D.MatrixError) as ctx:
            D.token_value(self.css, "--token-that-does-not-exist")
        self.assertIn("--token-that-does-not-exist", str(ctx.exception))

    def test_token_chains_resolve_to_real_values(self):
        # 语义 token 指向 primitive：链条必须有第二段，且末段不是 var()
        chain = D.token_chain(self.css, "--bg")
        self.assertEqual(chain[0], "var(--gray-0)")
        self.assertTrue(D.HEX_RE.match(chain[-1]), chain)
        self.assertEqual(D.resolved_token(self.css, "--measure"), "74ch")

    def test_token_chain_cycle_is_caught(self):
        css = ":root { --a: var(--b); --b: var(--a); }"
        with self.assertRaises(D.MatrixError):
            D.token_chain(css, "--a")

    # --- 对比度 -----------------------------------------------------------

    def test_contrast_formula_matches_wcag_known_values(self):
        self.assertEqual(D.contrast_ratio("#000000", "#ffffff"), 21.0)
        self.assertEqual(D.contrast_ratio("#ffffff", "#ffffff"), 1.0)

    def test_every_contrast_pair_passes_its_requirement(self):
        for fg, bg, need, label in D.CONTRAST_PAIRS:
            with self.subTest(pair=(fg, bg)):
                ratio = D.contrast_ratio(D.hex_of(self.css, fg), D.hex_of(self.css, bg))
                self.assertGreaterEqual(ratio, need, f"{fg} on {bg} = {ratio}:1（{label}）")

    def test_contrast_table_shows_the_computed_ratio(self):
        table = D.contrast_table(self.css)
        self.assertIn("✅ 通过", table)
        self.assertNotIn("❌", table)
        fg, bg, need, _ = D.CONTRAST_PAIRS[0]
        ratio = D.contrast_ratio(D.hex_of(self.css, fg), D.hex_of(self.css, bg))
        self.assertIn(f"**{ratio}:1**", table)

    def test_non_hex_token_in_the_contrast_pairs_is_loud(self):
        with self.assertRaises(D.MatrixError):
            D.hex_of(self.css, "--measure")     # 74ch 不是颜色，不许静默跳过

    # --- 出处 -------------------------------------------------------------

    def test_every_system_links_to_an_official_page(self):
        for system in D.SYSTEMS:
            self.assertTrue(system["urls"], system["key"])
            for label, url in system["urls"]:
                self.assertTrue(label.strip(), system["key"])
                self.assertTrue(url.startswith("https://"), url)

    def test_sources_are_unique_https_urls(self):
        urls = [s["url"] for s in D.SOURCES]
        self.assertEqual(len(urls), len(set(urls)))
        for url in urls:
            self.assertTrue(url.startswith("https://"), url)
        self.assertRegex(D.FETCHED, r"^\d{4}-\d{2}-\d{2}$")

    def test_sources_section_urls_all_appear_in_the_page(self):
        md = D.render_markdown(self.css)
        for source in D.SOURCES:
            self.assertIn(source["url"], md, source["url"])


class TestRenderedPage(unittest.TestCase):
    """正文 markdown 的形态：结论必须由数据现算出来，不是写死的字符串。"""

    @classmethod
    def setUpClass(cls):
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.md = D.render_markdown(cls.css)

    def test_winner_and_runner_ups_are_computed(self):
        self.assertIn(D.winner()["name"], self.md)
        self.assertIn(f"{D.score(D.winner()):.2f}", self.md)
        for system in D.ranking()[1:4]:
            self.assertIn(f"{system['name']} {D.score(system):.2f}", self.md)

    def test_matrix_has_one_row_per_system_plus_two_reference_rows(self):
        rows = re.findall(r"^\| \*\*.*← 赢家.*\*\* \|", self.md, re.M)
        self.assertEqual(len(rows), 1)
        body = D.matrix_table().splitlines()
        # 表头 + 分隔行 + 10 个方案 + 2 行参考基线
        self.assertEqual(len(body), 2 + len(D.SYSTEMS) + 2)
        header_cells = body[0].count("|") - 1
        for line in body:
            self.assertEqual(line.count("|") - 1, header_cells, line[:60])

    def test_every_dimension_and_system_shows_up(self):
        for d in D.DIMENSIONS:
            self.assertIn(d["name"], self.md, d["key"])
        for s in D.SYSTEMS:
            self.assertIn(s["name"], self.md, s["key"])

    def test_chart_placeholder_is_present_and_owned_by_build_site(self):
        self.assertIn(D.CHART_PLACEHOLDER, self.md)
        self.assertIn("{{design-chart}}", self.md)   # 占位符形态是构建期的约定

    def test_stylesheet_size_is_computed_not_written_by_hand(self):
        stats = D.css_stats(self.css)
        self.assertIn(f"{stats['bytes']:,} 字节", self.md)
        self.assertIn(f"{stats['lines']} 行", self.md)

    def test_no_hand_written_average_in_the_prose(self):
        """防止有人「顺手」把某个数字抄进正文：正文里出现的两位小数，只允许来自现算。"""
        allowed = {f"{D.score(s):.2f}" for s in D.ranking()}
        allowed |= {f"{D.score(D.BEFORE):.2f}", f"{D.score(D.AFTER):.2f}"}
        # 对比度也是现算的（5.79:1 这种形态同样出现在正文里）
        allowed |= {
            f"{D.contrast_ratio(D.hex_of(self.css, fg), D.hex_of(self.css, bg)):.2f}"
            for fg, bg, _, _ in D.CONTRAST_PAIRS
        }
        found = set(re.findall(r"(?<![\d.])([345]\.\d{2})(?![\d])", self.md))
        self.assertTrue(found <= allowed, f"正文里出现了非现算的分数：{sorted(found - allowed)}")


class TestChart(unittest.TestCase):
    def test_chart_has_one_bar_per_row(self):
        svg = D.average_chart_svg()
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertEqual(svg.count("<rect"), len(D.SYSTEMS) + 2)
        self.assertIn('role="img"', svg)
        self.assertIn("<title>", svg)

    def test_bars_are_proportional_to_scores(self):
        """条长按分数等比，且赢家是**参评方案里**最长的那条。

        参考基线（改造后的自评 4.70）会比赢家更长 —— 这没关系：它是「本站自己
        现在长什么样」，不参与排名，所以在图里也不该被当成竞争对手。
        这里把「参评的 10 条」与「参考的 2 条」分开断言，正是为了让这条区分
        不会在将来被谁一句 `max(widths)` 抹平。
        """
        svg = D.average_chart_svg()
        widths = [float(m) for m in re.findall(r'<rect x="150" y="[\d.]+" width="([\d.]+)"', svg)]
        self.assertEqual(len(widths), len(D.SYSTEMS) + 2)
        competing, reference = widths[:len(D.SYSTEMS)], widths[len(D.SYSTEMS):]
        self.assertEqual(competing[0], max(competing))          # 第一行是赢家
        for width, system in zip(competing, D.ranking()):
            expected = round((760 - 150 - 46) * D.score(system) / D.MAX_SCORE, 2)
            self.assertAlmostEqual(width, expected, places=2, msg=system["key"])
        self.assertGreater(ref_width := max(reference), competing[0])   # 参考行更长也正常
        self.assertAlmostEqual(ref_width, round(564 * D.score(D.AFTER) / D.MAX_SCORE, 2), places=2)

    def test_chart_is_deterministic_and_colour_free(self):
        self.assertEqual(D.average_chart_svg(), D.average_chart_svg())   # 无随机、无时间戳
        svg = D.average_chart_svg()
        self.assertNotIn("#", svg.replace("&#", ""))     # 不写裸色值，全走 CSS 变量
        self.assertIn("var(--accent)", svg)
        self.assertIn("var(--fg-muted)", svg)

    def test_every_system_has_a_short_chart_label(self):
        for s in D.SYSTEMS:
            self.assertIn(s["key"], D.CHART_LABELS, s["key"])
            self.assertLessEqual(len(D.CHART_LABELS[s["key"]]), 16)


class TestJsonExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.data = D.as_json(cls.css)

    def test_winner_and_ranking_are_in_the_json(self):
        self.assertEqual(self.data["winner"], D.winner()["key"])
        ranks = [s["rank"] for s in self.data["systems"]]
        self.assertEqual(ranks, list(range(1, len(D.SYSTEMS) + 1)))
        for entry in self.data["systems"]:
            self.assertEqual(entry["mean"], D.score(D.ranking()[entry["rank"] - 1]))

    def test_json_carries_tokens_and_contrast(self):
        self.assertEqual(self.data["stylesheet"]["path"], "web/assets/app.css")
        self.assertEqual(len(self.data["applied_tokens"]), len(D.APPLIED_TOKENS))
        for row in self.data["contrast"]:
            self.assertTrue(row["pass"], row)
        self.assertEqual(len(self.data["contrast"]), len(D.CONTRAST_PAIRS))


if __name__ == "__main__":
    unittest.main()
