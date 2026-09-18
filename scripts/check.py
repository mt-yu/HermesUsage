#!/usr/bin/env python3
"""scripts/check.py —— 一条命令跑完所有检查。

顺序是有意的，从便宜到贵、从内容到产物：
  1. 内容门禁（verify.py 的 12 条规则）
  2. 索引同步（llms.txt 是否与课程集一致）
  3. Python 单元测试（解析层 / 渲染层 / 构建器）
  4. 前端单元测试（Node 内置测试器；没装 node 就跳过并提示）
  5. 站点构建自检（临时目录构建 + 站内链接全解析）
  6. 路线图 SVG 同步（docs/roadmap.svg 是否还与课程集合一致）

用法
----
  python scripts/check.py            # 全绿退出 0
  python scripts/check.py --skip-node
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(label: str, cmd: list[str]) -> bool:
    print(f"\n=== {label} ===")
    print("$ " + " ".join(cmd))
    rc = subprocess.run(cmd, cwd=REPO).returncode
    print(f"--- {label}: {'通过' if rc == 0 else f'失败（退出码 {rc}）'}")
    return rc == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="HermesUsage 全量检查")
    ap.add_argument("--skip-node", action="store_true")
    args = ap.parse_args()

    steps: list[tuple[str, list[str]]] = [
        ("内容门禁 verify.py", [PY, "scripts/verify.py", "--quiet"]),
        ("索引同步 build_index.py", [PY, "scripts/build_index.py", "--check"]),
        ("路线图 SVG 同步 build_roadmap_svg.py", [PY, "scripts/build_roadmap_svg.py", "--check"]),
        ("Python 单元测试", [PY, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-p", "test_*.py"]),
        ("站点构建自检 build_site.py --check", [PY, "scripts/build_site.py", "--check"]),
    ]
    if not args.skip_node:
        node = shutil.which("node")
        if node:
            steps.insert(3, ("前端单元测试 node --test", [node, "--test", "tests/js/*.test.js"]))
        else:
            print("[提示] 没找到 node，跳过前端单元测试（python scripts/check.py --skip-node 可显式跳过）")

    results = [(label, run(label, cmd)) for label, cmd in steps]

    print("\n=== 汇总 ===")
    for label, ok in results:
        print(f"  {'✓' if ok else '✗'} {label}")
    failed = [label for label, ok in results if not ok]
    if failed:
        print(f"\n未通过：{len(failed)} 项 —— {', '.join(failed)}")
        return 1
    print(f"\n全部通过：{len(results)} 项检查全绿。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
