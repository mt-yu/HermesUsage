---
name: hermesusage-site-frontend
description: "Use when changing the HermesUsage site frontend: web/, the templates, or the built pages."
version: 1.0.0
author: HermesUsage
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [frontend, site, css, rendering, regression-test]
    related_skills: [hermes-tutorial-authoring, session-journal]
---

# 改 HermesUsage 站点的前端

站点是**编译产物**：`lessons/` + `web/` → 跑 `scripts/build_site.py` → `site/`（不进 git）。
本技能只管前端那一半（标记、CSS、`web/assets/*.js`），课程正文的规范见 `hermes-tutorial-authoring`。

## 何时用

- 用户说「站点上某个地方显示不对 / 不好看 / 想加个入口」；
- 你要动 `web/assets/app.css`、`web/assets/app.js`、`web/partials/layout.html`、
  或 `scripts/build_site.py` 里的 `render_*` 函数；
- 你要给侧栏/导航/卡片加一个入口。

**不要**手改 `site/` 里的任何文件（`.gitignore` 里，下次构建即被覆盖）。

## 铁律：渲染层的 bug 看不见，必须去浏览器里量

门禁 + 单测 + 链接自检**全绿也可能很丑**。2026-09-18 实测：侧栏「入口」下的
「学习地图」在页面里是**竖排**（4 行 / 103px 高，一个字一行），而 `check.py` 六项全绿 ——
它只看链接与文本，不看谁落在哪一列。

所以改前端的最小闭环是三步，**缺一步都不算改完**：

```bash
python scripts/build_site.py                  # ① 重建（改 web/ 后必须）
python scripts/serve.py --port 8137 --no-build &   # ② 本地起站（别用 python -m http.server，.js 的 MIME 不对）
# ③ 真实浏览器里量：行盒数量 / 高度 / 左边缘，而不是「看起来还行」
```

用 `browser_exec` + `js(...)` 量，别靠肉眼：

```javascript
// 一个汉字一行 = getClientRects() 返回 4 个矩形（典型症状）
const r = document.createRange(); r.selectNodeContents(a.querySelector('.nav-title'));
r.getClientRects().length                     // 期望 1；4 就是竖排
a.getBoundingClientRect().height              // 期望 32；103 就是被折了 4 行
```

顺带要量/看的还有：`getComputedStyle(icon).color`（跟不跟主题）、
`sidebar.scrollWidth === sidebar.clientWidth`（有没有横向溢出）、
悬停态（CDP `CSS.forcePseudoState`）、窄屏抽屉（`Emulation.setDeviceMetricsOverride` 390×844）、
以及 `window.__errs`（注入 `error` + `unhandledrejection` 监听，别只看控制台刷不刷红）。

## 契约：网格的列数 = 子元素个数

侧栏那条坑的根因，值得当成通用规则：

- `.nav-stage li a` 是四列网格（`14px 34px minmax(0,1fr) auto`），列数是按**课程行**的
  四个 span（`○ / 课号 / 标题 / 分钟`）定的；
- 普通条目（「入口」「规范与出处」）只有一个 span，落进 14px 的第一列就被**逐字折行**；
- 修法有两半，缺一半就会复发：**CSS 把网格限定到 `li[data-lesson] a`**，
  **标记里给普通条目「内联 SVG 图标 + `<span class="nav-title">`」的 flex 结构**。

同类检查：写 `grid-template-columns` 之前先数一遍子元素；「图标 + 一行文字」用 flex。

图标规矩：内联 SVG（`build_site.NAV_ICONS` + `nav_icon()`），`stroke="currentColor"`
跟主题、`aria-hidden="true"` 对读屏隐藏、**不许引外链** —— `offline.html` 断网也要能读，
图标字体/CDN 在无网时就是一个空方块。别用 emoji（跨平台字号与基线不一致）。

## 加一个回归测试（约定俗成）

纯渲染的坑用「标记与 CSS 的契约」钉住，参照
`tests/test_build_site.py::TestSidebarEntriesAreNotVertical`：

- 结构：用 `html.parser`（`SidebarAnchorTextCollector`）数 `<a>` 的**直接文本子节点** ——
  裸文本正是会被折进窄列的那种；正则数不清嵌套深度；
- 样式：抽出选择器的声明块，断言 `grid-template-columns` **只**出现在
  `li[data-lesson]` 那条规则里；
- 图标：断言内联 SVG 有 `stroke="currentColor"` / `aria-hidden="true"` / 不含 `http`。

**先证明这个测试能抓到旧写法**（把旧标记喂给 collector，看它是否报出 `['学习地图']`），
否则你写的是一条永远绿的断言。

## 收尾

```bash
python scripts/check.py       # 全量：门禁 + 单测 + 站点自检（前端唯一可信的验收入口）
python scripts/journal.py commit --kind fix --title "…" --scope site \
    --summary "…" --learned "…"
```

还要落到文档：`docs/manual-qa.md`（加一条能被人手工验的浏览器条目，并说明哪半已进单测）、
`.hermes.md` 第 6 节已知坑表（现象 / 真实原因 / 处理三段，现象照抄用户的原话）。

## 常见坑

- **只改 CSS 不改标记（或反过来）**：两半是互补的，只做一半能修好当前这一处，
  下一次「加个普通条目」又会竖排。单测同时守两半。
- **同一条 CSS 规则里塞两种布局**：`.nav-stage li a` 一旦再写回 grid，普通条目立刻复发；
  测试断言 `grid-template-columns` 在样式表里只出现一次（4 列那一份）。
- **`site/` 里的 `data/design.json` 是现读现算的产物**：改了 `app.css` 的 `:root` 令牌
  或字节数，必须重建站点，否则 `/design.html` 印的是旧值（构建会报错，别手改 JSON）。
- **忘了重跑 `build_site.py` 就截图**：浏览器里看到的是上一版；`serve.py` 带 `no-store`，
  但磁盘上的文件它不会替你重建（`--no-build` 时）。
- **顶层 `const/let` 写在 `boot();` 之后** → 交互全哑且不报错（TDZ + 未处理的 Promise 拒绝）。
  顶层声明一律放在 `boot();` 之前，`tests/js/app-module-order.test.js` 已钉住。
