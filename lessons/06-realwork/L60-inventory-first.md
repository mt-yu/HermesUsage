---
id: L60
title: "先把目录看清楚：只读侦察与可核对清单"
stage: 6
level: 进阶
minutes: 30
prereq: [L11, L21]
tags: ["清理", "清单", "只读原则", "inventory", "工作目录"]
sources: [tools, tools-runtime, code-execution, context-references, deliverable-mode]
updated: 2026-09-16
---

# L60 · 先把目录看清楚：只读侦察与可核对清单

> **一句话**：拿到一个塞满杂物的目录，先花两分钟把它变成一份 CSV 清单，再决定动哪个文件。

## 你将学会

- 用 `ls -la` 加一段 30 行的 `inv.py`，把一个目录变成 `清单-<日期>.csv`，并打印扩展名分布
- 说清「只读侦察」允许写什么、不允许写什么
- 用 `hermes chat -q "…" --in <目录>` 让 agent 在你指定的目录里侦察，并知道不加 `--in` 它会跑在**你的用户主目录**里
- 亲手读出三种边界的报错：被侦察的目录不存在、目录是空的、`--in` 的路径写错
- 判断什么时候该把目录「喂」给它、什么时候让它自己用工具看

**前置**：[[L11]]、[[L21]] · **预计耗时**：30 分钟

## 先动手

> 目标：2 分钟内手上出现一份可以数的清单。全程不改动任何原有文件。

**① 造一个塞满杂物的示例目录**（你也可以把它换成自己的下载文件夹）：

```bash
D="$LOCALAPPDATA/Temp/L60-demo"
mkdir -p "$D"
printf 'no extension here\n' > "$D/README"
printf 'fake pdf\n'         > "$D/report final 2026.pdf"
printf 'fake xlsx\n'        > "$D/客户清单.xlsx"
printf 'fake png\n'         > "$D/Screenshot 2026-09-17 143210.png"
printf 'fake jpg\n'         > "$D/IMG_0042.JPG"
printf '# notes\n'          > "$D/notes.md"
touch "$D/empty.txt"
ls -la --time-style=long-iso "$D"
```

本机真实输出（文件名故意凑齐四种怪情况：无扩展名、含空格、含中文、0 字节）：

```
total 6154
drwxr-xr-x 1 develop 197121  0 2026-09-17 08:45 .
drwxr-xr-x 1 develop 197121  0 2026-09-17 08:45 ..
-rw-r--r-- 1 develop 197121  0 2026-09-17 08:45 empty.txt
-rw-r--r-- 1 develop 197121  9 2026-09-17 08:45 IMG_0042.JPG
-rw-r--r-- 1 develop 197121  8 2026-09-17 08:45 notes.md
-rw-r--r-- 1 develop 197121 18 2026-09-17 08:45 README
-rw-r--r-- 1 develop 197121  9 2026-09-17 08:45 report final 2026.pdf
-rw-r--r-- 1 develop 197121  9 2026-09-17 08:45 Screenshot 2026-09-17 143210.png
-rw-r--r-- 1 develop 197121 10 2026-09-17 08:45 客户清单.xlsx
```

**② 把这个脚本存到上一层目录**（放上一层是为了不让清单脚本把自己也算进去）：

```bash
cat > "$LOCALAPPDATA/Temp/inv.py" <<'PY'
# inv.py —— 只读侦察：把一个目录变成可核对的清单（不递归、不改任何文件）
import csv, os, sys
from collections import Counter
from datetime import date

root = sys.argv[1] if len(sys.argv) > 1 else "."
rows = []
for name in sorted(os.listdir(root)):        # 只列这一层，不递归
    path = os.path.join(root, name)
    if not os.path.isfile(path):             # 子目录先跳过
        continue
    ext = os.path.splitext(name)[1].lower() or "(无扩展名)"
    size = os.path.getsize(path)
    rows.append((name, ext, size, "空" if size == 0 else ""))

out = "清单-%s.csv" % date.today().isoformat()
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["文件名", "扩展名", "字节数", "备注"])
    for name, ext, size, note in rows:
        w.writerow([name, ext, size, note])

print("扫描目录：%s" % os.path.abspath(root))
print("文件数：%d    空白文件：%d    写入：%s" % (
    len(rows), sum(1 for r in rows if r[3] == "空"), out))
print("-" * 58)
for name, ext, size, note in rows:
    print("%8d  %-12s %-4s %s" % (size, ext, note, name))
print("-" * 58)
for ext, n in Counter(r[1] for r in rows).most_common():
    print("  %-12s %d 个" % (ext, n))
PY
```

**③ 跑它**（在示例目录里跑，清单会落在同一层）：

```bash
cd "$LOCALAPPDATA/Temp/L60-demo" && python ../inv.py .
```

本机真实输出：

```
扫描目录：C:\Users\28189\AppData\Local\Temp\L60-demo
文件数：7    空白文件：1    写入：清单-2026-09-17.csv
----------------------------------------------------------
       9  .jpg              IMG_0042.JPG
      18  (无扩展名)            README
       9  .png              Screenshot 2026-09-17 143210.png
       0  .txt         空    empty.txt
       8  .md               notes.md
       9  .pdf              report final 2026.pdf
      10  .xlsx             客户清单.xlsx
----------------------------------------------------------
  .jpg         1 个
  (无扩展名)       1 个
  .png         1 个
  .txt         1 个
  .md          1 个
  .pdf         1 个
  .xlsx        1 个
```

CSV 里就是同一份数据（`cat 清单-<日期>.csv`）：

```
文件名,扩展名,字节数,备注
IMG_0042.JPG,.jpg,9,
README,(无扩展名),18,
Screenshot 2026-09-17 143210.png,.png,9,
empty.txt,.txt,0,空
notes.md,.md,8,
report final 2026.pdf,.pdf,9,
客户清单.xlsx,.xlsx,10,
```

**这一步的价值**：你现在有了一份可以数、可以 diff、可以贴进邮件的东西。目录还是原来那 7 个文件（`ls -la` 的时间戳没变），只多出一个 CSV —— 这就是「只读侦察」的意思：清单脚本写的是**新文件**，被侦察的东西一个字节都没动。

> 一个小自我指涉：清单落在被侦察的目录里，所以你**第二次**跑同一段脚本时文件数会变成 8（清单把自己也数进去了，`ls -la` 里那个 228 字节的 CSV 就是）。文件名里带日期，同一天重跑是**覆盖**，不会越堆越多；想干净就先把它删掉再跑。

## 原理

### 为什么先出清单，而不是先动手

面对一个杂乱目录，人容易直奔「整理」：移动、改名、删空文件。问题是这些动作一旦开始，你就失去了「原始状态」这个对照物 —— 之后没法回答「原来有多少个」「这个是本来就有还是刚生成的」。

清单先行的三个作用：

1. **可核对**：文件数和扩展名分布是能自己数的，不用信任任何人的转述。
2. **可复现**：同一段脚本对同一目录跑两次，结果应该完全一样（`diff` 一下就知道）。
3. **可交接**：CSV 是文件，不是对话里的一段话。它在磁盘上，谁都能打开。

### 它在哪个目录里动手（这是本课最容易踩的地方）

先说官方口径：命令跑在哪个环境由**终端后端**决定（`local` 是默认值），`terminal.cwd` 是配置项 [[src:tools]]；工具运行时支持按任务覆盖工作目录 [[src:tools-runtime]]；而 `execute_code` 的 `project` 模式文档写得很直白 —— 脚本在**会话的工作目录**里跑，与 `terminal()` 同一个目录 [[src:code-execution]]。

所以关键问题是：`hermes chat -q "…"` 起的那个会话，工作目录是哪个？**本机实测：不是你 shell 的当前目录。** 即使你已经 `cd` 进目标目录，它仍然在用户主目录里干活。要让它进指定目录，必须给 `--in <目录>`（本机 v0.21.3 的 `hermes chat --help` 原文：`--in DIR  Change into DIR before starting or resuming`）。

| 你怎么起会话 | 它跑在哪个目录 |
|---|---|
| `cd "$D" && hermes chat -q "…"` | `/c/Users/28189`（用户主目录，**不是** `$D`） |
| `hermes chat -q "…" --in "$D"` | `/c/Users/28189/AppData/Local/Temp/L60-demo`（就是 `$D`） |

两个命令的完整对照在「亲手验证」第一节，包括它的原文回答。**这条对你后面所有课都成立**：让 agent 在某个目录干活，就给 `--in`，别指望 shell 的 `cd` 传过去。

### 两条侦察路线：你喂它，还是它自己看

| 路线 | 怎么做 | 代价与边界 |
|---|---|---|
| **你喂** | 消息里写 `@folder:<目录>`，Hermes 把目录树 + 文件元数据展开进消息（`@file:` 注入文件内容，`@file:main.py:10-25` 可只注入行区间） | 单个文件夹引用上限 **200 条**，超出的部分被替换成 `- ...`；这是交互式 CLI 的展开功能 [[src:context-references]] |
| **它自己看** | 给它一个目录，让它用 `file` / `terminal` / `code_execution` 工具集自己列 | 每一步都消耗一次工具调用；目录里文件很多时，原始列表会占上下文 |

`@folder:` 那个 200 条上限是硬的，官方文档把阈值写在「Size Limits」表里，同时还规定了两条软/硬上下文阈值（超过上下文长度的 25% 追加警告、超过 50% 直接拒绝展开）[[src:context-references]]。目录一乱就上百个文件的场景，`@folder:` 会被截断 —— 这就是本课先用脚本把它压成 CSV 的原因。

**三步以上带逻辑的活，让它写脚本而不是连点工具**：`execute_code` 让 agent 写 Python 脚本，通过 RPC 调 Hermes 工具，**中间的工具结果根本不进上下文**，只有脚本的 `print()` 回到模型 [[src:code-execution]]。单次执行的额度是 300 秒 / stdout 50 KB（超出部分落盘并给出路径）/ 50 次工具调用 [[src:code-execution]]；脚本里能用的工具是 `web_search`、`web_extract`、`read_file`、`write_file`、`search_files`、`patch`、`terminal`（仅前台，没有 `background` 和 `pty`）[[src:code-execution]]。本课这份 `inv.py` 的复杂度（遍历 + 分类 + 写 CSV）正好落在它的舒适区。

### 「只读」是一条约定，不是开关

Hermes 没有「只准读」的开关。你能收紧的是**给它哪些工具**（`hermes chat --toolsets "web,terminal"` 这类写法可按任务收窄，本课只用 `file` / `terminal` 就够，见 [[L11]] [[src:tools]]）和**危险动作的审批**：

- 终端工具在执行前会把命令拿去比对一组破坏性模式（递归删除、`mkfs`/`dd`、不带 `WHERE` 的 `DELETE FROM`、`> /etc/`、`curl | sh`、fork 炸弹等），命中就让你批准/拒绝/永久允许 [[src:tools-runtime]]。
- 批准是**按会话**记的：同一会话里批准过一次「递归删除」，后面的 `rm -rf` 不再问 [[src:tools-runtime]]；选「永久允许」会把该模式写进 `config.yaml` 的 `command_allowlist` [[src:tools-runtime]]。
- 可选一个辅助模型做「智能审批」，自动放行低风险命令（官方举的例子正是 `rm -rf node_modules/` 这种命中模式但其实安全的命令）[[src:tools-runtime]]。

**本机实测**：在示例目录外跑一句 `rm -rf L60-demo` 重建现场时，命令被标为 `recursive delete` 并由智能审批自动放行 —— 也就是说，「命中模式」和「真的危险」是两件事，你得自己看命令本身（[[L50]] 讲怎么收紧）。反过来，**侦察阶段你不该看到任何审批弹窗**：清单脚本只做 `listdir` + `getsize` + 写一个新 CSV，没有任何一条会碰到那组模式。看到弹窗，说明你的手指已经越过只读线了。

### 清单怎么交出去

清单落在磁盘上之后，交付只是一个路径问题：在消息平台（Slack / Discord / Telegram 等）里，网关会扫描回复中的**绝对路径**并把对应文件当附件上传，你不需要写 `MEDIA:` 之类的标签；放在代码块或行内代码里的路径会被忽略，避免把代码示例里的路径也发出去 [[src:deliverable-mode]]。

扩展名决定投递方式：`.csv` / `.md`（本课清单的两种形态）走「文件上传」，而 `.py`、`.log` 这类源码/日志扩展名**被故意排除**在表外，理由是不要自动把任意源码发给对方 [[src:deliverable-mode]]。所以清单别存成 `.log`，也别指望把 `inv.py` 当附件发出去。

一处**未验证**的细节照实说：官方文档举的路径例子都是 POSIX 风格（`/tmp/...`、`~/...`），本课是 Windows 路径，我没有在网关里实测过 Windows 绝对路径的识别，这一条留给你在「试一试」里试 [[src:deliverable-mode]]。

## 亲手验证

### 验证一：`--in` 前 vs `--in` 后的工作目录

两次都在**同一个 shell、同一个目录**里发起，唯一区别是有没有 `--in`：

```bash
cd "$LOCALAPPDATA/Temp/L60-demo"
hermes chat -q "只做只读侦察，不要创建/修改/删除任何文件：（1）跑 pwd 报告你的工作目录；（2）用 ls 列出当前目录里的文件名。" -Q
```

本机真实输出（节选）：

```
（1）工作目录：/c/Users/28189

（2）当前目录内容（`ls` 输出，未做任何改动）：
- 目录：AppData、Contacts、Desktop、Documents、dotnet、Downloads、Favorites、Links、Music、OneDrive、Pictures、Postman、Saved Games、Searches、Smart、source、Videos、WorkBuddy、WorkBuddy AI、WPS Cloud Files、WPSDrive
- 文件：CmDust-Result.log、NTUSER.DAT、ntuser.dat.LOG1、ntuser.dat.LOG2、ntuser.ini、SystemPatch.zip，以及若干 NTUSER.DAT 的注册表事务日志（.TM.blf / .TMContainer*.regtrans-ms）
```

它老老实实列了**你家里的目录**，不是那个示例目录。现在加上 `--in`，命令和提示词一字不变：

> 这两段都是本机真跑出来的。**内容随机、形状固定**：它每次措辞都不一样，但 `pwd` 那一行与「列的是哪个目录」不会变 —— 照抄命令复跑，你看到的文字会不同，形状应该一样。

```bash
hermes chat -q "只做只读侦察，不要创建/修改/删除任何文件：（1）跑 pwd 报告你的工作目录；（2）用 ls 列出当前目录里的文件名。" --in "$LOCALAPPDATA/Temp/L60-demo" -Q
```

本机真实输出：

```
工作目录：/c/Users/28189/AppData/Local/Temp/L60-demo

当前目录文件（9 个）：
- empty.txt
- IMG_0042.JPG
- notes.md
- README
- report final 2026.pdf
- Screenshot 2026-09-17 143210.png
- 客户清单.xlsx
- 清单-2026-09-17.csv
```

| 你观察到的 | 说明什么 |
|---|---|
| 不加 `--in` 时它跑在 `/c/Users/28189` | `hermes chat -q` 的会话工作目录**不是**你 shell 的 cwd |
| 加 `--in` 后 `pwd` 就是那个目录 | `--in` 是让它在指定目录干活的开关 |
| 它说「9 个」，可 `ls` 数出来只有 8 个 | **别信转述的数字**：清单（CSV 行数）才是可核对的那一份 |

### 验证二：三种边界，三种不同的报错

**边界 A · 被侦察的目录不存在**（清单脚本直接把路径交给了 `os.listdir()`）：

```bash
cd "$LOCALAPPDATA/Temp"
python inv.py C:/Users/28189/AppData/Local/Temp/L60-nope
```

本机真实输出：

```
Traceback (most recent call last):
  File "C:\Users\28189\AppData\Local\Temp\inv.py", line 17, in <module>
    for name in sorted(os.listdir(root)):          # 只列这一层，不递归
                       ^^^^^^^^^^^^^^^^
FileNotFoundError: [WinError 3] 系统找不到指定的路径。: 'C:/Users/28189/AppData/Local/Temp/L60-nope'
```

**边界 B · 目录存在但是空的**：文件数 0，CSV 只有表头。

```
扫描目录：C:\Users\28189\AppData\Local\Temp\L60-empty
文件数：0    空白文件：0    写入：清单-2026-09-17.csv
----------------------------------------------------------
----------------------------------------------------------
```

「0 个文件」和「清单没生成」是两件事：空目录也会产出一份（只有表头的）清单 —— 这恰恰是你需要知道的事实。

**边界 C · `--in` 的路径写错**：

```bash
hermes chat -q "报告你的工作目录（pwd）" --in "$LOCALAPPDATA/Temp/L60-nope" -Q
```

本机真实输出（会话根本没起，直接在启动阶段报错）：

```
Error: --in directory not found: C:\Users\28189\AppData\Local/Temp/L60-nope
```

三种报错对应三种成因：路径**不存在**（`WinError 3` / `--in directory not found`）与目录**空**（0 个文件）不是一类问题，前者要改路径，后者是正常结果。

### 验证三：`@folder:` 在一行模式里没展开

```bash
cd "$LOCALAPPDATA/Temp"
hermes chat -q "看 @folder:L60-demo —— 如果这份目录内容真的进来了，说出其中字节数最大的那个文件名；没进来就只回答「没拿到」，不要自己跑去 ls。" --in "$LOCALAPPDATA/Temp" -Q
```

本机真实输出：

```
没拿到
```

官方文档把 `@` 引用定位成 **CLI 的展开功能**：交互式 CLI 里 `@` 会触发补全、引用在消息发出前就被展开；而消息平台不展开它，消息原样传给 agent [[src:context-references]]。本机这一跑补上了另一半：**`-q` 一行模式也不展开**（提示词里的 `@folder:L60-demo` 被当成普通文字传过去了）。这里的「形状」就是一个词：模型没拿到目录内容 —— 它每次的回答可能换措辞，但不会变成「拿到了」。

| 你想让 agent 看到目录 | 怎么做 |
|---|---|
| 交互式 CLI 里 | 消息里写 `@folder:<目录>` [[src:context-references]] |
| 一行模式 / 脚本里 | 让它自己列（提示词写「用 ls 列出当前目录」），或者先把清单 CSV 生成好、把 CSV 的路径写进提示词 |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `Error: --in directory not found: C:\Users\28189\AppData\Local/Temp/L60-nope` | `--in` 给的目录不存在（拼错 / 盘符不对 / `/` 与 `\` 混写） | 先 `ls "<目录>"` 确认能列出来，再把它传给 `--in` |
| `FileNotFoundError: [WinError 3] 系统找不到指定的路径。: 'C:/…/L60-nope'` | 脚本把不存在的路径直接喂给 `os.listdir()` | 先判断：`test -d "$D" && python ../inv.py "$D"` |
| 它报告的文件数和 `ls` 数出来的不一样（实测它说 9 个、实际 8 行） | `hermes chat -q` 默认跑在用户主目录，看到的不是你的目录 | 加 `--in "<目录>"`；数字以清单 CSV 为准 |
| 提示词里的 `@folder:xxx` 没生效，它回「没拿到」 | `@` 引用是 CLI 交互模式的展开功能，`-q` 一行模式与非 TTY 不展开 [[src:context-references]] | 交互模式用 `@folder:`；一行模式改让它 `ls`，或把清单 CSV 路径给它 |
| 目录里几百个文件时，`@folder:` 尾部变成 `- ...` | 单个文件夹引用上限 200 条，超出部分被省略 [[src:context-references]] | 先用 `inv.py` 把它压成 CSV，再把 CSV 交出去 |
| 文件名带空格，shell 循环把它们拆成了好几个名字（实测 `report final 2026.pdf` → `report`、`final`、`2026.pdf`） | `for f in $(ls)` 按空白分词，路径没被当成一个整体 | 用 `inv.py` 里的 Python 循环；非要 shell 就用 `while IFS= read -r f` |
| 同一段脚本跑第二次，文件数从 7 变成 8 | 上一次生成的 `清单-<日期>.csv` 也在被侦察的目录里，清单把自己数了进去 | 先删掉旧清单再跑，或把脚本里 `out` 改成上一层目录；同一天重跑是覆盖，不会累积 |
| 某个 `.txt` 在别的工具里打开是乱码，Hermes 却读得出来 | 它是 **UTF-16**（Windows 记事本、PowerShell `>` 重定向的常见产物） | 不用先转格式：`read_file` 会检测并转码成 UTF-8 展示，改回文件时按 UTF-8 写 [[src:tools]] |
| 整理时 `rm -rf` 弹审批，或者被智能审批直接放行 | 命中破坏性模式「递归删除」；低风险命令可被辅助模型自动放行 [[src:tools-runtime]] | 侦察阶段不该出现；真要动手先看 [[L50]]（收紧审批）与 [[L24]]（回滚点） |

## 试一试

- [ ] 把 `inv.py` 指向你自己的 `Downloads` 目录，生成清单，然后**只根据 CSV**回答：最大的三个文件是哪个（不许打开它们）
- [ ] 给清单加一列修改时间（`os.path.getmtime` + `datetime.fromtimestamp`），重新生成，再用 `ls -la` 核对被侦察文件的 mtime 一个都没变
- [ ] 在交互模式里（直接 `hermes chat`，或 `hermes chat --in "$D"`）用 `@folder:` 把示例目录喂进去，和 `-q` 一行模式的结果对比
- [ ] 在配好网关的会话里（见 [[L33]]）把清单 CSV 的绝对路径写成普通文本，观察它是否作为附件到达；再试试 `.log` 后缀，看有没有区别 [[src:deliverable-mode]]

## 下一步

- [[L11]] —— 工具集是权限边界，侦察时只给它 `file` / `terminal`
- [[L21]] —— 四类工具各自适合什么、代价差在哪
- [[L24]] —— 真动手改文件之前，先把回滚点准备好（`hermes chat --checkpoints`）
- [[L50]] —— 危险命令审批的默认值与收紧方式
- 想深入：[[src:code-execution]]（脚本执行的额度与「中间结果不进上下文」）、[[src:context-references]]（`@folder:` 的上限与阈值）

## 出处

- [[src:tools]] Tools & Toolsets — https://hermes-agent.nousresearch.com/docs/user-guide/features/tools
- [[src:tools-runtime]] Tools Runtime — https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime
- [[src:code-execution]] Code Execution — https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution
- [[src:context-references]] Context References — https://hermes-agent.nousresearch.com/docs/user-guide/features/context-references
- [[src:deliverable-mode]] Deliverable Mode (Artifacts in Chat) — https://hermes-agent.nousresearch.com/docs/user-guide/features/deliverable-mode
