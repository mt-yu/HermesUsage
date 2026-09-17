#!/usr/bin/env python3
"""tests/test_journal.py —— 自动归档的「别卷走在途改动」闸门。

运行：python -m unittest discover -s tests -t . -p "test_*.py" -v

背景（实测踩了 4 次）：cron 的小时级自动归档会 `git status` 见到什么就提交什么，
于是子代理写到一半的课/脚本会被卷进一个 `session:` 自动提交 —— 历史里多出
「未验收状态」的提交，而人精心写的那条提交信息反而落不了地。

这里的测试只覆盖闸门本身（纯函数 + 一次接线），**不碰真的 git 与 state.db**。
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import journal as J  # noqa: E402


def make_manifest(home: Path, name: str, *, completed: bool, statuses: list[str],
                  age_seconds: float = 0.0) -> Path:
    d = home / "cache" / "delegation" / "live" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "manifest.json"
    data = {
        "delegation_id": name,
        "task_count": len(statuses),
        "tasks": [{"status": s} for s in statuses],
    }
    if completed:
        data["completed"] = "2026-09-17 09:00:00"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        import os
        os.utime(p, (old, old))
    return p


class TestChangedPaths(unittest.TestCase):
    def _paths(self, porcelain_z: str) -> list[str]:
        with mock.patch.object(J, "run", return_value=mock.Mock(stdout=porcelain_z)):
            return J.changed_paths()

    def test_parses_modified_and_untracked(self):
        raw = " M README.md\0?? lessons/06-realwork/L64-x.md\0"
        self.assertEqual(self._paths(raw), ["README.md", "lessons/06-realwork/L64-x.md"])

    def test_keeps_chinese_and_space_paths_intact(self):
        """-z 模式不做引号转义，中文/空格路径必须原样出来（否则 stat 会失败）。"""
        raw = " M lessons/06-realwork/L60 先把目录看清.md\0"
        self.assertEqual(self._paths(raw), ["lessons/06-realwork/L60 先把目录看清.md"])

    def test_rename_skips_the_old_path_record(self):
        """改名在 -z 里是两条记录：新路径 + 旧路径，旧的那条要跳过。"""
        raw = "R  new.md\0old.md\0 M other.md\0"
        self.assertEqual(self._paths(raw), ["new.md", "other.md"])


class TestRealRepoIntegration(unittest.TestCase):
    """**不打 mock** 地跑一次真函数。

    为什么必须有这一条：闸门最初用 `run([...], cwd=repo)` 调用，而 `run` 内部已经
    写死 `cwd=REPO` —— mock 掉 run 的单元测试全绿，真仓库上一跑就是 TypeError。
    凡是「真调用链容易写错」的地方，都得有一条不 mock 的测试。
    """

    def test_changed_paths_against_real_repo(self):
        paths = J.changed_paths()
        self.assertIsInstance(paths, list)
        for p in paths:
            self.assertFalse(p.startswith('"'), f"路径被 git 加了引号：{p!r}")

    def test_guard_functions_run_on_real_repo(self):
        paths = J.changed_paths()
        self.assertIsInstance(J.freshest_change_age(paths), (float, type(None)))
        self.assertIsInstance(J.delegation_in_flight(), (str, type(None)))
        self.assertIsInstance(J.skip_reason(paths), (str, type(None)))


class TestDelegationInFlight(unittest.TestCase):
    def test_no_live_dir_means_nobody_is_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(J.delegation_in_flight(Path(tmp)))

    def test_running_subagent_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            make_manifest(home, "deleg_running", completed=False,
                          statuses=["completed", "running"])
            self.assertEqual(J.delegation_in_flight(home), "deleg_running")

    def test_finished_batch_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            make_manifest(home, "deleg_done", completed=True, statuses=["completed"] * 3)
            self.assertIsNone(J.delegation_in_flight(home))

    def test_all_tasks_terminal_but_no_completed_field_does_not_block(self):
        """有些收尾路径只写任务状态、不写 completed —— 不能因此永久静默归档。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            make_manifest(home, "deleg_x", completed=False,
                          statuses=["completed", "failed", "stopped"])
            self.assertIsNone(J.delegation_in_flight(home))

    def test_stale_manifest_does_not_block_forever(self):
        """残留 manifest（超过上限时间还没收工）不该把归档永久卡死。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            make_manifest(home, "deleg_stale", completed=False, statuses=["running"],
                          age_seconds=J.MANIFEST_STALE_S + 60)
            self.assertIsNone(J.delegation_in_flight(home))

    def test_manifest_under_the_limit_still_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            make_manifest(home, "deleg_young", completed=False, statuses=["running"],
                          age_seconds=J.MANIFEST_STALE_S - 600)
            self.assertEqual(J.delegation_in_flight(home), "deleg_young")


class TestFreshestChangeAge(unittest.TestCase):
    def test_returns_age_of_newest_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            old = repo / "old.md"
            new = repo / "new.md"
            old.write_text("a", encoding="utf-8")
            new.write_text("b", encoding="utf-8")
            now = time.time()
            import os
            os.utime(old, (now - 5000, now - 5000))
            os.utime(new, (now - 30, now - 30))
            age = J.freshest_change_age(["old.md", "new.md"], repo=repo, now_ts=now)
            self.assertAlmostEqual(age, 30, delta=5)

    def test_missing_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(J.freshest_change_age(["不存在.md"], repo=Path(tmp)))


class TestSkipReason(unittest.TestCase):
    def _repo_with_age(self, tmp: str, age: float) -> Path:
        repo = Path(tmp)
        p = repo / "a.md"
        p.write_text("x", encoding="utf-8")
        import os
        now = time.time()
        os.utime(p, (now - age, now - age))
        return repo

    def test_in_flight_delegation_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            make_manifest(home, "deleg_run", completed=False, statuses=["running"])
            repo = self._repo_with_age(tmp, 9999)
            reason = J.skip_reason(["a.md"], repo=repo, home=home)
            self.assertIsNotNone(reason)
            self.assertIn("子代理", reason)

    def test_fresh_edit_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_age(tmp, age=5)
            reason = J.skip_reason(["a.md"], repo=repo, home=Path(tmp) / "nohome")
            self.assertIsNotNone(reason)
            self.assertIn("秒", reason)

    def test_calm_workspace_does_not_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo_with_age(tmp, age=J.IN_FLIGHT_GRACE_S + 60)
            self.assertIsNone(J.skip_reason(["a.md"], repo=repo, home=Path(tmp) / "nohome"))


class TestAutocommitWiring(unittest.TestCase):
    """接线测试：闸门挡住时**不写记录**，挡不住时照常写（别把正常归档改坏）。

    注意必须 patch `J.REPO`：闸门里的 `changed_paths()` 与文件新鲜度检查默认对
    **真仓库**生效（生产就该这样），不指到临时仓库的话 fixture 根本不起作用。
    """

    def _run_main(self, repo: Path, home: Path, verbose: bool = False):
        argv = ["journal.py", "autocommit"] + (["--verbose"] if verbose else [])
        porcelain = " M a.md\n"
        porcelain_z = " M a.md\0"

        def fake_run(cmd, **kw):
            if cmd[:3] == ["git", "status", "--porcelain"]:
                return mock.Mock(stdout=porcelain_z if "-z" in cmd else porcelain)
            return mock.Mock(stdout="")

        with mock.patch.object(J, "run", side_effect=fake_run), \
             mock.patch.object(J, "write_entry") as we, \
             mock.patch.object(J, "session_digest", return_value=("摘要", {})), \
             mock.patch.object(J, "hermes_home", return_value=home), \
             mock.patch.object(J, "REPO", repo), \
             mock.patch.object(sys, "argv", argv):
            code = J.main()
        return code, we

    def test_skips_silently_when_subagent_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            home = Path(tmp) / "home"
            make_manifest(home, "deleg_run", completed=False, statuses=["running"])
            code, we = self._run_main(repo, home)
            self.assertEqual(code, 0)
            we.assert_not_called()          # 关键：一条记录都没写

    def test_skips_silently_when_file_just_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            p = repo / "a.md"
            p.write_text("x", encoding="utf-8")
            code, we = self._run_main(repo, Path(tmp) / "home")
            self.assertEqual(code, 0)
            we.assert_not_called()

    def test_commits_when_workspace_is_calm(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            p = repo / "a.md"
            p.write_text("x", encoding="utf-8")
            import os
            now = time.time()
            os.utime(p, (now - J.IN_FLIGHT_GRACE_S - 60, now - J.IN_FLIGHT_GRACE_S - 60))

            def fake_run(cmd, **kw):
                if cmd[:3] == ["git", "status", "--porcelain"]:
                    return mock.Mock(stdout=" M a.md\0" if "-z" in cmd else " M a.md\n")
                return mock.Mock(stdout="")

            with mock.patch.object(J, "run", side_effect=fake_run), \
                 mock.patch.object(J, "write_entry") as we, \
                 mock.patch.object(J, "session_digest", return_value=("摘要", {})), \
                 mock.patch.object(J, "hermes_home", return_value=Path(tmp) / "home"), \
                 mock.patch.object(J, "REPO", repo), \
                 mock.patch.object(sys, "argv", ["journal.py", "autocommit"]):
                code = J.main()
            self.assertEqual(code, 0)
            we.assert_called_once()         # 平静的工作区照常归档

    def test_force_env_bypasses_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            p = repo / "a.md"
            p.write_text("x", encoding="utf-8")
            with mock.patch.dict("os.environ", {"HERMESUSAGE_AUTOCOMMIT_FORCE": "1"}):
                code, we = self._run_main(repo, Path(tmp) / "home")
            self.assertEqual(code, 0)
            we.assert_called_once()

    def test_verbose_says_why_it_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            p = repo / "a.md"
            p.write_text("x", encoding="utf-8")
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                self._run_main(repo, Path(tmp) / "home", verbose=True)
            self.assertIn("跳过", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
