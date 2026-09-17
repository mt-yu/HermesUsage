#!/usr/bin/env python3
"""scripts/design_matrix.py —— 「UI 方案横向对比」的唯一数据源。

为什么把一张对比表写成 Python 模块
-----------------------------------
这一页上的每个数字都会被读者当真：平均分、排名、赢家是谁。如果它是一段手抄的
Markdown 表格，那么「改了评分表但正文里的结论没跟着改」这件事在页面上**看不出
来** —— 读者只会读到一句悄悄变假的话。所以：

1. 评分、维度、评述只写在这里，`build_site.py` 从它渲染 `/design.html`；
2. 平均分、排名、赢家全部由 `score()` / `ranking()` / `winner()` **现算**，
   正文里不出现手写的数字；
3. 「落地清单」里的 token **值**不在这个文件里抄一遍，而是在渲染时从
   `web/assets/css`（实际是 `web/assets/app.css`）里现读 —— 样式改了、
   文档没改，构建直接报错（`token_value()` 找不到就抛 SiteError）。

判据：`tests/test_design_matrix.py` 断言「页面上的赢家 == 现算的最高分」，
`tests/test_build_site.py` 断言「页面上印的 token 值 == app.css 里的值」。

评分口径
--------
10 个维度、每项 1~5 分、**等权平均**（用户的要求：多维度取平均值，最高分执行）。
分数是**作者按本项目的约束打的自评**，不是任何官方评分，也不是客观测量 ——
所以每个方案都同时给出「赢在哪」与「为什么不能直接搬」，让读者能自己反驳。
参照基线（改造前 / 改造后）是本站自己的两行，标了「参考」且**不参与排名**。
"""

from __future__ import annotations

import re

# 抓取/核对日期：本文件里所有外部事实都是这一天从官方页面读到的（见 SOURCES 的 url）
FETCHED = "2026-09-17"

# --------------------------------------------------------------------------- 维度

DIMENSIONS: list[dict[str, str]] = [
    {
        "key": "reading",
        "name": "长文阅读（中文正文）",
        "short": "长文阅读",
        "why": "读者 30 分钟里九成以上的时间在读中文正文。字号、行高（CJK 要比拉丁更松）、"
               "行宽、字族直接决定他能不能读完，而不是这一页好不好看。",
    },
    {
        "key": "ia",
        "name": "信息架构与导航",
        "short": "信息架构",
        "why": "40 课 + 学习地图 + 坑表 + 搜索。找不到入口的教程等于没有："
               "「多级目录 + 页内目录 + 全站搜索」这三者要同时成立。",
    },
    {
        "key": "color",
        "name": "色彩体系与双主题",
        "short": "色彩主题",
        "why": "明暗两套主题都要能读，层次靠语义 token 而不是手写色值；"
               "正文对比度要过 WCAG AA（4.5:1），次要文字也不能掉到 3:1 以下。",
    },
    {
        "key": "type",
        "name": "排版系统",
        "short": "排版",
        "why": "字号阶梯、字重、等宽数字。标题层级是初学者在长页面里的脚手架，"
               "字号乱跳会让他不知道自己读到哪一层了。",
    },
    {
        "key": "space",
        "name": "空间与网格",
        "short": "空间网格",
        "why": "间距刻度统一，才不会出现「这里 12px、那里 13px」的漂移；"
               "三栏布局的对齐全靠一套可复述的刻度。",
    },
    {
        "key": "motion",
        "name": "动效与反馈",
        "short": "动效反馈",
        "why": "打勾、切主题、开搜索都要有可见反馈；同时必须尊重 "
               "prefers-reduced-motion（有前庭敏感的用户会被动画伤到）。",
    },
    {
        "key": "a11y",
        "name": "无障碍",
        "short": "无障碍",
        "why": "键盘可达、焦点可见、指针目标 ≥24×24px（WCAG 2.2 SC 2.5.8）、语义正确。"
               "本站已有 skip-link 与大量 aria，不能因为换皮而倒退。",
    },
    {
        "key": "portable",
        "name": "零依赖可移植",
        "short": "零依赖",
        "why": "本站硬约束：无 npm、无 CDN 字体、构建期渲染成真 HTML。"
               "「必须装包才能用」的方案搬不进来 —— 这一项就是为此设的。",
    },
    {
        "key": "size",
        "name": "体积与性能预算",
        "short": "体积预算",
        "why": "离线版把整套 CSS 逐字内联进一个 HTML 供读者下载，"
               "样式表体积直接等于读者的下载量；运行时越少越好。",
    },
    {
        "key": "license",
        "name": "许可与可维护性",
        "short": "许可维护",
        "why": "能不能合法搬运这些值，以及 token 化程度决定「改一处会不会漏一处」。"
               "不许再分发的方案只能当参考，不能当底座。",
    },
]

DIM_KEYS = [d["key"] for d in DIMENSIONS]
SHORT = {d["key"]: d["short"] for d in DIMENSIONS}
MAX_SCORE = 5


# --------------------------------------------------------------------------- 方案

SYSTEMS: list[dict] = [
    {
        "key": "primer",
        "name": "GitHub Primer",
        "steward": "GitHub",
        "headline": "语义 token 两段式（primitive → semantic）+ 无障碍守则",
        "note": "GitHub 自家文档站的底座，token 以原生 CSS 变量发布，MIT。",
        "license": "MIT（primer/primitives、primer/css）",
        "urls": [
            ("Primer 首页", "https://primer.style/"),
            ("Primitives（token 体系）", "https://primer.style/foundations/primitives/"),
            ("无障碍守则", "https://primer.style/guides/accessibility/guidelines/"),
        ],
        "scores": {"reading": 4, "ia": 4, "color": 5, "type": 4, "space": 5,
                   "motion": 3, "a11y": 5, "portable": 5, "size": 4, "license": 5},
        "good": "唯一把「不许在组件里写裸值（hex/px），只能用语义 token」写成硬规则的方案"
                "（DESIGN_TOKENS_GUIDE.md 原文），而且这套 token 就是原生 CSS 变量："
                "零运行时、可直接抄值、MIT。它的 a11y 守则与本站既有的 skip-link / aria 传统同源。",
        "block": "组件库（primer/react）是 React 的，本站用不上；动效规范偏薄（它自己不靠动效表达层级）。",
    },
    {
        "key": "spectrum",
        "name": "Adobe Spectrum 2",
        "steward": "Adobe",
        "headline": "跨端一致 + 令牌化的「表达力」分层",
        "note": "桌面与移动同一套令牌，色彩与字体阶梯写得很细。",
        "license": "Apache-2.0（adobe/spectrum-css）",
        "urls": [("Spectrum", "https://spectrum.adobe.com/")],
        "scores": {"reading": 4, "ia": 4, "color": 5, "type": 4, "space": 5,
                   "motion": 4, "a11y": 5, "portable": 4, "size": 3, "license": 5},
        "good": "令牌分层的完备度与 a11y 条款都是第一梯队；字体与间距刻度写得比 Primer 更细。",
        "block": "整套 CSS 体量偏大（为跨端设计），本站只需要其中的排版与色彩两层。",
    },
    {
        "key": "carbon",
        "name": "IBM Carbon",
        "steward": "IBM",
        "headline": "2x 网格 + 完整动效规范",
        "note": "企业级设计系统里文档最齐的一套：网格、运动曲线、状态都有专页。",
        "license": "Apache-2.0（carbon-design-system/carbon）",
        "urls": [
            ("Carbon", "https://carbondesignsystem.com/"),
            ("2x Grid", "https://carbondesignsystem.com/elements/2x-grid/overview/"),
            ("Motion", "https://carbondesignsystem.com/elements/motion/overview/"),
        ],
        "scores": {"reading": 3, "ia": 4, "color": 5, "type": 4, "space": 5,
                   "motion": 5, "a11y": 5, "portable": 4, "size": 3, "license": 5},
        "good": "动效与时长的规范最完整（本站在动效那一项就是照它的口径定的："
                "短 100ms 级、标准 200ms 级、并且必须给 reduced-motion 留出口），2x 网格也对得上三栏布局。",
        "block": "为密集的企业界面而生：信息密度高、字号偏小，直接搬到「给初学者读的中文长文」上等于反着来。",
    },
    {
        "key": "geist",
        "name": "Vercel Geist",
        "steward": "Vercel",
        "headline": "极简、留白优先的文档视觉",
        "note": "Vercel 官方文档的观感来源：近乎无装饰，靠字距与留白分层。",
        "license": "Geist 字体 OFL-1.1（vercel/geist-font）；其余见官方页面",
        "urls": [
            ("Geist 设计系统", "https://vercel.com/geist/introduction"),
            ("Geist 色板", "https://vercel.com/geist/colors"),
        ],
        "scores": {"reading": 5, "ia": 4, "color": 4, "type": 5, "space": 4,
                   "motion": 4, "a11y": 3, "portable": 3, "size": 5, "license": 4},
        "good": "长文阅读与排版是它的强项：本文的「留白优先、装饰最少」这一条就是从它来的；"
                "字体以 OFL-1.1 发布，理论上可自托管。",
        "block": "它的观感与 Geist 自己那套字体绑定，而本站不许下载网络字体；"
                "a11y 不是它对外承诺的重点（没有 Primer 那样的无障碍守则页）。",
    },
    {
        "key": "fluent2",
        "name": "Microsoft Fluent 2",
        "steward": "Microsoft",
        "headline": "令牌化 + 材质（acrylic/mica）分层",
        "note": "把「层级」做成材质而不是阴影，令牌页有完整的语义命名。",
        "license": "MIT（microsoft/fluentui）",
        "urls": [("Fluent 2 Design Tokens", "https://fluent2.microsoft.design/design-tokens")],
        "scores": {"reading": 3, "ia": 4, "color": 5, "type": 4, "space": 5,
                   "motion": 4, "a11y": 4, "portable": 3, "size": 3, "license": 4},
        "good": "语义令牌的命名与分层很规范（color/typography/spacing/elevation 四类），"
                "本站的 `--shadow-*` 与 `--z-*` 分层参照了它的思路。",
        "block": "acrylic 材质依赖 backdrop-filter 与动态层叠，在长文阅读里是干扰；"
                "整套实现是 React 为主，搬值容易、搬结构难。",
    },
    {
        "key": "m3expressive",
        "name": "Material 3 Expressive",
        "steward": "Google",
        "headline": "情感化设计：形状、动效物理、色彩一起表达",
        "note": "2025-05-13 发布（官方 blog 原文日期），是 M3 的一次「表达力」升级。",
        "license": "Apache-2.0（开源实现；字体 Roboto 为 OFL）",
        "urls": [
            ("发布说明（Material 官网 blog）", "https://m3.material.io/blog/building-with-m3-expressive"),
            ("Material Design 3", "https://m3.material.io/"),
        ],
        "scores": {"reading": 3, "ia": 4, "color": 5, "type": 4, "space": 4,
                   "motion": 5, "a11y": 4, "portable": 2, "size": 3, "license": 4},
        "good": "动效与色彩的推进最激进（spring 物理、动态取色），适合「有情绪表达」的产品。",
        "block": "它要的是可交互的动效系统与运行时取色；一个静态教程站搬过来只能拿到最表层的配色，"
                "反而会得到一堆需要 JS 才成立的样式。",
    },
    {
        "key": "antd",
        "name": "Ant Design 5",
        "steward": "Ant Group / 社区",
        "headline": "三层算法令牌（Seed → Map → Alias）",
        "note": "中文语境下做得最深的一套：排版与字重就是按中日韩字形定的。",
        "license": "MIT（ant-design/ant-design）",
        "urls": [("定制主题（令牌算法）", "https://ant.design/docs/react/customize-theme")],
        "scores": {"reading": 4, "ia": 4, "color": 5, "type": 5, "space": 4,
                   "motion": 4, "a11y": 3, "portable": 2, "size": 2, "license": 5},
        "good": "中文排版这一项它是天花板：字号/行高/字重的默认值就是为 CJK 调的，"
                "本文的字号阶梯与中文行高就是照它的口径放宽的。",
        "block": "5.x 用 CSS-in-JS 在运行时算令牌：要装包、要 React、首屏要跑脚本。"
                "本站「无依赖 + 离线单文件」的约束与它正面冲突。",
    },
    {
        "key": "tailwind4",
        "name": "Tailwind CSS v4",
        "steward": "Tailwind Labs",
        "headline": "CSS-first 配置 + OKLCH/P3 色板",
        "note": "2025-01-22 发布（官方 blog 的发布日期），把令牌直接暴露成原生 CSS 变量。",
        "license": "MIT（tailwindlabs/tailwindcss）",
        "urls": [("v4.0 发布说明", "https://tailwindcss.com/blog/tailwindcss-v4")],
        "scores": {"reading": 3, "ia": 3, "color": 5, "type": 4, "space": 5,
                   "motion": 3, "a11y": 2, "portable": 4, "size": 3, "license": 5},
        "good": "P3/OKLCH 色板是本站在色彩那一项采纳的东西：同样的观感，"
                "在广色域屏上更准，而且对比度可以在 oklch 的亮度轴上直接调。"
                "间距刻度（4px 基准）也与本站一致。",
        "block": "它是工具而不是设计语言：不给信息架构、不给阅读排版、不给无障碍答案，"
                "而且常规用法要跑构建（本站不许 npm）。",
    },
    {
        "key": "radix",
        "name": "Radix Primitives + shadcn/ui",
        "steward": "WorkOS / shadcn",
        "headline": "无样式 + 可访问性交给库，样式留给自己",
        "note": "当下最主流的「组件照抄进仓库」路线，a11y 是它的卖点。",
        "license": "MIT（radix-ui/primitives、shadcn-ui/ui）",
        "urls": [
            ("Radix 无障碍说明", "https://www.radix-ui.com/primitives/docs/overview/accessibility"),
            ("shadcn/ui 文档", "https://ui.shadcn.com/docs"),
        ],
        "scores": {"reading": 3, "ia": 3, "color": 4, "type": 3, "space": 3,
                   "motion": 4, "a11y": 5, "portable": 2, "size": 3, "license": 5},
        "good": "焦点管理、`aria-*`、键盘交互的实践是业界标杆；本站搜索面板的「焦点不逸出」"
                "与冻结滚动这两条就是照它的模式做的（这原本是 v1.3 就有的行为，这里只是确认口径一致）。",
        "block": "它是 React 组件库：本站的交互是几十行原生 ES 模块，引入它等于把整个运行时搬进来。",
    },
    {
        "key": "apple-hig",
        "name": "Apple HIG · Liquid Glass",
        "steward": "Apple",
        "headline": "材质即层级：可交互层浮在内容层之上",
        "note": "WWDC25 引入的新材质：能动态弯折光线，随内容与交互变化。",
        "license": "未提供可再分发的许可（HIG 是规范文档，不开放搬运其资源）",
        "urls": [
            ("HIG · Materials", "https://developer.apple.com/design/human-interface-guidelines/materials"),
            ("WWDC25 · Meet Liquid Glass", "https://developer.apple.com/videos/play/wwdc2025/219/"),
        ],
        "scores": {"reading": 4, "ia": 4, "color": 5, "type": 4, "space": 4,
                   "motion": 5, "a11y": 5, "portable": 1, "size": 2, "license": 1},
        "good": "「可交互层浮在内容层之上」这一条被本站采纳：顶栏、侧栏、搜索面板是独立的一层，"
                "阅读正文是另一层 —— 这就是 sticky + 半透明 + 细分割线那套做法的来源。"
                "它对动效与无障碍的克制（动效必须能关）也是标杆。",
        "block": "材质效果依赖平台合成的模糊与折射，Web 上只能近似；"
                "而且 HIG 不含任何可再分发的令牌或资源，分数低在「搬不动」而不是「不好」。",
    },
]

# 参照基线：本站自己的两行，**不参与排名**（值来自改造前后的同一套口径自评）
BEFORE: dict = {
    "name": "本站（改造前 · 参考）",
    "scores": {"reading": 3, "ia": 4, "color": 3, "type": 3, "space": 3,
               "motion": 2, "a11y": 4, "portable": 5, "size": 3, "license": 5},
    "note": "能用、能读，但没有令牌层：颜色与间距散在各处硬写，动效只有一处 transition，"
            "暗色主题是「亮色的手改镜像」。",
}

AFTER: dict = {
    "name": "本站（改造后 · 参考）",
    "scores": {"reading": 5, "ia": 4, "color": 5, "type": 5, "space": 5,
               "motion": 4, "a11y": 5, "portable": 5, "size": 4, "license": 5},
    "note": "语义 token 三层落地（primitive → semantic → component），明暗两套都按对比度定；"
            "动效有时长/缓动令牌并受 reduced-motion 管辖；字号阶梯用 clamp 流体化。",
    # 每条自评都要给出一条「读者自己能跑」的核验方式，否则不许写进表中
    "checks": {
        "reading": "在课页把窗口拖到 1440px：正文行宽 ≤74ch、中文行高 1.75（`.lesson { max-width: var(--measure) }`、`--leading`）",
        "ia": "侧栏「入口」里出现「设计对比」；这一页与 `/map.html`、`/pitfalls.html` 三页互链",
        "color": "切暗色后 `--bg` / `--fg` 换成第二套语义值（DevTools 看 `:root[data-theme=\"dark\"]`）；本页的对比度表是构建期从 app.css 现算的",
        "type": "h1~h3 用 `--step-1..3` 阶梯，标题随视口在 1.3125rem~1.75rem 间流体缩放",
        "space": "间距只取 `--space-1..8`（4px 基准）：在 `web/assets/app.css` 里搜 `padding: 13px` 这类裸值应当是 0 处",
        "motion": "打勾/切主题有过渡；系统开启「减少动态效果」后过渡归零（`prefers-reduced-motion` 那段规则）",
        "a11y": "Tab 走一遍顶栏与侧栏：焦点环可见（`:focus-visible`）；指针目标 ≥24px（`--target-min`）；skip-link 仍在首位",
        "portable": "仍是「一个 CSS 文件 + 原生 ES 模块」：`package.json` 无 dependencies、样式表里无 `@import`/`url()`",
        "size": "**单个** CSS 文件、没有第二份样式来源；本页顶部按构建时的真实字节数写明它多大（离线版逐字内联的也是它）",
        "license": "只搬 MIT / Apache-2.0 方案的值与规则（Primer / Tailwind / Carbon / Fluent）；Apple HIG 与 Spectrum 只当参考，不搬资源",
    },
}

# --------------------------------------------------------------------------- 采纳清单

# 赢家之外从其他方案采纳的具体做法（每条都指到落地的 token / 规则）
ADOPTED: list[dict[str, str]] = [
    {
        "from": "Tailwind CSS v4",
        "what": "广色域色板：先给 sRGB 兜底值，再用 `@supports (color: oklch(0% 0 0))` 覆盖成 oklch",
        "where": "`--accent` / `--bg` / `--fg` 等语义色的 primitive 定义",
    },
    {
        "from": "IBM Carbon",
        "what": "动效按时长分档（快 120ms / 标准 200ms / 慢 320ms）并给出统一缓动曲线",
        "where": "`--dur-fast` / `--dur` / `--dur-slow` / `--ease-standard`",
    },
    {
        "from": "Vercel Geist",
        "what": "留白优先：卡片不加阴影，靠 1px 细线与间距分层；正文行宽收在 74ch",
        "where": "`.card` / `--measure`",
    },
    {
        "from": "Radix + shadcn/ui",
        "what": "焦点可见是一等公民：全局 `:focus-visible` 才画环，鼠标点击不画",
        "where": "`--focus-ring` + `:focus-visible` 规则",
    },
    {
        "from": "Apple HIG",
        "what": "层级靠「层」而不是靠阴影：顶栏/侧栏/搜索面板是一个独立的交互层",
        "where": "`.topbar` 的半透明 + `backdrop-filter`、`--z-topbar` / `--z-overlay`",
    },
    {
        "from": "Ant Design 5",
        "what": "中文排版口径：正文 16px、行高放到 1.75 以上、标题字重不靠加粗堆叠",
        "where": "`body` 的 font 简写与 `.lesson h2/h3`",
    },
    {
        "from": "Microsoft Fluent 2",
        "what": "层级与圆角也令牌化（elevation / radius 分档），不在组件里写裸值",
        "where": "`--radius-sm/md/lg` / `--shadow-sm/md`",
    },
]

# 落地到 app.css 的 token（**值**渲染时从 app.css 现读，不在这里抄）
APPLIED_TOKENS: list[dict[str, str]] = [
    {"token": "--bg", "why": "页面底色（语义层，暗色有一套独立取值）"},
    {"token": "--fg", "why": "正文前景色，正文对比度 ≥7:1"},
    {"token": "--fg-muted", "why": "次要文字（时长、摘要），仍要 ≥4.5:1"},
    {"token": "--line", "why": "细分割线，同时用作卡片描边"},
    {"token": "--card", "why": "卡片/代码块的表面色（比底色略高一档）"},
    {"token": "--accent", "why": "链接、当前项、进度条：全站唯一强调色"},
    {"token": "--accent-soft", "why": "强调色的浅底（当前项背景、出处徽标）"},
    {"token": "--code-bg", "why": "行内代码与代码块底色"},
    {"token": "--focus-ring", "why": "键盘焦点环（3:1 以上，鼠标点击不显示）"},
    {"token": "--measure", "why": "正文行宽上限（74ch ≈ 中文 37 字/行）"},
    {"token": "--step-3", "why": "字号阶梯的最高一档（h1，随视口流体缩放）"},
    {"token": "--space-4", "why": "间距刻度的一档（4px 基准 ×4）"},
    {"token": "--radius-md", "why": "圆角分档：卡片与按钮"},
    {"token": "--shadow-md", "why": "浮层阴影（全站只有搜索面板这一层用）"},
    {"token": "--dur", "why": "标准过渡时长（Carbon 口径 200ms）"},
    {"token": "--ease-standard", "why": "统一缓动曲线"},
    {"token": "--target-min", "why": "指针目标最小边长（WCAG 2.2 SC 2.5.8 的 24px）"},
    {"token": "--z-topbar", "why": "层级令牌之一：顶栏 40 / 抽屉 50 / 搜索面板 60"},
]

# --------------------------------------------------------------------------- 出处

SOURCES: list[dict[str, str]] = [
    {"what": "Primer 的 token 硬规则「不要写裸值，只用语义 token」",
     "url": "https://primer.style/foundations/primitives/",
     "note": "原文见 primer/primitives 的 DESIGN_TOKENS_GUIDE.md：`Never use raw values (hex, px, etc.). Only use semantic tokens.`"},
    {"what": "Primer 无障碍守则（键盘、焦点、对比度）",
     "url": "https://primer.style/guides/accessibility/guidelines/", "note": ""},
    {"what": "Tailwind v4.0 发布日期 2025-01-22 与 P3/OKLCH 色板、CSS-first 配置",
     "url": "https://tailwindcss.com/blog/tailwindcss-v4", "note": "发布日期读自该页的 <time datetime>"},
    {"what": "Material 3 Expressive 发布日期 2025-05-13 与「动效物理 + 色彩」升级",
     "url": "https://m3.material.io/blog/building-with-m3-expressive", "note": "页面顶部原文日期"},
    {"what": "Apple HIG：平台有两种材质，Liquid Glass 是统一各平台设计语言的动态材质",
     "url": "https://developer.apple.com/design/human-interface-guidelines/materials",
     "note": "原文：`Liquid Glass is a dynamic material that unifies the design language across Apple platforms`"},
    {"what": "WWDC25「Meet Liquid Glass」场次",
     "url": "https://developer.apple.com/videos/play/wwdc2025/219/", "note": ""},
    {"what": "Carbon 2x 网格与动效规范",
     "url": "https://carbondesignsystem.com/elements/motion/overview/", "note": ""},
    {"what": "Fluent 2 设计令牌（color/typography/spacing/elevation 四类）",
     "url": "https://fluent2.microsoft.design/design-tokens", "note": ""},
    {"what": "Ant Design 5 的 Seed → Map → Alias 令牌算法",
     "url": "https://ant.design/docs/react/customize-theme", "note": ""},
    {"what": "Radix Primitives 的无障碍承诺（按 WAI-ARIA 实践与焦点管理）",
     "url": "https://www.radix-ui.com/primitives/docs/overview/accessibility", "note": ""},
    {"what": "Spectrum 2 跨端令牌",
     "url": "https://spectrum.adobe.com/", "note": ""},
    {"what": "Vercel Geist 设计系统",
     "url": "https://vercel.com/geist/introduction", "note": ""},
    {"what": "WCAG 2.2（现行 W3C Recommendation，页面标注 2024-12-12）",
     "url": "https://www.w3.org/TR/WCAG22/", "note": ""},
    {"what": "WCAG 2.2 SC 2.5.8 Target Size (Minimum)：指针目标至少 24×24 CSS 像素",
     "url": "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html", "note": ""},
    {"what": "prefers-reduced-motion（动效必须能关）",
     "url": "https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion", "note": ""},
    {"what": "oklch()：在广色域上表达颜色与亮度",
     "url": "https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/oklch", "note": ""},
    {"what": "light-dark()：用一条声明同时给出明暗两套取值",
     "url": "https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/light-dark",
     "note": "本站最终**没有**用它：它要求 color-scheme 由浏览器媒体查询驱动，"
             "而本站的主题是用户可手动切换的（存 localStorage），两者会打架 —— 记为「看过但不用」，"
             "免得下一个人再试一遍"},
]


# --------------------------------------------------------------------------- 计算

class MatrixError(RuntimeError):
    """矩阵数据本身不合法（维度对不上、分数越界）。构建期报错，不让坏数据上台。"""


def score(system: dict) -> float:
    """等权平均分，保留两位小数（正文里印的就是这个数）。"""
    values = [system["scores"][k] for k in DIM_KEYS]
    return round(sum(values) / len(values), 2)


def ranking(candidates: list[dict] | None = None) -> list[dict]:
    """按平均分从高到低排序；同分按 key 字母序（确定性，不靠 dict 顺序）。"""
    rows = list(candidates if candidates is not None else SYSTEMS)
    return sorted(rows, key=lambda s: (-score(s), s["key"]))


def winner() -> dict:
    return ranking()[0]


def validate() -> None:
    """数据自检：维度齐全、分数在 1~5、key 不重复。tests 与构建都调它。"""
    if len(SYSTEMS) < 2:
        raise MatrixError("至少要两个方案才谈得上对比")
    seen: set[str] = set()
    for system in SYSTEMS + [BEFORE, AFTER]:
        key = system.get("key") or system["name"]
        if key in seen:
            raise MatrixError(f"方案 key 重复：{key}")
        seen.add(key)
        missing = [k for k in DIM_KEYS if k not in system["scores"]]
        extra = [k for k in system["scores"] if k not in DIM_KEYS]
        if missing or extra:
            raise MatrixError(f"{key}: 维度对不上（缺 {missing}，多 {extra}）")
        for k, v in system["scores"].items():
            if not isinstance(v, int) or not 1 <= v <= MAX_SCORE:
                raise MatrixError(f"{key}.{k} 的分数必须是 1~{MAX_SCORE} 的整数，实际 {v!r}")


# --------------------------------------------------------------------------- 从 app.css 现读 token

ROOT_BLOCK_RE = re.compile(r":root\s*\{(.*?)\}", re.S)
CSS_VAR_RE = re.compile(r"(--[A-Za-z0-9-]+)\s*:\s*([^;]+);")


def css_root_tokens(css: str) -> dict[str, str]:
    """取 `:root { … }` 里声明的变量（浅色主题那一份）。

    只读第一个 :root 块是刻意的：第二个块（`@supports (color: oklch…)` 里那份）
    是覆盖值，页面要展示「兜底值 → 覆盖值」这件事，而不是把两个混起来。
    """
    m = ROOT_BLOCK_RE.search(css)
    if not m:
        raise MatrixError("app.css 里找不到 `:root { … }`：令牌层是这套视觉的地基，不能没有")
    return {name: value.strip() for name, value in CSS_VAR_RE.findall(m.group(1))}


def token_value(css: str, token: str) -> str:
    """读一个 token 的值；读不到就报错（页面上的值不许手抄，见模块 docstring）。"""
    tokens = css_root_tokens(css)
    if token not in tokens:
        raise MatrixError(
            f"app.css 的 :root 里没有 {token} —— 设计对比页会印它的值，"
            f"两处必须同源：要么在 app.css 里定义它，要么从 APPLIED_TOKENS 里去掉"
        )
    return tokens[token]


VAR_REF_RE = re.compile(r"var\(\s*(--[A-Za-z0-9-]+)\s*\)")
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def token_chain(css: str, token: str, max_depth: int = 6) -> list[str]:
    """`--bg` 的取值链：['var(--gray-0)', '#ffffff']。

    为什么要展示链条而不只是末值：本站的语义 token 指向 primitive
    （`--bg: var(--gray-0)`），只印「#ffffff」会看不出「暗色靠换 primitive 值
    就整站生效」这件事 —— 那正是这套分层存在的理由。深度上限防的是变量互相
    引用造成的死循环（写错时构建要停下，而不是挂住）。
    """
    value = token_value(css, token)
    chain = [value]
    for _ in range(max_depth):
        m = VAR_REF_RE.fullmatch(value.strip())
        if not m:
            return chain
        nxt = token_value(css, m.group(1))
        chain.append(nxt)
        value = nxt
    raise MatrixError(f"{token} 的取值链超过 {max_depth} 层，疑似循环引用")


def resolved_token(css: str, token: str) -> str:
    return token_chain(css, token)[-1]


def hex_of(css: str, token: str) -> str:
    """取一个 token 的**兜底 hex 值**（对比度就是按它算的）。

    取不到 hex 直接报错而不是「跳过这一行」：对比度表是这一页的可考证部分，
    少一行没人会发现，等于悄悄把一条断言删了。
    """
    value = resolved_token(css, token)
    if not HEX_RE.match(value):
        raise MatrixError(f"{token} 的最终值 {value!r} 不是 hex，对比度表算不了（别静默跳过）")
    return value


# 对比度表的检查项： (前景 token, 背景 token, 要求, 这是哪条要求)
CONTRAST_PAIRS: list[tuple[str, str, float, str]] = [
    ("--fg", "--bg", 7.0, "正文：WCAG AAA 对正文的建议值是 ≥7:1"),
    ("--fg", "--card", 7.0, "卡片里的正文，同一条要求"),
    ("--fg", "--code-bg", 7.0, "代码块正文，同一条要求"),
    ("--fg-muted", "--bg", 4.5, "次要文字：字号 12~13px，走 WCAG AA 小字 ≥4.5:1"),
    ("--fg-muted", "--card", 4.5, "卡片里的次要文字，同一条要求"),
    ("--accent", "--bg", 4.5, "链接与强调文字：WCAG AA ≥4.5:1"),
    ("--accent", "--accent-soft", 4.5, "侧栏「当前项」：强调色落在浅底上"),
    ("--focus-ring", "--bg", 3.0, "焦点环属于非文本元素：WCAG 2.2 要求 ≥3:1"),
]


def _lin(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_value: str) -> float:
    h = hex_value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.x 的相对对比度公式（(L1+0.05)/(L2+0.05)）。"""
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return round((hi + 0.05) / (lo + 0.05), 2)


def contrast_table(css: str) -> str:
    lines = ["| 前景 | 背景 | 实测对比度 | 要求 | 依据 |", "|---|---|---|---|---|"]
    for fg, bg, need, label in CONTRAST_PAIRS:
        ratio = contrast_ratio(hex_of(css, fg), hex_of(css, bg))
        verdict = "✅ 通过" if ratio >= need else "❌ 未达标（去改 app.css 的 primitive 值）"
        lines.append(
            f"| `{fg}` {hex_of(css, fg)} | `{bg}` {hex_of(css, bg)} | **{ratio}:1** | "
            f"≥{need}:1 | {label} · {verdict} |"
        )
    return "\n".join(lines)


def css_stats(css: str) -> dict[str, int]:
    return {"bytes": len(css.encode("utf-8")), "lines": css.count("\n") + 1}


# 图表用的短标签（图里放不下全名；与列表里的正式名字分开，避免为了排版去改正式名）
CHART_LABELS: dict[str, str] = {
    "primer": "Primer",
    "spectrum": "Spectrum 2",
    "carbon": "Carbon",
    "geist": "Geist",
    "fluent2": "Fluent 2",
    "m3expressive": "M3 Expressive",
    "antd": "Ant Design 5",
    "tailwind4": "Tailwind v4",
    "radix": "Radix + shadcn",
    "apple-hig": "Apple HIG",
}


def average_chart_svg(width: int = 760) -> str:
    """平均分条形图（确定性几何：没有随机数、没有时间戳，产物字节可重现）。

    颜色一律走 CSS 变量（`var(--accent)` 等）：这份 SVG 是内联在页面里的，
    所以暗色主题下自动跟着变，不需要第二套配色 —— 这也是「不写裸值」的应用。
    """
    rows = [(CHART_LABELS[s["key"]], score(s), False) for s in ranking()]
    rows += [("改造前（参考）", score(BEFORE), True), ("改造后（参考）", score(AFTER), True)]

    label_w, right_pad, row_h, top, bottom = 150, 46, 26, 10, 30
    plot_w = width - label_w - right_pad
    height = top + row_h * len(rows) + bottom
    domain = MAX_SCORE

    def bar_len(value: float) -> float:
        return round(plot_w * value / domain, 2)

    out = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-label="十个方案的等权平均分（满分 {domain} 分）：'
        + "、".join(f"{name} {value:.2f}" for name, value, _ in rows) + '">',
        f'<title>十个 UI 方案的等权平均分（满分 {domain} 分）</title>',
        # 网格与刻度
    ]
    for tick in range(domain + 1):
        x = round(label_w + bar_len(tick), 2)
        out.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + row_h * len(rows)}" '
                   f'stroke="var(--line)" stroke-width="1"/>')
        out.append(f'<text x="{x}" y="{height - 12}" text-anchor="middle" font-size="10" '
                   f'fill="var(--fg-muted)">{tick}</text>')
    for i, (name, value, reference) in enumerate(rows):
        y = top + i * row_h
        cy = y + row_h / 2
        w = bar_len(value)
        if reference:
            out.append(f'<rect x="{label_w}" y="{cy - 7}" width="{w}" height="14" rx="3" '
                       f'fill="none" stroke="var(--fg-muted)" stroke-width="1" stroke-dasharray="3 3"/>')
        else:
            fill = "var(--accent)" if i == 0 else "color-mix(in srgb, var(--accent) 42%, var(--line))"
            out.append(f'<rect x="{label_w}" y="{cy - 7}" width="{w}" height="14" rx="3" fill="{fill}"/>')
        out.append(f'<text x="{label_w - 8}" y="{cy + 4}" text-anchor="end" font-size="11" '
                   f'fill="var(--fg)">{escape_text(name)}</text>')
        out.append(f'<text x="{round(label_w + w + 6, 2)}" y="{cy + 4}" font-size="11" '
                   f'font-weight="600" fill="var(--fg-muted)">{value:.2f}</text>')
    out.append("</svg>")
    return "\n".join(out)


def escape_text(text: str) -> str:
    """图里只有方案名，但仍然统一转义：名字里将来出现 & 或 < 不该把 SVG 弄坏。"""
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# 图表在 markdown 里的占位行。build_site 把它换成 SVG；换不掉就报错
# （与模板占位符同样的思路：宁可构建失败，也不要读者在页面上看到一个标记）。
CHART_PLACEHOLDER = "{{design-chart}}"


# --------------------------------------------------------------------------- 渲染

def _avg(value: float) -> str:
    return f"{value:.2f}"


def matrix_table() -> str:
    """10 维度 × 10 方案 的矩阵 + 两行参照基线。数字全部现算。"""
    head = ["方案"] + [SHORT[k] for k in DIM_KEYS] + ["平均"]
    lines = ["| " + " | ".join(head) + " |",
             "|" + "---|" * len(head)]
    for s in ranking():
        name = f"**{s['name']}**" + (" ← 赢家" if s["key"] == winner()["key"] else "")
        cells = [name] + [str(s["scores"][k]) for k in DIM_KEYS] + [f"**{_avg(score(s))}**"]
        lines.append("| " + " | ".join(cells) + " |")
    for ref in (BEFORE, AFTER):
        cells = [f"_{ref['name']}_"] + [f"_{ref['scores'][k]}_" for k in DIM_KEYS] + [f"_{_avg(score(ref))}_"]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def systems_table() -> str:
    lines = ["| 方案 | 维护方 | 一句话主张 | 许可 | 官方入口 |", "|---|---|---|---|---|"]
    for s in SYSTEMS:
        links = " · ".join(f"[{label}]({url})" for label, url in s["urls"])
        lines.append(f"| **{s['name']}** | {s['steward']} | {s['headline']} | {s['license']} | {links} |")
    return "\n".join(lines)


def dimensions_table() -> str:
    lines = ["| # | 维度 | 为什么这条对本站重要 |", "|---|---|---|"]
    for i, d in enumerate(DIMENSIONS, 1):
        lines.append(f"| {i} | {d['name']} | {d['why']} |")
    return "\n".join(lines)


def verdict_table() -> str:
    """赢家与其余方案的差距：赢在哪 / 为什么不能直接搬。"""
    lines = ["| 排名 | 方案 | 平均分 | 赢在哪（采纳的） | 为什么不能直接搬（病灶） |", "|---|---|---|---|---|"]
    for i, s in enumerate(ranking(), 1):
        lines.append(
            f"| {i} | **{s['name']}** | {_avg(score(s))} | {s['good']} | {s['block']} |"
        )
    return "\n".join(lines)


def adopted_table() -> str:
    lines = ["| 来自 | 采纳了什么 | 落在哪 |", "|---|---|---|"]
    for a in ADOPTED:
        lines.append(f"| {a['from']} | {a['what']} | {a['where']} |")
    return "\n".join(lines)


def applied_tokens_table(css: str) -> str:
    """落地 token 表：**值从 app.css 现读**（见 token_value 的注释）。"""
    lines = ["| token | 在 app.css 里的取值链 | 用来做什么 |", "|---|---|---|"]
    for item in APPLIED_TOKENS:
        chain = token_chain(css, item["token"])
        shown = " → ".join(f"`{step}`" for step in chain)
        lines.append(f"| `{item['token']}` | {shown} | {item['why']} |")
    return "\n".join(lines)


def before_after_table() -> str:
    lines = ["| 维度 | 改造前 | 改造后 | 你怎么自己核验 |", "|---|---|---|---|"]
    for d in DIMENSIONS:
        k = d["key"]
        lines.append(
            f"| {d['name']} | {BEFORE['scores'][k]} | {AFTER['scores'][k]} | {AFTER['checks'][k]} |"
        )
    lines.append(
        f"| **平均** | **{_avg(score(BEFORE))}** | **{_avg(score(AFTER))}** | "
        "`python -m unittest tests.test_design_matrix` 会现算这两行 |"
    )
    return "\n".join(lines)


def sources_list() -> str:
    lines = []
    for s in SOURCES:
        note = f" —— {s['note']}" if s["note"] else ""
        lines.append(f"- [{s['what']}]({s['url']}){note}")
    return "\n".join(lines)


def render_markdown(css: str) -> str:
    """整页 markdown。所有数字（平均分、排名、token 值、对比度）都由本模块现算。"""
    w = winner()
    top = ranking()
    runners = "、".join(f"{s['name']} {_avg(score(s))}" for s in top[1:4])
    stats = css_stats(css)
    return "\n".join([
        "# 设计对比：把市面上的 UI 方案横着比一遍",
        "",
        "这一页记录本站的视觉系统是怎么选出来的：**10 套 2025—2026 年在用的 UI 方案**，"
        f"按 **{len(DIMENSIONS)} 个维度**逐个打分（每项 1~5 分），取**等权平均**，最高分的方案被采用。"
        "分数是作者按本项目的约束打的自评，不是官方评分；每个方案的「赢在哪 / 为什么不能直接搬」都写在下面，"
        "你可以逐条反驳。",
        "",
        "> **一句话结论**：赢家是 **GitHub Primer**（平均 "
        f"**{_avg(score(w))}** 分，第二名是 {runners}）。本站照它的两条主规则重写了样式表 —— "
        "语义 token 分层（不写裸值）、以及把无障碍当硬约束；其余方案里能搬的几件东西"
        "（P3 色板、动效时长、焦点策略、中文排版口径）也一并采纳，清单在下面。",
        "",
        f"落地后的样式表就是 `web/assets/app.css`：**{stats['bytes']:,} 字节 / {stats['lines']} 行**"
        "（这个数字是构建时按文件真实字节数写的，不是手抄的），没有第二个样式来源。",
        "",
        "## 比的是什么",
        "",
        systems_table(),
        "",
        f"这套 10 个方案的分数、评述与出处，都写在一个可以执行的文件里："
        f"`scripts/design_matrix.py`。平均分、排名、赢家、下面的 token 值与对比度**全部是渲染时现算的**，"
        f"正文里没有一个手写的数字（外部事实的读取日期：{FETCHED}）。",
        "",
        "## 怎么打分",
        "",
        "十个维度、等权、每项 1~5 分。维度不是「好看不好看」这类无法证伪的词，"
        "而是本站真实存在约束的十个面：",
        "",
        dimensions_table(),
        "",
        "## 矩阵（十个维度 × 十个方案）",
        "",
        matrix_table(),
        "",
        "矩阵最后两行是**本站自己的前后对照**（斜体、标了「参考」，不参与排名）。"
        "「改造后」的每一格都给出了一条「你自己怎么核验」的操作，见下文的对照表。",
        "",
        "### 平均分条图",
        "",
        CHART_PLACEHOLDER,
        "",
        "条长按满分 5 分画，虚线框的两行是本站的前后对照（不参与排名）。"
        "这张图是构建期生成的 SVG：没有随机数、没有时间戳，颜色全部走 CSS 变量，"
        "所以暗色主题下它跟着换色，不需要第二套配色。",
        "",
        "## 赢家与差距",
        "",
        verdict_table(),
        "",
        "## 从输家身上也拿了东西",
        "",
        "对比的意义不是选一个偶像照抄，而是**把每家最强的那一条抽出来**。"
        "下面每一条都已经落进本站的样式表：",
        "",
        adopted_table(),
        "",
        "## 落地：本站现在的令牌表",
        "",
        "赢家 Primer 的核心规则是「不要写裸值，只用语义 token」。本站照此把颜色、间距、圆角、"
        "阴影、动效时长、层级全部收进一层变量，并且分了三层：primitive（只有这里出现色值）→ "
        "semantic（按角色命名，组件只认这一层）→ component（页面级）。"
        "下表是构建时从 `web/assets/app.css` **现读**出来的取值链（不是手抄的副本）："
        "样式表改了而这一页没跟着改，构建会直接失败。",
        "",
        applied_tokens_table(css),
        "",
        "暗色主题是同一套语义 token 的第二份取值（`:root[data-theme=\"dark\"]` 换掉 primitive 的值），"
        "所以组件规则里一条 `data-theme` 判断都不需要 —— 这也是「不写裸值」带来的直接好处。",
        "",
        "## 对比度实测（也是现算的）",
        "",
        "无障碍不是「看起来还行」：下面每一行都是构建时用 WCAG 的相对对比度公式"
        "（(L1+0.05)/(L2+0.05)）从 app.css 的 token 值算出来的，站在读者这边的判据是"
        "**正文 ≥7:1、小字与链接 ≥4.5:1、非文本元素 ≥3:1**：",
        "",
        contrast_table(css),
        "",
        "这一栏刻意只算 **sRGB 兜底值**：现代浏览器会走 `@supports (color: oklch(…))` 里的覆盖值，"
        "但那两个值在 oklch 里的**明度（L）相同**，所以对比度不变；"
        "唯一被推出 sRGB 之外的是强调色的 chroma（P3 屏更饱和），它不改变亮度。",
        "",
        "## 改造前后（同一套维度自评）",
        "",
        before_after_table(),
        "",
        "## 你怎么自己复核",
        "",
        "1. **看矩阵对不对**：`python -m unittest tests.test_design_matrix` —— 会检查"
        "「页面上的赢家 == 现算的最高分」「每个方案都有十个维度的分数」「分数都在 1~5」"
        "「这一页印的 token 值 == app.css 里的值」「对比度表每一行都达标」。",
        "2. **看落地有没有生效**：样式表就是 `web/assets/app.css` 这一个文件；"
        "打开任意页面按 `Ctrl+Shift+I`，在 `:root` 上能看到上表的每一个变量与实时值。",
        "3. **看动效克不克制**：系统设置里开「减少动态效果」，刷新页面 —— 过渡与动画应当全部归零"
        "（搜索面板也不再有缩放动画）。",
        "4. **看它是不是真的零依赖**：`package.json` 没有 dependencies；"
        "样式表里没有 `@import`、没有 `url()`、没有网络字体。断网打开本地预览，观感不变。",
        "5. **看这一页自己有没有过期**：任何一处改动后跑 `python scripts/check.py`，"
        "它会重建站点并做站内链接自检；token 对不上时构建会直接报错。",
        "",
        "## 出处",
        "",
        f"下面每条都是 {FETCHED} 当天从官方页面读到的原文（不是二手转述；"
        "Material 3 Expressive 与 Apple HIG 两页是渲染后的正文，用真实浏览器读的）。",
        "",
        sources_list(),
        "",
    ])


def as_json(css: str | None = None) -> dict:
    """机器可读版本 → `site/data/design.json`（与页面同一个数据源，供脚本消费）。"""
    ranked = ranking()
    pos = {s["key"]: i + 1 for i, s in enumerate(ranked)}
    data = {
        "fetched": FETCHED,
        "method": {
            "dimensions": len(DIMENSIONS),
            "scale": f"1~{MAX_SCORE}",
            "aggregate": "equal-weight mean",
            "winner_rule": "highest mean, ties broken by key ascending",
        },
        "dimensions": DIMENSIONS,
        "systems": [
            {
                "key": s["key"],
                "name": s["name"],
                "steward": s["steward"],
                "headline": s["headline"],
                "license": s["license"],
                "urls": [{"label": label, "url": url} for label, url in s["urls"]],
                "scores": s["scores"],
                "mean": score(s),
                "rank": pos[s["key"]],
            }
            for s in ranked
        ],
        "reference": {
            "before": {"name": BEFORE["name"], "scores": BEFORE["scores"], "mean": score(BEFORE)},
            "after": {"name": AFTER["name"], "scores": AFTER["scores"], "mean": score(AFTER)},
        },
        "winner": ranked[0]["key"],
        "adopted": ADOPTED,
        "sources": SOURCES,
    }
    if css is not None:
        data["stylesheet"] = {"path": "web/assets/app.css", **css_stats(css)}
        data["applied_tokens"] = [
            {**item, "chain": token_chain(css, item["token"])} for item in APPLIED_TOKENS
        ]
        data["contrast"] = [
            {
                "fg": fg, "bg": bg, "label": label, "required": need,
                "ratio": contrast_ratio(hex_of(css, fg), hex_of(css, bg)),
            }
            for fg, bg, need, label in CONTRAST_PAIRS
        ]
        for row in data["contrast"]:
            row["pass"] = row["ratio"] >= row["required"]
    return data
