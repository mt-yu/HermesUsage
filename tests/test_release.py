#!/usr/bin/env python3
"""tests/test_release.py —— 发布体系脚本（scripts/release.py）的单元测试。

运行：python -m unittest tests.test_release -v

两条自我约束
------------
1. **绝不触网**：HTTP 三件套（`_request` / `_api` / `upload_asset`）在本文件里从没被真调用过，
   `--dry-run` 的用例还会把它们与 `get_token` 一起换成会抛异常的桩 —— dry-run 一旦偷偷取令牌
   或发请求，测试就红。
2. **只读 git**：只用 `tag -l` / `rev-list` / `for-each-ref` / `ls-tree` / `show` / `log` /
   `rev-parse --verify`，不做任何写操作（add/commit/tag/checkout 一个都没有）。

为什么断言真实 tag 集合
-----------------------
`tag_order` / `previous_tag` / `build_notes` 的正确性只体现在真数据上（谁在谁前面、
`v1.1-web` 的说明里 `journal:` 有没有被吞掉）。浅克隆（`actions/checkout` 默认 depth=1、
不带 tag）下这些用例会**显式 skip** 并在消息里写明原因 —— 不静默通过、也不假装跑过。
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest
import zipfile
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import release as rel  # noqa: E402

# 计划里点名的历史 tag（断言顺序时只在「已知集合」内比，不写死 len()：
# 计划本身要在最后 push v3.4-release，写死长度会让仓库自己下一步就把测试弄红）
KNOWN_TAGS = (
    "v0.2-orient", "v0.3-core", "v1.0-tutorial", "v1.1-web", "v1.2-seo", "v1.3-site",
    "v1.4-content", "v1.5-auto", "v2.0-deliverable", "v2.1-ops", "v3.0-cases",
    "v3.1-ui", "v3.3-topbar",
)

# 计划第二节的分类映射表（前缀 → 分类键），逐条照抄，用来查表有没有漏
EXPECTED_CATEGORY_OF_PREFIX = {
    "feat": "added", "stage": "added", "session": "added",
    "fix": "fixed",
    "docs": "docs",
    "refactor": "changed", "perf": "changed", "revert": "changed", "change": "changed",
    "deprecate": "deprecated",
    "remove": "removed",
    "security": "security",
    "ci": "internal", "chore": "internal", "release": "internal",
}


def real_tags() -> list[str]:
    """仓库里真实的 tag；浅克隆没有 tag 时显式跳过（并说清怎么修）。"""
    tags = rel.all_tags()
    if not tags:
        raise unittest.SkipTest(
            "本地没有 tag（浅克隆？）：这几个用例要读真实 tag 集合与提交历史，"
            "CI 里 checkout 需要 fetch-depth: 0"
        )
    return tags


class TestClassify(unittest.TestCase):
    def test_every_prefix_from_the_plan(self):
        wrong = {p: (rel.classify(f"{p}: 示例提交"), want)
                 for p, want in EXPECTED_CATEGORY_OF_PREFIX.items()
                 if rel.classify(f"{p}: 示例提交") != want}
        self.assertFalse(wrong, f"前缀分类与计划不一致：{wrong}")

    def test_table_covers_exactly_the_planned_prefixes(self):
        diff = set(EXPECTED_CATEGORY_OF_PREFIX) ^ set(rel._PREFIX_TO_CATEGORY)
        self.assertFalse(diff, f"前缀集合与计划有差集：{sorted(diff)}")

    def test_chinese_fullwidth_colon(self):
        self.assertEqual(rel.classify("fix：修一个坑"), "fixed")

    def test_unknown_prefix_and_bare_subject_are_internal(self):
        self.assertEqual(rel.classify("wip: 半成品"), "internal")
        self.assertEqual(rel.classify("随便写的一条提交"), "internal")
        self.assertEqual(rel.classify(""), "internal")

    def test_prefix_match_is_case_insensitive(self):
        self.assertEqual(rel.classify("FEAT: 大写前缀"), "added")


class TestNoise(unittest.TestCase):
    def test_journal_prefix_is_noise(self):
        self.assertTrue(rel.is_noise("journal: 教程站：可交互前端"))
        self.assertTrue(rel.is_noise("journal: 自动归档 2026-09-16 14:00（1 个文件变动）"))

    def test_session_auto_archive_is_noise(self):
        self.assertTrue(rel.is_noise("session: 自动归档 2 个文件变动"))

    def test_changelog_prefix_is_noise(self):
        # 重新生成 CHANGELOG.md 的那次提交必须在两侧都消失 —— 否则发布流程自己绕不出来
        # （`--assume-tag` 生成的文件不可能包含「生成这个文件的提交」，而那一次提交又在 tag 的区间内）
        self.assertTrue(rel.is_noise("changelog: 收进 v3.4-release 这一节"))

    def test_plain_session_commit_is_not_noise(self):
        self.assertFalse(rel.is_noise("session: 加一课"))

    def test_other_prefixes_are_never_noise(self):
        self.assertFalse(rel.is_noise("feat: 新增一课"))
        self.assertFalse(rel.is_noise("随便写的一条提交"))
        self.assertFalse(rel.is_noise(""))

    def test_noise_is_counted_but_not_listed(self):
        commits = [{"sha": "a" * 7, "subject": "journal: 归档"},
                   {"sha": "b" * 7, "subject": "session: 自动归档 3 个文件变动"},
                   {"sha": "c" * 7, "subject": "feat: 真东西"}]
        groups, noise = rel.group_commits(commits)
        self.assertEqual(noise, 2)
        self.assertEqual([c["subject"] for c in groups["added"]], ["feat: 真东西"])
        self.assertNotIn("journal", rel.render_category_sections(commits))


class TestTagOrder(unittest.TestCase):
    def test_known_tags_are_all_present(self):
        missing = set(KNOWN_TAGS) - set(real_tags())
        self.assertFalse(missing, f"本地缺少历史 tag：{sorted(missing)}")

    def test_first_and_last_of_the_known_set(self):
        ordered = rel.tag_order(real_tags())
        self.assertEqual(ordered[0], "v0.2-orient", f"最早的不是 v0.2-orient（第 1 位是 {ordered[0]}）")
        rest = [t for t in KNOWN_TAGS if t != "v3.3-topbar"]
        last_pos = ordered.index("v3.3-topbar")
        after = [t for t in rest if ordered.index(t) > last_pos]
        self.assertFalse(after, f"v3.3-topbar 之后还有已知 tag：{after}")

    def test_order_is_a_permutation_of_input(self):
        tags = real_tags()
        self.assertEqual(sorted(rel.tag_order(tags)), sorted(tags))

    def test_previous_tag(self):
        real_tags()
        self.assertEqual(rel.previous_tag("v1.0-tutorial"), "v0.3-core")
        self.assertEqual(rel.previous_tag("v1.1-web"), "v1.0-tutorial")
        self.assertEqual(rel.previous_tag("v3.3-topbar"), "v3.1-ui")
        self.assertIsNone(rel.previous_tag("v0.2-orient"), "第一个 tag 没有前一个")

    def test_unknown_tag_raises(self):
        real_tags()
        with self.assertRaises(rel.ReleaseError):
            rel.previous_tag("v9.9-不存在")

    def test_depth_is_monotonic(self):
        ordered = rel.tag_order(real_tags())
        depths = [rel.tag_depth(t) for t in ordered]
        self.assertEqual(depths, sorted(depths), f"深度不是升序：{depths}")


class TestStatsAndNaming(unittest.TestCase):
    def test_stats_at_counts_the_tag_tree(self):
        real_tags()
        stats = rel.stats_at("v1.1-web")
        self.assertEqual(stats["lessons"], 32, f"v1.1-web 的课数不对：{stats['lessons']}")
        self.assertEqual(stats["sources"], 89, f"v1.1-web 的出处条数不对：{stats['sources']}")
        self.assertEqual(rel.stats_at("v1.0-tutorial")["lessons"], 32)
        self.assertEqual(rel.stats_at("v0.2-orient")["lessons"], 4)

    def test_pages_only_when_receipt_exists(self):
        real_tags()
        receipt = rel.DIST / "v0.3-core-build.json"
        stats = rel.stats_at("v0.3-core")
        if receipt.is_file():
            self.assertIsInstance(stats.get("pages"), int, f"有回执时应给出页数：{sorted(stats)}")
        else:
            self.assertNotIn("pages", stats, "没有构建回执就不该给出页数（不许猜）")

    def test_asset_name(self):
        self.assertEqual(rel.asset_name("v1.1-web"), "hermesusage-site-v1.1-web.zip")
        self.assertEqual(rel.asset_name("v3.3-topbar"), "hermesusage-site-v3.3-topbar.zip")

    def test_sha256sums_line_has_two_spaces(self):
        digest = "a" * 64
        line = rel.sha256sums_line(digest, "hermesusage-site-v1.1-web.zip")
        self.assertEqual(line, f"{digest}  hermesusage-site-v1.1-web.zip")
        idx = line.index("hermesusage")
        self.assertEqual(line[idx - 2:idx], "  ", "GNU 格式必须是两个空格分隔（sha256sum -c 认这个）")
        self.assertEqual(line.count("  "), 1, "多一个空格就会被 sha256sum 判成文件名的一部分")

    def test_sha256sums_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            rel.write_sha256sums(out, "b.zip", "b" * 64)
            rel.write_sha256sums(out, "a.zip", "a" * 64)
            path = out / "SHA256SUMS"
            got = rel.read_sha256sums(path)
            self.assertEqual(got, {"a.zip": "a" * 64, "b.zip": "b" * 64},
                             f"合并后条目不对：{sorted(got)}")
            # 排序：a 在 b 之前（同一份清单跑两次必须字节相同）
            first = path.read_text(encoding="utf-8")
            rel.write_sha256sums(out, "a.zip", "a" * 64)
            self.assertEqual(path.read_text(encoding="utf-8"), first, "重复写入应保持字节不变")
            self.assertLess(first.index("a.zip"), first.index("b.zip"), "清单没按文件名排序")

    def test_should_prerelease(self):
        self.assertTrue(rel.should_prerelease("v0.2-orient"))
        self.assertTrue(rel.should_prerelease("v0.3-core"))
        self.assertFalse(rel.should_prerelease("v1.1-web"))
        self.assertFalse(rel.should_prerelease("v1.0-tutorial"))
        self.assertFalse(rel.should_prerelease("v3.3-topbar"))

    def test_release_title(self):
        real_tags()
        title = rel.release_title("v1.1-web")
        self.assertTrue(title.startswith("v1.1-web · "), f"标题少了 tag 或分隔符：{title[:20]}")
        self.assertLessEqual(len(title), rel.TITLE_MAX)

    def test_release_title_truncates(self):
        with mock.patch.object(rel, "tag_subject", return_value="长" * 200):
            title = rel.release_title("v9.9")
        self.assertLessEqual(len(title), rel.TITLE_MAX, f"标题长度 {len(title)} 超过上限")
        self.assertTrue(title.endswith("…"), f"截断没留省略号：{title[-3:]}")

    def test_tag_has_site(self):
        real_tags()
        self.assertFalse(rel.tag_has_site("v1.0-tutorial"))
        self.assertFalse(rel.tag_has_site("v0.2-orient"))
        self.assertTrue(rel.tag_has_site("v1.1-web"))


class TestBuildNotes(unittest.TestCase):
    def test_first_tag_has_no_compare_line(self):
        real_tags()
        data = rel.collect_data("v0.2-orient", None)
        notes = rel.build_notes("v0.2-orient", None, data)
        self.assertNotIn("**对比**", notes, "第一个 tag 打不出「对比」行")
        self.assertIn("**发布日期**：", notes)
        self.assertIn("本版尚未有站点，无构建资产", notes)

    def test_v1_1_web_notes(self):
        real_tags()
        prev = rel.previous_tag("v1.1-web")
        data = rel.collect_data("v1.1-web", prev)
        notes = rel.build_notes("v1.1-web", prev, data)
        self.assertIn("## 新增", notes)
        self.assertIn("**对比**", notes)
        self.assertIn(f"/compare/{prev}...v1.1-web", notes)
        self.assertIn(f"/blob/v1.1-web/CHANGELOG.md", notes)
        self.assertNotIn("journal:", notes, "journal: 归档提交是噪声，不该逐条列出")
        self.assertIn("另有 ", notes, "噪声条数应该报在统计行里")

    def test_title_is_first_line(self):
        real_tags()
        prev = rel.previous_tag("v1.1-web")
        notes = rel.build_notes("v1.1-web", prev, rel.collect_data("v1.1-web", prev))
        self.assertEqual(notes.splitlines()[0], f"# {rel.release_title('v1.1-web')}")

    def test_empty_category_is_not_printed(self):
        commits = [{"sha": "a" * 7, "subject": "feat: 只加了一个功能"}]
        notes = rel.build_notes("v9.9", "v9.8", {"date": "2026-01-01", "commits": commits,
                                                 "stats": {"lessons": 1, "sources": 1}})
        self.assertIn("## 新增", notes)
        self.assertNotIn("## 修复", notes, "空分类不该打印小标题")


class TestChangelog(unittest.TestCase):
    def test_render_is_reversed_and_one_section_per_tag(self):
        releases = [
            {"tag": "v1.0-x", "date": "2026-01-01",
             "commits": [{"sha": "a" * 7, "subject": "feat: 第一个版本"}]},
            {"tag": "v1.1-y", "date": "2026-02-02",
             "commits": [{"sha": "b" * 7, "subject": "fix: 修一个坑"}]},
        ]
        text = rel.render_changelog(releases, [{"sha": "c" * 7, "subject": "ci: 加流水线"}])
        self.assertTrue(text.startswith("# 更新日志"), "开头必须是 Keep a Changelog 的 H1")
        for tag in ("v1.0-x", "v1.1-y"):
            self.assertEqual(text.count(f"## [{tag}]"), 1, f"{tag} 的节不是恰好一节")
        pos = [text.index("## [未发布]"), text.index("## [v1.1-y]"), text.index("## [v1.0-x]")]
        self.assertEqual(pos, sorted(pos), f"顺序不是「未发布 → 最新 tag → 更早 tag」：{pos}")
        self.assertIn("## [v1.0-x] - 2026-01-01", text)
        self.assertIn("### 修复", text)
        self.assertIn("不要手改", text, "头部要写明本文件由脚本生成，不要手改")

    def test_unreleased_without_commits_says_none(self):
        text = rel.render_changelog([], [])
        self.assertIn("## [未发布]\n\n无", text, "没有未发布提交时该节正文写「无」")

    def test_real_history(self):
        tags = real_tags()
        releases, unreleased = rel.changelog_data()
        text = rel.render_changelog(releases, unreleased)
        ordered = rel.tag_order(tags)
        for tag in ordered:
            self.assertEqual(text.count(f"## [{tag}]"), 1, f"{tag} 的节不是恰好一节")
        positions = {tag: text.index(f"## [{tag}]") for tag in ordered}
        by_position = sorted(ordered, key=lambda t: positions[t])
        self.assertEqual(by_position, list(reversed(ordered)),
                         "节没有倒序（按出现位置排出来第 1 个是 %s）" % by_position[0])
        listed_noise = [l for l in text.splitlines() if l.startswith("- journal:")
                        or l.startswith("- session: 自动归档")]
        self.assertFalse(listed_noise, f"CHANGELOG 里不该逐条列归档提交：{len(listed_noise)} 条")

    def test_assume_tag_closes_the_section_and_empties_unreleased(self):
        real_tags()
        tag = "v9.9-assume"
        releases, unreleased = rel.changelog_data(assume_tag=tag)
        self.assertEqual(releases[-1]["tag"], tag, "假设的 tag 要成为最新一节")
        self.assertEqual(unreleased, [], "假设它已存在 → 未发布区为空；tag 打上后算法与此完全一致")
        self.assertEqual(releases[-1]["date"], rel.head_date(), "它的日期就是 HEAD 的 commit 日期")
        self.assertIn(f"## [{tag}]", rel.changelog_text(tag), "正文里要出现这一节")

    def test_assume_tag_is_ignored_when_the_tag_already_exists(self):
        real_tags()
        existing = rel.tag_order(rel.all_tags())[-1]
        releases, _ = rel.changelog_data(assume_tag=existing)
        self.assertEqual([r["tag"] for r in releases].count(existing), 1,
                         "已存在的 tag 不该被重复加一节")

    def test_first_difference_finds_the_line(self):
        lineno, want, have = rel.first_difference("a\nb\nc\n", "a\nX\nc\n")
        self.assertEqual((lineno, want, have), (2, "b", "X"))
        self.assertEqual(rel.first_difference("x\n", "x\n")[0], 0)
        lineno, want, have = rel.first_difference("a\n", "a\nb\n")
        self.assertEqual((lineno, have), (2, "b"), "多出来的行要报出来")

    def test_write_then_check_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "CHANGELOG.md"
            with mock.patch.object(rel, "CHANGELOG", target), redirect_stdout(io.StringIO()):
                self.assertEqual(rel.main(["changelog", "--write"]), 0)
                self.assertTrue(target.is_file())
                self.assertEqual(rel.main(["changelog", "--check"]), 0)
                target.write_text(target.read_text(encoding="utf-8") + "手改一行\n",
                                  encoding="utf-8", newline="\n")
                err = io.StringIO()
                with redirect_stderr(err), redirect_stdout(io.StringIO()):
                    self.assertEqual(rel.main(["changelog", "--check"]), 1)
            self.assertIn("首个不同行", err.getvalue())

    def test_check_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "CHANGELOG.md"
            err = io.StringIO()
            with mock.patch.object(rel, "CHANGELOG", missing), redirect_stderr(err), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(rel.main(["changelog", "--check"]), 1)
            self.assertIn("不存在", err.getvalue())


class TestZipsAndNormalization(unittest.TestCase):
    def _tree(self, root: Path) -> Path:
        (root / "sub").mkdir(parents=True)
        (root / "index.html").write_text("<html>你好</html>\n", encoding="utf-8", newline="\n")
        (root / "sub" / "a.js").write_text("export default 1;\n", encoding="utf-8", newline="\n")
        (root / "data" / "index.json").parent.mkdir()
        (root / "data" / "index.json").write_text('{"generated": "2026-01-01T00:00:00+08:00"}\n',
                                                  encoding="utf-8", newline="\n")
        return root

    def test_zip_dir_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = self._tree(tmp_path / "site")
            first = tmp_path / "a.zip"
            second = tmp_path / "b.zip"
            rel.zip_dir(src, first, root="site")
            time.sleep(1.1)                      # 跨秒：date_time 固定后不该有任何影响
            os.utime(src / "sub" / "a.js", (0, 0))   # 改 mtime 也不该有影响
            rel.zip_dir(src, second, root="site")
            self.assertEqual(rel.sha256_file(first), rel.sha256_file(second),
                             "同一个目录打两次 zip 的 sha256 不同（确定性被破坏）")

    def test_zip_dir_keeps_all_files_under_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = self._tree(tmp_path / "site")
            dest = tmp_path / "c.zip"
            rel.zip_dir(src, dest, root="site")
            with zipfile.ZipFile(dest) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                self.assertEqual(sorted(names), ["site/data/index.json", "site/index.html",
                                                 "site/sub/a.js"])
                self.assertIsNone(zf.testzip(), "zip 内容校验失败（CRC 不符）")

    def test_normalize_build_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self._tree(Path(tmp) / "site")
            (site / "data" / "manifest.json").write_text(
                '{"built_at": "2026-09-18T11:17:33+08:00"}\n', encoding="utf-8", newline="\n")
            (site / "sitemap.xml").write_text(
                '<url><loc>x</loc><lastmod>2026-09-18</lastmod></url>\n',
                encoding="utf-8", newline="\n")
            (site / "sub" / "a.js").write_text("const today = '2026-03-15T09:00:00';\n",
                                               encoding="utf-8", newline="\n")
            changed = rel.normalize_build_clock(site, "2026-09-16T14:39:53+08:00", "2026-09-16")
            index = json.loads((site / "data" / "index.json").read_text(encoding="utf-8"))
            manifest = json.loads((site / "data" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(index["generated"], "2026-09-16T14:39:53+08:00")
            self.assertEqual(manifest["built_at"], "2026-09-16T14:39:53+08:00")
            sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
            self.assertIn("<lastmod>2026-09-16</lastmod>", sitemap)
            self.assertNotIn("2026-09-18", sitemap)
            # 课程内容里的日期一个都不许动
            self.assertIn("2026-03-15T09:00:00", (site / "sub" / "a.js").read_text(encoding="utf-8"))
            self.assertFalse([p for p in changed if p.startswith("sub/")],
                             f"不该改课程内容文件：{changed}")

    def test_normalize_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self._tree(Path(tmp) / "site")
            rel.normalize_build_clock(site, "2026-09-16T14:39:53+08:00", "2026-09-16")
            first = rel.sha256_file(site / "data" / "index.json")
            rel.normalize_build_clock(site, "2026-09-16T14:39:53+08:00", "2026-09-16")
            self.assertEqual(rel.sha256_file(site / "data" / "index.json"), first)


class TestPurePayloads(unittest.TestCase):
    def test_draft_payload_is_a_draft_with_string_make_latest(self):
        payload = rel.draft_payload("v1.1-web", "标题", "正文", prerelease=False, latest=False)
        self.assertIs(payload["draft"], True, "新 release 必须先建草稿")
        self.assertIsInstance(payload["make_latest"], str,
                              "make_latest 必须是字符串（传布尔 GitHub 会拒）")
        self.assertEqual(payload["make_latest"], "false")
        self.assertEqual(payload["tag_name"], "v1.1-web")
        self.assertIs(payload["prerelease"], False)

    def test_draft_payload_latest_true_is_string(self):
        payload = rel.draft_payload("v3.3-topbar", "标题", "正文", prerelease=False, latest=True)
        self.assertIsInstance(payload["make_latest"], str)
        self.assertEqual(payload["make_latest"], "true")

    def test_publish_payload_only_flips_draft(self):
        self.assertEqual(rel.publish_payload(), {"draft": False},
                         "不带 make_latest 时只翻 draft 一个字段")

    def test_publish_payload_carries_make_latest(self):
        # 草稿阶段发 make_latest 会被 422 拒（Latest release cannot be draft or prerelease），
        # 所以它必须挂在「转正」这一步上；值为字符串 "true"/"false"（GitHub 的 schema）
        self.assertEqual(rel.publish_payload(True), {"draft": False, "make_latest": "true"})
        self.assertEqual(rel.publish_payload(False), {"draft": False, "make_latest": "false"})

    def test_publish_payload_repeats_tag_name(self):
        # 转正时必须再给一次 tag_name：搁置太久的旧草稿转正后，占位名 untagged-… 会留下
        # （实测 v3.3-topbar 踩过：release 建出来了，tag_name 却还是占位名，audit 判它「缺 release」）
        payload = rel.publish_payload(True, tag="v3.3-topbar")
        self.assertEqual(payload["tag_name"], "v3.3-topbar")
        self.assertEqual(payload["draft"], False)

    def test_update_payload_omits_locked_fields_for_immutable(self):
        locked = rel.update_payload("标题", "正文")
        self.assertEqual(set(locked), {"name", "body"}, "不可变发布只许改 name/body")
        full = rel.update_payload("标题", "正文", prerelease=False, latest=True)
        self.assertEqual(full["make_latest"], "true")
        self.assertIsInstance(full["make_latest"], str)

    def test_merge_body_keeps_the_original_text(self):
        original = "这是手写的原始说明第一行\n第二行"
        merged = rel.merge_body("# 生成的标题\n\n生成正文\n", original)
        self.assertIn("## 原始发布说明", merged)
        self.assertIn(original, merged, "原文必须逐字保留")
        self.assertTrue(merged.rstrip("\n").endswith("第二行"), "原文应在末尾")
        self.assertTrue(merged.startswith("# 生成的标题"))

    def test_merge_body_without_original(self):
        merged = rel.merge_body("生成的正文\n", "")
        self.assertNotIn("原始发布说明", merged)
        self.assertEqual(merged, "生成的正文\n")

    def test_repo_slug_from_env(self):
        with mock.patch.dict(os.environ, {"GH_REPO": "owner/name"}):
            self.assertEqual(rel.repo_slug(), "owner/name")
        with mock.patch.dict(os.environ, {"GH_REPO": "不是一个 slug"}):
            self.assertIsNone(rel.repo_slug(), "非法 GH_REPO 应判失败而不是猜")

    def test_repo_slug_from_remote(self):
        env = dict(os.environ)
        env.pop("GH_REPO", None)
        with mock.patch.dict(os.environ, env, clear=True):
            slug = rel.repo_slug()
        remote = rel._git("remote", "get-url", "origin", check=False).strip()
        self.assertTrue(remote, "本仓库应有 origin remote")
        self.assertEqual(slug, "mt-yu/HermesUsage", f"从 {remote} 解析出的 slug 不对：{slug}")


class TestDryRunNeverTouchesTheNetwork(unittest.TestCase):
    def setUp(self):
        real_tags()
        if rel.repo_slug() is None:
            self.skipTest("解析不出 owner/name，dry-run 的 URL 无从校验")

    def test_create_dry_run_does_not_resolve_token_or_send(self):
        boom = AssertionError("dry-run 不该走到这里")
        with mock.patch.object(rel, "get_token", side_effect=boom), \
                mock.patch.object(rel, "_request", side_effect=boom), \
                mock.patch.object(rel, "_api", side_effect=boom), \
                mock.patch.object(rel, "upload_asset", side_effect=boom):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = rel.main(["create", "--tag", "v1.1-web", "--dry-run"])
            out = buf.getvalue()
        self.assertEqual(rc, 0, f"create --dry-run 应该成功（实际退出码 {rc}）")
        self.assertIn("[dry-run]", out)
        self.assertIn("releases/tags/v1.1-web", out)
        self.assertIn('"draft": true', out, "请求体摘要里要能看出先建草稿")
        self.assertIn('{"draft": false}', out, "最后一步必须是转正发布")

    def test_create_dry_run_first_tag_has_no_compare(self):
        with mock.patch.object(rel, "get_token", side_effect=AssertionError("不该取令牌")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = rel.main(["create", "--tag", "v0.2-orient", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("make_latest=false", buf.getvalue())

    def test_create_dry_run_body_only_skips_assets(self):
        with mock.patch.object(rel, "get_token", side_effect=AssertionError("不该取令牌")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = rel.main(["create", "--tag", "v1.1-web", "--dry-run", "--body-only"])
        self.assertEqual(rc, 0)
        self.assertIn("--body-only", buf.getvalue())
        self.assertNotIn("uploads.github.com", buf.getvalue())

    def test_audit_dry_run_prints_urls_only(self):
        with mock.patch.object(rel, "get_token", side_effect=AssertionError("不该取令牌")), \
                mock.patch.object(rel, "_request", side_effect=AssertionError("不该发请求")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = rel.main(["audit", "--dry-run"])
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("api.github.com/repos/", out)
        self.assertIn("releases?per_page=", out)

    def test_audit_without_token_exits_2(self):
        with mock.patch.object(rel, "get_token", return_value=None), \
                mock.patch.object(rel, "_request", side_effect=AssertionError("不该发请求")):
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = rel.main(["audit", "--check"])
        self.assertEqual(rc, 2, "没令牌应退出 2（前置错误），不是 1（差异）")
        self.assertIn("令牌", err.getvalue())


class TestUsageErrors(unittest.TestCase):
    def test_unknown_tag_exits_2(self):
        real_tags()
        for argv in (["notes", "--tag", "v9.9-不存在"],
                     ["artifact", "--tag", "v9.9-不存在", "--out", "dist"],
                     ["create", "--tag", "v9.9-不存在", "--dry-run"]):
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = rel.main(argv)
            self.assertEqual(rc, 2, f"{argv[0]} 对未知 tag 应退出 2（实际 {rc}）")

    def test_artifact_skips_tags_without_a_site(self):
        real_tags()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = rel.main(["artifact", "--tag", "v1.0-tutorial", "--out", str(out)])
            self.assertEqual(rc, 0, "没有站点的 tag 不是错误（不产出资产，退出 0）")
            self.assertIn("尚无站点", buf.getvalue())
            self.assertFalse(out.exists(), "没有站点的 tag 不该产出任何文件/目录")


class TestReleasesForTag(unittest.TestCase):
    """`releases_for_tag` 是纯函数：给一份 release 列表，挑出正主与多余草稿。

    它不是「顺手写的小工具」—— 没有它，上传中断留下的空草稿就永远找不回来：
    `GET /releases/tags/<tag>` 看不到草稿，带令牌的 `GET /releases` 才看得到。
    """

    TAG = "v1.1-web"

    def _rel(self, rid, *, draft, tag=None, body=""):
        return {"id": rid, "tag_name": tag or self.TAG, "draft": draft, "body": body,
                "html_url": f"https://x/{rid}"}

    def test_no_match_returns_none(self):
        got, extras = rel.releases_for_tag([self._rel(1, draft=False, tag="v9-别的")], self.TAG)
        self.assertIsNone(got)
        self.assertEqual(extras, [])

    def test_published_wins_over_drafts(self):
        listing = [self._rel(3, draft=True), self._rel(5, draft=False), self._rel(4, draft=True)]
        got, extras = rel.releases_for_tag(listing, self.TAG)
        self.assertEqual(got["id"], 5, "已发布的那条才是正主")
        self.assertEqual([r["id"] for r in extras], [3, 4], "多余的草稿要如实报出来（按 id 升序）")

    def test_only_drafts_reuses_the_newest_and_reports_the_rest(self):
        listing = [self._rel(10, draft=True), self._rel(11, draft=True)]
        got, extras = rel.releases_for_tag(listing, self.TAG)
        self.assertEqual(got["id"], 11, "没有已发布的 → 沿用最新那次尝试建的草稿")
        self.assertEqual([r["id"] for r in extras], [10])

    def test_single_draft_has_no_extras(self):
        got, extras = rel.releases_for_tag([self._rel(7, draft=True)], self.TAG)
        self.assertEqual(got["id"], 7)
        self.assertEqual(extras, [])


class TestCreateIsIdempotentAndSelfCleaning(unittest.TestCase):
    """`create` 必须能安全重跑，而且**不留残骸**。

    三件事各有用例：
    1. 新建的草稿在任何一步失败时被回滚（否则留下看不见的孤儿草稿）；
    2. 已存在的 release 绝不被删（正文/资产是别人的东西）；
    3. 上次崩掉留下的草稿被**沿用**，并在发布成功后把同 tag 的多余草稿清掉。
    """

    TAG = "v1.1-web"

    def setUp(self):
        # 成功路径会读上传文件的字节数（`path.stat()`），所以得给一个真实存在的小文件
        self._tmp = tempfile.TemporaryDirectory()
        self._asset = Path(self._tmp.name) / "hermesusage-site-v1.1-web.zip"
        self._asset.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    def tearDown(self):
        self._tmp.cleanup()

    def _patches(self, calls, *, listing, upload_ok: bool):
        def fake_api(method, path, token, payload=None):
            calls.append((method, path))
            if path.endswith("/releases?per_page=100&page=1"):
                return 200, listing
            if path == "/repos/owner/repo/releases" and method == "POST":
                return 201, {"id": 42, "html_url": "https://x/untagged-abc", "draft": True}
            if path.endswith("/assets?per_page=100"):
                return 200, []
            if path.endswith(f"/releases/tags/{self.TAG}") and method == "GET":
                return 200, {"id": 42, "draft": False, "assets": []}
            if method == "PATCH" and "/releases/" in path:
                rid = int(path.rsplit("/", 1)[-1])
                return 200, {"id": rid, "html_url": f"https://x/{rid}", "draft": False, "body": "原文"}
            if method == "DELETE" and "/releases/" in path:
                return 204, ""
            raise AssertionError(f"未预期的请求：{method} {path}")

        def upload(*_a, **_kw):
            if not upload_ok:
                raise rel.ReleaseError("上传中断（模拟 TLS 抖动）")
            return {"browser_download_url": "https://x/asset"}

        return [
            mock.patch.object(rel, "get_token", lambda: "token"),
            mock.patch.object(rel, "repo_slug", lambda: "owner/repo"),
            mock.patch.object(rel, "_api", fake_api),
            mock.patch.object(rel, "upload_asset", upload),
            mock.patch.object(rel, "ensure_artifact", lambda tag, quiet=False: None),
            mock.patch.object(rel, "materialize_assets", lambda tag: [(self._asset, "application/zip")]),
            mock.patch.object(rel, "tag_exists", lambda tag: True),
            mock.patch.object(rel, "tag_has_site", lambda tag: True),
            mock.patch.object(rel, "previous_tag", lambda tag: None),
            mock.patch.object(rel, "collect_data", lambda tag, prev: {"date": "2026-09-16", "commits": [], "stats": {}}),
            mock.patch.object(rel, "build_notes", lambda tag, prev, data: "BODY"),
            mock.patch.object(rel, "release_title", lambda tag: "TITLE"),
        ]

    def _run(self, calls, *, listing, upload_ok):
        with ExitStack() as stack:
            for patch_obj in self._patches(calls, listing=listing, upload_ok=upload_ok):
                stack.enter_context(patch_obj)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return rel.main(["create", "--tag", self.TAG, "--quiet"])

    def test_new_draft_is_deleted_when_a_later_step_fails(self):
        calls: list[tuple[str, str]] = []
        rc = self._run(calls, listing=[], upload_ok=False)
        self.assertEqual(rc, 2, "上传失败应退出 2（前置/网络错误）")
        self.assertIn(("DELETE", "/repos/owner/repo/releases/42"), calls,
                      "本次新建的草稿必须被回滚（否则留下看不见的孤儿草稿）")
        self.assertNotIn(("PATCH", "/repos/owner/repo/releases/42"), calls,
                         "失败路径不该走到「发布」（把草稿转正）")

    def test_existing_release_is_never_deleted(self):
        calls: list[tuple[str, str]] = []
        listing = [{"id": 7, "tag_name": self.TAG, "draft": False, "immutable": False, "body": "原文"}]
        rc = self._run(calls, listing=listing, upload_ok=False)
        self.assertEqual(rc, 2)
        self.assertFalse([c for c in calls if c[0] == "DELETE"],
                         "已存在的 release 一个字节都不该动（正文/资产是别人的东西）")

    def test_leftover_draft_is_reused_and_extra_drafts_are_cleaned(self):
        calls: list[tuple[str, str]] = []
        listing = [{"id": 10, "tag_name": self.TAG, "draft": True, "immutable": False, "body": ""},
                   {"id": 11, "tag_name": self.TAG, "draft": True, "immutable": False, "body": ""}]
        rc = self._run(calls, listing=listing, upload_ok=True)
        self.assertEqual(rc, 0)
        self.assertNotIn(("POST", "/repos/owner/repo/releases"), calls,
                         "已有草稿就沿用（id 11），不该再建一个")
        self.assertIn(("PATCH", "/repos/owner/repo/releases/11"), calls)
        self.assertIn(("DELETE", "/repos/owner/repo/releases/10"), calls,
                      "同 tag 的多余草稿要在发布成功后清掉")


if __name__ == "__main__":
    unittest.main()
