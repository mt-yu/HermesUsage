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
    """`- [ ] 练习` → 带方框的行。

    用 <span> 而不是 <input>：Markdown 的 HTML 块规则会把块级 <input> 当独立
    段落处理，把「练习」折到下一行；span 是行内元素，不会改变列表结构。
    """

    def repl(m: re.Match[str]) -> str:
        checked = "1" if m.group(2).lower() == "x" else "0"
        return f'{m.group(1)}<span class="task-box" data-checked="{checked}" aria-hidden="true"></span> {m.group(3)}'

    return _outside_fences(text, lambda s: TASKLIST_RE.sub(repl, s))


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


def render_markdown(body: str) -> tuple[str, list[dict]]:
    """Markdown 正文 → (带 id 的 HTML, 目录)。

    每次调用新建 Markdown 实例：扩展对象带内部状态（脚注编号、标题计数），
    复用同一个实例会让第 2 课的目录从 s5 开始 —— 这种 bug 极难肉眼发现。
    """
    import markdown  # 延迟导入：只在真正渲染时才要求装了 Markdown

    md = markdown.Markdown(extensions=["extra", "sane_lists"])
    html = md.convert(preprocess_tasklist(strip_template_comments(body)))
    return add_heading_ids(html)


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
