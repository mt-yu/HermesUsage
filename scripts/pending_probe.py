#!/usr/bin/env python3
"""scripts/pending_probe.py —— ROADMAP 里那 19 条「上游已写、release 里还没有」的可执行清单。

为什么存在
----------
2026-09-20/21 的两次复核（过时 + 超前）在人肉 grep 里攒下 19 条待办：这些行为上游的 main
已经有了，但**读者装到的最新 release 里还没有**，所以课程里要么不能讲、要么已经删掉。

人肉记着的清单会腐烂。这里把它变成一条命令：**上游一发新 release，跑一次就知道哪几条落地了**，
落地的那几条正好就是「该改课 / 该恢复内容」的清单。

  python scripts/pending_probe.py                 # 与上游最新 release 比
  python scripts/pending_probe.py --tag v2026.10.1
  python scripts/pending_probe.py --item 15        # 只看一条
  python scripts/pending_probe.py --json
  python scripts/pending_probe.py --quiet          # 全部仍未发布时零输出（cron 用）

三种探针（每条的探针写在下面的 ITEMS 表里，**改清单就改这张表**）：
  * `code`  —— 某个源文件里有没有这个符号（`path` + `needles`）
  * `doc`   —— 官方文档某一页里有没有这句话（`doc_id`，路径从 registry.yaml 取）
  * `file`  —— 某个文件在 tag 上是否存在（新模块）

退出码
------
  0   19 条全部仍未发布（课程基线不用动）
  1   有若干条已经进了这个 release —— 该按 ROADMAP 恢复/改课
  2   探针本身跑不起来（解析不出 tag、网络全挂）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import release_probe as RP  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：python -m pip install pyyaml")


def _item(n, kind, path, needles, claim, roadmap_token, doc_id=None, course=""):
    return {"n": n, "kind": kind, "path": path, "needles": tuple(needles),
            "claim": claim, "roadmap_token": roadmap_token, "doc_id": doc_id, "course": course}


# --------------------------------------------------------------------------- 数据表
# 1-14 来自「官方文档漂移复核（2026-09-20 第二次）」，15-19 来自「审计：课程有没有引用
# release 里还没有的行为（2026-09-21）」。改动这张表时，ROADMAP 里的对应行也要一起改
# （tests/test_pending_probe.py 会核对 roadmap_token 还在 ROADMAP.md 里）。
ITEMS: tuple[dict, ...] = (
    _item(1, "code", "hermes_cli/auth.py", ["111724"],
          "命名 profile 只认自己的 auth.json，不再回落读根库", "111724"),
    _item(2, "code", "hermes_cli/config_defaults.py", ['"multiplex_profiles": True'],
          "multiplex 网关默认开启", "multiplex_profiles"),
    _item(3, "doc", "", ["Copy API keys from the main profile"],
          "新建 Bot 默认复制主 profile 的静态 API key", "复制主 profile 的静态 API key",
          doc_id="bot-mode"),
    _item(4, "code", "hermes_cli/config_defaults.py", ['"threshold_tokens": 256_000'],
          "压缩触发有 256k 绝对上限", "256000"),
    _item(5, "code", "cron/scheduler.py", ["DEFAULT_FAILURE_REPEAT_ALERT_HOURS"],
          "同一错误签名不再每次 ping（默认 6h 冷却）", "DEFAULT_FAILURE_REPEAT_ALERT_HOURS"),
    _item(6, "doc", "", ["historical late or catch-up"],
          "cron doctor 把历史迟到也算 finding", "历史迟到", doc_id="cron"),
    _item(7, "doc", "", ["the pending worker was abandoned"],
          "失速子代理被中断并放弃等待", "放弃等待", doc_id="delegation"),
    _item(8, "doc", "", ["Stopped children return a structured result"],
          "/stop 之后被停子代理带着最后产出回来", "最后一段产出",
          doc_id="delegation"),
    _item(9, "code", "hermes_cli/config_defaults.py", ["oneshot_max_children"],
          "一次性运行的子代理总数上限（默认 2）", "oneshot_max_children"),
    _item(10, "code", "agent/prompt_builder.py", ["user_authored"],
          "自己写的 SOUL.md 命中注入只警告、仍加载", "user_authored"),
    _item(11, "code", "tools/checkpoint_manager.py", ["unsupported_backend_reason"],
          "容器终端后端不拍检查点", "unsupported_backend_reason"),
    _item(12, "doc", "", ["quit the browser before launching a"],
          "真 profile 会话前要退出浏览器（跨平台结论）", "跨平台结论",
          doc_id="browser"),
    _item(13, "code", "hermes_cli/config_env_routing.py", ["is_env_setting_key"],
          "任何 UPPER_SNAKE 名字只进 .env", "UPPER_SNAKE"),
    _item(14, "doc", "", ["Looked in:"],
          "hermes send 的 not configured 会列出查过的文件", "not configured", doc_id="pipe-script-output"),
    _item(15, "code", "gateway/platforms/webhook_coalesce.py", ["coalesce"],
          "webhook 路由支持 coalesce 事件去抖", "coalesce", course="L31"),
    _item(16, "code", "agent/file_safety.py", ["read-denied"],
          "项目 .env 变成「读拒绝、但可写」", "可以写，但读不回来", course="L50"),
    _item(17, "code", "hermes_cli/approvals_suggest.py", ["redact_sensitive_text"],
          "挖审批历史时凭据被打码", "凭据会被打码", course="L50"),
    _item(18, "code", "agent/credential_pool.py", ["numbered"],
          "编号环境变量兄弟自动入池", "numbered", course="L51"),
    _item(19, "code", "agent/context_file_sources.py", ["Context files"],
          "/context 输出逐文件 Context files 清单", "Context files", course="L12,L14"),
)


# --------------------------------------------------------------------------- 纯函数

def evaluate(text: str | None, needles: tuple[str, ...]) -> bool:
    """tag 版内容里有没有这些符号（任一命中即算「已发布」；text=None 表示文件不存在）。"""
    if text is None:
        return False
    return any(n in text for n in needles)


def summarize(results: list[dict]) -> dict:
    landed = [r for r in results if r["landed"]]
    errored = [r for r in results if r.get("error")]
    return {
        "total": len(results),
        "landed": landed,
        "landed_count": len(landed),
        "still_missing_count": len(results) - len(landed) - len(errored),
        "errored_count": len(errored),
        "errored": errored,
    }


def render(results: list[dict], tag: str, quiet: bool = False) -> str:
    s = summarize(results)
    if not s["landed_count"] and not s["errored_count"]:
        if quiet:
            return ""
        return (f"待发布清单：{s['total']} 条**全部仍未进** {tag} —— 课程基线不用动"
                f"（{s['still_missing_count']}/{s['total']}）。")
    lines = []
    if s["landed_count"]:
        lines += [f"待发布清单：**有 {s['landed_count']} 条已经进了 {tag}** —— 该按 ROADMAP 恢复/改课：", ""]
        for r in s["landed"]:
            where = f"{r['course']} · " if r.get("course") else ""
            lines.append(f"  ✅ #{r['n']} {where}{r['claim']}")
            lines.append(f"       证据：{r['evidence']}")
    else:
        lines += [f"待发布清单：{tag} 里一条都没落地（仍有 {s['errored_count']} 条没核成）。", ""]
    if s["still_missing_count"]:
        names = "、".join(f"#{r['n']}" for r in results if not r["landed"] and not r.get("error"))
        lines += ["", f"  仍未进这个 tag（继续等）：{names}"]
    if s["errored_count"]:
        names = "、".join(f"#{r['n']}" for r in s["errored"])
        lines += ["", f"  ⚠ 没核成（网络抖动，重跑即可）：{names}"]
    lines += ["", "下一步：改完课程后把 `sources/registry.yaml` 的 `# baseline-release:` 换成 "
                  f"`{tag}`，并跑 `python scripts/check.py`。"]
    return "\n".join(lines)


def load_doc_paths() -> dict[str, str]:
    """registry.yaml 的 id → website/docs 下的相对路径（doc 类探针靠它）。"""
    data = yaml.safe_load((REPO / "sources" / "registry.yaml").read_text(encoding="utf-8")) or {}
    flat: dict[str, str] = {}
    for entries in data.values():
        if isinstance(entries, dict):
            flat.update(entries)
    return flat


# --------------------------------------------------------------------------- 探针

def probe_items(tag: str, only: int | None = None, retries: int = 2,
                timeout: float = 45.0) -> list[dict]:
    """逐条探。**单条抓取失败不中止整轮** —— 网络抖一下不该让 19 条全废（记为 error 继续）。"""
    docs = load_doc_paths()
    out: list[dict] = []
    for item in ITEMS:
        if only is not None and item["n"] != only:
            continue
        path = item["path"]
        if item["kind"] == "doc":
            rel = docs.get(item.get("doc_id") or "")
            if not rel:
                raise RuntimeError(f"#{item['n']} 的 doc_id {item.get('doc_id')!r} 不在 registry.yaml 里")
            target = f"website/docs/{rel}"
        else:
            target = path
        row = {**{k: item[k] for k in ("n", "kind", "claim", "roadmap_token", "course")},
               "target": target, "landed": False, "error": ""}
        try:
            raw = RP.fetch_path(target, tag, timeout=timeout, retries=retries)
        except RuntimeError as e:
            row["evidence"] = f"<没核成：{str(e)[:120]}>"
            row["error"] = str(e)[:200]
            out.append(row)
            continue
        text = raw.decode("utf-8", "replace") if raw is not None else None
        row["landed"] = evaluate(text, item["needles"])
        line = ""
        if row["landed"] and text:
            for i, l in enumerate(text.splitlines()):
                if any(n in l for n in item["needles"]):
                    line = f"{target}:{i+1} {l.strip()[:110]}"
                    break
        row["evidence"] = line or (f"{target} 在 {tag} 上不存在" if text is None else f"{target} 里 0 命中")
        out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ROADMAP 里那 19 条待发布项：进 release 了吗")
    ap.add_argument("--tag", help="指定 tag（默认上游最新 release）")
    ap.add_argument("--item", type=int, help="只查第 N 条")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    ap.add_argument("--quiet", action="store_true", help="全部仍未发布时零输出（cron 用）")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args(argv)

    tag = args.tag or RP.latest_release_tag()
    if not tag:
        print("解析不出上游最新 release tag（git ls-remote 与 GitHub API 都不通）", file=sys.stderr)
        return 2
    try:
        results = probe_items(tag, only=args.item, retries=args.retries, timeout=args.timeout)
    except RuntimeError as e:
        print(f"待发布清单跑不起来：{e}", file=sys.stderr)
        return 2

    s = summarize(results)
    if args.json:
        print(json.dumps({"tag": tag, **{k: v for k, v in s.items() if k != "landed"},
                          "landed": [r["n"] for r in s["landed"]],
                          "results": results}, ensure_ascii=False, indent=2))
    else:
        text = render(results, tag, quiet=args.quiet)
        if text:
            print(text)
    if s["landed_count"]:
        return 1
    if s["errored_count"] and s["still_missing_count"] == 0:
        return 2          # 一条都没核成：别把它当成「全都还没发布」
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
