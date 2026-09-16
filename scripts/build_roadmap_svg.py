#!/usr/bin/env python3
"""scripts/build_roadmap_svg.py —— 生成 docs/roadmap.svg：README 里的学习路线图。

为什么它必须是个生成物
----------------------
README 原来有一张手抄的 ASCII 路线图。手抄的东西一定会漂移：32 课里改一个标题、
把一课挪到别的阶段，那张图不会报错，只会安静地变成假的。而本仓库的原则是
「**规范写在脚本里**」—— 凡是能从课程 frontmatter 推出来的东西，都得由脚本重建，
并被自动化断言锁住（对照 `build_map.py` 的 `docs/learning-map.html`、
`build_index.py` 的 `llms.txt`）。

课号 / 阶段 / 标题**一个都不许手抄**：全部来自 `scripts/tutorial_core.py`
（全仓库唯一的解析入口）。本文件只负责「怎么画」。

为什么手写 SVG 字符串（不装 Graphviz、不用 node 画图）
------------------------------------------------------
1. **零新依赖**：Graphviz 要在本地和 CI 装二进制，mermaid/d2 要 node；
   这里只用标准库拼字符串，`python scripts/build_roadmap_svg.py` 就能跑。
2. **可重现**：同样的课程集合 → 字节完全相同的文件。`--check` 靠这一点比对
   （没有时间戳、没有随机数、没有机器相关信息）。
3. **GitHub 的 README 直接渲染 SVG**（`![路线图](docs/roadmap.svg)`），
   而且它能自带深色底 —— 不管读者开着亮色还是暗色主题，观感一致。

已知限制（写在这里，免得下一个人以为是 bug）
------------------------------------------
- 文本宽度是**估算**的（CJK 按一个字号宽、ASCII 按 0.55 个字号），所以截断点
  在个别字体下会早一点或晚一点。宁可早截加 `…`，也不让文字溢出芯片外。
- 中文靠 `system-ui, 'Microsoft YaHei', 'PingFang SC'` 落地，**不引外部字体或
  `@import`**：引 CDN 字体等于「断网就变方框」外加一次外网请求。
- 手绘感用「确定性几何」（虚线分隔线、双色描边）实现，**刻意不用
  `<filter>` + `feTurbulence`**：一旦渲染器（或被消毒过的 SVG）把 `<filter>`
  定义去掉却留下 `filter="url(#…)"`，按 SVG 1.1 该元素将**整个不渲染** ——
  边框消失是小事，填充一起消失才是灾难。抖动边框的收益不值这个风险。
- 深色底在 GitHub 浅色主题下是一块深色面板（而不是「看不清」）。这是刻意的：
  GitHub 把 SVG 当图片渲染，它读不到页面的 `prefers-color-scheme`，只能选一种。
- 不用 `<foreignObject>` / `<script>` / 外部 `href`：GitHub 会消毒掉它们，
  本地看着好好的，线上就缺一块。文本一律 XML 转义（课程标题里真的有 `&`、`<`）。

用法
----
  python scripts/build_roadmap_svg.py            # 写 docs/roadmap.svg
  python scripts/build_roadmap_svg.py --check    # 重算并与落盘文件比对（CI / check.py 用）
  python scripts/build_roadmap_svg.py --stdout   # 打到屏幕（调试用）
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# 同目录的解析层：显式入栈，脚本被以任何方式启动都能找到 tutorial_core
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tutorial_core as core  # noqa: E402 —— 必须在 sys.path 调整之后导入

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "roadmap.svg"

# --------------------------------------------------------------------------- 版面与配色

W = 1200            # 画布宽（README 正文栏宽约 800px，1200 缩到 100% 仍然清晰）
M = 24              # 画布外边距
BAND_PAD = 22       # 阶段色带的内边距
HEAD_H = 46         # 色带里「阶段名 + 课数」那一行的高度
CHIP_H = 44         # 课芯片高度
GAP_X = 14          # 芯片横向间距
GAP_Y = 10          # 芯片纵向间距
BOLD_FACTOR = 1.06  # 粗体比估算宽约 6%：名字后面紧跟副标题时，不乘这一下就会贴上
BAND_GAP = 18       # 色带之间的间距
PAD_X = 12          # 芯片内左右留白
LABEL_GAP = 10      # 芯片里「课号」与「标题」之间的间距
MIN_TITLE_W = 40    # 标题最少要留这么宽，否则宁可只显示课号

# 字号写死：README 里的 SVG 不能指望外部样式表，也不该跟随页面缩放变化
FS_TITLE = 32
FS_SUB = 15
FS_STAGE = 17
FS_STAGE_WHY = 13
FS_CHIP_ID = 14
FS_CHIP_TITLE = 14
FS_NOTE = 13

# 配色 = web/assets/app.css 的暗色主题变量（--bg/--card/--line/--fg/--muted/--accent/--accent-soft）。
# 抄同一套值是有意的：站点与 README 的这张图看起来要是同一个产品。
C_BG = "#0f1115"          # --bg
C_CARD = "#161a21"        # --card
C_LINE = "#242a33"        # --line
C_FG = "#e6e8eb"          # --fg
C_MUTED = "#9aa4b2"       # --muted
C_ACCENT = "#7aa2ff"      # --accent
C_ACCENT_DEEP = "#3b5bdb"  # 站点亮色主题的 --accent（用来做描边，深底上不刺眼）
C_SOFT = "#1b2233"        # --accent-soft（暗色主题）

FONT = "system-ui, 'Microsoft YaHei', 'PingFang SC', sans-serif"
MONO = "ui-monospace, SFMono-Regular, Consolas, 'Cascadia Mono', monospace"

GEN_NOTE = ("本图由 python scripts/build_roadmap_svg.py 生成，请勿手改 —— "
            "课号 / 阶段 / 标题全部取自课程 frontmatter（scripts/tutorial_core.py）。")


# --------------------------------------------------------------------------- 小工具

def esc(text: str) -> str:
    """XML 转义：课程标题里真的会出现 `&`（`A & B`）和 `<`（`<N>`），不转义就是坏文档。

    顺序不能反：`&` 必须第一个换，否则会把后面换出来的 `&amp;` 再换一遍。
    """
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def num(value: float) -> str:
    """数字 → 属性字符串：整数不写小数点（`x="361"`），免得满屏 `361.0` 的噪音。"""
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


def char_width(ch: str, size: float) -> float:
    """单字符宽度估算：CJK / 全角标点算一个字号，其余算 0.55 个字号。

    估错的代价是不对称的：**估大**只会让标题早截几个字，**估小**会让文字溢出
    芯片压到隔壁上。所以门槛设在「宁可早截」这一侧。
    """
    if ch == " ":
        return size * 0.28
    return size if ord(ch) > 0x2E80 else size * 0.55


def text_width(text: str, size: float) -> float:
    return sum(char_width(c, size) for c in text)


def clip(text: str, max_w: float, size: float) -> str:
    """按估算宽度截断，加 `…`。`…` 自己也占宽度，所以要留出它的位置。"""
    if text_width(text, size) <= max_w:
        return text
    ell = "…"
    budget = max_w - text_width(ell, size)
    out: list[str] = []
    used = 0.0
    for ch in text:
        w = char_width(ch, size)
        if used + w > budget:
            break
        out.append(ch)
        used += w
    # 极端情况（max_w 小到放不下任何字）退回空串，让调用方决定怎么显示
    return "".join(out).rstrip() + ell if out else ""


def text(x: float, y: float, content: str, size: float, fill: str,
         weight: str = "normal", font: str = FONT, anchor: str = "start",
         opacity: float | None = None, extra: str = "") -> str:
    """一行 `<text>`。所有属性写死在元素上：不引外部样式表，不依赖页面字体。"""
    attrs = [
        f'x="{num(x)}"', f'y="{num(y)}"', f'font-family="{font}"',
        f'font-size="{num(size)}"', f'fill="{fill}"',
    ]
    if weight != "normal":
        attrs.append(f'font-weight="{weight}"')
    if anchor != "start":
        attrs.append(f'text-anchor="{anchor}"')
    if opacity is not None:
        attrs.append(f'opacity="{num(opacity)}"')
    if extra:
        attrs.append(extra)
    return f'<text {" ".join(attrs)}>{esc(content)}</text>'


def rect(x: float, y: float, w: float, h: float, fill: str, rx: float = 0,
         stroke: str | None = None, dash: str | None = None) -> str:
    attrs = [f'x="{num(x)}"', f'y="{num(y)}"', f'width="{num(w)}"', f'height="{num(h)}"',
             f'fill="{fill}"']
    if rx:
        attrs.append(f'rx="{num(rx)}"')
    if stroke:
        attrs.append(f'stroke="{stroke}" stroke-width="1.2"')
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    return f'<rect {" ".join(attrs)}/>'


def dashed_line(x1: float, y1: float, x2: float, y2: float, color: str,
                dash: str = "7 6") -> str:
    """虚线分隔线 —— 「手绘感」的来源之一（圆头虚线的节奏像手画的短划线）。"""
    return (f'<line x1="{num(x1)}" y1="{num(y1)}" x2="{num(x2)}" y2="{num(y2)}" '
            f'stroke="{color}" stroke-width="1.2" stroke-dasharray="{dash}" '
            f'stroke-linecap="round"/>')


def grid(n: int) -> tuple[int, int]:
    """n 个芯片排成几列几行：最多 3 列（再多标题就被截得没法读了）。"""
    cols = min(max(n, 1), 3)
    return cols, (n + cols - 1) // cols


# --------------------------------------------------------------------------- 渲染

def render(lessons: list[dict], baseline: dict | None = None) -> str:
    """课程列表 + 出处基线 → 整份 SVG 文本（纯函数，不碰文件、不看时钟）。

    课程结构与 `tutorial_core.load_lessons` 一致（id/title/stage/minutes 足够）；
    解析层 `group_by_stage` 负责分组与阶段名，本函数不再自己查 `STAGES` 表
    —— 阶段名再抄一份，就会出现「站点写阶段 5、README 写阶段 5 但名字不一样」。
    """
    baseline = baseline or {}
    groups = core.group_by_stage(lessons)
    n_total = len(lessons)
    minutes = sum(int(l.get("minutes", 0)) for l in lessons)
    n_stages = len(groups)

    inner_x = M + BAND_PAD
    inner_w = W - 2 * (M + BAND_PAD)

    parts: list[str] = []
    A = parts.append

    # header_x = 两倍画布边距，让标题与色带里的文字不在同一条竖线上（视觉上更稳）
    head_x = 48

    def make_chip(x: float, y: float, w: float, lesson: dict, ready: bool) -> str:
        """一枚课芯片。`ready=False` 是「课程还没写」的形态（本仓库 32 课都已建）。"""
        fill = C_SOFT if ready else "none"
        stroke = C_ACCENT_DEEP if ready else C_MUTED
        dash = None if ready else "5 4"
        id_fill = C_ACCENT if ready else C_MUTED
        title_fill = C_FG if ready else C_MUTED
        lid = str(lesson.get("id", ""))
        title = str(lesson.get("title", ""))
        label_w = text_width(lid, FS_CHIP_ID)
        avail = w - 2 * PAD_X - label_w - LABEL_GAP
        # 芯片本身的文字可能与缩略不符，用 <title> 悬停显示全称（原生 tooltip，无需 JS）
        tip = f"{lid} {title}".strip()
        out = [rect(x, y, w, CHIP_H, fill, rx=10, stroke=stroke, dash=dash),
               text(x + PAD_X, y + CHIP_H / 2 + 5, lid, FS_CHIP_ID, id_fill, weight="600")]
        if avail >= MIN_TITLE_W:
            out.append(text(x + PAD_X + label_w + LABEL_GAP, y + CHIP_H / 2 + 5,
                            clip(title, avail, FS_CHIP_TITLE), FS_CHIP_TITLE, title_fill))
        return f"<g><title>{esc(tip)}</title>" + "".join(out) + "</g>"

    # --- 标题栏 -------------------------------------------------------------
    A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{{H}}" '
      f'viewBox="0 0 {W} {{H}}" role="img" aria-labelledby="rm-title rm-desc">')
    A('<title id="rm-title">Hermes Agent 教程路线图</title>')
    desc = (f"{n_total} 课 / {n_stages} 个阶段的学习路线图：每条色带是一个阶段，"
            f"课号与标题来自课程 frontmatter")
    A(f'<desc id="rm-desc">{esc(desc)}</desc>')
    A(f'<rect x="0" y="0" width="{W}" height="{{H}}" fill="{C_BG}"/>')

    A(text(head_x, 68, "Hermes Agent 教程路线图", FS_TITLE, C_FG, weight="700"))
    sub = f"{n_total} 课 / {n_stages} 个阶段 / 约 {minutes} 分钟"
    if baseline.get("version"):
        sub += f" · 出处基线 hermes v{baseline['version']}"
        if baseline.get("commit"):
            sub += f"（官方文档 {baseline['commit']}"
            sub += f" · {baseline['generated']}）" if baseline.get("generated") else "）"
    A(text(head_x, 98, sub, FS_SUB, C_MUTED))
    A(dashed_line(head_x, 118, W - head_x, 118, C_LINE))

    # --- 每个阶段一条色带 ---------------------------------------------------
    y = 140.0
    for group in groups:
        stage = group["stage"]
        rows_list = group["lessons"]
        cols, rows = grid(len(rows_list))
        band_h = HEAD_H + rows * CHIP_H + (rows - 1) * GAP_Y + BAND_PAD
        chip_w = (inner_w - GAP_X * (cols - 1)) // cols
        # 单列时（毕业项目只有 1 课）不要把芯片拉满整条色带：按三列的宽度来，
        # 读者看到的才是「同一套卡片、只是这行只有一张」，而不是一条空条
        chip_w = min(chip_w, (inner_w - 2 * GAP_X) // 3)

        A(rect(M, y, W - 2 * M, band_h, C_CARD, rx=14))
        # 左侧重色竖条：色带的视觉锚点（不用 <filter> 抖动，见文件头「已知限制」）
        A(rect(M, y + 10, 6, band_h - 20, C_ACCENT_DEEP, rx=3))

        done = sum(1 for l in rows_list if l.get("done", True))
        # 统一写「阶段 9 · 毕业项目」：不为毕业项目另起一套叫法（另起一套就等于
        # 在第二个地方抄了一份阶段表，迟早与 tutorial_core 的 STAGES 漂移）。
        name = f"阶段 {stage} · {group['name']}"
        A(text(inner_x, y + 32, name, FS_STAGE, C_FG, weight="700"))
        name_w = text_width(name, FS_STAGE) * BOLD_FACTOR   # 阶段名是粗体，见 BOLD_FACTOR
        why_y = y + 32
        if group["why"]:
            why = f"— {group['why']}"
            avail = inner_w - name_w - 14 - text_width(
                f"{done}/{len(rows_list)} 课就绪 · 约 {sum(int(l.get('minutes', 0)) for l in rows_list)} 分钟",
                FS_STAGE_WHY)
            if avail > 60:
                A(text(inner_x + name_w + 14, why_y, clip(why, avail, FS_STAGE_WHY),
                       FS_STAGE_WHY, C_MUTED))
        stage_min = sum(int(l.get("minutes", 0)) for l in rows_list)
        A(text(M + W - 2 * M - BAND_PAD, y + 32,
               f"{done}/{len(rows_list)} 课就绪 · 约 {stage_min} 分钟",
               FS_STAGE_WHY, C_ACCENT, anchor="end"))

        for i, lesson in enumerate(rows_list):
            cx = inner_x + (i % cols) * (chip_w + GAP_X)
            cy = y + HEAD_H + (i // cols) * (CHIP_H + GAP_Y)
            A(make_chip(cx, cy, chip_w, lesson, ready=bool(lesson.get("done", True))))

        y += band_h + BAND_GAP

    # --- 图例 + 生成说明 ----------------------------------------------------
    y += 4
    legend_h = 116
    A(rect(M, y, W - 2 * M, legend_h, C_CARD, rx=14))
    A(text(inner_x, y + 28, "图例", FS_STAGE, C_FG, weight="700"))

    # 两个样例芯片：把「已就绪 / 未建课」两种配色摆出来，而不是用文字描述颜色
    sample_y = y + 44
    done_w = 74
    A(rect(inner_x, sample_y, done_w, 28, C_SOFT, rx=8, stroke=C_ACCENT_DEEP))
    A(text(inner_x + 10, sample_y + 19, "L15", FS_CHIP_TITLE, C_ACCENT, weight="600"))
    A(text(inner_x + done_w + 10, sample_y + 19, "已就绪（本仓库 32 课都已建）",
           FS_CHIP_TITLE, C_FG))

    notdone_x = inner_x + 360
    A(rect(notdone_x, sample_y, done_w, 28, "none", rx=8, stroke=C_MUTED, dash="5 4"))
    A(text(notdone_x + 10, sample_y + 19, "L99", FS_CHIP_TITLE, C_MUTED, weight="600"))
    A(text(notdone_x + done_w + 10, sample_y + 19, "未建课（课程还没写时是这种虚线灰）",
           FS_CHIP_TITLE, C_MUTED))

    A(text(inner_x, y + 96, GEN_NOTE, FS_NOTE, C_MUTED))
    y += legend_h + M
    A("</svg>")

    svg = "\n".join(parts)
    # 高度是算出来的：占位符 {H} 最后统一替换，免得每一处都要先知道总高
    return svg.replace("{H}", num(y)) + "\n"


def build(repo: Path = REPO) -> str:
    """从仓库现状生成 SVG —— 解析全在 tutorial_core，本模块不自己读 frontmatter。"""
    return render(core.load_lessons(repo), core.source_baseline(repo))


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 README 用的 SVG 路线图")
    ap.add_argument("--check", action="store_true", help="只校验 docs/roadmap.svg 是否与课程集合一致")
    ap.add_argument("--stdout", action="store_true", help="打到标准输出，不写文件")
    args = ap.parse_args()

    content = build()
    if not core.load_lessons(REPO):
        print("lessons/ 下还没有课程，先写课再生成路线图。")
        return 0

    if args.stdout:
        print(content, end="")
        return 0

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current == content:
            print(f"docs/roadmap.svg 已同步（{len(core.load_lessons(REPO))} 课）。")
            return 0
        print("docs/roadmap.svg 与课程集合不同步：python scripts/build_roadmap_svg.py")
        # 打印差异而不是只报「不一致」：不同步的原因通常是某一课的标题/阶段变了
        diff = difflib.unified_diff(
            current.splitlines(), content.splitlines(),
            fromfile="docs/roadmap.svg（当前）", tofile="docs/roadmap.svg（重算）", lineterm="",
        )
        for i, line in enumerate(diff):
            if i >= 24:
                print("  … （差异过长，已截断）")
                break
            print(line)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8", newline="\n")
    lessons = core.load_lessons(REPO)
    # 注意：len(str) 是**字符数**，中文在 UTF-8 里占 3 字节 —— 报字节要 encode
    size = len(content.encode("utf-8"))
    # OUT 未必在仓库内（测试与自定义输出会指到别处），relative_to 会抛 ValueError
    try:
        shown = OUT.relative_to(REPO)
    except ValueError:
        shown = OUT
    print(f"写入 {shown}：{len(lessons)} 课 / "
          f"{len(core.group_by_stage(lessons))} 个阶段 / {size} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
