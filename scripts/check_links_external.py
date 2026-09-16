#!/usr/bin/env python3
"""scripts/check_links_external.py —— 官方文档外链存活检测（四分类）。

为什么存在
----------
sources/citations.yaml 里 91 条 URL 全部指向 hermes-agent.nousresearch.com。
scripts/sync_sources.py --check 比的是**本地快照的 sha256**，它只能回答
"我抄的那份文件有没有变"，回答不了"读者点进去还能不能打开"。
官方文档改版、页面改名、站点换域名时，本仓库的哈希可以毫无变化，
但线上 URL 已经 404 —— 教程里的"出处"就这么静默烂掉了。

这个脚本负责另一半：**外网可达性**。它把每条 URL 的实际 HTTP 结果分成四类：

  ok       2xx / 3xx                      链接活着
  blocked  403 / 429                      可能是 Cloudflare 之类的机器人拦截，
                                          **不能当成坏链**（浏览器里其实是好的）
  broken   404 / 410 / 其余 4xx / 5xx     真坏了，需要人介入
  network  超时 / DNS / 连接被拒          自己这边的问题，不算文档的错

分类是三个互不重叠的纯函数（classify / summarize / select），便于单元测试。

怎么跑
------
  python scripts/check_links_external.py                    # 默认全量 91 条
  python scripts/check_links_external.py --limit 8          # 先拿 8 条探路
  python scripts/check_links_external.py --only acp,quickstart
  python scripts/check_links_external.py --timeout 30 --json

退出码
------
  0   没有 broken
  1   存在 broken（4xx/5xx，排除 403/429）
blocked 与 network 只告警、不影响退出码：前者多为误判，后者是本地网络问题，
两者都不该让定时任务判"官方文档坏了"。真正的坏链才会让退出码变 1。

**不要把本脚本接进 CI。** 它会打 91 次外网请求，可能被限流甚至拉黑，
上游抖动还会造成假失败 —— 一个因为 GitHub Actions 出口 IP 被 CF 拦而
变红的 CI，比没有这条检查更糟。它的正确用法是用 `hermes cron` 低频跑
（比如每周一次）或需要时手动跑，出结果了再人工复核。

已知限制
--------
  * HEAD 被 405/403/400/501 拒绝时回退 GET，并只读状态码/响应头，不下载正文。
  * 只看"HTTP 能不能打开"，不看"页面内容还是不是原来那一页"。内容漂移归
    scripts/sync_sources.py --check 管，两者互补。
  * 本机 git/curl 默认走一个已停掉的本地代理（http://127.0.0.1:7897），
    所以这里显式 ProxyHandler({}) 清空代理。要真的走代理请改代码，
    别指望环境变量 —— 显式清空就是为了避免"上次能跑这次全 network"。
  * 但本机出网还叠着一层会**抖动**的本地隧道（域名都解析到 198.18.x.x 的
    fake-IP 段）：同一域名可能连续十几次 `SSL: UNEXPECTED_EOF_WHILE_READING`，
    40 秒后又全好。所以连不上时会重试（--retries，默认 2 次）。
    即便如此，`network` 仍可能混进"隧道抖动"与"站点真挂了"两种情况 ——
    network 不参与退出码，正是为了不让人把它当结论。
  * 隧道抖动走的是 TLS 层（握手被重置），所以 403/429 之外还有一种
    "被中间盒子掐掉"的形态**长得像 network 而不像 blocked**，
    靠状态码分不出来，这也是四分类的固有边界。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CITATIONS = REPO / "sources" / "citations.yaml"

CATEGORIES = ("ok", "blocked", "broken", "network")
BLOCKED_STATUS = (403, 429)
HEAD_FALLBACK = (400, 403, 405, 501)
UA = "HermesUsage-linkcheck/1.0 (+https://github.com/mt-yu/HermesUsage)"


# --------------------------------------------------------------------------- 纯函数

def classify(status: int | None) -> str:
    """HTTP 状态码 -> 四分类之一。None 表示压根没连上（超时/DNS/被拒）。

    >>> classify(200), classify(403), classify(404), classify(None)
    ('ok', 'blocked', 'broken', 'network')
    """
    if status is None:
        return "network"
    if 200 <= status < 400:
        return "ok"
    if status in BLOCKED_STATUS:
        return "blocked"
    return "broken"


def summarize(results: list[dict]) -> dict:
    """把逐条结果压成汇总。broken_ids 保持传入顺序（= citations.yaml 顺序，按 id 排）。

    容错：结果里缺 category 字段时按 status 现算，避免手写 dict 漏字段就崩。
    """
    counts = {c: 0 for c in CATEGORIES}
    broken_ids: list[str] = []
    for r in results:
        cat = r.get("category") or classify(r.get("status"))
        counts[cat] = counts.get(cat, 0) + 1
        if cat == "broken":
            broken_ids.append(r.get("id", "?"))
    return {
        "ok": counts["ok"],
        "blocked": counts["blocked"],
        "broken": counts["broken"],
        "network": counts["network"],
        "broken_ids": broken_ids,
    }


def has_broken(summary: dict) -> bool:
    """退出码的唯一依据：有 broken 才是失败。"""
    return bool(summary.get("broken"))


def select(entries: list[dict], only: str | None = None, limit: int | None = None) -> list[dict]:
    """--only 按逗号分隔的 id 过滤（保持用户书写顺序），--limit 取前 N 条。"""
    out = list(entries)
    if only:
        wanted = [s.strip() for s in only.replace("，", ",").split(",") if s.strip()]
        index = {e["id"]: e for e in entries}
        out = [index[w] for w in wanted if w in index]
    if limit is not None:
        out = out[:limit]
    return out


# --------------------------------------------------------------------------- 取 URL

def load_citations() -> list[dict]:
    """读 sources/citations.yaml 的 id/url（自动生成，别手改）。"""
    import yaml  # 懒导入：纯函数测试不需要 PyYAML

    data = yaml.safe_load(CITATIONS.read_text(encoding="utf-8")) or []
    entries = [{"id": e["id"], "title": e.get("title", e["id"]), "url": e["url"]} for e in data]
    return sorted(entries, key=lambda e: e["id"])


def opener() -> urllib.request.OpenerDirector:
    """显式清空代理：本机默认代理已挂，否则 91 条全会变成 network。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _request(op: urllib.request.OpenerDirector, url: str, method: str, timeout: float):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
    with op.open(req, timeout=timeout) as resp:
        return int(resp.status), resp.geturl()


def check_one(entry: dict, timeout: float = 15.0, retries: int = 2, backoff: float = 1.5) -> dict:
    """查一条 URL（连不上会重试 retries 次，退避 backoff 秒）。

    为什么要重试：本机出网走的是一个会抖动的本地隧道（TUN/fake-IP），
    同一个域名可能连续十几次 `SSL: UNEXPECTED_EOF_WHILE_READING`，过 40 秒又全好。
    不重试的话，一次抖动就会把 91 条全报成 network —— 看起来像"官方文档全挂"，
    实际是自己的网。重试把这种假信号压掉，剩下的才值得人看。
    """
    result: dict = {}
    for attempt in range(retries + 1):
        result = _attempt_once(entry, timeout)
        if result["status"] is not None:
            result["attempts"] = attempt + 1
            return result
        if attempt < retries:
            time.sleep(backoff * (attempt + 1))
    result["attempts"] = retries + 1
    return result


def _attempt_once(entry: dict, timeout: float) -> dict:
    """一次尝试。返回 {id, url, status, category, method, error, final_url}。"""
    url = entry["url"]
    op = opener()
    status: int | None = None
    method = "HEAD"
    error: str | None = None
    final = url

    try:
        status, final = _request(op, url, "HEAD", timeout)
        if status in HEAD_FALLBACK:
            method = "GET"
            try:
                status, final = _request(op, url, "GET", timeout)
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception as e:  # GET 也挂了：保留 HEAD 的状态码
                error = f"{type(e).__name__}: {e}"
    except urllib.error.HTTPError as e:
        status = e.code
        e.close()
        if status in HEAD_FALLBACK:
            method = "GET"
            try:
                status, final = _request(op, url, "GET", timeout)
                error = None
            except urllib.error.HTTPError as e2:
                status = e2.code
            except Exception as e2:
                error = f"{type(e2).__name__}: {e2}"
    except Exception as e:
        # 连接层直接失败（有些站点对 HEAD 断连），再试一次 GET 再定 network
        method = "GET"
        try:
            status, final = _request(op, url, "GET", timeout)
        except urllib.error.HTTPError as e2:
            status = e2.code
        except Exception as e2:
            error = f"{type(e2).__name__}: {e2}"

    return {
        "id": entry["id"],
        "url": url,
        "status": status,
        "category": classify(status),
        "method": method,
        "final_url": final,
        "error": error,
    }


def run_checks(entries: list[dict], timeout: float, workers: int = 8, retries: int = 2) -> list[dict]:
    """并发查（顺序结果保持不变）。91 条串行最容易在超时上翻车。"""
    if not entries:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(entries)))) as pool:
        return list(pool.map(lambda e: check_one(e, timeout, retries), entries))


# --------------------------------------------------------------------------- 输出

def render(results: list[dict], summary: dict) -> str:
    lines = [f"外链存活检测：共 {len(results)} 条"]
    for cat, label in (("ok", "ok      "), ("blocked", "blocked "), ("broken", "broken  "), ("network", "network ")):
        lines.append(f"  {label} {summary[cat]:3d}")
    for r in results:
        if r["category"] != "ok":
            extra = f"  [{r['error']}]" if r.get("error") else ""
            lines.append(f"    - {r['category']:7s} {r['id']:26s} HTTP {r['status']} ({r['method']}){extra}")
    if summary["broken_ids"]:
        lines.append("坏链明细（需要人改 citations.yaml / 上游文档）：")
        for r in results:
            if r["category"] == "broken":
                lines.append(f"    ! {r['id']:26s} HTTP {r['status']}  {r['url']}")
    else:
        lines.append("没有 broken —— 外链全部可达（blocked/network 若不为 0，请人工扫一眼上面明细）。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="官方文档外链存活检测（默认全量，别接进 CI）")
    ap.add_argument("--limit", type=int, default=None, help="只查前 N 条（探路用）")
    ap.add_argument("--only", default=None, help="只查这些 id，逗号分隔")
    ap.add_argument("--timeout", type=float, default=15.0, help="单条请求超时秒数（默认 15）")
    ap.add_argument("--workers", type=int, default=8, help="并发数（默认 8）")
    ap.add_argument("--retries", type=int, default=2, help="连不上时的重试次数（默认 2，退避 1.5s/3s）")
    ap.add_argument("--json", action="store_true", help="只输出 JSON，便于 cron/脚本消费")
    args = ap.parse_args(argv)

    entries = select(load_citations(), only=args.only, limit=args.limit)
    if not entries:
        print("没有匹配的条目 —— 检查 --only / --limit", file=sys.stderr)
        return 1

    results = run_checks(entries, args.timeout, args.workers, args.retries)
    summary = summarize(results)

    if args.json:
        print(json.dumps({"total": len(results), **summary, "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print(render(results, summary))
    return 1 if has_broken(summary) else 0


if __name__ == "__main__":
    raise SystemExit(main())
