---
id: L62
title: "盯一件外部变化，只在变的时候通知你"
stage: 6
level: 进阶
minutes: 35
prereq: [L23, L21]
tags: ["cron", "watchdog", "no-agent", "静默", "退出码"]
sources: [cron, cron-script-only, automate-with-cron, heartbeat, browser]
updated: 2026-09-16
---

# L62 · 盯一件外部变化，只在变的时候通知你

> **一句话**：把「每天顺手看一眼」交给定时任务，并且把「没变化」写成零输出 —— 否则第一个开始忽略它的人就是你。

## 你将学会

- 判断一件「盯着看」的活该交给 `hermes cron` 还是 `/heartbeat`，并说出两者各自在哪儿跑
- 写一个只看变化的看守脚本，用 `wc -c` 证明「无变化 = 0 字节输出」
- 让看守的三种结果长得不一样：无变化静默 / 有变化说话 / 检查本身失败 —— 靠退出码分开
- 用 `hermes cron runs` 与 `hermes cron doctor` 证明一个安静的作业是真的安静，而不是死了

**前置**：L23、L21 · **预计耗时**：35 分钟

## 先动手

写一个只会说「变了」的看守，5 条命令看完它的三个状态。示例文件都放系统临时目录，跑完删掉不留痕。

```bash
mkdir -p "$LOCALAPPDATA/Temp/hu-watch" && cd "$LOCALAPPDATA/Temp/hu-watch"

cat > watch-demo.py <<'PY'
#!/usr/bin/env python3
"""盯一件事（一个文件或一个网址）：变了才说话，没变零输出。

用法：python watch-demo.py <被盯的文件或网址> <状态文件>
退出码：0 = 检查本身跑通了（有没有输出另说）；2 = 检查本身跑不起来。
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path


def digest_of(target: str) -> str:
    """这次盯到的内容指纹：http(s) 抓正文，其它当本地文件读字节。"""
    if target.startswith(("http://", "https://")):
        req = urllib.request.Request(target, headers={"User-Agent": "hu-watch/1.0"})
        raw = urllib.request.urlopen(req, timeout=20).read()
    else:
        raw = Path(target).read_bytes()
    return hashlib.sha256(raw).hexdigest()[:12]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("用法：python watch-demo.py <被盯的文件或网址> <状态文件>", file=sys.stderr)
        return 2
    target, state_path = argv[1], Path(argv[2])

    try:
        now = digest_of(target)
    except Exception as exc:  # 检查失败 ≠ 没有变化
        print(f"检查失败：{target} 读不到／抓不到（{type(exc).__name__}: {exc}）", file=sys.stderr)
        return 2

    prev = None
    if state_path.is_file():
        prev = json.loads(state_path.read_text(encoding="utf-8")).get("hash")
    state_path.write_text(json.dumps({"target": target, "hash": now}), encoding="utf-8")

    if prev is None or prev == now:
        return 0  # 没变化 → stdout 零字节 → 计划里就是「不投递」
    print(f"[变化] {target} 内容变了：{prev} -> {now}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
PY

printf 'price: 19.9\nstock: 3\n' > page.txt
```

然后按顺序跑：

```bash
python watch-demo.py page.txt state.json | wc -c      # ① 第一次：只记基线
python watch-demo.py page.txt state.json | wc -c      # ② 内容没变
printf 'price: 29.9\nstock: 0\n' > page.txt           # ③ 人为改一次
python watch-demo.py page.txt state.json              # ④ 它说话了
python watch-demo.py page.txt state.json | wc -c      # ⑤ 再跑：又安静了
```

本机真实输出（逐条对得上就算跑通）：

```
0
0
[变化] page.txt 内容变了：b386cfedc240 -> 1f888fa05f00
0
```

`wc -c` 数的是 stdout 的字节数：`0` 就是「一个字都没说」。这正是 cron 的 `no_agent` 模式要的东西 —— 脚本 stdout 为空，这一轮就是静默、不投递。[[src:cron-script-only]]

**为什么用文件哈希而不是比内容**：比字节是确定性的，不需要判断「这次算不算变化」；判断留给后面的告警策略。

## 原理

### 一、先决定「盯着看」发生在哪里

| | `hermes cron` | `/heartbeat` |
|---|---|---|
| 跑在 | 每次触发一个**全新会话**，没有你当前对话的记忆 | **你当前这个会话**，带着上下文与 prompt 缓存 |
| 谁驱动 | 网关守护进程，每 60 秒 tick 一次 | 会话自己（消息平台上的会话由网关看护） |
| 数量 | 不限，一个作业一行 | 一个会话一个 |
| 适合 | 站得住的活：看守、报表、投递 | 「我们边聊边盯一下 X」 |
| 提示写法 | 必须自包含（新会话不认识你的上下文） | 可以依赖上文 |

[[src:cron]] [[src:heartbeat]]

`/heartbeat` 有一条设计值得抄进你自己的看守里：它注入的提示要求 agent「没有实质变化就简短收尾、不要发明工作」。也就是说 —— **「没变化就别说话」是这两个机制共同的前提**，不是 cron 的洁癖。[[src:heartbeat]]

```text
/heartbeat every 15m 查一次 PR #1234 的 CI，结束了再汇总
```

### 二、「安静」这件事得由你自己写进脚本

cron 有两种运行形状，安静的手法各有一套：

| 形状 | 怎么建 | 怎么安静 |
|---|---|---|
| **no_agent（脚本即作业）** | `--no-agent --script 文件名` | 脚本 **stdout 为空** → silent tick，不投递 |
| 常规（LLM 作业） | 给 prompt，可选 `--script` 预跑脚本 | 让 agent 无事时**只回 `[SILENT]`**，投递被抑制（本地仍留审计文件） |

[[src:cron-script-only]] [[src:cron]]

`no_agent` 模式把「脚本干了什么」直接映射成「你会不会被吵到」，整张规则表就这些：

| 脚本行为 | 结果 |
|---|---|
| exit 0，stdout 非空 | stdout 原样投递 |
| exit 0，stdout 为空 | 这一轮静默，不投递 |
| exit 0，最后一行是 `{"wakeAgent": false}` | 静默（与 LLM 作业共用的闸门） |
| **非零退出码** | 投递一条错误告警（坏掉的看门狗不许静默失败） |
| 脚本超时 | 投递一条错误告警 |

[[src:cron-script-only]]

**「空输出 ≠ 成功」就藏在这张表的前两行与第四行的关系里**：静默的条件是「exit 0 且没有输出」。如果脚本把失败也吞成 exit 0，那它就变成了一个哑火的看门狗 —— 那种「安静」和不健康时的安静长得一模一样。本课脚本把「读不到／抓不到」单列成 `exit 2`，就是为了让这两种安静有区别。

本仓库真的在跑这套东西。`scripts/drift_watch.py`（漂移哨兵）无漂移时零输出；你人肉排障时把 `--quiet` 去掉，它又把话说清楚：

```bash
python scripts/drift_watch.py --dry-run --quiet    # 无漂移：stdout 0 字节，exit 0
python scripts/drift_watch.py --dry-run            # 人看：漂移哨兵：无漂移（sync_sources.py --check 无变化），不开 issue。
```

同一个脚本、两种嗓子：**给机器听的那句是空的，给人看的那句是有字的**。cron 用前者，你排障时用后者。这个仓库里三个定时任务（每小时自动归档、每天的漂移哨兵、每周一的外链存活检测）全是这个形状，定义在 `scripts/cron_ctl.py` 的 `JOBS` 表里。

### 三、投递和失败是两条独立的线

- **执行成功 ≠ 送到了**。跑完但没送到你手里会记成 `delivery_failed`（而不是 `ok`），原因写进 `last_delivery_error`，`hermes cron list` 里显示成黄色的 `delivery_failed: <reason>`。投递失败**不算进**失败连击。[[src:cron]]
- **失败会攒连击**。连续失败到阈值（默认 3 次）时，失败消息里会多一句「这个作业已连续失败 N 次，建议修/暂停/删」。`[SILENT]` 只压得住成功的那一次运行 —— **硬失败永远会投**。[[src:cron]]
- **同一个错误反复出现**会被记成 incident；`hermes cron incidents ack <id>` 只压掉这一个签名的重复 ping，别的一切照旧（历史照样记、连击照样数）。[[src:cron]]
- 共享频道怕吵的话，`--failure-deliver local` 让失败通知彻底闭嘴（运行状态仍在 `hermes cron list` 里看得到），或者把它引到 ops 频道。[[src:automate-with-cron]]

### 四、盯网页、盯要登录的页面

同一个形状换成网页，岔口有两个：

1. **脚本抓 + agent 判断**：`--script` 负责机械活（抓取、比哈希），agent 负责判断「这个变化值不值得说」，无事时只回 `[SILENT]`。官方把这列成 "Website Change Monitor" 模式，并明确 `[SILENT]` 是 cron 的静默标记。[[src:automate-with-cron]]
2. **要登录的页面交给浏览器工具**：真 profile 会话能让定时作业驱动你已登录的站点，但三件事得先做到 —— `browser.use_real_profile` 打开（默认 `false`，不打开拿到的是一个干净的、未登录的 profile）；给这个作业 `enabled_toolsets=["browser", ...]`；以及记住「无人值守时没人能回答提示」：站点会话过期会以登录页的形式被那一轮**报出来**，而不是挂住不返回。Windows 上还多一条：截快照需要浏览器已经**完全退出**。[[src:browser]]

`web_extract` 抓不动时该改走浏览器工具的判断在 [[L21]]；这里只多一条：**定时那一轮没有人能替你点登录**，凭证要事先存好。[[src:browser]]

### 五、可选的第三条路：让调度器自己比字节

本机 `hermes cron create --help` 里还有两个参数，你连状态文件都不用写：

```text
--monitor-script MONITOR_SCRIPT
                      Monitor mode: path to a cheap source script under
                      ~/.hermes/scripts/ that runs each tick BEFORE the
                      agent. Unchanged output (exact-bytes hash) suppresses
                      the agent run entirely; changed output injects a
                      MONITOR CHANGE DETECTED diff into the prompt. Script
                      output must be stable (no timestamps). Mutually
                      exclusive with --monitor-url; incompatible with --no-
                      agent.
```

读法：它按**输出字节的哈希**判重，没变就干脆不跑 agent（省钱），变了就把 diff 注进提示。两个前提要看清楚：脚本输出必须稳定（不许带时间戳）、不能和 `--no-agent` 同用。这段只贴本机 `--help` 原文 —— 我登记的这 5 个官方来源里没有它的详细说明，所以本课不对它的行为下别的结论。

## 亲手验证

### 验证一：三种结果，输出和退出码都不一样

```bash
cd "$LOCALAPPDATA/Temp/hu-watch"
python watch-demo.py page.txt state.json | wc -c            # 无变化
python watch-demo.py page-txt state.json; echo "exit=$?"    # 检查本身失败（路径写错）
```

本机真实输出：

```
0
检查失败：page-txt 读不到／抓不到（FileNotFoundError: [Errno 2] No such file or directory: 'page-txt'）
exit=2
```

| 你观察到的 | stdout | exit | 在 cron 里意味着 |
|---|---|---|---|
| 无变化 | 0 字节 | 0 | silent tick，不投递 [[src:cron-script-only]] |
| 有变化 | 一行 `[变化] …` | 0 | 这一行原样投递 |
| 检查本身失败 | **0 字节** | **2** | 投递一条错误告警 |

**为什么「空输出 ≠ 成功」**：第 1 行和第 3 行的 stdout 一模一样，都是 0 字节 —— 只看输出，你分不出「一切正常」和「根本没查成」。真正把两者分开的是退出码，所以失败一定要**走出非零退出码**，不能吞掉。这也是为什么本课脚本第一行就是 try/except，把异常翻译成 `exit 2` 而不是「没变化」。

再补一刀：网络不通也是同一种失败（同一台机器实测）：

```bash
python watch-demo.py https://no-such-domain-l62.invalid page.txt
```

```text
检查失败：https://no-such-domain-l62.invalid 读不到／抓不到（URLError: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1016)>）
```

注意 stdout 依然是 0 字节 —— 如果你把这种异常写成 `return 0`，你的看守就会在断网期间显得非常安静。

### 验证二：让真的调度器跑一遍（用隔离的 HOME，不动你自己的作业）

```bash
DEMO="$LOCALAPPDATA/Temp/hu-l62-home"
export HERMES_HOME="$DEMO"                       # 只影响这一个 shell 会话
mkdir -p "$HERMES_HOME/scripts"
cp "$LOCALAPPDATA/Temp/hu-watch/watch-demo.py" "$HERMES_HOME/scripts/"
printf 'price: 19.9\n' > "$DEMO/page.txt"
```

`--script` 只收 `$HERMES_HOME/scripts/` 下的相对文件名，脚本本身也不接受参数，所以要放一个薄包装器进去（仓库里 `scripts/cron_ctl.py install` 生成的就是这种东西）：

```bash
cat > "$HERMES_HOME/scripts/l62-shim.py" <<'PY'
import subprocess, sys
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
res = subprocess.run(
    [sys.executable, str(HOME / "scripts" / "watch-demo.py"),
     str(HOME / "page.txt"), str(HOME / "state.json")],
    capture_output=True, text=True, encoding="utf-8",
)
if (res.stdout or "").strip():
    print(res.stdout.strip())          # 有话说才说
if res.returncode != 0:
    print((res.stderr or "").strip()[-500:], file=sys.stderr)
sys.exit(res.returncode)
PY

hermes cron create "every 1h" --no-agent --script l62-shim.py --deliver local --name "L62 演示"
hermes cron run "L62 演示"               # 触发一次（本机实测是同步报结果的）
```

本机真实输出（作业 id 每台机器都不一样，看名字和 `Ran now:` 那行即可）：

```text
Created job: 1f740bebbc2b
  Name: L62 演示
  Schedule: every 60m
  Script: l62-shim.py
  Mode: no-agent (script stdout delivered directly)
  Next run: 2026-09-17T09:48:37.706705+08:00

Triggered job: L62 演示 (L62 演示)
  Next run: 2026-09-17T09:45:12.573385+08:00
  Ran now: succeeded.
```

失败的那一轮会写成 `Ran now: failed.` —— 但**那一轮照样有产出文件**，别把 `Ran now:` 当成唯一信号。

`--deliver local` 下，「投递面」就是产出目录，三轮的真实产出文件内容如下（`$HERMES_HOME/cron/output/<job_id>/*.md`）：

```text
# Cron Job: L62 演示            ← 第 1 轮：还没有状态文件 → 静默
**Status:** silent (empty output)

# Cron Job: L62 演示            ← 第 2 轮：改了 page.txt
[变化] C:\Users\…\hu-l62-home\page.txt 内容变了：f2bab3ffd51a -> a747b20e6046

# Cron Job: L62 演示            ← 第 3 轮：把 page.txt 挪走
**Status:** script failed
Script exited with code 2
stderr:
检查失败：C:\Users\…\hu-l62-home\page.txt 读不到／抓不到（FileNotFoundError: …）
```

三处证据互相印证：

```bash
hermes cron runs <job_id> --limit 5    # 三次尝试：failed / completed / completed
hermes cron doctor                     # 1 issue：last run failed: Script exited with code 2
echo $?                                # 1
```

`doctor` 是只读体检，有任何可操作的问题就 `exit 1`（健康时 0）—— 所以它自己就能放进别的看门狗脚本里。[[src:cron]]

**跑完务必收尾**：

```bash
unset HERMES_HOME            # 忘了这步，后面每条 hermes 命令都在这个空 profile 上跑
rm -rf "$DEMO"
```

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `No scheduled jobs.` / `Create one with 'hermes cron create ...' or the /cron command in chat.`，以为作业丢了 | `hermes cron list` 默认不显示已暂停的作业（`--all` 的帮助原文是 "Include disabled jobs"）；全暂停时它就是这个样子 | `hermes cron list --all`，或直接读存储 `python scripts/cron_ctl.py status` |
| `Failed to create job: Script path must be relative to C:\Users\…\hermes\scripts/. Got absolute or home-relative path: 'D:/Projects/…/drift_watch.py'. Place scripts in … and use just the filename.` | `--script` 只认 `$HERMES_HOME/scripts/` 里的相对文件名，绝对路径和 `~` 开头的路径都会被拒 | 放一个薄包装器进去（仓库里 `scripts/cron_ctl.py install` 生成的那种），或把脚本复制进那个目录后用文件名 |
| 作业显示 active，却从不触发 | 调度器靠网关驱动，网关没跑就没有 tick | `hermes cron status` 直接给结论（`cron jobs will fire automatically` / `will NOT fire`），`hermes gateway status` 看进程 |
| 静默的看守其实早就坏了，没人知道 | `exit 0 + 空输出`（正常）和「脚本坏了但被吞成 `exit 0`」长得一模一样 | 失败一律走非零退出码；定期 `hermes cron doctor`（它会查 last run failed、`next_run_at` 停在过去这种「静默不触发」的信号）[[src:cron]] |
| 每天都在响，一看全是噪音 | 整页字节哈希把时间戳、推荐位、广告位也算进去了 | 只盯稳定那一小段内容；或用 `--monitor-script`（帮助原文要求 "output must be stable (no timestamps)"） |
| 失败告警把共享频道刷了 | 硬失败会投一条 `⚠️ Cron 'X' failed…`，而 `[SILENT]` 只压成功的那次运行 | `--failure-deliver local` 彻底闭嘴（运行状态仍在 `hermes cron list`），或引到 ops 频道 [[src:automate-with-cron]] |
| 状态文件被删、换机之后看守永远安静 | 「没有基线」被当成「无变化」 | 本课写法是第一次只记基线、不吭声 —— 当成已知行为管理（状态文件放稳定位置），或让「基线重置」也打一行 |
| `Script timed out` | 预跑脚本有默认上限 3600 秒 | 调 `cron.script_timeout_seconds` [[src:cron]] |
| `hermes chat -q "跑一下 scripts/watch.py …"` 报找不到文件 | agent 的工作目录不是你 shell 的当前目录 | `hermes chat -q "…" --in 你的目录`（帮助原文：Change into DIR before starting or resuming） |

## 试一试

- [ ] 把「被盯的文件」换成你真正在乎的那样东西（一个 CSV、下载目录里的文件、一个 API 的 JSON），跑两次，把两次的 `wc -c` 记下来
- [ ] 故意制造一次「检查本身失败」（路径写错，或把被盯的文件挪走），确认退出码不是 0，并写下为什么不能让这种情况变安静
- [ ] 在隔离的 `HERMES_HOME` 里把三态各跑一轮，用 `hermes cron runs <job_id>` 数出 3 条记录，最后 `unset HERMES_HOME` 并删掉临时目录
- [ ] 打开自己机器的 `hermes cron list --all`，指出哪些作业是「无问题则零输出」
- [ ] 把结果记到 `journal/` 里并提交（见 CONTRIBUTING.md 的会话总结流程）

## 下一步

- [[L23]] —— cron / loop / goal / heartbeat 的选型；本课只深挖「变化」这一件事
- [[L21]] —— 盯网页时要用到的浏览器与抓取工具边界
- [[L34]] —— 把「盯变化 → 判断 → 投递」拼成一条无人值守流水线
- [[L53]] —— 作业在跑但你收不到消息时的排障顺序
- 想深入：[[src:cron-script-only]]（输出→投递映射表）、[[src:cron]]（no-agent / `[SILENT]` / preflight / incidents）、[[src:automate-with-cron]]（`[SILENT]` 与失败投递）、[[src:heartbeat]]（会话内盯梢）

## 出处

- [[src:cron]] Scheduled Tasks (Cron) — https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- [[src:cron-script-only]] Script-Only Cron Jobs (No LLM) — https://hermes-agent.nousresearch.com/docs/guides/cron-script-only
- [[src:automate-with-cron]] Automate Anything with Cron — https://hermes-agent.nousresearch.com/docs/guides/automate-with-cron
- [[src:heartbeat]] Session Heartbeats — https://hermes-agent.nousresearch.com/docs/user-guide/features/heartbeat
- [[src:browser]] Browser Automation — https://hermes-agent.nousresearch.com/docs/user-guide/features/browser
