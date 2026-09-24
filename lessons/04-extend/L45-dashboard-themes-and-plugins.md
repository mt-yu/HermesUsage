---
id: L45
title: 魔改 Web 面板：主题与插件
stage: 4
level: 进阶
minutes: 30
prereq: [L41]
tags: ["Web 面板", "dashboard", "主题", "插件", "shell slot"]
sources: [extending-the-dashboard, web-dashboard]
updated: 2026-09-24
---

# L45 · 魔改 Web 面板：主题与插件

> **一句话**：两个颜色就能改掉整个 Web 面板的配色，一个 `manifest.json` 加一段 IIFE 就能给自己加一个 tab —— 全程不碰 Hermes 仓库。

## 你将学会

- 写一个只改两个颜色的主题 YAML，让背景、文字和所有派生色（卡片 / 边框 / 焦点环）一起变
- 说清 `~/.hermes/dashboard-themes/`（主题）与 `~/.hermes/plugins/<name>/dashboard/`（插件）这两条磁盘路径各认哪些文件
- 写一个出现在导航里的插件 tab（`manifest.json` + IIFE 调 `register`），再往一个 shell slot 里注入自己的组件
- 用带令牌的 `curl` 让新插件在不重启进程的前提下生效，并说清**哪些**改动必须重启
- 亲手触发两次失败：不带令牌的 `rescan` 请求（401）、未启用插件的 `/api/plugins/<name>/`（404）

**前置**：[[L41]] · **预计耗时**：30 分钟

## 先动手

主题是纯声明 —— **一个文件、两个颜色**，整页就变（以下命令在 Git Bash 里跑；PowerShell 没有 `grep` / `sed`）[[src:extending-the-dashboard]]：

```bash
mkdir -p ~/.hermes/dashboard-themes
```

```yaml
# ~/.hermes/dashboard-themes/neon.yaml
name: neon
label: Neon
description: Pure magenta on black

palette:
  background: "#000000"
  midground: "#ff00ff"
```

```bash
hermes dashboard
```

**你应该看到**（本机实测：首次运行会先构建 Web UI，本机这一步打印 `✓ built in 12.50s`；**产物落在安装树的 `hermes_cli/web_dist`**，不是仓库里的 `web/dist`）[[src:web-dashboard]]：

```
✓ built in 12.50s
```

已经有产物、只想直接伺服时加 `--skip-build`，启动日志会说明它用了哪份 dist：

```
→ Skipping web UI build (--skip-build); using dist at …hermes_cli\web_dist
```

刷新页面 → 点顶部栏的**调色板图标** → 选 **Neon**。背景变黑、文字与强调色变品红，卡片 / 边框 / 静音色 / 焦点环这些派生色由 CSS `color-mix()` 从那两个颜色重算出来 [[src:extending-the-dashboard]]。

不想点界面，就从命令行看主题列表：

```bash
curl -s http://127.0.0.1:9119/api/dashboard/themes
```

**你应该看到**（本机实测：这个端点**不需要令牌**，返回 JSON；`active` 是当前主题名，内置主题只回 `name` / `label` / `description`，**user 主题额外带一个 `definition`** —— 是你那份 YAML 归一化后的全量对象）：

```json
{
  "themes": [
    { "name": "default", "label": "Hermes Teal", "description": "Classic dark teal — the canonical Hermes look" },
    { "name": "neon", "label": "Neon", "description": "Pure magenta on black",
      "definition": { "name": "neon", "label": "Neon",
        "palette": { "background": { "hex": "#000000", "alpha": 1.0 },
                     "midground":  { "hex": "#ff00ff", "alpha": 1.0 },
                     "foreground": { "hex": "#ffffff", "alpha": 0.0 },
                     "warmGlow": "rgba(…)", "noiseOpacity": 1.0 } } }
  ],
  "active": "default"
}
```

本机实测：`palette.warmGlow`、`palette.noiseOpacity`、`foreground.alpha` 这些你**没写**的键都被补全了 —— 归一化会替你把缺的键按内置 `default` 填上（具体数值随主题不同，你机器上的派生值不必和上面逐字一致）[[src:extending-the-dashboard]]。

## 原理

### 主题：三层 YAML，认 `name:` 不认文件名

主题放 `~/.hermes/dashboard-themes/*.yaml`，**文件名无所谓，认的是文件里的 `name:` 字段**（惯例写成 `<name>.yaml`）；每个字段都可省，缺的键回落到内置 `default` 主题，所以一个主题可以小到一个颜色 [[src:extending-the-dashboard]]。

**① 调色板是三层 + 两个旋钮**，每层接受 `{hex, alpha}` 或裸 hex（裸 hex 的 alpha 默认 1.0）[[src:extending-the-dashboard]]：

| 键 | 管什么 |
|---|---|
| `palette.background` | 最底层画布色 —— 页面背景与卡片填充 |
| `palette.midground` | 正文与强调色 —— 大部分界面 chrome 都读它 |
| `palette.foreground` | 最上层高光；`default` 主题把它设成 alpha 0（不可见） |
| `palette.warmGlow` | `<Backdrop />` 的暗角颜色，`rgba(...)` 字符串 |
| `palette.noiseOpacity` | 颗粒叠加的倍数，0–1.2，越大越"砂" |

整条 shadcn 令牌链（card / popover / muted / border / primary / destructive / ring …）都由这三个颜色经 CSS `color-mix()` 派生 —— 改三个颜色，全 UI 跟着变 [[src:extending-the-dashboard]]。

**② 其余可调块**（都想改时再看，先动手那一步不需要）[[src:extending-the-dashboard]]：

| 块 | 内容 |
|---|---|
| `typography` | `fontSans` / `fontMono` / `fontDisplay` / `fontUrl`（注入 `<link>`，同一 URL 不会注入两次）/ `baseSize` / `lineHeight` / `letterSpacing` |
| `layout` | `radius`（级联到 `--radius-sm/md/lg/xl`）、`density`：`compact` 0.85× / `comfortable` 1.0× / `spacious` 1.2×（写进 `--spacing-mul`） |
| `layoutVariant` | `standard`（默认，单列 1600px 上限）/ `cockpit`（左侧 260px 导轨 + 主区）/ `tiled`（去掉宽度上限）。当前值暴露在 `document.documentElement.dataset.layoutVariant` |
| `assets` | 具名图片位，落成 CSS 变量 `--theme-asset-<name>`（另有 `-raw` 版本；`bg` 自动接到 backdrop） |
| `componentStyles` | 不写选择器就改组件 chrome，落成 `--component-<bucket>-<kebab>`；bucket 只有 `card` / `header` / `footer` / `sidebar` / `tab` / `progress` / `badge` / `backdrop` / `page` |
| `colorOverrides` | 直接指定某个 shadcn 令牌（`primary` → `--color-primary`），**只对当前主题有效，切主题即清空** |
| `customCSS` | 选择器级 CSS，注入成**一条** `<style data-hermes-theme-css>`，切换主题时清理；**上限 32 KiB** |

**③ 切换与持久化**：界面上点调色板图标，选择写进 `config.yaml` 的 `dashboard.theme`，重载后恢复 [[src:web-dashboard]]。等价接口是 **`PUT /api/dashboard/theme`**（注意：**读是复数 `themes`、写是单数 `theme`**），body `{"name": "midnight"}` [[src:extending-the-dashboard]]。本机实测（隔离 home）写出来是：

```yaml
dashboard:
  theme: l45-neon
```

同一选择器里还有 **Font** 一栏：它独立于主题覆盖正文字体（`config.yaml` 的 `dashboard.font`），换主题时保留，选 **Theme default** 清掉 [[src:web-dashboard]]。

**④ 内置主题**：文档那张表列了 7 套，差异不只在颜色，字体与版式也一起换 [[src:extending-the-dashboard]]：

| 主题（`name`） | 调色板 | 字体 | 版式 |
|---|---|---|---|
| Hermes Teal（`default`） | 深青 + 米白 | 系统栈 15px | 0.5rem 圆角，comfortable |
| Hermes Teal (Large)（`default-large`） | 同 default | 系统栈 18px，行高 1.65 | 0.5rem 圆角，spacious |
| Midnight（`midnight`） | 深蓝紫 | Inter + JetBrains Mono，14px | 0.75rem 圆角，comfortable |
| Ember（`ember`） | 暖绯红 + 青铜 | Spectral（衬线）+ IBM Plex Mono，15px | 0.25rem 圆角，comfortable |
| Mono（`mono`） | 灰阶 | IBM Plex Sans + IBM Plex Mono，13px | 0 圆角，compact |
| Cyberpunk（`cyberpunk`） | 黑底霓虹绿 | 通篇 Share Tech Mono，14px | 0 圆角，compact |
| Rosé（`rose`） | 粉 + 象牙 | Fraunces（衬线）+ DM Mono，16px | 1rem 圆角，spacious |

除 Hermes Teal 外都引用 Google Fonts，**第一次切过去时**才往 `<head>` 注入字体样式表 [[src:extending-the-dashboard]]。另外：较旧的 `web-dashboard` 快照说内置是 8 套，多一个浅色的 **Nous Blue**（`nous-blue`）[[src:web-dashboard]]；本机这个 release 的清单里确实有第 8 个（见「常见坑」最后一条）。

### 插件：一个目录，四件套

插件的磁盘形态是 `~/.hermes/plugins/<name>/dashboard/` —— 之所以嵌在 `dashboard/` 里，是因为同一个插件目录可以同时扩展 CLI/网关侧和面板侧 [[src:extending-the-dashboard]]：

```
~/.hermes/plugins/my-plugin/
├── plugin.yaml              # 可选 —— CLI/网关插件清单（见 [[L41]]）
├── __init__.py              # 可选 —— CLI/网关侧钩子
└── dashboard/
    ├── manifest.json        # 必需 —— tab 配置、图标、入口
    ├── dist/
    │   ├── index.js         # 必需 —— 预构建 JS bundle（IIFE）
    │   └── style.css        # 可选 —— 自定义 CSS
    └── plugin_api.py        # 可选 —— 后端路由（FastAPI）
```

**关键约束：插件不打包 React**，一切从 `window.__HERMES_PLUGIN_SDK__` 拿（`SDK.React`、`SDK.hooks.*`、`SDK.components.*`、`SDK.api`、`SDK.fetchJSON`、`SDK.utils.*`）。bundle 因此只有几 KB，也不会和面板的 React 版本打架 [[src:extending-the-dashboard]]：

```javascript
// ~/.hermes/plugins/my-plugin/dashboard/dist/index.js
(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;
  const { Card, CardHeader, CardTitle, CardContent } = SDK.components;

  function MyPage() {
    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, null, "My Plugin")),
      React.createElement(CardContent, null,
        React.createElement("p", { className: "text-sm text-muted-foreground" },
          "Hello from my custom dashboard tab.")));
  }

  window.__HERMES_PLUGINS__.register("my-plugin", MyPage);
})();
```

`manifest.json` 的字段 [[src:extending-the-dashboard]]：

| 字段 | 必需 | 说明 |
|---|---|---|
| `name` | 是 | 唯一标识，小写、可带连字符；URL 与注册都用它，**必须和 `register()` 的第一个参数一致** |
| `label` | 是 | 导航 tab 上显示的名字 |
| `description` | 否 | 简短描述（出现在面板的管理界面） |
| `icon` | 否 | Lucide 图标名，默认 `Puzzle`；**未知名字静默回落 `Puzzle`** |
| `version` | 否 | semver，默认 `0.0.0` |
| `tab.path` | 是 | tab 的 URL 路径，如 `/my-plugin` |
| `tab.position` | 否 | `"end"`（默认）、`"after:<path>"`、`"before:<path>"`，冒号后是**目标 tab 的路径段**（不带斜杠），如 `"after:skills"` |
| `tab.override` | 否 | 填一个内置路由（`"/"`、`"/sessions"`、`"/config"` …）来**替换**那一页 |
| `tab.hidden` | 否 | `true` = 注册组件与 slot，但导航里不加 tab（slot-only 插件用） |
| `slots` | 否 | **只给文档看** —— 真正注册发生在 bundle 里调 `registerSlot()` |
| `entry` | 是 | 相对 `dashboard/` 的 JS 路径，默认 `dist/index.js` |
| `css` | 否 | 注入成 `<link>` 的 CSS 文件路径 |
| `api` | 否 | FastAPI 路由文件，挂到 `/api/plugins/<name>/` |

**槽位（slot）** 让插件不用占整页也能插东西；多个插件可以占同一个 slot，按注册顺序叠着渲染 [[src:extending-the-dashboard]]：

- **shell 槽 10 个**：`backdrop`、`header-left`、`header-right`、`header-banner`、`sidebar`（**只在 `layoutVariant: cockpit` 下渲染**）、`pre-main`、`post-main`、`footer-left`、`footer-right`、`overlay`
- **页内槽 18 个**：`sessions` / `analytics` / `logs` / `cron` / `skills` / `config` / `env` / `docs` / `chat` 各带 `:top` 与 `:bottom`（`docs:top` 在 iframe 之上，`chat:*` 只在启用内嵌聊天时有效）

注册 API 就两个函数 [[src:extending-the-dashboard]]：

```javascript
window.__HERMES_PLUGINS__.register("my-plugin", MyPage);            // 主组件（tab / 被 override 的页）
window.__HERMES_PLUGINS__.registerSlot("my-plugin", "sessions:top", Banner);  // 往槽里插一个组件
```

加载生命周期（官方口径）：面板先暴露 SDK 与注册表 → `GET /api/dashboard/plugins` → 给每个 manifest 先注入 CSS 链接、再加载 JS 脚本文件 → IIFE 调 `register()` → 解析组件、加 tab、挂路由。插件脚本加载后**只有 2 秒**窗口调 `register()`，超时面板不再等它（之后再注册仍会出现，导航是响应式的）；脚本加载失败只在浏览器控制台警告，**不阻塞页面** [[src:extending-the-dashboard]]。

**发现优先级**（同名冲突时高优先级赢）[[src:extending-the-dashboard]]：

| 优先级 | 目录 | source |
|---|---|---|
| 1 | `~/.hermes/plugins/<name>/dashboard/` | `user` |
| 2 | `<仓库>/plugins/memory/<name>/dashboard/`、`<仓库>/plugins/<name>/dashboard/` | `bundled` |
| 3 | `./.hermes/plugins/<name>/dashboard/` | `project`（需要环境变量 `HERMES_ENABLE_PROJECT_PLUGINS`） |

另外有一条**没写在文档里、但会很浪费时间**的门（本机源码 + 本机实测）：`user` 源的插件必须出现在 `config.yaml` 的 `plugins.enabled` 里才会被列出/伺服，`bundled` 只要没被显式 disable 就行 —— 源码 `hermes_cli/web_routers/dashboard_ui.py::_plugin_activated()` 就是这么判的。而 `hermes plugins enable <手放插件>` 会报 `No plugin named '<name>'`，所以**只能手写 config.yaml**。

**后端路由** `plugin_api.py` 里导出模块级 `router = APIRouter()`，就挂到 `/api/plugins/<name>/` 下 [[src:extending-the-dashboard]]。它跑在面板进程里，可以直接 `from hermes_state import SessionDB`、`from hermes_cli.config import load_config` 读 Hermes 内部状态。安全上两句话：路由**在面板的鉴权门后面**（没登录/没令牌的请求根本到不了它）；但**别拿 `--host 0.0.0.0` 暴露一个跑着不可信插件的面板** —— 一个已认证会话同样能打到这些路由 [[src:extending-the-dashboard]]。

### 鉴权：本课最值钱的一段

先把事实摆平（本机实测 + 本 release 源码）：

**`/api/*` 默认要令牌，连 loopback 也一样。** 免令牌的白名单只有 8 条（源码 `hermes_cli/dashboard_auth/public_paths.py`）：

```
/api/health            /api/status
/api/config/defaults   /api/config/schema
/api/model/info        /api/dashboard/themes
/api/dashboard/plugins /api/cron/fire
```

其余一律要令牌 —— **包括 `/api/dashboard/plugins/rescan`、`/api/dashboard/plugins/hub` 和插件自己的 `/api/plugins/<name>/*`**。

令牌从哪来：页面 HTML 里注入了一行 `window.__HERMES_SESSION_TOKEN__="…"`（源码 `hermes_cli/web_server_dashboard.py`），必须用**专用头** `X-Hermes-Session-Token: <token>`（`Authorization: Bearer <token>` 这条老路也还认）；`?token=` 只对 `/api/files/download` 有效 [[src:extending-the-dashboard]]。

实测对照（同一台机器、同一个进程）：

```bash
# 不带令牌 —— 官方文档 troubleshooting 教的正是这条
curl -s http://127.0.0.1:9119/api/dashboard/plugins/rescan
# {"detail":"Unauthorized"}

# 从页面 HTML 取令牌，再带上专用头
TOK=$(curl -s http://127.0.0.1:9119/ | grep -oE '_SESSION_TOKEN__="[^"]+"' | head -1 | sed 's/.*="\(.*\)"/\1/')
curl -s -H "X-Hermes-Session-Token: $TOK" http://127.0.0.1:9119/api/dashboard/plugins/rescan
# {"ok":true,"count":3}
```

（那行正则能命中，是因为注入的全局名是 `window.__HERMES_SESSION_TOKEN__="…"`，`_SESSION_TOKEN__="` 只是它的后缀。`count` 是你机器上发现的插件数，本机是 3。）

唯一的例外是**静态资产**：`/dashboard-plugins/<name>/<path>` **故意不鉴权** —— 浏览器用 script / link 标签取插件文件时装不了头，所以这条路由靠别的约束兜底 [[src:extending-the-dashboard]]。本 release 的源码给它加了两道：只伺服**白名单后缀**（`.js` / `.css` / `.json` / 图片 / 字体 …），且**插件必须已启用**（`user` 源要求 `plugins.enabled`，`bundled` 要求没被 disable），否则一律 404 `{"detail":"Plugin not found"}`。

再往外一层：**绑定非 loopback 时会另起一套 cookie/OAuth 门** —— `hermes dashboard --host 0.0.0.0` 会让门生效，此时页面 HTML 里**不再注入**令牌；`--insecure` 从 2026 年 6 月硬化后已是 no-op；万一没有注册任何 provider，进程会**拒绝绑定**而不是降级放行（fail-closed）[[src:web-dashboard]]。所以「本课这套令牌活」只在 loopback 的默认启动方式下成立。

### 刷新语义：三个动词，别混

这是实际动手时最容易白折腾的地方，差异都是本机实测：

| 你改了什么 | 要做什么 | 本机实测 |
|---|---|---|
| 新增插件 / 改 `manifest.json`（如 `label`） | 带令牌 `GET /api/dashboard/plugins/rescan`（**不重启**） | 把 `label` 从 `L45 Demo` 改成 `L45 Demo v2`，rescan 后 `GET /api/dashboard/plugins` 立刻是 `L45 Demo v2` |
| `dist/index.js`、`dist/style.css`（UI bundle） | **刷新浏览器页面** | 页面重新加载后生效 |
| `plugin_api.py`（后端路由） | **重启 `hermes dashboard`** —— 路由只在进程启动时挂载 | 进程先起、插件后加：`GET /api/plugins/l45-demo/ping` → `404 {"detail":"Plugin not found"}`；重启后（插件在场）→ `200 {"pong":true,"from":"l45-demo"}` |
| 新增/修改主题 YAML | 刷新页面即可 | 主题是**读接口时现扫目录**（源码 `_discover_user_themes()` 在 `GET /api/dashboard/themes` 里现调），不用重启进程 |
| 插件未启用（不在 `plugins.enabled`） | 先启用 | 静态资产 `/dashboard-plugins/<name>/dist/index.js` 未启用时 404，启用后 200 |

## 亲手验证

本节所有数字都是本机实测（Windows 11 + Git Bash + Chromium）；插件那几项是在一个**隔离的 `HERMES_HOME`**、跑在端口 `9120` 的 dashboard 实例上量的。

### 验证一：主题是"真换了"，不是"看着像"

在浏览器里**用界面按钮**切（不是打 API）：把鼠标悬停在顶部调色板图标上，读它的 `title`：

| 你观察到的 | 说明什么 |
|---|---|
| 切之前：`Switch theme: Hermes Teal` | 按钮反映的是**当前生效**的主题 |
| 选 `L45 Neon` 之后：`Switch theme: L45 Neon` | 选择立刻生效，且这个按钮就是"我现在是谁"的读数 |

切完在同一页读 computed style（DevTools 控制台）：

| 读什么 | 本机实测值 |
|---|---|
| `getComputedStyle(document.body).backgroundColor` | `color(srgb 0 0 0)` |
| `getComputedStyle(document.body).color` | `color(srgb 1 0 1)` |
| `--background` | `color-mix(in srgb, #000000 100%, transparent)` |
| `--midground` | `color-mix(in srgb, #ff00ff 100%, transparent)` |
| `document.querySelectorAll('style[data-hermes-theme-css]').length` | `1` |
| 那条 style 的内容 | 含主题 YAML 里写的 `.l45-theme-marker` 规则 |

| 你观察到的 | 说明什么 |
|---|---|
| `--background` 是 `color-mix(...)` 而不是你写的 `#000000` | 面板不是"替换颜色"，而是把调色板喂进 `color-mix()` 现算派生色 [[src:extending-the-dashboard]] |
| `style[data-hermes-theme-css]` 恰好 **1** 条 | `customCSS` 是单条 scoped style，切换主题时复用/替换而不是叠加 —— 多刷几次主题它也不会变成 2 条 |

### 验证二：插件的三件套各就各位

| 你观察到的 | 说明什么 |
|---|---|
| 导航里出现插件 tab `L45 Demo`，点开路径是 `/l45-demo`，页面里出现 IIFE 渲染的自己的文字 | `register()` 生效，且 manifest 的 `name` 与 bundle 里传的名字对上了（对不上面板就不认） [[src:extending-the-dashboard]] |
| 页面里出现插件自己那份样式表的引用（`dashboard-plugins/l45-demo/dist/style.css`） | `manifest.css` 被注入成样式表链接 |
| 插件页元素的 computed `border-left: 4px rgb(255, 0, 255)`、`padding-left: 8px` | 那份 CSS 真的应用上了（值来自插件自己的 style.css，不是面板的） |
| `header-banner` slot 的节点与文本出现在页面里 | `registerSlot()` 生效，组件真的挂进了 shell 槽 |

### 验证三：全局对象 + 令牌门

DevTools 控制台（两个都必须是 `object`）：

```javascript
typeof window.__HERMES_PLUGIN_SDK__   // "object"
typeof window.__HERMES_PLUGINS__      // "object"
```

命令行侧，把"401 → 200"这对现象亲手跑一遍（命令见「原理 → 鉴权」）：先不带 `-H` 打一次 `rescan`，看到 `{"detail":"Unauthorized"}`；再用 `TOK=` 那行取令牌、带上 `X-Hermes-Session-Token` 打第二次，看到 `{"ok":true,"count":3}`。

| 你观察到的 | 说明什么 |
|---|---|
| 同一个 URL、同一个进程，只差一个头就 401/200 | 鉴权**不是**按"是不是本机"判的，而是按请求里有没有那张令牌 [[src:web-dashboard]] |
| 插件自己的 `/api/plugins/<name>/*` 也一样要头 | 它落在面板的通用 `/api/*` 门后面（`/api/dashboard/plugins（列表）` 才是那 8 条免令牌之一） [[src:extending-the-dashboard]] |

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `curl .../api/dashboard/plugins/rescan` 直接返回 `{"detail":"Unauthorized"}` | 它不在那 8 条免令牌白名单里 —— **官方 troubleshooting 教的正是这条不带头的 curl** | 从页面 HTML 取令牌后加 `-H "X-Hermes-Session-Token: $TOK"`；`TOK=` 那行见「原理 → 鉴权」 |
| 主题 YAML 语法写错了，界面上没有它，`~/.hermes/logs/errors.log` 也没多一行 | 官方文档说解析失败会记到 `errors.log`，但**本 release 的源码是静默跳过**（`_discover_user_themes` 里 `except Exception: continue`）；本机实测放一个语法错误的 YAML 后，主题列表里没有它、errors.log 也没有新行 | 坏主题是"**静默不出现**"：拿 `curl -s http://127.0.0.1:9119/api/dashboard/themes` 的返回对照 —— 文件在磁盘上、列表里没有 = YAML 没解析成功 |
| 主题文件明明放着，列表里就是没有 | 扫描的 glob 只认 `*.yaml`（源码 `themes_dir.glob("*.yaml")`），而官方 troubleshooting 写的是"`.yaml` 或 `.yml`" | 后缀统一写 `.yaml` |
| 手放的插件不出现在面板里 | `user` 源插件必须出现在 `config.yaml` 的 `plugins.enabled` 里才会被列出/伺服（源码 `_plugin_activated()`）；`hermes plugins enable <name>` 对手放插件会报 `No plugin named '<name>'` | 手写 `plugins:` 下的 `enabled: [<name>]` 到 config.yaml，然后刷新页面 |
| `GET /api/plugins/<name>/ping` 404 | 两种可能：① 插件没启用（见上一条）；② `plugin_api.py` **只在 dashboard 进程启动时挂载**，进程先起、插件后加就是永远 404 | 先确认 `plugins.enabled`，再重启 `hermes dashboard` |
| 页面标题变成桌面应用的样子、插件全不出现、`window.__HERMES_PLUGIN_SDK__` 是 `undefined` | 环境里有 `HERMES_WEB_DIST` 指向别处的 dist：本机实测指向桌面端的 dist 时，`hermes dashboard` 会伺服**桌面端 UI**，启动日志打印 `→ Using web dist from HERMES_WEB_DIST: …` | `unset HERMES_WEB_DIST` 再启动（读者自己机器上一般没有这个变量） |
| 按文档写 `PUT /api/dashboard/themes` 得到 404 | **读接口是复数、写接口是单数**：`GET /api/dashboard/themes` 但 `PUT /api/dashboard/theme` [[src:extending-the-dashboard]] | 写改用单数路径，body `{"name": "<主题名>"}` |
| `customCSS` 写了一大段，界面上只生效一半 | 上限 32 KiB，**超长是静默截断**（源码 `custom_css_val[:_THEME_CUSTOM_CSS_MAX]`），不是报错 —— 官方 troubleshooting 只说 "capped at 32 KiB" | 别把整张样式表塞进主题；拆成多个主题，或改用插件的 `css` 字段（那条没有大小上限） [[src:extending-the-dashboard]] |
| 切到另一个主题后，我调过的颜色没了 | `colorOverrides` 只作用于当前主题，切主题即清空（官方说 by design） [[src:extending-the-dashboard]] | 要持久就写进主题 YAML，别用运行时的临时覆盖 |
| 插件里登记的 `sidebar` slot 什么都不渲染 | `sidebar` 只在 `layoutVariant: cockpit` 下渲染 [[src:extending-the-dashboard]] | 主题 YAML 里加 `layoutVariant: cockpit` |
| `manifest.json` 里写 `"icon": "Rocket"`，界面显示成拼图 | 只有映射表里的 Lucide 名会被认出来，未知名字**静默回落 `Puzzle`** [[src:extending-the-dashboard]] | 从文档列出的那 20 个名字里挑一个 |
| 主题选择器里比文档那张表多一套 `Nous Blue` | 文档口径不一致：较旧的 `web-dashboard` 快照说内置 8 套（含浅色的 `nous-blue`）[[src:web-dashboard]]，较新的 `extending-the-dashboard` 快照那张表只列 7 套 [[src:extending-the-dashboard]] | 以**你自己机器上的界面**为准：`curl -s http://127.0.0.1:9119/api/dashboard/themes` 列出几个就是几个 |

## 试一试

- [ ] 写一个 `~/.hermes/dashboard-themes/<你的名字>.yaml`，只改 `background` + `midground` 两个颜色，再加一段 `customCSS`（比如给 `body::before` 加一条扫描线规则）；切过去后用 `document.querySelectorAll('style[data-hermes-theme-css]').length` 确认它仍是 1 条
- [ ] 写一个只挂 `sessions:top` 一个 slot 的插件（`tab.hidden: true` + `register()` 一个返回 `null` 的占位组件），确认 `/sessions` 页顶部出现你的卡片、而导航里**没有**新 tab
- [ ] 给插件加一个 `plugin_api.py`（导出 `router`）并调通：先用不带头的 curl 看到 404 或 401，重启 dashboard 后再用带 `X-Hermes-Session-Token` 的 curl 看到 200
- [ ] 用 `tab.override` 把 `/` 换成自己的首页，然后说明风险：你从此**接管整页**（包括官方后续对它的更新），同一个路径只允许一个插件，第二个会被忽略并给一条 dev-mode 警告 [[src:extending-the-dashboard]]
- [ ] 把主题切回默认，说清"恢复默认"的两条路径：① 界面里直接选 `Hermes Teal`（它的 `name` 就是 `default`）；② 删掉自己的 YAML 文件 —— 此时 `config.yaml` 的 `dashboard.theme` 里仍留着旧主题名，界面上会发生什么？**本课没有实测这一条，不要照抄任何结论**：自己跑一遍，把观察到的现象记进 `journal/`
- [ ] 判断这三件事分别该改**主题 YAML**、**插件 manifest**，还是 **plugin_api.py**：① 让卡片四个角变成斜切角 ② 在日志页顶部加一条提示 ③ 把会话库里某个统计数字暴露给面板
- [ ] 把结果记到 `journal/` 里并提交

## 下一步

- [[L41]] —— 插件目录里的 `plugin.yaml` / `__init__.py` 那半边：工具、钩子、中间件
- [[L42]] —— 桌面应用与 TUI 的外观：另一套完全不同的插件 SDK，别把两者的 import 混着写
- [[L44]] —— 嫌面板改不动？那一课教你把 Hermes 当库用，前端自己写
- 想深入：[[src:extending-the-dashboard]] 的 "Shell slots" 与 "Replacing built-in pages" 两节 —— 本课只放了最小的 slot 例子
- 想深入：[[src:web-dashboard]] 的 "Authentication (gated mode)" 一节 —— 绑定非 loopback 之后，令牌那套就不成立了

## 出处

- [[src:extending-the-dashboard]] Extending the Dashboard — https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard
- [[src:web-dashboard]] Hermes Web Dashboard — https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
