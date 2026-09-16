#!/usr/bin/env python3
"""tests/test_cron_ctl.py —— 定时任务总开关的单元测试。

运行：python -m unittest discover -s tests -t . -p "test_*.py" -v

两条纪律：
1. **绝不真的调用 hermes、绝不写真实 $HERMES_HOME**：所有用例的 home 都指向临时目录，
   需要「成功登记」时把 run_hermes 换成一个只记录参数的假函数。
2. `--dry-run` 的用例是唯一能证明「这个动词不会动系统」的东西 —— 所以它必须断言
   「没写文件、没调 hermes」，而不只是看打印了什么。
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import cron_ctl as cc  # noqa: E402


def job(job_id: str, name: str, enabled: bool, sched: str = "0 * * * *") -> dict:
    return {
        "id": job_id,
        "name": name,
        "enabled": enabled,
        "schedule": {"kind": "cron", "expr": sched, "display": sched},
        "next_run_at": "2026-09-16T18:00:00+08:00",
        "last_status": "ok",
    }


AUTOJOURNAL = job("c2e058a277da", "HermesUsage 自动归档", True)
DRIFT = job("aaaaaaaaaaaa", "HermesUsage 漂移哨兵", False, "0 9 * * *")
FOREIGN = job("ffffffffffff", "别人的任务", True)


def write_store(home: Path, jobs: list[dict]) -> Path:
    store = home / "cron" / "jobs.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps({"jobs": jobs, "updated_at": "2026-09-16"},
                                ensure_ascii=False), encoding="utf-8")
    return store


def run_and_capture(fn, *a, **kw) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*a, **kw)
    return code, buf.getvalue()


class TestShimText(unittest.TestCase):
    """包装器是「cron 只收 $HERMES_HOME/scripts/ 下的相对文件名」逼出来的东西。"""

    def test_contains_repo_script_and_args(self):
        drift = next(j for j in cc.JOBS if j.slug == "drift")
        text = cc.shim_text(drift)
        self.assertIn(str(REPO), text)              # 仓库绝对路径写死
        self.assertIn("scripts/drift_watch.py", text)
        self.assertIn("('--quiet',)", text)

    def test_is_valid_python_for_every_generated_shim(self):
        for j in cc.JOBS:
            if not j.generate_shim:
                continue
            compile(cc.shim_text(j), f"<{j.shim}>", "exec")   # 不合法会抛 SyntaxError

    def test_shim_lets_env_var_override_repo(self):
        drift = next(j for j in cc.JOBS if j.slug == "drift")
        self.assertIn("HERMESUSAGE_REPO", cc.shim_text(drift))

    def test_autojournal_shim_is_not_generated(self):
        """自动归档的包装器是早期手工安装的那份，install 不该去重写它。"""
        auto = next(j for j in cc.JOBS if j.slug == "autojournal")
        self.assertFalse(auto.generate_shim)

    def test_every_job_has_prefix_name_and_relative_script(self):
        for j in cc.JOBS:
            self.assertTrue(j.name.startswith(cc.NAME_PREFIX), j.name)
            self.assertTrue(j.script.startswith("scripts/"), j.script)
            self.assertTrue(j.shim.endswith(".py"), j.shim)


class TestLoadAndFilter(unittest.TestCase):
    def test_parses_jobs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_store(home, [AUTOJOURNAL, FOREIGN])
            self.assertEqual([j["id"] for j in cc.load_registered(home)],
                             ["c2e058a277da", "ffffffffffff"])

    def test_missing_store_is_empty_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cc.load_registered(Path(tmp)), [])

    def test_corrupt_store_is_empty_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "cron").mkdir(parents=True)
            (home / "cron" / "jobs.json").write_text("{ 这不是 json", encoding="utf-8")
            self.assertEqual(cc.load_registered(home), [])

    def test_repo_jobs_only_claims_own_prefix(self):
        names = [j["name"] for j in cc.repo_jobs([AUTOJOURNAL, DRIFT, FOREIGN])]
        self.assertEqual(names, ["HermesUsage 自动归档", "HermesUsage 漂移哨兵"])


class TestPlanStateChange(unittest.TestCase):
    def test_off_targets_only_active(self):
        plan = cc.plan_state_change([AUTOJOURNAL, DRIFT, FOREIGN], want_enabled=False)
        self.assertEqual(plan, [("c2e058a277da", "pause", "HermesUsage 自动归档")])

    def test_on_targets_only_paused(self):
        plan = cc.plan_state_change([AUTOJOURNAL, DRIFT], want_enabled=True)
        self.assertEqual(plan, [("aaaaaaaaaaaa", "resume", "HermesUsage 漂移哨兵")])

    def test_noop_when_already_target(self):
        self.assertEqual(cc.plan_state_change([AUTOJOURNAL], want_enabled=True), [])

    def test_never_touches_foreign_jobs(self):
        self.assertEqual(cc.plan_state_change([FOREIGN], want_enabled=False), [])


class TestGatewayParsing(unittest.TestCase):
    def test_detects_running(self):
        self.assertIs(cc.gateway_running("✓ Gateway is running — cron jobs will fire automatically"),
                      True)

    def test_detects_not_running(self):
        self.assertIs(cc.gateway_running("✗ Gateway is not running — cron jobs will NOT fire"),
                      False)

    def test_unknown_text_returns_none(self):
        self.assertIsNone(cc.gateway_running("莫名输出"))

    def test_status_line_marks_paused(self):
        line = cc.parse_status_line(DRIFT)
        self.assertIn("paused", line)
        self.assertIn("HermesUsage 漂移哨兵", line)
        self.assertIn("0 9 * * *", line)


class TestInstall(unittest.TestCase):
    def test_dry_run_spawns_no_process_and_writes_no_file(self):
        """dry-run 的正确判据不是「没调 run_hermes」——短路发生在它内部 ——
        而是「一个子进程都没起、一个文件都没写」。"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch.object(cc.subprocess, "run") as spawn:
                code, out = run_and_capture(cc.cmd_install, home, True)
            self.assertEqual(code, 0)
            spawn.assert_not_called()                        # 没有真的起 hermes 进程
            self.assertFalse((home / "scripts").exists())     # 一个文件都没写
            self.assertIn("[dry-run]", out)
            self.assertIn("cron create", out)
            self.assertIn("--script hu-drift.py", out)
            self.assertIn("--no-agent", out)
            self.assertIn("--deliver local", out)
            self.assertIn(str(REPO), out)

    def test_dry_run_off_and_run_also_spawn_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_store(home, [AUTOJOURNAL, DRIFT])
            with mock.patch.object(cc.subprocess, "run") as spawn:
                code_off, out_off = run_and_capture(cc.cmd_set, False, home, True)
                code_on, out_on = run_and_capture(cc.cmd_set, True, home, True)
                code_run, out_run = run_and_capture(cc.cmd_run, home, True)
            self.assertEqual((code_off, code_on, code_run), (0, 0, 0))
            spawn.assert_not_called()
            self.assertIn("cron pause c2e058a277da", out_off)      # off 只动 active 那个
            self.assertIn("cron resume aaaaaaaaaaaa", out_on)      # on 只动 paused 那个
            self.assertIn("cron run c2e058a277da", out_run)

    def test_creates_shim_then_registers_missing_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            calls: list[list[str]] = []

            def fake(args, dry_run=False):
                calls.append(list(args))
                return 0, "ok"

            with mock.patch.object(cc, "run_hermes", side_effect=fake):
                code, _out = run_and_capture(cc.cmd_install, home, False)

            self.assertEqual(code, 0)
            drift_shim = home / "scripts" / "hu-drift.py"
            self.assertTrue(drift_shim.is_file())
            self.assertIn("drift_watch.py", drift_shim.read_text(encoding="utf-8"))
            created = [c for c in calls if c[:2] == ["cron", "create"]]
            self.assertEqual(len(created), len(cc.JOBS))   # 空 home：三个都该建
            names = [c[c.index("--name") + 1] for c in created]
            self.assertIn("HermesUsage 外链存活检测", names)

    def test_skips_already_registered_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_store(home, [AUTOJOURNAL, DRIFT])
            calls: list[list[str]] = []

            with mock.patch.object(cc, "run_hermes", side_effect=lambda a, dry_run=False: (calls.append(list(a)), (0, ""))[1]):
                code, out = run_and_capture(cc.cmd_install, home, False)

            self.assertEqual(code, 0)
            created = [c for c in calls if c[:2] == ["cron", "create"]]
            self.assertEqual(len(created), 1)
            self.assertEqual(created[0][created[0].index("--name") + 1], "HermesUsage 外链存活检测")
            self.assertIn("已登记，跳过", out)

    def test_refuses_to_overwrite_differing_shim(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "scripts").mkdir(parents=True)
            mine = home / "scripts" / "hu-drift.py"
            mine.write_text("# 我自己手改过的，别动我\n", encoding="utf-8")

            with mock.patch.object(cc, "run_hermes", return_value=(0, "")):
                code, out = run_and_capture(cc.cmd_install, home, False)

            self.assertEqual(code, 0)
            self.assertEqual(mine.read_text(encoding="utf-8"), "# 我自己手改过的，别动我\n")
            self.assertIn("未覆盖", out)

    def test_install_error_surfaces_hermes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch.object(cc, "run_hermes", return_value=(1, "Script path must be relative to ...")):
                code, out = run_and_capture(cc.cmd_install, home, False)
            self.assertEqual(code, 1)
            self.assertIn("登记失败", out)


class TestSetAndStatus(unittest.TestCase):
    def test_off_pauses_only_active_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_store(home, [AUTOJOURNAL, DRIFT])
            calls: list[list[str]] = []

            with mock.patch.object(cc, "run_hermes",
                                   side_effect=lambda a, dry_run=False: (calls.append(list(a)), (0, ""))[1]):
                code, out = run_and_capture(cc.cmd_set, False, home)

            self.assertEqual(code, 0)
            self.assertEqual(calls, [["cron", "pause", "c2e058a277da"]])
            self.assertIn("暂停", out)

    def test_noop_message_when_already_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_store(home, [AUTOJOURNAL])
            with mock.patch.object(cc, "run_hermes") as fake:
                code, out = run_and_capture(cc.cmd_set, True, home)
            self.assertEqual(code, 0)
            fake.assert_not_called()
            self.assertIn("没有需要恢复的任务", out)

    def test_status_without_jobs_hints_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch.object(cc, "run_hermes", return_value=(0, "✗ Gateway is not running — cron jobs will NOT fire")):
                code, out = run_and_capture(cc.cmd_status, home)
            self.assertEqual(code, 0)
            self.assertIn("还没有登记任何定时任务", out)
            self.assertIn("hermes gateway install", out)

    def test_status_lists_repo_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            write_store(home, [AUTOJOURNAL, FOREIGN])
            with mock.patch.object(cc, "run_hermes", return_value=(0, "✓ Gateway is running — cron jobs will fire automatically")):
                code, out = run_and_capture(cc.cmd_status, home)
            self.assertIn("HermesUsage 自动归档", out)
            self.assertNotIn("别人的任务", out)      # 不认领别人的任务


class TestCli(unittest.TestCase):
    def test_unknown_verb_exits_2(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            cc.main(["不存在"])
        self.assertEqual(cm.exception.code, 2)

    def test_verb_is_required(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cc.main([])

    def test_home_flag_overrides_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(cc, "run_hermes", return_value=(0, "")) as fake:
                code, out = run_and_capture(cc.main, ["--home", tmp, "status"])
            self.assertEqual(code, 0)
            self.assertIn("还没有登记任何定时任务", out)
            self.assertTrue(fake.called)             # status 会问一次 hermes cron status

    def test_dry_run_works_on_both_sides_of_the_verb(self):
        """用法说明里写的是 `install --dry-run`，所以动词后的写法必须也能用。"""
        with tempfile.TemporaryDirectory() as tmp:
            for argv in (["--home", tmp, "--dry-run", "install"],
                         ["--home", tmp, "install", "--dry-run"]):
                with mock.patch.object(cc.subprocess, "run") as spawn:
                    code, out = run_and_capture(cc.main, argv)
                self.assertEqual(code, 0, argv)
                spawn.assert_not_called()
                self.assertIn("[dry-run]", out)

    def test_default_home_follows_platform_convention(self):
        """断言「规则」而不是本机的字面结果 —— 写死 %LOCALAPPDATA% 会让 Linux 上的 CI 红。"""
        with mock.patch.dict(cc.os.environ, {}, clear=False):
            cc.os.environ.pop("HERMES_HOME", None)
            expected = "hermes" if cc.os.name == "nt" else ".hermes"
            self.assertEqual(cc.hermes_home().name, expected)

    def test_env_var_wins_over_platform_default(self):
        with mock.patch.dict(cc.os.environ, {"HERMES_HOME": os.path.join("tmp", "xx")}, clear=False):
            self.assertEqual(cc.hermes_home().name, "xx")


if __name__ == "__main__":
    unittest.main()
