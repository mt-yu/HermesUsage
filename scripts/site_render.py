#!/usr/bin/env python3
"""scripts/site_render.py —— 纯函数渲染层：Markdown 正文 → 站点 HTML 片段。

为什么全部做成纯函数
--------------------
渲染是唯一「错了很难发现」的环节：Markdown 里的裸尖括号会让整段话在浏览器里消失、
出处标记没接上会让「可考证」这个卖点变成空话。所以这一层不碰文件、不打印，
只用 unittest 喂字符串断言输出 —— 出问题在测试里就能看见，而不是靠肉眼翻页面。
"""

from __future__ import annotations

import html as html_mod
import re

# 出处与交叉引用标记（与 verify.py 的正则保持一致，别各写一份）
SRC_RE = re.compile(r"\[\[src:([A-Za-z0-9_.\-]+)\]\]")
XREF_RE = re.compile(r"\[\[(L\d{2,})\]\]")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
TASKLIST_RE = re.compile(r"^(\s*[-*]\s+)\[([ xX])\]\s+(.*)$", re.M)
# 出现在 <pre>/<code> 里的标记不许改写（读者要看到字面量）
CODE_RE = re.compile(r"<pre\b.*?</pre>|<code\b.*?</code>", re.S)
PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
HEADING_RE = re.compile(r"<(h[23])>(.*?)</\1>", re.S | re.I)
# Markdown 围栏代码块的开头/结尾（``` 或 ~~~）：里面的内容不是正文语法
FENCE_RE = re.compile(r"^\s*(```|~~~)")


class SiteError(RuntimeError):
    """站点构建错误。消息必须带上下文（哪一课、哪个标记），否则等于没报错。"""


def escape(text: str) -> str:
    return html_mod.escape(str(text), quote=True)


def strip_template_comments(text: str) -> str:
    """删掉 HTML 注释：课程模板里的写作提示不该出现在读者眼前。"""
    return COMMENT_RE.sub("", text)


def _outside_fences(text: str, transform) -> str:
    """只对围栏代码块之外的文本做替换。

    `preprocess_tasklist` 面对的是**尚未渲染的 Markdown**，所以代码保护的粒度是
    围栏代码块而不是 `<pre>`：课程里教「怎么写练习清单」时给的是 ```- [ ] …``` 的
    示例代码，那几行必须原样留给读者，不能被换成复选框。
    """
    lines = text.split("\n")
    out: list[str] = []
    buf: list[str] = []
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line):
            if in_fence:
                out.append(line)
                in_fence = False
            else:
                if buf:
                    out.append(transform("\n".join(buf)))
                    buf = []
                out.append(line)
                in_fence = True
            continue
        if in_fence:
            out.append(line)
        else:
            buf.append(line)
    if buf:
        out.append(transform("\n".join(buf)))
    return "\n".join(out)


def preprocess_tasklist(text: str) -> str:
    """`- [ ] 练习` → 带方框的行，并给每个方框编上课内稳定编号 `data-ex`。

    用 <span> 而不是 <input>：Markdown 的 HTML 块规则会把块级 <input> 当独立
    段落处理，把「练习」折到下一行；span 是行内元素，不会改变列表结构。

    编号从 1 开始、在一次调用内递增。本站的调用约定是「一课正文调一次」，
    所以编号天然是课内编号：L15 的第 3 题就是 data-ex="3"，与它在正文里
    出现的顺序一致。这也正是打勾状态能被存下来的前提 —— 课号 + 题号就是
    一个稳定主键（见 web/assets/lib/exercises.js）。

    `- [x]`（模板里预勾的）与 `- [ ]` 一视同仁地参与编号：编号描述的是
    「这是第几题」，不是「做完了几题」。计数器挂在闭包上，因此跨越围栏
    代码块前后仍然连续（围栏只影响替换，不影响编号顺序）。
    """
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        checked = "1" if m.group(2).lower() == "x" else "0"
        return (
            f'{m.group(1)}<span class="task-box" data-ex="{counter}"'
            f' data-checked="{checked}" aria-hidden="true"></span> {m.group(3)}'
        )

    return _outside_fences(text, lambda s: TASKLIST_RE.sub(repl, s))


def count_exercises(body: str) -> int:
    """数一门课的练习数：**围栏代码块之外**的 `- [ ]` / `- [x]` 行数。

    需要它的理由：读者看到的「这课 5 道题、你做完 3 道」需要一个**总数**，而总数
    只可能来自正文。数在哪里、怎么数，必须与 `preprocess_tasklist` 完全一致 ——
    它决定读者看见几个方框，这里决定进度写「3/5」还是「3/6」。两处一旦漂移，
    页面上没有任何东西会报错，只是数字悄悄变成假的。

    所以这里直接复用同一个 `_outside_fences` 与同一个 `TASKLIST_RE`，而不是
    另写一遍「扫描行、跳过 ``` 」：围栏的判定规则（含缩进、含 ~~~、含未闭合）
    只有一份实现，才谈得上「两处口径一致」。

    `[x]` 与 `[ ]` 一视同仁地计数（与编号一致）：这里数的是「有几道题」，
    不是「做完了几道」—— 已做数由浏览器的练习题状态给出（web/assets/lib/exercises.js）。
    """
    total = 0

    def count(segment: str) -> str:
        nonlocal total
        total += len(TASKLIST_RE.findall(segment))
        return segment

    _outside_fences(body, count)
    return total


def _outside_code(fragment: str, transform) -> str:
    """只在代码块之外做替换：`[[src:x]]` 出现在代码里时，读者要看到字面量。"""
    parts: list[str] = []
    last = 0
    for m in CODE_RE.finditer(fragment):
        parts.append(transform(fragment[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(transform(fragment[last:]))
    return "".join(parts)


def outside_code(fragment: str, transform) -> str:
    """公开版 `_outside_code`：给链接改写器用。

    为什么需要它：文档里会**讨论** href（例如写在反引号里的 `href="../x"`），
    那是给人看的文本，不是链接。不区分代码区就会出现「文档写什么、构建报什么」的怪现象。
    """
    return _outside_code(fragment, transform)


def add_heading_ids(fragment: str, prefix: str = "s") -> tuple[str, list[dict]]:
    """给 h2/h3 编上稳定 id，并返回扁平目录列表。

    目录只用 h2/h3：h1 是课程标题本身（页面顶部已经有了），再列一次是噪音。

    id 用自增的 `s1`/`s2`…，而不是从标题文字生成的 slug：Python-Markdown 的 `toc`
    扩展默认 slugify 是非 Unicode（中文标题会被过滤成 `_1`、`_2` 这种不可读 id），
    换个版本行为还会变。自增编号与语言无关、确定、可断言。
    """
    toc: list[dict] = []
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        hid = f"{prefix}{counter}"
        level = 2 if m.group(1).lower() == "h2" else 3
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        toc.append({"id": hid, "level": level, "text": text})
        return f'<{m.group(1)} id="{hid}">{m.group(2)}</{m.group(1)}>'

    return HEADING_RE.sub(repl, fragment), toc


def build_toc_html(toc: list[dict]) -> str:
    """把扁平目录列表变成嵌套 <ol>（h3 落到 h2 的下级）。

    嵌套的正确形态是 `<li>h2 链接<ol>h3…</ol></li>`：h3 必须落在它所属的 h2 的
    <li> 里面，且同级 h2 要回到 toc-l2 这一层。所以 `<li>` 不能立刻闭合 ——
    要等看到下一条目录项才知道后面跟不跟子列表。
    """
    if not toc:
        return ""
    out: list[str] = ['<nav class="page-toc" aria-label="本页目录"><p class="toc-title">本页目录</p><ol class="toc-l2">']
    open_sub = False   # 当前是否有一个未闭合的 <ol class="toc-l3">
    open_li = False    # 当前是否有一个未闭合的顶层 <li>（h2 那条）
    for item in toc:
        link = f'<a href="#{escape(item["id"])}">{escape(item["text"])}</a>'
        if item["level"] == 3:
            if not open_sub:
                out.append('<ol class="toc-l3">')
                open_sub = True
            out.append(f"<li>{link}</li>")
        else:
            if open_sub:
                out.append("</ol></li>")
                open_sub = False
                open_li = False
            elif open_li:
                out.append("</li>")
                open_li = False
            out.append(f"<li>{link}")
            open_li = True
    if open_sub:
        out.append("</ol></li>")
    elif open_li:
        out.append("</li>")
    out.append("</ol></nav>")
    return "".join(out)


def render_markdown(body: str, prefix: str = "s") -> tuple[str, list[dict]]:
    """Markdown 正文 → (带 id 的 HTML, 目录)。

    每次调用新建 Markdown 实例：扩展对象带内部状态（脚注编号、标题计数），
    复用同一个实例会让第 2 课的目录从 s5 开始 —— 这种 bug 极难肉眼发现。

    `prefix` 透传给 `add_heading_ids`（**原样拼在编号前**，不会自动补 `s`）。
    默认 `"s"` 是单页正文的形态（一课一个 HTML，页内不会撞 id）；**单文件离线版
    必须传带课号的前缀**（`"L15-s"` → `L15-s1`），因为 32 课要被拼进同一份文档：
    都用 `s1/s2…` 的话，文档里会出现 32 组重复 id，浏览器与 `#s1` 式锚点只认
    第一个 —— 于是「点第 20 课的目录项跳到第 1 课」，而页面看起来完全正常。
    """
    import markdown  # 延迟导入：只在真正渲染时才要求装了 Markdown

    md = markdown.Markdown(extensions=["extra", "sane_lists"])
    html = md.convert(preprocess_tasklist(strip_template_comments(body)))
    return add_heading_ids(html, prefix)


def linkify_citations(fragment: str, citations: dict[str, dict], where: str) -> str:
    """[[src:id]] → 指向官方文档的链接，title 里带上版本与快照哈希。

    这是「可考证」在界面上的落地：读者把鼠标停在标记上就能看到
    「哪一版官方文档的哪一段、哈希是多少」，不需要相信作者。
    """

    def repl(m: re.Match[str]) -> str:
        sid = m.group(1)
        entry = citations.get(sid)
        if not entry:
            raise SiteError(
                f"{where}: 引用了未登记的出处 [[src:{sid}]]"
                f"（先在 sources/registry.yaml 登记并跑 python scripts/sync_sources.py）"
            )
        tip = (
            f'{entry.get("title", sid)}（hermes v{entry.get("hermes_version", "?")}'
            f' · 快照 sha256 {str(entry.get("sha256", ""))[:12]}…）'
        )
        return (
            f'<a class="cite" href="{escape(entry.get("url", ""))}" target="_blank" rel="noopener"'
            f' title="{escape(tip)}">src:{escape(sid)}</a>'
        )

    return _outside_code(fragment, lambda s: SRC_RE.sub(repl, s))


def linkify_xrefs(fragment: str, id_to_page: dict[str, str], where: str) -> str:
    """[[L13]] → 同级页面链接（课程页都在 site/lessons/ 下）。"""

    def repl(m: re.Match[str]) -> str:
        lid = m.group(1)
        page = id_to_page.get(lid)
        if not page:
            raise SiteError(f"{where}: 交叉引用 [[{lid}]] 指向不存在的课程")
        return f'<a class="xref" href="{escape(page)}">{escape(lid)}</a>'

    return _outside_code(fragment, lambda s: XREF_RE.sub(repl, s))


def prereq_links(prereq: list[str], url_of: dict[str, str], where: str) -> str:
    """frontmatter 的 `prereq` → 可点击的「前置」串（`L02、L10`，为空时 `无`）。

    为什么放在渲染层：读者看到的两处「前置：…」（课程页底部、离线单页每课末尾）
    都从这里出，而链接目标随**页面所在层级**变化 —— 课程页指向同级文件名
    （`L02-….html`），离线单页指向文档内锚点（`#L02`）。所以目标映射由调用方给，
    函数只负责「有链接」这件事。

    查不到目标 id 直接报错，不静默降级成纯文字：一个点了 404 的「前置」链接
    比没有链接更坏，而静默降级在浏览器里根本看不出来。
    """
    if not prereq:
        return "无"
    links: list[str] = []
    for lid in prereq:
        url = url_of.get(str(lid))
        if not url:
            raise SiteError(
                f"{where}: frontmatter 的 prereq 里有不存在的课程 {lid}"
                "（前置链接会指向 404）"
            )
        links.append(f'<a class="xref" href="{escape(url)}">{escape(str(lid))}</a>')
    return "、".join(links)


def repo_doc_slug(rel: str) -> str:
    """'.hermes.md' -> 'hermes-md'；'sources/README.md' -> 'sources-readme'。

    非隐藏文件先去掉扩展名（README.md → README）：URL 里带个 `-md` 是噪音。
    以点开头的文件（`.hermes.md`）例外 —— 它的「文件名」本身就是 `.hermes`，
    再去扩展名等于替作者猜命名意图，所以整名参与 slug（`hermes-md`）。
    """
    name = rel.rsplit("/", 1)[-1]
    stem = rel if name.startswith(".") else re.sub(r"\.(md|markdown|txt)$", "", rel, flags=re.I)
    return re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()


def render_template(template: str, values: dict[str, str], where: str) -> str:
    """极简 {{占位符}} 替换。

    残留占位符必须报错：模板少填一个值，页面上就会出现 {{footer}} 这种字面量，
    靠肉眼巡检 33 个页面发现不了。
    """
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    left = PLACEHOLDER_RE.search(out)
    if left:
        raise SiteError(f"{where}: 模板占位符没有被填充：{left.group(1)}")
    return out


def search_text(body: str) -> str:
    """把 Markdown 正文压成检索文本。

    刻意保留代码块内容：这套教程里「hermes cron list」「/rollback <N>」这类命令
    是最常被搜的东西，把它们排除掉，搜索就废了一半。
    """
    text = strip_template_comments(body)
    text = re.sub(r"^\s*```.*$", " ", text, flags=re.M)          # 去围栏行，留代码
    text = SRC_RE.sub(r" \1 ", text)                              # 出处 id 也可搜
    text = XREF_RE.sub(r" \1 ", text)
    text = re.sub(r"^\s*[-*|>#]+\s*", " ", text, flags=re.M)      # 列表/表格/引用符号
    text = re.sub(r"[*_`\[\]()]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
