#!/usr/bin/env python3
"""scripts/drift_watch.py —— 文档漂移哨兵：该复核了就开一个 GitHub issue。

为什么存在
----------
课程的判据是**读者装得到的那个 release**（见 ROADMAP「官方文档漂移复核（2026-09-20 第二次）」），
所以哨兵要问的不是「哈希一样吗」，而是**上游是不是发了比基线更新的 release**：

  release_probe.watch()  →  GitHub issue（标题前缀去重）

两种来源：
  * `--source release`（**默认**）：只做一次 `git ls-remote --tags`，比较
    `sources/registry.yaml` 顶部的 `# baseline-release:` 与上游最新 release。便宜、安静，
    **只有真的发新版才响** —— 这正是「该复核了」的那一刻。
  * `--source tree`（调试用）：老的比法 —— 跑 `sync_sources.py --check`，比手上那个 docs 目录
    （本机安装树 / 上游 main）与快照。本机跟踪 main 时它**永远**报漂移（实测 86 页里
    「课程写错了」的是 0 条），所以不再当默认。

怎么跑
------
  python scripts/drift_watch.py --dry-run     # 只打印会开什么 issue，绝不发请求
  python scripts/drift_watch.py               # 需要行动就开 issue（没问题则什么都不做）
  python scripts/drift_watch.py --json        # 机器可读结果

令牌
----
按顺序取：环境变量 GITHUB_TOKEN → 否则 `git credential fill`（Git Credential
Manager，scope 含 repo）。**令牌是敏感值：不打印、不写文件、不进提交。**
两处都拿不到时**不算失败**：本脚本把 issue 正文原样打到 stdout 并提示
"没找到令牌，已跳过开 issue"，人肉复制即可。

退出码
------
  0   无需行动（没有新 release / 没有漂移）
  1   需要行动（无论 issue 是新建、已存在被跳过、还是没令牌只打印）
  2   检查本身跑不起来（解析不出上游 tag / sync_sources.py 找不到官方文档源码目录等）

已知限制
--------
  * `--source tree` 只认 sync_sources.py --check 的那三种行（`~ id old -> new` /
    `新增未登记快照` / `路径失效`）。上游改输出格式时 parse_drift 会静默返回空 → 哨兵哑火，
    所以 tests/test_drift_watch.py 用真实输出样本钉住格式。
  * 去重只按标题前缀，同一批漂移反复出现（比如上游长期不修）不会重复开 issue，
    但也意味着**不会提醒你"这条还挂着"** —— superseded 的旧 issue 需要人工关。
  * 发请求用 Python + ProxyHandler({})：本机默认代理已挂（http://127.0.0.1:7897），
    curl 会 schannel handshake 失败。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYNC = REPO / "scripts" / "sync_sources.py"

# 同目录的 release_probe：哨兵默认走它（比「上游有没有新 release」）
sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_probe as RP  # noqa: E402

ISSUE_PREFIX = "官方文档漂移："
API = "https://api.github.com"
UA = "HermesUsage-drift-watch/1.0 (+https://github.com/mt-yu/HermesUsage)"

RE_DIFTED = re.compile(r"^\s*~\s+([A-Za-z0-9_.\-]+)")
RE_ADDED = re.compile(r"新增未登记快照\s*\d+\s*条[：:]\s*(.+?)\s*$")
RE_MISSING = re.compile(r"路径失效\s*\d+\s*条[：:]\s*(.+?)\s*$")


# --------------------------------------------------------------------------- 纯函数

def parse_drift(output: str) -> dict:
    """解析 sync_sources.py --check 的 stdout。

    三种行各对应一个列表；`漂移检查：无变化` 或空串 → 三个空列表。
    行首缩进/多余空白都容忍，因为那是上游 print 出来的格式，不是我们控制。
    """
    drifted: list[str] = []
    added: list[str] = []
    missing: list[str] = []

    for line in output.splitlines():
        m = RE_DIFTED.match(line)
        if m:
            drifted.append(m.group(1))
            continue
        m = RE_ADDED.search(line)
        if m:
            added += [s.strip() for s in re.split(r"[,\uFF0C]", m.group(1)) if s.strip()]
            continue
        m = RE_MISSING.search(line)
        if m:
            # 每项形如 `id -> user-guide/x.md`：只要箭头左边的 id
            for item in re.split(r"[,\uFF0C]", m.group(1)):
                item = item.strip()
                if not item:
                    continue
                missing.append(item.split("->")[0].strip())
            continue

    return {"drifted": drifted, "added": added, "missing": missing}


def has_drift(drift: dict) -> bool:
    return bool(drift.get("drifted") or drift.get("added") or drift.get("missing"))


def total_changes(drift: dict) -> int:
    return len(drift.get("drifted", [])) + len(drift.get("added", [])) + len(drift.get("missing", []))


def repo_from_remote(url: str) -> str | None:
    """https://github.com/owner/repo.git / git@github.com:owner/repo.git -> owner/repo"""
    url = (url or "").strip()
    m = re.search(r"github\.com[/:]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def issue_title(drift: dict) -> str:
    return (
        f"{ISSUE_PREFIX}{total_changes(drift)} 项待复核"
        f"（{len(drift['drifted'])} 处内容变化 / {len(drift['added'])} 条新增 / {len(drift['missing'])} 条路径失效）"
    )


def _ul(items: list[str]) -> str:
    return "\n".join(f"- `{i}`" for i in items) if items else "- 无"


def issue_body(drift: dict) -> str:
    """issue 正文：三组清单 + 处理步骤（照着做就能收敛，不用再想）。"""
    return f"""`python scripts/sync_sources.py --check` 检测到官方文档与本仓库快照不一致。

> 自动生成，由 `scripts/drift_watch.py` 创建。本 issue 只做提醒，处理完请手动关闭。

## 1. 内容漂移（快照哈希变了，正文可能已过时）— {len(drift['drifted'])} 条
{_ul(drift['drifted'])}

## 2. 新增未登记快照（官方多出来的页，考虑补进 registry）— {len(drift['added'])} 条
{_ul(drift['added'])}

## 3. 路径失效（官方把文件挪了/删了，sources/registry.yaml 里的路径要修）— {len(drift['missing'])} 条
{_ul(drift['missing'])}

## 处理步骤
1. `python scripts/sync_sources.py` —— 刷新 `sources/cache/` 与 `sources/citations.yaml`
2. 复核受影响课程：正文里引用了漂移页面结论的课要重读一遍（`git diff lessons/` 帮你看清改了哪些）
3. `python scripts/check.py` —— 内容门禁 + 单元测试 + 站点构建自检，全绿才算收敛

---
由 `scripts/drift_watch.py` 生成；标题前缀用于去重，改动时勿去掉 `{ISSUE_PREFIX}`。
"""


# --------------------------------------------------------------------------- 跑检查

def run_check(timeout: float = 180.0) -> tuple[int, str, str]:
    """跑 sync_sources.py --check。显式 PYTHONIOENCODING=utf-8：
    子进程 stdout 是管道，Windows 上默认 cp936 —— 不设就会把中文读成乱码。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    p = subprocess.run(
        [sys.executable, str(SYNC), "--check"],
        cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=timeout,
    )
    return p.returncode, p.stdout or "", p.stderr or ""


# --------------------------------------------------------------------------- 令牌

def token_from_env() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or None


def token_from_git_credential() -> str | None:
    """从 Git Credential Manager 取令牌。只在内存里流转，绝不打印。"""
    try:
        p = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            cwd=REPO, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except Exception:
        return None
    for line in (p.stdout or "").splitlines():
        if line.startswith("password="):
            value = line[len("password="):].strip()
            return value or None
    return None


def get_token() -> str | None:
    return token_from_env() or token_from_git_credential()


# --------------------------------------------------------------------------- GitHub API

def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _api(method: str, path: str, token: str, payload: dict | None = None, timeout: float = 30.0):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        API + path, method=method, data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": UA,
            "Content-Type": "application/json",
        },
    )
    op = _opener()
    try:
        with op.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        # 只带状态码与响应体片段；请求头里有令牌，绝不回显
        detail = e.read().decode("utf-8", "replace")[:300]
        e.close()
        raise RuntimeError(f"GitHub API {method} {path} 失败：HTTP {e.code} {detail}") from None


def find_existing_issue(repo: str, token: str, open_limit: int = 100, max_pages: int = 3) -> dict | None:
    """找标题以 ISSUE_PREFIX 开头的 open issue（用列表接口，不用 search —— 后者有索引延迟）。"""
    for page in range(1, max_pages + 1):
        _, issues = _api("GET", f"/repos/{repo}/issues?state=open&per_page={open_limit}&page={page}", token)
        if not issues:
            return None
        for it in issues:
            if "pull_request" in it:
                continue
            if str(it.get("title", "")).startswith(ISSUE_PREFIX):
                return it
        if len(issues) < open_limit:
            return None
    return None


def create_issue(repo: str, token: str, title: str, body: str) -> dict:
    _, created = _api("POST", f"/repos/{repo}/issues", token, {"title": title, "body": body})
    return created


# --------------------------------------------------------------------------- 来源一：最新 release

def release_watch(baseline: str | None = None) -> dict:
    """上游有没有比基线更新的 release —— 转手 release_probe.watch()（只一次 ls-remote）。"""
    return RP.watch(baseline=baseline)


def release_issue_title(result: dict) -> str:
    latest = result.get("latest") or "?"
    base = result.get("baseline") or "（未写基线）"
    return f"{ISSUE_PREFIX}上游发了新 release：{latest}（本仓库基线 {base}）"


def release_issue_body(result: dict) -> str:
    return f"""课程的判据是「读者装得到的那个 release」。本仓库基线是 `{result.get('baseline') or '（未写）'}`，
上游已经发了 `{result.get('latest')}` —— 该做一次官方文档漂移复核了。

> 自动生成，由 `scripts/drift_watch.py --source release` 创建。本 issue 只做提醒，处理完请手动关闭。

{RP.render_watch(result)}

---
由 `scripts/drift_watch.py` 生成；标题前缀用于去重，改动时勿去掉 `{ISSUE_PREFIX}`。
"""


# --------------------------------------------------------------------------- 主流程

def no_drift_message(quiet: bool) -> str:
    """无漂移时该说的话；--quiet 下返回空串。

    cron 的 --no-agent 模式靠「空输出」来保持安静，所以静默必须发生在**返回内容**上，
    而不是靠调用方记得别 print。
    """
    if quiet:
        return ""
    return "漂移哨兵：无需行动（没有新 release，快照基线仍然有效），不开 issue。"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="文档漂移哨兵：有新 release（或漂移）就开 GitHub issue")
    ap.add_argument("--source", choices=("release", "tree"), default="release",
                    help="release=只看上游有没有新 release（默认）；tree=比手上那个 docs 目录（调试用）")
    ap.add_argument("--dry-run", action="store_true", help="只打印会做什么与 issue 内容，绝不发请求")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    ap.add_argument("--quiet", action="store_true",
                    help="静默：无需行动时不输出任何内容（给 cron 的 --no-agent 模式用，空输出=不投递）")
    args = ap.parse_args(argv)

    if args.source == "release":
        try:
            watch_result = release_watch()
        except RuntimeError as e:
            print(f"release 哨兵跑不起来：{e}", file=sys.stderr)
            return 2
        needs_action = bool(watch_result.get("has_new_release"))
        title = release_issue_title(watch_result)
        body = release_issue_body(watch_result)
        no_action_msg = (f"漂移哨兵：无需行动 —— 上游最新 release 仍是 {watch_result.get('latest')}"
                         f"（本仓库基线 {watch_result.get('baseline') or '（未写）'}），不开 issue。")
        result = {"source": "release", "watch": watch_result, "title": title,
                  "has_drift": needs_action, "action": "none"}
    else:
        rc, out, err = run_check()
        if "漂移检查" not in out:
            msg = "漂移检查本身没跑起来（sync_sources.py --check 没有输出预期内容）"
            print(f"{msg}\n退出码 {rc}\nstderr:\n{err.strip()[:2000]}", file=sys.stderr)
            return 2
        drift = parse_drift(out)
        needs_action = has_drift(drift)
        title = issue_title(drift)
        body = issue_body(drift)
        no_action_msg = None
        result = {"source": "tree", "drift": drift, "title": title,
                  "has_drift": needs_action, "action": "none"}

    if not needs_action:
        result["action"] = "no-drift"
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            msg = "" if args.quiet else (no_action_msg or no_drift_message(False))
            if msg:
                print(msg)
        return 0

    if args.dry_run:
        # 保证：dry-run 分支在任何网络/令牌操作之前返回
        result["action"] = "dry-run"
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("[dry-run] 检测到漂移，本应开 issue（未发任何请求、未取令牌）：\n")
            print(f"标题：{title}\n")
            print("--- 正文 ---")
            print(body)
        return 1

    repo = repo_from_remote(_git_remote())
    result["repo"] = repo
    if not repo:
        print("拿不到 origin（git remote get-url origin），无法开 issue。", file=sys.stderr)
        print(body)
        result["action"] = "no-repo"
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    token = get_token()
    if not token:
        result["action"] = "no-token"
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("没找到令牌（GITHUB_TOKEN 与 git credential 都没有），已跳过开 issue。")
            print("把下面这段正文手动贴到 %s 的 issue 里即可：\n" % repo)
            print(f"标题：{title}\n")
            print(body)
        return 1

    try:
        existing = find_existing_issue(repo, token)
        if existing:
            result["action"] = "skipped-existing"
            result["issue"] = {"number": existing.get("number"), "url": existing.get("html_url")}
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"已存在同前缀 open issue #{existing.get('number')}，跳过（不重复刷屏）：{existing.get('html_url')}")
            return 1

        created = create_issue(repo, token, title, body)
        result["action"] = "created"
        result["issue"] = {"number": created.get("number"), "url": created.get("html_url")}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"已开 issue #{created.get('number')}：{created.get('html_url')}")
    except RuntimeError as e:
        result["action"] = "api-error"
        result["error"] = str(e)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"GitHub API 调用失败，漂移依然存在（退出码 1）：{e}", file=sys.stderr)
            print(f"\n标题：{title}\n")
            print(body)
    return 1


def _git_remote() -> str:
    try:
        p = subprocess.run(["git", "remote", "get-url", "origin"], cwd=REPO,
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return (p.stdout or "").strip()
    except Exception:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
