#!/usr/bin/env python3
"""scripts/cron_ctl.py —— HermesUsage 定时任务的总开关（本仓库里唯一需要维护的地方）。

为什么需要它
------------
1. `hermes cron` 的开关要输入 12 位 job id，对人不友好 —— 这里换成 `on` / `off`。
2. `hermes cron create --script` **只接受 `$HERMES_HOME/scripts/` 下的相对文件名**。
   绝对路径会被直接拒绝（实测报错："Script path must be relative to ..."），所以仓库
   里的脚本没法被 cron 直接调用，必须在那固定目录放一个薄包装器。本脚本按下面的
   JOBS 表生成这些包装器 —— 于是「有哪些定时任务、多久跑一次、跑哪个脚本、传什么参数」
   全部写在仓库里，换台机器一条命令就能重建。

用法
----
    python scripts/cron_ctl.py status      # 网关是否在跑 + 本仓库每个任务的状态
    python scripts/cron_ctl.py off         # 暂停本仓库的全部定时任务
    python scripts/cron_ctl.py on          # 恢复
    python scripts/cron_ctl.py run         # 让它们在下一次 tick 立刻跑一次（不改周期）
    python scripts/cron_ctl.py install     # 按 JOBS 表补登记缺失任务 + 生成包装器（幂等）

每个动词都支持 `--dry-run`：只打印将要执行的 hermes 命令，绝不真的调用或写文件。
改任务定义请改下面的 JOBS 表，然后重跑 `install`。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# 本仓库任务的统一前缀：`status` / `on` / `off` / `run` 都按它认领（别人的任务不碰）
NAME_PREFIX = "HermesUsage"

SHIM_TEMPLATE = '''#!/usr/bin/env python3
"""$HERMES_HOME/scripts/{shim} —— 由 HermesUsage 仓库的 scripts/cron_ctl.py 生成，请勿手改。

它只做一件事：调用仓库里的 `{script}` 并把它的 stdout 原样转出去。
cron 的 --no-agent 模式里 **空输出 = 不投递**，所以被调用的脚本要用 --quiet 保持安静。

改任务定义请改仓库里的 scripts/cron_ctl.py（JOBS 表），然后重跑：
    python scripts/cron_ctl.py install
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("HERMESUSAGE_REPO", r"{repo}"))
SCRIPT = REPO / "{script}"
ARGS = {args}


def main() -> int:
    if not SCRIPT.is_file():
        print(f"未找到 {{SCRIPT}}（用环境变量 HERMESUSAGE_REPO 指定仓库路径）")
        return 1
    res = subprocess.run(
        [sys.executable, str(SCRIPT), *ARGS],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
    )
    out = (res.stdout or "").strip()
    if out:
        print(out)
    if res.returncode != 0:
        print((res.stderr or "").strip()[-800:])
        return res.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


@dataclass(frozen=True)
class Job:
    """一个定时任务的定义。`shim` 是 `$HERMES_HOME/scripts/` 下的文件名。"""

    slug: str
    name: str
    schedule: str
    script: str  # 仓库内相对路径
    args: tuple[str, ...] = ()
    shim: str = ""
    generate_shim: bool = True
    note: str = ""


JOBS: tuple[Job, ...] = (
    Job(
        slug="autojournal",
        name="HermesUsage 自动归档",
        schedule="0 * * * *",
        script="scripts/journal.py",
        args=("autocommit", "--hours", "24"),
        shim="hu-autojournal.py",
        generate_shim=False,
        note="每小时：工作区有改动才提交并记一条 journal；无改动零输出。"
             "包装器是本项目最早手工安装的那份，install 不重写它（见 .hermes.md 第 4 节）",
    ),
    Job(
        slug="drift",
        name="HermesUsage 漂移哨兵",
        schedule="0 9 * * *",
        script="scripts/drift_watch.py",
        args=("--quiet",),
        shim="hu-drift.py",
        note="每天 09:00：上游发了比基线更新的 release 就开 issue；"
             "基线写在 sources/registry.yaml 的 # baseline-release:，没有新 release 时零输出（不打扰）",
    ),
    Job(
        slug="links",
        name="HermesUsage 外链存活检测",
        schedule="0 9 * * 1",
        script="scripts/check_links_external.py",
        args=("--quiet",),
        shim="hu-links.py",
        note="每周一 09:00：95 条官方外链全查一遍；全部可达时零输出",
    ),
)


# --------------------------------------------------------------------- 纯函数（可测）

def hermes_home() -> Path:
    """$HERMES_HOME 优先；没设就按平台默认（Windows 是 %LOCALAPPDATA%\\hermes）。"""
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "hermes"
    return Path.home() / ".hermes"


def shim_text(job: Job, repo: Path = REPO) -> str:
    """生成包装器源码。repo 用原始字符串写死，避免 Windows 反斜杠被当转义。"""
    return SHIM_TEMPLATE.format(
        shim=job.shim, script=job.script, repo=repo, args=repr(tuple(job.args))
    )


def load_registered(home: Path) -> list[dict]:
    """读 cron 的任务存储（**只读**）。文件缺失或坏掉都返回空列表，不抛异常。"""
    store = home / "cron" / "jobs.json"
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    return [j for j in jobs if isinstance(j, dict)]


def repo_jobs(registered: list[dict], prefix: str = NAME_PREFIX) -> list[dict]:
    """只认领名字以 prefix 开头的任务 —— 别人的任务一律不碰。"""
    return [j for j in registered if str(j.get("name", "")).startswith(prefix)]


def plan_state_change(registered: list[dict], want_enabled: bool,
                      prefix: str = NAME_PREFIX) -> list[tuple[str, str, str]]:
    """返回 [(job_id, 'resume'|'pause', name)]；已经是目标状态的**不重复下发**。"""
    out: list[tuple[str, str, str]] = []
    for job in repo_jobs(registered, prefix):
        if bool(job.get("enabled")) != want_enabled:
            verb = "resume" if want_enabled else "pause"
            out.append((str(job.get("id")), verb, str(job.get("name", ""))))
    return out


def gateway_running(status_text: str) -> bool | None:
    """从 `hermes cron status` 的输出里判读调度器是否活着。判不出来返回 None。"""
    if "cron jobs will fire automatically" in status_text:
        return True
    if "cron jobs will NOT fire" in status_text:
        return False
    return None


def parse_status_line(job: dict) -> str:
    """把一条任务渲染成人看的一行（纯函数，方便测试）。"""
    state = "active" if job.get("enabled") else "paused"
    sched = (job.get("schedule") or {}).get("display") or (job.get("schedule") or {}).get("expr") or "?"
    return (f"  {job.get('id')}  {state:6s}  {job.get('name'):26s} [{sched}]"
            f"  下次 {job.get('next_run_at') or '—'}  上次 {job.get('last_status') or '—'}")


# --------------------------------------------------------------------- 执行层

def run_hermes(args: list[str], dry_run: bool = False) -> tuple[int, str]:
    """调 hermes CLI。dry_run 下只打印命令、不执行。"""
    cmd = ["hermes", *args]
    if dry_run:
        print("  [dry-run] " + " ".join(cmd))
        return 0, ""
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return res.returncode, ((res.stdout or "") + (res.stderr or "")).strip()


def cmd_status(home: Path) -> int:
    _code, out = run_hermes(["cron", "status"])
    if out:
        print(out)
    verdict = gateway_running(out)
    if verdict is False:
        print("  ⚠ 调度器没在跑 —— 跑 `hermes gateway install` 装登录自启（见 .hermes.md 第 4 节）")

    mine = repo_jobs(load_registered(home))
    if not mine:
        print("本仓库还没有登记任何定时任务：跑 `python scripts/cron_ctl.py install`")
        return 0
    print(f"本仓库的任务（{len(mine)} 个）：")
    for job in mine:
        print(parse_status_line(job))
    print("  提示：`hermes cron list` 默认不显示已暂停的任务（要看全得加 --all），"
          "本命令直接读存储，所以暂停的也在这儿。")
    return 0


def cmd_set(enabled: bool, home: Path, dry_run: bool = False) -> int:
    plan = plan_state_change(load_registered(home), enabled)
    verb_cn = "恢复" if enabled else "暂停"
    if not plan:
        print(f"没有需要{verb_cn}的任务（本仓库的任务都已是目标状态，或还没登记）")
        return 0
    failed = 0
    for job_id, verb, name in plan:
        code, out = run_hermes(["cron", verb, job_id], dry_run=dry_run)
        flag = "✓" if code == 0 else "✗"
        print(f"  {flag} {verb_cn}：{name} ({job_id})" + (f"  {out[:120]}" if out else ""))
        failed += code != 0
    return 1 if failed else 0


def cmd_run(home: Path, dry_run: bool = False) -> int:
    mine = repo_jobs(load_registered(home))
    if not mine:
        print("没有可跑的任务（还没登记，先跑 install）")
        return 0
    for job in mine:
        code, out = run_hermes(["cron", "run", str(job.get("id"))], dry_run=dry_run)
        flag = "✓" if code == 0 else "✗"
        print(f"  {flag} 已排入下一次 tick：{job.get('name')} ({job.get('id')})"
              + (f"  {out[:120]}" if out else ""))
    print("  提示：真正执行发生在调度器的下一次 tick（≤60 秒一轮）")
    return 0


def cmd_install(home: Path, dry_run: bool = False) -> int:
    scripts_dir = home / "scripts"
    registered = load_registered(home)
    existing = {str(j.get("name", "")) for j in registered}
    created = skipped = 0

    for job in JOBS:
        if job.name in existing:
            print(f"✓ 已登记，跳过：{job.name}")
            skipped += 1
            continue

        if job.generate_shim:
            target = scripts_dir / job.shim
            text = shim_text(job)
            if target.exists():
                if target.read_text(encoding="utf-8") == text:
                    print(f"✓ 包装器已是最新：{target}")
                else:
                    print(f"! 包装器已存在但内容不同，**未覆盖**：{target}")
                    print("  （想让它跟着仓库走，先手工比对这两份文件再决定删哪份）")
            else:
                print(f"  + 写包装器：{target}")
                if not dry_run:
                    scripts_dir.mkdir(parents=True, exist_ok=True)
                    target.write_text(text, encoding="utf-8", newline="\n")

        args = ["cron", "create", job.schedule, "--name", job.name,
                "--script", job.shim, "--no-agent", "--deliver", "local",
                "--workdir", str(REPO)]
        code, out = run_hermes(args, dry_run=dry_run)
        if code == 0:
            print(f"  ✓ 已登记：{job.name}（{job.schedule}）— {job.note}")
            created += 1
        else:
            print(f"  ✗ 登记失败：{job.name}\n    {out[:400]}")
            return 1

    print(f"\n完成：新登记 {created} 个，跳过已存在 {skipped} 个。")
    if dry_run:
        print("（--dry-run：以上都只是打印，没有真的调用 hermes、也没有写文件）")
    else:
        print("用 `python scripts/cron_ctl.py status` 复核。")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="HermesUsage 定时任务总开关（任务定义在 scripts/cron_ctl.py 的 JOBS 表里）",
    )
    ap.add_argument("--home", default=None,
                    help="覆盖 $HERMES_HOME（多 profile / 测试用）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印将要执行的 hermes 命令，不调用也不写文件")
    sub = ap.add_subparsers(dest="verb", required=True)
    for verb in ("status", "on", "off", "run", "install"):
        sp = sub.add_parser(verb, help=argparse.SUPPRESS)
        # 同一个开关在「动词前」「动词后」两种写法都要能用
        # （default=SUPPRESS：动词后没写时不要覆盖顶层已解析出的值）
        sp.add_argument("--home", default=argparse.SUPPRESS,
                        help="覆盖 $HERMES_HOME（多 profile / 测试用）")
        sp.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                        help="只打印将要执行的 hermes 命令，不调用也不写文件")

    args = ap.parse_args(argv)
    home = Path(args.home) if args.home else hermes_home()

    if args.verb == "status":
        return cmd_status(home)
    if args.verb == "on":
        return cmd_set(True, home, args.dry_run)
    if args.verb == "off":
        return cmd_set(False, home, args.dry_run)
    if args.verb == "run":
        return cmd_run(home, args.dry_run)
    if args.verb == "install":
        return cmd_install(home, args.dry_run)

    print(f"未知动词：{args.verb}（可用：status / on / off / run / install）", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
