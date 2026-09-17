---
id: L65
title: "并行委派一批活，并验收子代理的产物"
stage: 6
level: 进阶
minutes: 40
prereq: [L22, L24]
tags: ["delegate_task", "并行", "子代理", "验收", "退出码"]
sources: [delegation, delegation-patterns, goals, batch-processing, curator]
updated: 2026-09-16
---

# L65 · 并行委派一批活，并验收子代理的产物

> **一句话**：一批互不相干的活可以一次派给多个子代理并行做，但决定成败的是最后一步 —— 用可核对的产物验收，而不是听它说「我做完了」。

## 你将学会

- 判断一批活里哪些能并行、哪些必须留在自己手里（依赖、同一批文件、需要人拍板）
- 用一次 `delegate_task` 派出 3 个互不依赖的子任务，并在终端里读出每个任务的耗时与状态
- 写一个四十来行的验收脚本，检查「每份输入都有产出 / 产出非空 / 字段齐全 / 数字与源文件一致」
- 亲手造出「空产出」与「数字对不上」的产出，看脚本把它们一条条抓出来
- 用退出码（0 / 1）而不是它打印的措辞，判定一批活是否真的做完了

**前置**：L22、L24 · **预计耗时**：40 分钟

## 先动手

场景：手边有 3 份周报，要各写一份结构化总结。三份谁都不用等谁 —— 这正是能并行的形状。

### 第 1 步：造输入，把验收脚本放进同一个目录

```bash
mkdir -p "$LOCALAPPDATA/Temp/l65/inputs" "$LOCALAPPDATA/Temp/l65/outs"
cd "$LOCALAPPDATA/Temp/l65"
cat > inputs/week1.md <<'EOF'
# 第 1 周：把日志看明白
本周做了自动归档的开关，写了两条单元测试。
问题是网关没跑的时候任务不会触发，下周要确认登录自启装上了。
EOF
cat > inputs/week2.md <<'EOF'
# 第 2 周：出处体系补齐
把 browser 与 web-search 两页登记进 registry，快照从 89 条变成 91 条。
顺手修掉一处登记错误：prompt-cache 原先和 tips 指向同一页。
EOF
cat > inputs/week3.md <<'EOF'
# 第 3 周：站点交互
练习可以点着打勾并保存，存储键与课程完成分开计。
学习地图并进站点，键盘左右键翻课。
EOF
```

```bash
cat > check_outputs.py <<'PY'
#!/usr/bin/env python3
"""验收脚本：输入目录里每份文档的产出必须存在、非空、含规定字段，且字数与源文件对得上。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS, OUTS = ROOT / "inputs", ROOT / "outs"
FIELDS = ("标题：", "字数：", "要点：")

def body_chars(text):
    """字数口径：去掉所有空白字符后的字符数（脚本与写产出的事先约定好同一个口径）。"""
    return len(re.sub(r"\s", "", text))

problems = 0
for src in sorted(INPUTS.glob("*.md")):
    out = OUTS / src.name
    if not out.exists():
        print(f"FAIL  {out.name}  产出不存在")
        problems += 1
        continue
    text = out.read_text(encoding="utf-8")     # 显式 utf-8，否则中文产出会乱码
    if not text.strip():
        print(f"FAIL  {out.name}  产出是空文件")
        problems += 1
        continue
    missing = [f for f in FIELDS if f not in text]
    if missing:
        print(f"FAIL  {out.name}  缺字段 {'、'.join(missing)}")
        problems += 1
        continue
    claimed = int(re.search(r"字数：(\d+)", text).group(1))
    actual = body_chars(src.read_text(encoding="utf-8"))
    if claimed != actual:
        print(f"FAIL  {out.name}  字数对不上（声称 {claimed}，实际 {actual}）")
        problems += 1
        continue
    print(f"OK    {out.name}  字数 {actual} 与源文件一致")

if problems:
    print(f"\n未通过：{problems} 份产出不合格")
    sys.exit(1)
print("\n通过：产出都存在、非空、字段齐全、字数可核对")
PY
```

这份脚本干四件事：**产出存在 → 非空 → 三个字段齐全 → 数字与源文件复算一致**。四条的判定结果最后压成一个退出码：合格 `0`，不合格 `1`。

### 第 2 步：先跑一次，看它红（这一步是重点）

```bash
python check_outputs.py; echo "EXIT=$?"
```

本机真实输出：

```
FAIL  week1.md  产出不存在
FAIL  week2.md  产出不存在
FAIL  week3.md  产出不存在

未通过：3 份产出不合格
EXIT=1
```

**验收脚本第一次跑就该是红的。** 它现在证明了：这个脚本真的会拦人，而不是一个永远打印 OK 的摆设。

### 第 3 步：补一份产出，看它局部变绿

```bash
cat > outs/week1.md <<'EOF'
标题：第 1 周周报（自动归档开关）
字数：62
要点：
- 自动归档的开关做完了，补了两条单元测试
- 网关没跑时任务不会触发，下周确认登录自启是否装上
EOF
python check_outputs.py; echo "EXIT=$?"
```

本机真实输出：

```
OK    week1.md  字数 62 与源文件一致
FAIL  week2.md  产出不存在
FAIL  week3.md  产出不存在

未通过：2 份产出不合格
EXIT=1
```

一份产出合格，整批仍然不合格，退出码还是 `1`。**批量的验收单位是「全部」，不是「平均」** —— 3 份里有 1 份没交，这批活就没做完。

## 原理

### 什么活能并行，什么不能

| 情形 | 为什么不能并行 | 怎么办 |
|---|---|---|
| B 要用 A 的输出 | 子代理之间不会互相等，派 B 的那一刻它还不知道 A 会产出什么 | 先派 A，拿到结果后再派 B [[src:delegation]] |
| 两个任务要改同一批文件 | 默认共享父会话的工作目录，会互相覆盖 | 那批文件自己动手；或开 `delegation.worktree_isolation: true`，每个子代理在自己的 git worktree 里干活 [[src:delegation-patterns]] [[src:delegation]] |
| 中间需要人拍板 | 子代理不能用 `clarify`，问不到你 | 把决策点切出来自己做，决策之后的执行再派出去 [[src:delegation-patterns]] |

同一份指南还列了「别用委派」的几种：单次工具调用（直接调那个工具）、机械的多步流程（用 `execute_code`）、需要用户交互、必须熬过会话关闭或进程重启的活（用 `cronjob` 或 `terminal(background=True, notify_on_complete=True)`，因为顶层委派虽然是异步的，但仍绑定在会话与进程上）。[[src:delegation-patterns]]

规模上去之后，还多一条形态上的要求：批量任务必须有**落盘的产物目录 + 检查点**。官方的 batch runner 把结果写进 `data/<run_name>/`（`trajectories.jsonl` / `batch_*.jsonl` / `checkpoint.json` / `statistics.json`），只把成功完成的样本记为 done，被中断后 `--resume` 按内容匹配补跑失败的样本。[[src:batch-processing]] 「哪些真做完了」的答案在那份检查点里，不在子代理的措辞里。

### 为什么「子代理说它做完了」是最危险的验收依据

三条官方机制指向同一件事：

1. **只有最终摘要回到你的上下文** —— 中间的工具结果、它读到的原文、它算错的数字，全都不回来。[[src:delegation]]
2. **`status: completed` 只表示「这一轮跑完了」**。带 `output_schema` 的委派由父代理校验结构，不达标会补一次纠正轮；仍然不达标时结果**还是** `status: completed`，只是标上 `schema_valid: false` 和 `schema_errors`（工作不丢，但也说明 completed 不等于合格）。[[src:delegation]]
3. **官方指南把话说白了**：子代理的总结就只是总结 —— 它说「改好了、测试过了」，你要自己跑测试或读 diff。[[src:delegation-patterns]]

还有一条常被忽略：委派**不是持久执行**。进程重启后，还在跑的子代理被记为 `unknown`，因为 Hermes 无法证明它的外部副作用到底发生过没有。[[src:delegation]] 运行时都不替你担保，就更不该拿它的自述当证据。

### 验收用哪几样东西

| 层 | 具体产物 | 能证明什么 / 不能证明什么 |
|---|---|---|
| 契约 | `output_schema` 的结果字段 `schema_valid` / `schema_errors` | 证明**形状**对；证明不了内容对（数字可以是估的）[[src:delegation]] |
| 产物 | 文件、目录、退出码、测试输出 | 可核对的主证据：在不在、非空、字段齐、数字与源文件一致 |
| 过程 | `~/.hermes/cache/delegation/live/<delegation_id>/task-<n>.log` 与同目录 `manifest.json`（派发响应里就带这些路径，每个任务一份追加式日志） | 每个任务真实干了什么、`status` 与 `exit_reason` [[src:delegation]] |
| 长期 | 变更清单 + 每文件 sha256：技能变更会写进 `~/.hermes/skills/.curator_ledger.jsonl`，可用 `hermes curator ledger` 查、`hermes curator rollback <id>` 回滚单条（回滚前先写安全快照，写不下就不动，fail closed） | 证明「改了什么」并留一条可回退的路 [[src:curator]] |

本机 `hermes curator ledger --limit 2` 的真实输出（「谁改了什么」的可核对清单长这样）：

```
id             when         actor    action       skill
31e8342c8732   14h ago      curator  patch        verifiable-docs-repo
4929a05a9ad5   14h ago      curator  patch        verifiable-docs-repo

Roll back a single mutation with `hermes curator rollback <id>`; whole-tree snapshots remain available via `hermes curator rollback --list`.
```

### 把「验收」装成一条能自动判定的命令

`/goal` 里有个现成的形态叫 quality gate：一条确定性 shell 命令，退出 0 之前不许把目标判成完成；门失败时连裁判模型都不调用，门的退出码与输出尾部直接变成下一轮的输入。同一页的 completion contract 还把它写成了字段 —— `verification`「用什么证明」，裁判只在验证标准**带着具体证据**（命令结果、文件片段、测试输出）满足时才判 done。[[src:goals]]

`check_outputs.py` 就是同形状的东西：它把「这批活做完了」翻译成一个退出码。你可以把它当普通命令跑，也可以挂到会话的 `/goal` 上：

```
/goal 把 inputs/ 下 3 份周报各自总结到 outs/
verify: python check_outputs.py 退出 0
boundaries: 只动 $LOCALAPPDATA/Temp/l65
```

字段名（`verify:` / `boundaries:` / `stop when:` 等）是 `/goal` 的契约语法；`/goal gate add python check_outputs.py` 则是把同一条命令装成硬门。[[src:goals]]

## 亲手验证

### 验证一：空产出会被抓出来

```bash
: > outs/week2.md          # 0 字节：模拟"子代理建了文件，但没写内容"
python check_outputs.py; echo "EXIT=$?"
```

本机真实输出：

```
OK    week1.md  字数 62 与源文件一致
FAIL  week2.md  产出是空文件
FAIL  week3.md  产出不存在

未通过：2 份产出不合格
EXIT=1
```

### 验证二：内容对不上的产出会被抓出来

```bash
cat > outs/week3.md <<'EOF'
标题：第 3 周周报（站点交互）
字数：999
要点：
- 练习可以打勾并保存
- 学习地图并进站点
EOF
python check_outputs.py; echo "EXIT=$?"
```

本机真实输出：

```
OK    week1.md  字数 62 与源文件一致
FAIL  week2.md  产出是空文件
FAIL  week3.md  字数对不上（声称 999，实际 50）

未通过：2 份产出不合格
EXIT=1
```

字段漏一个也拦得住（把 `要点：` 那行删掉再跑）：

```bash
cat > outs/week3.md <<'EOF'
标题：第 3 周周报（站点交互）
字数：50
第 3 周做了练习打勾与学习地图。
EOF
python check_outputs.py; echo "EXIT=$?"
```

本机真实输出：

```
OK    week1.md  字数 62 与源文件一致
FAIL  week2.md  产出是空文件
FAIL  week3.md  缺字段 要点：

未通过：2 份产出不合格
EXIT=1
```

| 你观察到的 | 说明什么 |
|---|---|
| 空文件被单独报成 `产出是空文件` | 「文件存在」与「有内容」是两条独立判据；只看文件在不在，等于没验收 |
| `字数对不上（声称 999，实际 50）` | 它的数字可能来自估计而不是数数；验收脚本用源文件复算同一个口径才拦得住 |
| 三次失败退出码都是 `1` | 判定靠退出码，不靠读它打印的措辞 |

### 验证三：真派一次，让脚本验收真实产出

```bash
hermes chat -q "这个目录里有 inputs/ 三份周报原文。请用一次 delegate_task 并行派 3 个子代理，每个子代理只负责一份文件：读 inputs/ 下那份文档，在 outs/ 下写一个同名文件，内容必须恰好包含三行字段：以「标题：」开头的标题行、以「字数：」开头的数字行（数字=该输入文档去掉所有空白字符后的字符数，用终端命令算出来）、以「要点：」开头的要点行（要点写 1-2 条）。三个子代理都完成后，再自己跑一次 python check_outputs.py 把结果原样贴给我。" -Q --in "C:/Users/28189/AppData/Local/Temp/l65"
```

`--in` 用来指定 **agent 的工作目录**：本机实测，shell 里 `cd` 到哪儿跟 agent 在哪儿动手是两件事。不带 `--in` 时，agent 跑 `pwd` 得到 `/c/Users/28189`；加上 `--in "C:/Users/28189/AppData/Local/Temp/l65"` 之后，`pwd` 输出 `/c/Users/28189/AppData/Local/Temp/l65`。

本机真实输出（节选；我实跑时用的是一份同结构的副本目录 `Temp/l65-delegate`，因为要让 `outs/` 从空开始 —— 你直接 `rm -f outs/*.md` 即可）：

```
  🔀 [set 1] delegating 3 tasks
  ✓ [set 1 · 3/3] 读取周报原文 inputs/week3.md，在 outs/week3.md 写  (19.62s)
  ✓ [set 1 · 2/3] 读取周报原文 inputs/week2.md，在 outs/week2.md 写  (20.39s)
  ✓ [set 1 · 1/3] 读取周报原文 inputs/week1.md，在 outs/week1.md 写  (22.49s)
```

脚本在真实产出上通过（退出码 `0`）：

```
OK    week1.md  字数 62 与源文件一致
OK    week2.md  字数 92 与源文件一致
OK    week3.md  字数 50 与源文件一致

通过：产出都存在、非空、字段齐全、字数可核对
```

再去过程记录里核对一遍（这批的 `delegation_id` 是 `deleg_c3e9e341`）：

```bash
ls "$LOCALAPPDATA/hermes/cache/delegation/live"
cat "$LOCALAPPDATA/hermes/cache/delegation/live/deleg_c3e9e341/manifest.json"
```

真实 `manifest.json` 节选：

```json
{
  "delegation_id": "deleg_c3e9e341",
  "task_count": 3,
  "tasks": [
    {"index": 0, "goal": "读取周报原文 inputs/week1.md，在 outs/week1.md 写出恰好三行的验收产出文件，并用终端命令算出准确的「字数」值。",
     "status": "completed", "exit_reason": "completed"}
  ],
  "completed": "2026-09-17 08:45:43"
}
```

三份产出、三个 `status: completed`、一个只用了约 20 秒就回来的批次 —— 但**只有脚本的退出码才说明它们合格**。三样东西凑齐，这批活才算验收完：终端里的批次状态、`outs/` 里的产物、脚本的退出码。[[src:delegation]]

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `FAIL  week1.md  产出不存在`，但子代理说「我写好了」 | 它写在自己的工作目录，不是你 shell 当前所在的目录 | 用 `--in "<目录>"` 指定 agent 的工作目录 |
| 我明明 `cd` 到了目标目录，agent 跑 `pwd` 却是 `/c/Users/28189` | shell 的 cwd 与 agent 的工作目录是两件事 | 加上 `--in "C:/Users/28189/AppData/Local/Temp/l65"`，实测 `pwd` 就对了 |
| `FAIL  week2.md  产出是空文件` | 建了文件没写内容，或写去了别的路径 | 把「存在」「非空」「字段齐全」「值可核对」拆成四条判据 |
| `FAIL  week3.md  字数对不上（声称 999，实际 50）` | 数字是估的，不是数出来的 | 数字由命令算出并写进契约；验收脚本用源文件复算同一个口径 |
| `⚠️ Subagent failed — "your goal": HTTP 404: model not found (after 12s)` | 子代理用的模型/凭证不可用 | 检查 `delegation.model` / `delegation.provider`；父代理结果里带 `status: "failed"` 与 `error` |
| 结果里 `status: completed`，却带 `schema_valid: false` 和 `schema_errors` | `output_schema` 契约没达标（已补过一次纠正轮） | 从 `summary` 的原始文本里自己取，或重派；别把 completed 当合格 |
| 结果里 `exit_reason: max_iterations`、`truncated: true` | 撞上 250 轮迭代预算 | 调 `delegation.max_iterations`，或把任务拆小 |
| 两个任务改同一个文件互相覆盖 | 默认共享父会话的工作目录 | 那批文件自己动手；或开 `delegation.worktree_isolation: true` |
| 关掉会话后这批结果永远没回来 | 委派不是持久执行，绑定在拥有它的会话与进程上 | 跨会话边界的活用 `cronjob` 或 `terminal(background=True, notify_on_complete=True)` |
| 中文产出成了乱码或 `UnicodeDecodeError` | 读写没写死编码（本机实测默认编码是 `utf-8`，但这是机器/语言设置决定的） | 读写都显式 `encoding="utf-8"`（仓库的 R11 也是这条） |
| 把脚本输出贴给人看，却没人看退出码 | 打印的文字只是给人读的，判定得靠退出码 | 流程里用 `&&` 或 `if` 吃掉退出码；`echo "EXIT=$?"` 是最低限度的自证 |

## 试一试

- [ ] 把 `check_outputs.py` 的要求改成「每份产出必须有 3 条要点」，先跑红、再补齐跑绿
- [ ] 给自己的委派加上 `output_schema`（例如要求返回 `{"summaries": [...]}`），检查结果里的 `schema_valid`
- [ ] 故意把一个子代理的目标写得含糊（「总结一下 week2」），对比它产出的字段齐不齐
- [ ] 在 `$LOCALAPPDATA/hermes/cache/delegation/live/` 找到你刚派的那一批，读 `manifest.json` 核对每个任务的 `status` / `exit_reason`
- [ ] 把这次的两次输出（红的与绿的）记到 `journal/` 里并提交（见 CONTRIBUTING.md 的会话总结流程）

## 下一步

- [[L22]] —— 委派的机制、参数与成本都在那课；这一课只管「派出去之后怎么验收」
- [[L24]] —— 验收没过、要把一批改动退回去时，回滚点在哪
- [[L20]] —— 目标写成判据，验收脚本才有东西可查
- [[L25]] —— 配方库里可以直接抄的批量流程
- [[L32]] —— 有依赖、要跨会话的活，用 kanban 排成看板而不是一次并行
- 想深入：[[src:delegation]]（`output_schema`、过程日志、worktree 隔离）、[[src:goals]]（quality gate 与 completion contract）

## 出处

- [[src:delegation]] Subagent Delegation — https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
- [[src:delegation-patterns]] Delegation & Parallel Work — https://hermes-agent.nousresearch.com/docs/guides/delegation-patterns
- [[src:goals]] Persistent Goals — https://hermes-agent.nousresearch.com/docs/user-guide/features/goals
- [[src:batch-processing]] Batch Processing — https://hermes-agent.nousresearch.com/docs/user-guide/features/batch-processing
- [[src:curator]] Curator — https://hermes-agent.nousresearch.com/docs/user-guide/features/curator
