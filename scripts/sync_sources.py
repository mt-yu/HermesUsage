#!/usr/bin/env python3
"""sources/sync_sources.py —— 把官方文档快照成本仓库可考证的“出处”。

为什么这样做
------------
教程里写“Hermes 的 X 是这样”的时候，必须能回答三个问题：
  1. 这句话出自官方文档的哪一页？        -> citations.yaml 里的 url
  2. 我读到的是哪个版本？                -> source_commit + hermes_version
  3. 现在还是这样吗？                    -> sha256 + `--check` 漂移检测

官方文档的源码就在本机 Hermes 安装目录里（website/docs/），所以这里是
“抄一份 + 记哈希 + 记版本”，而不是网络抓取——离线可复现、可 diff。

用法
----
  python scripts/sync_sources.py              # 刷新 sources/cache/ 与 citations.yaml
  python scripts/sync_sources.py --check      # 只校验：官方文档是否已漂移
  python scripts/sync_sources.py --list-missing   # 看看登记表里有没有写错的路径

环境变量
--------
  HERMES_AGENT_HOME   Hermes 源码目录（默认自动探测常见位置）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：python -m pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "sources" / "registry.yaml"
CACHE = REPO / "sources" / "cache"
CITATIONS = REPO / "sources" / "citations.yaml"

URL_BASE = "https://hermes-agent.nousresearch.com/docs"
SOURCE_REPO = "https://github.com/NousResearch/hermes-agent"
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


# --------------------------------------------------------------------------- 定位

def find_agent_home() -> Path:
    """找到 Hermes 源码目录（里面有 website/docs/）。"""
    env = os.environ.get("HERMES_AGENT_HOME")
    candidates = [Path(env)] if env else []
    candidates += [
        HERMES_HOME / "hermes-agent",
        Path.cwd() / "hermes-agent",
        Path.home() / "hermes-agent",
    ]
    for c in candidates:
        if c and (c / "website" / "docs").is_dir():
            return c
    sys.exit(
        "找不到 Hermes 源码目录（需要其中的 website/docs/）。\n"
        "官方安装脚本装完后通常在这里：\n"
        f"  {HERMES_HOME / 'hermes-agent'}\n"
        "也可以用环境变量指定：HERMES_AGENT_HOME=/path/to/hermes-agent"
    )


def git_commit(repo: Path) -> tuple[str, str]:
    """返回 (commit, 日期)；不是 git 仓库时返回占位值。"""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=15
        ).stdout.strip()
        when = subprocess.run(
            ["git", "log", "-1", "--format=%cs"], cwd=repo, capture_output=True, text=True, timeout=15
        ).stdout.strip()
        return (sha or "unknown", when or "unknown")
    except Exception:
        return ("unknown", "unknown")


def hermes_version() -> str:
    try:
        out = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=30).stdout
        m = re.search(r"v([\d.]+)", out)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- 解析

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def doc_title(text: str, fallback: str) -> str:
    """优先 frontmatter 的 title:，其次第一个 # 标题。"""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        t = re.search(r"^title:\s*(.+?)\s*$", m.group(1), re.M)
        if t:
            return t.group(1).strip().strip('"').strip("'")
    h = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    return h.group(1).strip() if h else fallback


def public_url(rel_path: str) -> str:
    p = rel_path
    for suffix in (".mdx", ".md"):
        if p.endswith(suffix):
            p = p[: -len(suffix)]
            break
    if p.endswith("/index"):
        p = p[: -len("/index")]
    return f"{URL_BASE}/{p}"


def load_registry() -> dict[str, str]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    flat: dict[str, str] = {}
    for group, entries in data.items():
        if not isinstance(entries, dict):
            continue
        for sid, rel in entries.items():
            if sid in flat:
                sys.exit(f"registry.yaml 里 id 重复：{sid}")
            flat[sid] = rel
    return flat


# --------------------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="把官方文档同步成本仓库的可考证出处")
    ap.add_argument("--check", action="store_true", help="只校验漂移，不写文件")
    ap.add_argument("--list-missing", action="store_true", help="只报告登记表里不存在或写错的文档路径")
    args = ap.parse_args()

    registry = load_registry()
    agent_home = find_agent_home()
    docs_root = agent_home / "website" / "docs"
    commit, commit_date = git_commit(agent_home)
    version = hermes_version()

    print(f"docs 源码 : {docs_root}")
    print(f"commit    : {commit[:12]}  ({commit_date})")
    print(f"hermes    : v{version}")
    print(f"登记来源  : {len(registry)} 条")

    known: dict[str, dict] = {}
    if CITATIONS.exists():
        for entry in yaml.safe_load(CITATIONS.read_text(encoding="utf-8")) or []:
            known[entry["id"]] = entry

    CACHE.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    missing: list[str] = []
    drifted: list[str] = []
    added: list[str] = []

    for sid in sorted(registry):
        rel = registry[sid]
        src = docs_root / rel
        if not src.is_file():
            missing.append(f"{sid} -> {rel}")
            continue
        raw = src.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        digest = sha256_bytes(raw)
        old = known.get(sid)

        if old is None:
            added.append(sid)
        elif old.get("sha256") != digest:
            drifted.append(sid)

        if not args.check and not args.list_missing:
            (CACHE / f"{sid}.md").write_bytes(raw)

        entries.append(
            {
                "id": sid,
                "title": doc_title(text, sid),
                "url": public_url(rel),
                "source_path": f"website/docs/{rel}",
                "source_repo": SOURCE_REPO,
                "source_commit": commit,
                "source_date": commit_date,
                "hermes_version": version,
                "sha256": digest,
                "bytes": len(raw),
                "retrieved_at": date.today().isoformat(),
                "local": f"sources/cache/{sid}.md",
            }
        )

    if args.list_missing:
        if missing:
            print("\n[!] 登记表里有 %d 条找不到对应文档：" % len(missing))
            for m in missing:
                print("    " + m)
        else:
            print("\n[ok] 登记表里所有文档路径都存在。")
        return 1 if missing else 0

    if args.check:
        print(f"\n漂移检查：{'发现 ' + str(len(drifted)) + ' 处变化' if drifted else '无变化'}")
        for d in drifted:
            old, new = known[d]["sha256"][:12], next(e["sha256"][:12] for e in entries if e["id"] == d)
            print(f"    ~ {d}  {old} -> {new}")
        if added:
            print(f"    新增未登记快照 {len(added)} 条：{', '.join(added)}")
        if missing:
            print(f"    路径失效 {len(missing)} 条：{', '.join(missing)}")
        return 1 if (drifted or added or missing) else 0

    header = (
        "# 自动生成，请勿手改 —— 由 scripts/sync_sources.py 从官方文档源码生成\n"
        f"# 生成时间: {date.today().isoformat()}   hermes v{version}\n"
        f"# 文档源码: {SOURCE_REPO} @ {commit} ({commit_date})\n"
        "# 校验：python scripts/sync_sources.py --check\n\n"
    )
    CITATIONS.write_text(
        header + yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8",
    )

    print(f"\n写入 {CITATIONS.relative_to(REPO)}（{len(entries)} 条）")
    print(f"写入 sources/cache/（{len(entries)} 个快照）")
    if added:
        print(f"新增 {len(added)} 条：{', '.join(added)}")
    if drifted:
        print(f"更新 {len(drifted)} 条快照内容：{', '.join(drifted)}")
    if missing:
        print(f"[!] {len(missing)} 条路径失效：{', '.join(missing)}")
    print("\n下一步：python scripts/verify.py")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
