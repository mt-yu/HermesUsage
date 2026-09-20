#!/usr/bin/env python3
"""scripts/release_probe.py —— 「我们的快照还等于**最新 release** 的文档吗？」一条命令回答。

为什么存在
----------
`sync_sources.py --check` 比的是「手上那个 docs 目录（本机安装树 / 上游 main）」，而课程的判据是
**读者装得到的那个 release**。本机安装树跟踪 main 时，这两种比法永远报漂移 —— 2026-09-20 实测
86 页，逐页定版后**没有一条**是「课程写错了」（见 ROADMAP「官方文档漂移复核（2026-09-20 第二次）」）。

所以哨兵要问的问题被改成一句：**上游有没有发比基线更新的 release？**

  * 没有 → 课程基线仍然有效，安静（退出码 0）
  * 有   → 该复核了（退出码 1）：新 release 里的行为，可能让某些课程表述过时

`--docs` 是复核时配套的第二问：快照各页与那个 release 的文档差多少（知道该重读哪些页）。

用法
----
  python scripts/release_probe.py                    # 哨兵模式：上游有没有发比基线更新的 release
  python scripts/release_probe.py --watch            # 同上（显式）
  python scripts/release_probe.py --docs             # 复核模式：逐页比「快照 vs 最新 release 的文档」
  python scripts/release_probe.py --docs --tag v2026.9.14
  python scripts/release_probe.py --json             # 机器可读
  python scripts/release_probe.py --quiet            # 无异常时零输出（cron 的 --no-agent 模式用）
  python scripts/release_probe.py --list             # 只解析 tag 与页数，不抓正文

**两种模式问的是两个不同的问题，别混**：

| 模式 | 问题 | 什么时候用 |
|---|---|---|
| `--watch`（默认） | 上游是不是发了比**基线**更新的 release？ | 哨兵：每天一次，有新 release 才响 |
| `--docs` | 快照各页与**最新 release 的文档**差多少？ | 复核：知道该重读哪些页 |

基线的 release 名写在 `sources/registry.yaml` 顶部（`# baseline-release: v2026.9.14`），
复核完（或决定不动课程）时一起更新它。

⚠️ **别指望「快照 == 最新 release 的文档」**：本仓库的快照取自主机安装树（跟踪 main），
实测它就比 `v2026.9.14` 的文档新 —— 95 页里有 48 页不同（都是快照那边多出来的正文）。
所以哨兵的判据是「有没有新 release」，不是「哈希是否相等」。

实现
----
`--docs` 逐页从
`raw.githubusercontent.com/NousResearch/hermes-agent/<tag>/website/docs/<rel>` 取原文，
按 LF 归一化后算 sha256，与 `sources/citations.yaml` 里记的 sha256 比。
（本仓库的 `sources/cache/<id>.md` 就是当初那份原文，`sync_sources.py --check` 自带这条对账。）

退出码
------
  0   没问题（没有新 release / 逐页都一致）
  1   需要行动（有新 release / 有页面漂移）—— 该按 ROADMAP 的复核流程走一遍
  2   检查本身跑不起来（解析不出 tag、网络全挂）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：python -m pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "sources" / "registry.yaml"
CITATIONS = REPO / "sources" / "citations.yaml"

OWNER_REPO = "NousResearch/hermes-agent"
LS_REMOTE = f"https://github.com/{OWNER_REPO}.git"
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER_REPO}"
API_REPO = f"https://api.github.com/repos/{OWNER_REPO}"
UA = "HermesUsage-release-probe/1.0 (+https://github.com/mt-yu/HermesUsage)"

CACHE_ROOT = Path(os.environ.get("HERMESUSAGE_RELEASE_PROBE_CACHE")
                  or Path(tempfile.gettempdir()) / "hermes-release-probe")


# --------------------------------------------------------------------------- 纯函数

def parse_ls_remote(text: str) -> list[str]:
    """`git ls-remote --tags` 的输出 → tag 名列表（去掉 `^{}` 解引用行与别的 ref）。

    行形如 `<sha>\\trefs/tags/v2026.9.14` 或 `<sha>\\trefs/tags/v2026.9.14^{}`。
    只看 `refs/tags/v*`；不出现在 ls-remote 里的东西一律不算。
    """
    tags: list[str] = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if not ref.startswith("refs/tags/v"):
            continue
        if ref.endswith("^{}"):          # annotated tag 的解引用行，同名去重
            continue
        tags.append(ref[len("refs/tags/"):])
    return sorted(set(tags))


def version_key(tag: str) -> tuple[int, ...]:
    """`v2026.9.14` → (2026, 9, 14)；非数字段按 0 处理，长度不足补 0。

    上游的 tag 是日期型（`v2026.9.14`），按数字元组比大小即可，别用字符串比
    （字符串比会把 v2026.10.1 排在 v2026.9.14 前面，实测过这种排序坑）。
    """
    nums = [int(n) for n in re.findall(r"\d+", tag or "")]
    return tuple(nums) if nums else (0,)


def pick_latest(tags: list[str]) -> str | None:
    return max(tags, key=version_key) if tags else None


def lf_bytes(data: bytes) -> bytes:
    """快照与哈希一律按 LF 归一化（与 sync_sources.py 同口径）。"""
    return data.replace(b"\r\n", b"\n")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify(fetched: dict[str, bytes | None], expected: dict[str, str]) -> dict:
    """逐页比对：fetched[id] 是原文（None = 官方 404 / 路径失效）。

    返回 {'same': [...], 'drifted': [...], 'missing': [...]}，全部按 id 排序。
    纯函数：不碰网络，测试直接喂字节。
    """
    same, drifted, missing = [], [], []
    for sid in sorted(expected):
        data = fetched.get(sid)
        if data is None:
            missing.append(sid)
        elif sha256(lf_bytes(data)) == expected[sid]:
            same.append(sid)
        else:
            drifted.append(sid)
    return {"same": same, "drifted": drifted, "missing": missing}


def has_drift(result: dict) -> bool:
    return bool(result.get("drifted") or result.get("missing"))


def summary_line(result: dict) -> str:
    d, m, s = result.get("drifted", []), result.get("missing", []), result.get("same", [])
    return (f"快照 vs {result.get('tag')}：一致 {len(s)} 页 / 内容变化 {len(d)} 页 / "
            f"路径失效 {len(m)} 页")


def load_registry() -> dict[str, str]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    flat: dict[str, str] = {}
    for entries in (data or {}).values():
        if isinstance(entries, dict):
            for sid, rel in entries.items():
                if sid in flat:
                    sys.exit(f"registry.yaml 里 id 重复：{sid}")
                flat[sid] = rel
    return flat


def load_expected() -> dict[str, str]:
    """citations.yaml → {id: sha256}（快照当初记下的哈希）。"""
    rows = yaml.safe_load(CITATIONS.read_text(encoding="utf-8")) or []
    return {r["id"]: r["sha256"] for r in rows if r.get("id") and r.get("sha256")}


BASELINE_RE = re.compile(r"^#\s*baseline-release:\s*(\S+)\s*$", re.M)


def baseline_release(text: str | None = None) -> str | None:
    """快照基准的 release tag —— 写在 `sources/registry.yaml` 顶部的那行注释里。

    为什么放在 registry.yaml：它是**人工维护**的那层（citations.yaml 是脚本生成的，
    手写会被覆盖），而「基线是哪个 release」正是人工决定、需要跟着复核一起更新的东西。
    """
    if text is None:
        text = REGISTRY.read_text(encoding="utf-8")
    m = BASELINE_RE.search(text)
    return m.group(1) if m else None


def watch(baseline: str | None = None, timeout: float = 60.0) -> dict:
    """哨兵模式：上游有没有发比基线更新的 release？

    只做一次 `git ls-remote --tags`（或一次 API 调用），不抓任何文档 —— 便宜到可以每天跑。
    """
    latest = latest_release_tag(timeout=timeout)
    if not latest:
        raise RuntimeError("解析不出上游最新的 release tag（git ls-remote 与 GitHub API 都不通）")
    base = baseline if baseline is not None else baseline_release()
    if not base:
        # 没写基线 = 判不了，按「需要行动」报出去（宁可按一次也不要静默哑火）
        return {"baseline": None, "latest": latest, "has_new_release": True,
                "note": "registry.yaml 顶部没有 `# baseline-release:` 行，无法判断是否有新 release"}
    return {
        "baseline": base,
        "latest": latest,
        "has_new_release": version_key(latest) > version_key(base),
        "note": "",
    }


def render_watch(result: dict, quiet: bool = False) -> str:
    if not result.get("has_new_release"):
        if quiet:
            return ""
        return (f"release 哨兵：上游最新 release 仍是 {result['latest']}（基线 {result['baseline']}），"
                "无需复核。")
    if quiet:
        # 有新 release 时必须出声（cron 的空输出 = 不投递）
        pass
    lines = [f"release 哨兵：**上游有新的 release** —— 最新 `{result['latest']}`，"
             f"本仓库基线 `{result['baseline'] or '（未写）'}`。"]
    if result.get("note"):
        lines.append(result["note"])
    lines += [
        "",
        "复核步骤（详见 ROADMAP「官方文档漂移复核」）：",
        f"1. `python scripts/release_probe.py --docs --tag {result['latest']}` —— 看哪些页变了",
        "2. 逐条定版：那个行为在**这个 release** 的源码/文档里有没有（`curl -s "
        f"https://raw.githubusercontent.com/{OWNER_REPO}/{result['latest']}/<path> | grep <符号>`）",
        "3. 有 → 改课程 + 更新 `updated`；没有 → 在 ROADMAP 里登记等下一个 release",
        f"4. `sources/registry.yaml` 顶部的 `# baseline-release:` 改成 {result['latest']}，跑 `python scripts/check.py`",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- 网络

def _opener() -> urllib.request.OpenerDirector:
    # 本机默认代理 127.0.0.1:7897 常挂，直连才稳（与 drift_watch/release.py 同口径）
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _git_ls_remote(timeout: float) -> str:
    """`git ls-remote --tags`，**显式绕开本机那个常挂的代理**（git 配置里 http.proxy=127.0.0.1:7897）。

    不绕的话：代理端口开着但不响应 → 每天定时任务随机报「跑不起来」。
    """
    p = subprocess.run(
        ["git", "-c", "http.proxy=", "-c", "https.proxy=", "ls-remote", "--tags", LS_REMOTE],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
    )
    return p.stdout or ""


def latest_release_tag(timeout: float = 60.0, retries: int = 2) -> str | None:
    """最新 release tag：优先 `git ls-remote --tags`（不依赖令牌、不依赖本机有 tag），
    失败再退到 GitHub API /releases/latest。两条路都带重试 —— 本机 TLS 会间歇性抽风。"""
    for attempt in range(retries + 1):
        try:
            tag = pick_latest(parse_ls_remote(_git_ls_remote(timeout)))
            if tag:
                return tag
        except Exception:
            pass
        if attempt < retries:
            time.sleep(2 * (attempt + 1))

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(API_REPO + "/releases/latest",
                                         headers={"Accept": "application/vnd.github+json", "User-Agent": UA})
            with _opener().open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            if data.get("tag_name"):
                return data["tag_name"]
        except Exception:
            pass
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    return None


def fetch_doc(rel: str, tag: str, timeout: float = 45.0, retries: int = 2) -> bytes | None:
    """取某一页在 tag 上的原文；404 → None；网络错误重试后仍失败 → 抛 RuntimeError。"""
    url = f"{RAW_BASE}/{tag}/website/docs/{rel}"
    last = ""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with _opener().open(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = f"HTTP {e.code}"
        except Exception as e:  # 本机 TLS 会间歇性抽风，重试是常态
            last = str(e)
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{rel}: {last}")


def probe(tag: str | None = None, ids: list[str] | None = None, retries: int = 2,
          timeout: float = 45.0, use_cache: bool = True, refresh: bool = False) -> dict:
    """抓最新（或指定）release 的文档逐页比哈希。返回结果字典（含 counts）。"""
    registry = load_registry()
    expected = load_expected()
    if tag is None:
        tag = latest_release_tag()
        if not tag:
            raise RuntimeError("解析不出最新 release tag（git ls-remote 与 GitHub API 都不通）")

    wanted = [i for i in (ids or sorted(registry)) if i in registry]
    cache_dir = CACHE_ROOT / tag
    fetched: dict[str, bytes | None] = {}
    errors: dict[str, str] = {}
    for sid in wanted:
        path = cache_dir / f"{sid}.md"
        if use_cache and not refresh and path.exists():
            fetched[sid] = path.read_bytes()
            continue
        try:
            data = fetch_doc(registry[sid], tag, timeout=timeout, retries=retries)
        except RuntimeError as e:
            errors[sid] = str(e)
            continue
        if data is not None:
            data = lf_bytes(data)
            if use_cache:
                cache_dir.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        fetched[sid] = data

    result = classify(fetched, {k: expected[k] for k in wanted if k in expected})
    result.update({
        "tag": tag,
        "registry_total": len(registry),
        "checked": len(wanted),
        "errors": errors,
    })
    return result


# --------------------------------------------------------------------------- 输出

def render_text(result: dict, quiet: bool = False) -> str:
    if not has_drift(result):
        if quiet:
            return ""
        return (f"release 探针：{summary_line(result)}\n"
                "课程基线仍然正确（快照 == 最新 release 的文档），无需复核。")
    lines = [f"release 探针：**有漂移** —— {summary_line(result)}", ""]
    if result.get("drifted"):
        lines.append(f"内容变化（{len(result['drifted'])} 页）：")
        lines += [f"  - {i}" for i in result["drifted"]]
    if result.get("missing"):
        lines.append(f"路径失效（{len(result['missing'])} 页，registry.yaml 里的路径要修）：")
        lines += [f"  - {i}" for i in result["missing"]]
    if result.get("errors"):
        lines.append(f"抓取失败（{len(result['errors'])} 页，不算漂移，重跑即可）：")
        lines += [f"  - {i}: {msg[:120]}" for i, msg in sorted(result["errors"].items())]
    lines += ["", "下一步：按 ROADMAP「官方文档漂移复核」的流程走一遍；"
                  "本机跟踪 main 时判据是 release tag，别拿本机源码当判据。"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="release 哨兵 / 快照 vs release 文档的逐页比对")
    ap.add_argument("--watch", action="store_true",
                    help="哨兵模式（默认）：上游有没有比基线更新的 release")
    ap.add_argument("--docs", action="store_true",
                    help="复核模式：逐页比「快照 vs 最新 release 的文档」")
    ap.add_argument("--tag", help="指定 release tag（默认取上游最新）")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    ap.add_argument("--quiet", action="store_true",
                    help="没问题时零输出（cron 的 --no-agent 模式用）；有问题照样出声")
    ap.add_argument("--list", action="store_true", help="只解析 tag 与页数，不抓正文")
    ap.add_argument("--refresh", action="store_true", help="忽略本地缓存，重新抓")
    ap.add_argument("--retries", type=int, default=2, help="每页重试次数（默认 2）")
    ap.add_argument("--timeout", type=float, default=45.0, help="单页超时秒数（默认 45）")
    args = ap.parse_args(argv)

    if args.list:
        tag = args.tag or latest_release_tag()
        if not tag:
            print("解析不出最新 release tag（git ls-remote 与 GitHub API 都不通）", file=sys.stderr)
            return 2
        print(f"上游最新 release：{tag}；本仓库基线：{baseline_release() or '（未写）'}；"
              f"registry 登记 {len(load_registry())} 页；citations 记了 {len(load_expected())} 个哈希")
        return 0

    if not args.docs:
        # 默认：哨兵模式（便宜，一次 ls-remote）
        try:
            result = watch(timeout=max(args.timeout, 60.0))
        except RuntimeError as e:
            print(f"release 哨兵跑不起来：{e}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            text = render_watch(result, quiet=args.quiet)
            if text:
                print(text)
        return 1 if result["has_new_release"] else 0

    try:
        result = probe(tag=args.tag, retries=args.retries, timeout=args.timeout,
                       refresh=args.refresh)
    except RuntimeError as e:
        print(f"release 探针跑不起来：{e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        text = render_text(result, quiet=args.quiet)
        if text:
            print(text)
    return 1 if has_drift(result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
