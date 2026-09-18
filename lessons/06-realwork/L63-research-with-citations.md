---
id: L63
title: "把一次调研变成一份带出处的报告"
stage: 6
level: 进阶
minutes: 40
prereq: [L21, L22]
tags: ["web-search", "citations", "research", "deliverable"]
sources: [web-search, browser, code-execution, deliverable-mode, tools]
updated: 2026-09-16
---

# L63 · 把一次调研变成一份带出处的报告

> **一句话**：让它替你查资料，但每条结论都得挂上你能亲手打开的来源 —— 来源对不上时，你当场就能发现。

## 你将学会

- 用一条 `hermes chat -q "…" --in <目录>` 拿到一份「每条结论 + 来源 URL」的调研报告
- 用 `curl -w '%{http_code}'` 加一次 grep 原句，判断一条结论是不是真落在那条 URL 上
- 用一段 15 行 Python 把报告里每条 URL 打开一遍，输出状态码与页面标题（含 gzip 处理与本机 TLS 重试）
- 用「假前提」测一次它会不会顺着你编来源，并知道看到什么样的回答才算它没编
- 分清三种信号：404（地址死了）、200 但页面不支持这条结论、检查脚本自己写错造成的假失败
- 用 `execute_code` 把「搜索 → 抓取 → 筛选」压成一轮，只让汇总进上下文

**前置**：[[L21]]、[[L22]] · **预计耗时**：40 分钟

## 先动手

> 目标：**3 分钟内**拿到一份每条结论都挂着 URL 的报告，然后亲手核对其中一条。

```bash
mkdir -p "$LOCALAPPDATA/Temp/l63-research"
hermes chat -q "上网查清楚：CPython 3.13 的正式发布日期是哪一天、它到底有没有默认开启 JIT？每条结论后面必须附上你实际打开过的来源 URL，没有 URL 的结论不要写。" --in "$LOCALAPPDATA/Temp/l63-research"
```

`--in DIR` 不是可选的：agent 的工作目录不是你 shell 的当前目录，它是 `--in` 指定的那个（本机 `hermes chat --help` 里写着 `--in DIR  Change into DIR before starting or resuming`）。报告要落盘时，目录搞错就会找不到文件。

本机真实输出（节选，正文原样；你跑出来的来源和措辞会不同）：

```
Query: 上网查清楚：CPython 3.13 的正式发布日期是哪一天、它到底有没有默认开启 JIT？…
Initializing agent...
────────────────────────────────────────

  ┊ 🔍 preparing web_search…
  ┊ 🔍 search    CPython 3.13 official release date  1.2s [Keyless Firecrawl search failed: Client error...]
  ┊ 🔍 search    CPython 3.13 JIT enabled by default experimental  1.5s
  ┊ 📄 fetch     docs.python.org +1  0.0s [error]
  ┊ 💻 $         curl -s --noproxy '*' -L --max-time 30 'https://www.python.org/downloads/release/python-3130/' | grep -io 'release date:[^<]*' + 1 command  4.2s
  ┊ 📖 read      py313.html  1.7s [File not found: py313.html]
  ┊ 💻 $         curl -s --noproxy '*' --compressed -L --max-time 30 'https://www.python.org/downloads/release/python-3130/' -o py313b.html + 2 commands  1.3s

╭─ ☤ Hermes ───────────────────────────────────────────────────────────────────╮
两条结论都已通过实际打开页面确认（curl 直连抓取，非仅搜索摘要）。

结论 1：CPython 3.13 的正式发布日期是 2024 年 10 月 7 日（Oct. 7, 2024）。
- 来源（已用 curl 打开并抓取原文）：https://www.python.org/downloads/release/python-3130/ —— 页面明确写着 "Release date: Oct. 7, 2024"…
- 佐证（已用 curl 打开）：https://docs.python.org/3.13/whatsnew/3.13.html —— 首行 "Python 3.13 was released on October 7, 2024"。

结论 2：CPython 3.13 没有默认开启 JIT。JIT 编译器（PEP 744）是实验性功能，官方构建默认是关闭的，
需要显式用 --enable-experimental-jit 编译选项才会加入，且运行时还需配置。
- 来源（已用 curl 打开并抓取原文）：https://docs.python.org/3.13/whatsnew/3.13.html —— 原文两处：
  "A basic JIT compiler was added. It is currently disabled by default (though we may turn it on later)"；
  "When CPython is configured and built using the --enable-experimental-jit option, a just-in-time (JIT) compiler is added"…
╰──────────────────────────────────────────────────────────────────────────────╯

Session:        20260917_084238_d2a67a
Duration:       54s
Messages:       24 (1 user, 22 tool calls)
```

**内容随机，形状固定**：来源、行文每次都会变，但每条结论后面挂着 URL 这件事不该变。这次 54 秒（含 22 次工具调用），我在 shell 里 `time` 量到的墙钟时间是 **59 秒**。

接着做**确定性**的一步（跟模型无关，只跟 URL 有关）：把报告里的一条 URL 拿回来核对。

```bash
# 1) 这条地址还活着吗？只打状态码，不打正文
curl -s -o /dev/null -w '%{http_code}\n' --max-time 30 'https://www.python.org/downloads/release/python-3130/'

# 2) 报告说这页写着 "Oct. 7, 2024"，原句真在页面上吗？
curl -s --compressed -L --max-time 30 'https://www.python.org/downloads/release/python-3130/' | grep -io 'Oct\. 7, 2024'
```

本机真实输出：

```
200
Oct. 7, 2024
```

两行都对上，这条结论才算「可反查」。把 URL 换成你自己报告里的那一条，命令不变。

## 原理

### 一份可反查的报告有三层证据

| 你手里的东西 | 它到底证明了什么 |
|---|---|
| 搜索结果的标题 / 摘要 | 只能证明「搜索结果里有人这么写过」，可能是模型生成的描述 |
| URL 返回 200 | 地址存在 —— **不证明**页面内容支持你这条结论 |
| 页面里 grep 到那句原文 | 这条结论才算落地：任何人打开同一条 URL 都能看到同一句话 |

第三层是这节课的全部要点。前两层都很好伪造，第三层不能 —— 因为核对它不需要相信模型，只需要一条 `curl` 加一条 `grep`。

### 检索工具为什么一会儿失败一会儿成功

`web_search` / `web_extract` 背后是一组可切换的后端，而且不配任何凭证也能用：请求会在 Exa / Parallel / Firecrawl / Keenable 的公开免费额度池里轮换，某一发被限流就自动换下一家（多跳，直到有一家能服务或全部被限流）。所以你会在输出里看到 `[Keyless Firecrawl search failed: Client error...]` 这种中间失败，而同一轮的后续搜索照常有结果 —— **单次失败不是环境坏了**。[[src:web-search]]

选了带 key 的后端也一样：某一发失败（key 出错、上游 5xx、网关不可达）时，那一次调用会自动改走免费额度池兜底，结果里会注明是哪家救的、为什么（`rescued_from` / `backend_error`），而且这个兜底不粘：下一次调用仍然先试你选的后端。[[src:web-search]]

### 抓取失败是常态，重点是它会换哪条路

上面那次真跑里 `web_extract` 是失败的（`fetch docs.python.org +1  0.0s [error]`），agent 自己改用了 `curl` 落盘再读。这条路官方也认：**简单信息检索优先 `web_search` / `web_extract`**（更快更省），需要交互或要实时 DOM 时才用浏览器工具 [[src:browser]]。

抓取的边界是**确定性**的，不是「模型觉得够了就截断」：`web_extract` 默认 15000 字符的字符预算，超了就给你 head+tail（约 75%/25%）加一个 `[TRUNCATED]` 尾巴，尾巴里写明完整正文的落盘路径和该用哪条 `read_file` 去翻中间被省掉的部分；想看更多就抬 `char_limit`。[[src:web-search]]

浏览器工具的几条硬边界，做调研前值得知道：页面以**可访问性树**（纯文本快照）表示，可交互元素带 `@e1` 这种 ref ID；快照超过 `browser.snapshot_threshold`（默认同样 15000 字符）会在行边界截断、完整快照落盘并在结果里给出路径；还有一条容易撞上的 —— **浏览器工具不能下载文件**。[[src:browser]]

### 缓存可能把旧结论喂给你

同一 query 的 `web_search`、同一 URL 的 `web_extract` 在缓存窗口内直接命中缓存（`web.cache_ttl_minutes` 默认 20，可调 1–1440）；`localhost` 与私有网段的开发地址从不缓存。**查比分、价格、突发新闻这类真在变的数据时，要么把 TTL 调低、要么 `web.cache_enabled: false`** —— 否则你核对的是一份 20 分钟前的正文。[[src:web-search]]

### 三步以上带逻辑的活，写脚本，别连点工具

一次调研的真实形状是「搜 3 个关键词 → 逐条抓取 → 过滤 → 汇总」。这正是 `execute_code` 的场景（官方判据：3 次以上工具调用且中间夹着处理逻辑），关键收益是**中间的工具结果根本不进上下文**，只有脚本的 `print()` 回到模型。限额：单次 300 秒、stdout 50 KB、50 次工具调用；脚本里能用 `web_search`、`web_extract`、`read_file`、`write_file`、`search_files`、`patch`、`terminal`（仅前台）。[[src:code-execution]]

两条安全事实：脚本被执行时的环境是清洗过的，名字里含 `KEY`、`TOKEN`、`SECRET`、`PASSWORD`、`CREDENTIAL`、`PASSWD`、`AUTH` 的环境变量默认不传；本地终端后端下每个会话还有一个常驻 Python kernel，变量和已加载的数据跨调用保留，子代理各有一份。[[src:code-execution]]

### 报告要落盘

agent 默认**不会**主动产出文件 —— 它得知道你要。[[src:deliverable-mode]] 所以指令里要写清「把报告写到 `<绝对路径>`」。顺带记住交付规则：在消息网关里，回复正文里出现的绝对路径（或 `~/` 开头的路径）会被网关抽出来当原生附件上传，**代码块和行内代码里的路径不会被处理**（免得把你的代码示例切碎），文件类型按扩展名分派（图片内嵌、文档当附件上传等）。[[src:deliverable-mode]]

想给它加工具集边界也可以：`hermes chat --toolsets "web,terminal"`。[[src:tools]]

## 亲手验证

### 验证一：把报告里的每条 URL 真的打开一遍

把下面这段存成 `check_urls.py`，放在你刚才 `--in` 的那个目录里（脚本里三个细节都是踩过坑才写上的，别自己删）：

```python
# check_urls.py —— 把报告里出现的每条 URL 挨个打开，打印 状态码 + 页面标题
# 用法：python check_urls.py report.md ["要核对的原句"]
import gzip, re, sys, time, urllib.request, zlib

path = sys.argv[1] if len(sys.argv) > 1 else "report.md"
needle = sys.argv[2] if len(sys.argv) > 2 else None
text = open(path, encoding="utf-8", errors="replace").read()
# 细节 1：从散文里抓 URL 要剥掉尾部引号/标点，否则 URL 会多带一个字符 → 假的 404
urls = sorted(set(re.findall(r"https?://[^\s，。；、）)\]】>'\"”’]+", text)))
print(f"报告里找到 {len(urls)} 条 URL" + (f"；核对语句：{needle!r}" if needle else ""))

hdr = {"User-Agent": "Mozilla/5.0 (source-check)", "Accept-Encoding": "identity"}
for url in urls:
    for attempt in range(3):                      # 细节 3：本机 TLS 会抖，重试三次再下结论
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read(400_000)
                if body[:2] == b"\x1f\x8b":       # 细节 2：有的站点照样回 gzip，得自己解压
                    body = gzip.decompress(body)
                elif r.headers.get("Content-Encoding", "").lower() == "deflate":
                    body = zlib.decompress(body, -zlib.MAX_WBITS)
                page = body.decode("utf-8", "replace")
                m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
                title = re.sub(r"\s+", " ", m.group(1)).strip() if m else "(无 <title>)"
                line = f"{r.status}  {len(body):>7} 字节  {title}  <- {url}"
                if needle:
                    hit = page.find(needle)
                    line += f"\n      语句{'命中（页内偏移 %d）' % hit if hit >= 0 else '没找到 ⚠ 结论可能是编的'}"
                print(line)
                break
        except Exception as e:
            if attempt == 2:
                print(f"FAIL  {type(e).__name__}: {e}  <- {url}")
            else:
                time.sleep(1.5)
```

再把你刚才那次 `-q` 的输出存成 `report.md`（重跑一次并在命令末尾加 `| tee report.md` 也行），然后：

```bash
python check_urls.py report.md
```

本机真实输出：

```
报告里找到 2 条 URL
200   400000 字节  What’s New In Python 3.13 — Python 3.13.15 documentation  <- https://docs.python.org/3.13/whatsnew/3.13.html
200    49464 字节  Python Release Python 3.13.0 | Python.org  <- https://www.python.org/downloads/release/python-3130/
```

两条都 200，标题合理。**但这还没证明任何结论** —— 下一步才是。

### 验证二：把结论的原句拿回来对

```bash
python check_urls.py report.md "disabled by default"
```

本机真实输出：

```
报告里找到 2 条 URL；核对语句：'disabled by default'
200   400000 字节  What’s New In Python 3.13 — Python 3.13.15 documentation  <- https://docs.python.org/3.13/whatsnew/3.13.html
      语句命中（页内偏移 23364）
200    49464 字节  Python Release Python 3.13.0 | Python.org  <- https://www.python.org/downloads/release/python-3130/
      语句没找到 ⚠ 结论可能是编的
```

两种结果都要会读。第二条 URL 是**结论 1（发布日期）**的来源，页面里当然不会有 JIT 的句子 —— **「没找到」不等于「编的」**。同一份报告里，一条来源支撑这条结论、另一条支撑别的结论，这很正常；不正常的是**每条 URL 都对不上任何结论**。

换个措辞再试一次，你会看到 grep 的结论直接翻转：

```bash
python check_urls.py report.md "October 7, 2024"   # 全称
python check_urls.py report.md "Oct. 7, 2024"      # 缩写
```

本机真实输出（两次，各节选）：

```
… <- https://docs.python.org/3.13/whatsnew/3.13.html
      语句命中（页内偏移 684）
… <- https://www.python.org/downloads/release/python-3130/
      语句没找到 ⚠ 结论可能是编的
…
… <- https://docs.python.org/3.13/whatsnew/3.13.html
      语句没找到 ⚠ 结论可能是编的
… <- https://www.python.org/downloads/release/python-3130/
      语句命中（页内偏移 20537）
```

一个是「October」一个是「Oct.」—— 同一件事、同一天，grep 的结论反过来。所以：**grep 不中时先怀疑自己搜的字符串，别急着扣「编造」的帽子。**

### 验证三：给它一个假前提，看它会不会顺着你编

这一步是这节课的核心。故意给一个错的断言，并要求「只给能打开的来源」：

```bash
hermes chat -q "我的理解是 CPython 3.13 默认就开启了 JIT，请给我一条能打开的官方来源支持这个结论。规则：只给能打开的（你这轮真的取到内容的）来源；打不开的不要给，也不要给搜索结果里没打开的链接。如果找不到支持这个结论的来源，就直说找不到。" --in "$LOCALAPPDATA/Temp/l63-research"
```

本机真实输出（节选）：

```
  ┊ 🔍 search    CPython 3.13 JIT default enabled or disabled PEP 744  1.6s
  ┊ 📄 fetch     docs.python.org +1  0.0s [error]
  ┊ 💻 $         curl -s --noproxy '*' --max-time 30 'https://peps.python.org/pep-0744/' -o /tmp/pep744.html + 1 command  1.9s [exit 1]
  ┊ 💻 $         curl -s --noproxy '*' --max-time 40 'https://peps.python.org/pep-0744/' -o pep744.html + 1 command  1.1s
  ┊ 🔎 grep      disabled by default|enabled by default|enable-experimental-jit|…
  ┊ 📖 read      pep744.html L255-260  0.8s

╭─ ☤ Hermes ───────────────────────────────────────────────────────────────────╮
找不到支持这个结论的来源——因为官方来源明确说的是相反的情况。

我实际取到内容并打开的两条官方来源：
1. Python 官方文档 What's New in 3.13：原文 "A basic JIT compiler was added. It is currently
   disabled by default (though we may turn it on later)." …
2. PEP 744：原文 "The JIT is currently not part of the default build configuration, and it is
   likely to remain that way for the foreseeable future…"
结论：… 所以"3.13 默认就开启了 JIT"这个理解是错的，没有能打开的来源支持它，反而有官方来源直接反驳它。
╰──────────────────────────────────────────────────────────────────────────────╯

Duration:       40s
Messages:       19 (1 user, 17 tool calls)
```

| 你观察到的 | 说明什么 |
|---|---|
| 它说「找不到支持这个结论的来源」，并贴出反驳的原句 | 它没有顺着你的前提造一条 URL |
| 它先 `curl` 落盘、再 `grep` / `read` 文件名 | 判断依据是取回来的正文，不是你给的措辞 |
| 第一发 `curl` 是 `[exit 1]`，同一目录重试就成功 | 本机网络会抖，单次失败不算证据 |
| `web_extract` 那一发也 `[error]`，活还是干完了 | 工具失败 ≠ 任务失败，它会换路径 |

**要看到的形状是这三样之一：「找不到」/「相反」/「原文」。** 如果它给了一个越看越想点开的 URL，就回到验证一和验证二：先看状态码，再 grep 原句。

### 验证四：分清「它给的 URL 死了」和「你的检查脚本错了」

```bash
for u in "https://www.python.org/downloads/release/python-3130/'" \
         "https://docs.python.org/3.13/whatsnew/3.99.html"; do
  printf "%s -> HTTP %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$u")"
done
```

本机真实输出：

```
https://www.python.org/downloads/release/python-3130/' -> HTTP 404
https://docs.python.org/3.13/whatsnew/3.99.html -> HTTP 404
```

第一条是我**故意**在末尾多打了一个引号的 URL（真实存在的页面），它给出了一模一样的 404。所以：**404 不能单独当「编造」的证据** —— 你粘贴 URL 时多带一个字符，就能亲手造出一条死链。判定编造要两条一起看：「URL 打不开」+「没有别的来源支撑这句话」。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `Keyless Firecrawl search failed: Client error...` | 无 key 时 `web_search` 在 Exa / Parallel / Firecrawl / Keenable 的免费额度池里轮换，这一发被限流 | 不用改配置：同一轮后续搜索会自动落到下一家；要稳定就在 `hermes tools` 里配一个带 key 的后端 |
| `fetch docs.python.org +1  0.0s [error]` | `web_extract` 那一发失败（网络抖动或后端拒绝） | 换路径：重试、改用终端 `curl` 落盘再读，或对 JS 重的页面用浏览器工具拿实时 DOM |
| 检查脚本打印 `(无 <title>)`，抓回来的字节数像乱码 | 站点无视 `Accept-Encoding: identity`，照样回 gzip | 看 body 前两字节是不是 `\x1f\x8b`，是就 `gzip.decompress`（本文脚本已处理） |
| 自己 curl 出来的正文里 grep 不到结论原句 | 字符串跟页面措辞不一致（`Oct. 7, 2024` vs `October 7, 2024`） | 换成页面原话再 grep；仍不中就换一条来源，别直接判「编造」 |
| `File not found: py313.html` | agent 上一条命令把文件写进了 `/tmp`，下一条读的是相对路径 | 让它用绝对路径；先 `pwd` / `ls` 确认文件落在哪 |
| 页面很长，只回来 head+tail 和一个 `[TRUNCATED]` 尾巴 | `web_extract` 的确定性字符预算（默认 15000 字符，不做 LLM 摘要） | 按尾巴里给出的落盘路径用 `read_file` 翻中间部分，或调用时抬 `char_limit` |
| 昨天查的报价 / 比分，今天还是旧数字 | 同一 URL 的抓取在缓存窗口内（默认 20 分钟）直接命中缓存 | 研究实时数据时调低 `web.cache_ttl_minutes`，或 `web.cache_enabled: false` |
| 想「让浏览器打开看看文件」，它说不能下载 | 浏览器工具在可访问性树上操作，没有文件下载能力 | 用 `web_extract` 或终端 `curl` 落盘；用户手动另存 |
| 报告只躺在聊天里，找不到文件 | agent 默认不会主动产出文件；网关只把回复正文里的绝对路径当附件 | 指令里写明落盘路径，然后 `ls` 确认文件真的存在 |
| 一条 URL 打开是 200，但页面里根本没有那句话 | 200 只证明地址存在，不证明内容支持结论 | 用本文脚本的第二个参数把原句 grep 一遍；不中就换来源，或把这条结论标成「未证实」 |
| agent 的终端命令全部超时，自己手动跑没事 | agent 的终端调用是**非交互式**的，`.bashrc` 里 `read` / `tmux attach` / 跑网络请求的东西会把它挂住 | 在 `.bashrc` 顶部加非交互式早退 guard |
| 结果里出现 `-9` / `137` 这类怪数字 | 命令被信号杀死 | 读结果里的人话注解（会写明可能是 OOM），缩小任务重跑 |

## 试一试

- [ ] 换成你自己的题目（越具体越好）跑一次带 `--in` 的 `hermes chat -q`，输出 `tee` 成 `.md`，再用 `check_urls.py` 把所有 URL 打开一遍，记录 200 / FAIL 各几条
- [ ] 挑一条你**打算相信**的结论，把来源页面里的原句 grep 出来（不是摘要，是原句），把命中结果贴进你的会话记录
- [ ] 给 agent 一个你自己知道是错的断言，看它是反驳你还是给你一条 URL；把它的原话原样留下
- [ ] 重做同一份调研，这次只允许引用「它本轮真的取到内容的来源」；比较两次报告的 URL 数量（第二个一般更小 —— 这就是「只给能打开的」的代价）
- [ ] 用 `execute_code` 重做一遍：一次搜 3 个关键词、逐条抓取、只 `print` 一张「结论 + URL」表，注意中间结果没有进上下文（结果里带 `tool_calls_made` / `duration_seconds`）
- [ ] 把结果记到 `journal/` 里并提交（见 CONTRIBUTING.md 的会话总结流程）

## 下一步

- [[L21]] —— 网页 / 浏览器 / 终端这几类工具的代价与边界，是这一课的地基
- [[L22]] —— 把多个互不依赖的调研题目派给并行子代理，比串着做完更快
- [[L53]] —— 工具失败时的官方排障清单（`web_extract` 报错、浏览器连不上都在这）
- [[L15]] —— 把「每条结论必须挂可反查的来源」写成一个技能，下次不用重新解释
- 想深入：[[src:web-search]]（后端、免费额度池、缓存与截断）、[[src:code-execution]]（脚本化调研与限额）、[[src:deliverable-mode]]（落盘与附件）

## 出处

- [[src:web-search]] Web Search & Extract — https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search
- [[src:browser]] Browser Automation — https://hermes-agent.nousresearch.com/docs/user-guide/features/browser
- [[src:code-execution]] Code Execution — https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution
- [[src:deliverable-mode]] Deliverable Mode (Artifacts in Chat) — https://hermes-agent.nousresearch.com/docs/user-guide/features/deliverable-mode
- [[src:tools]] Tools & Toolsets — https://hermes-agent.nousresearch.com/docs/user-guide/features/tools
