---
id: L46
title: 魔改桌面端：主题、命令与 plugin.js
stage: 4
level: 进阶
minutes: 30
prereq: [L41]
tags: ["桌面端", "plugin.js", "主题", "CDP", "外观"]
sources: [desktop-plugin-sdk, desktop]
updated: 2026-09-24
---

# L46 · 魔改桌面端：主题、命令与 plugin.js

> **一句话**：这一课改的是**桌面应用**（`hermes desktop`）—— 一半用设置界面就能换外观，另一半靠一个丢进 `$HERMES_HOME/desktop-plugins/<id>/plugin.js` 的 ESM 文件：不编译、不打包、保存后几秒热重载。

## 你将学会

- 说清 CLI 皮肤、TUI 部件、Web 面板插件、桌面插件是**四套互不相通**的机制，各自改哪个界面
- 不用写代码就改桌面端外观：VS Code Marketplace 主题导入、聊天/终端字体、宠物漫游、窗口布局
- 写一个最小桌面插件：目录名必须等于 `id`、ESM、用 `jsx()` 而不是 JSX、只能用三个 import
- 往九类注册区里挂东西：面板、页面与侧栏、状态栏与标题栏、命令面板、快捷键、**主题**
- 判断什么时候该用 `Settings → Appearance`、什么时候该写插件、什么时候该起一个隔离实例调试

**前置**：[[L41]] · **预计耗时**：30 分钟

## 先动手

桌面插件没有构建步骤：写一个文件、保存、看它出现在状态栏上。先建目录并写最小插件 [[src:desktop-plugin-sdk]]：

```bash
mkdir -p ~/.hermes/desktop-plugins/l46-demo
```

```javascript
// ~/.hermes/desktop-plugins/l46-demo/plugin.js
import { host } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

function Chip() {
  return jsx('button', {
    type: 'button',
    'data-l46': 'chip',
    className: 'px-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    onClick: () => host.notify({ kind: 'info', message: 'L46 demo clicked' }),
    children: 'L46-DEMO'
  })
}

export default {
  id: 'l46-demo',            // 必须等于目录名
  name: 'L46 Demo',
  register(ctx) {
    ctx.register({ id: 'chip', area: 'statusBar.right', order: 130, render: () => jsx(Chip, {}) })
  }
}
```

保存后**几秒内**状态栏右下角出现 `L46-DEMO` 按钮，点它会弹一条提示；以后每次保存都在原处热重载，不用重启应用 [[src:desktop-plugin-sdk]]。

**你应该看到**：状态栏右簇多出一个按钮（本机把插件写进真实 `$HERMES_HOME` 后由应用加载——本课末尾标注了这次实测到什么程度）；没出现就按 `⌘K`（Windows/Linux 用应用内命令面板）找 **Reload desktop plugins**，加载失败时应用会弹一条点名错误的提示 [[src:desktop-plugin-sdk]]。

## 原理

### 四套界面扩展，互不相通

| 你想改的界面 | 机制 | 磁盘形态 | 本课 |
|---|---|---|---|
| 终端经典 CLI | 皮肤（skin） | `~/.hermes/skins/<名字>.yaml` | [[L42]] |
| 终端 TUI | 子类化 `HermesCLI` 的 wrapper CLI | 你自己的 `my_cli.py` | [[L42]] |
| Web 面板（`hermes dashboard`） | 主题 YAML + 面板插件（`manifest.json` + JS bundle） | `~/.hermes/dashboard-themes/` + `~/.hermes/plugins/<id>/dashboard/` | [[L45]] |
| **桌面应用（`hermes desktop`）** | **`@hermes/plugin-sdk` + 单个 ESM 文件** | **`$HERMES_HOME/desktop-plugins/<id>/plugin.js`** | **本课** |

官方文档把这件事写在最显眼的位置：Web 面板那一页顶部有一段「**Not the desktop app**」的提示框，明确说两套插件系统互不相关，唯一共享的是后端 `plugin_api.py` 的 `/api/plugins/<name>` 命名空间；桌面端自己的参考页开头也写明「用一次 import、没有构建步骤」[[src:desktop-plugin-sdk]]。**别把 `~/.hermes/skins/` 或 `dashboard-themes/` 的 YAML 丢进 `desktop-plugins/` 期待生效** —— 它们归不同的界面。

### 磁盘形态、加载与热重载

- 位置：`$HERMES_HOME/desktop-plugins/<id>/plugin.js`（默认就是 `~/.hermes/desktop-plugins/`），**目录名必须等于插件导出的 `id`** [[src:desktop-plugin-sdk]]。
- 它是**应用级**的：无论你当前在看哪个 profile、哪台远端机器，桌面代码只从**本机**这一个目录加载 —— 这一点在源码里的测试断言写得很直白（读本机 `desktop-plugins`，不去读远端 home 的）[[src:desktop-plugin-sdk]]。
- 明文 ESM，**不编译**：所以 JSX 语法解析不了，只能用 `jsx()` / `jsxs()`（`react/jsx-runtime`）或 `React.createElement`；**只有三个 import 能解析**：`@hermes/plugin-sdk`、`react`、`react/jsx-runtime`，其他 specifier 一律加载失败 [[src:desktop-plugin-sdk]]。
- 保存即生效、热重载；管理入口是 **Capabilities → Plugins** 一行一个插件，桌面那一列的开关是**应用级**的（切 profile 不会加载/卸载它）[[src:desktop]]。
- 「统一包」形态：把桌面半区放进 `$HERMES_HOME/plugins/<id>/desktop/plugin.js`，同一份仓库同时给 agent 侧和桌面侧；安装统一包时应用会把桌面半区拷到 `desktop-plugins/` [[src:desktop-plugin-sdk]]。

### 一个 SDK，九类注册区

插件默认导出一个 `{ id, name, register(ctx) }`，在 `register` 里用 `ctx.register(...)`（或 `ctx.registerMany([...])`）往**注册区**（area）里挂东西 [[src:desktop-plugin-sdk]]：

| 注册区 | 挂什么 |
|---|---|
| `panes` | 右侧/底部面板（`data: { placement, width }`） |
| 页面与侧栏（`ROUTES_AREA` / `SIDEBAR_NAV_AREA`） | 自己的整页 + 侧栏入口 |
| `statusBar.left` / `.right`、标题栏 `TITLEBAR_AREAS.*` | 底部状态栏、标题栏里的按钮与提示 |
| 命令面板（`PALETTE_AREA`） | ⌘K 里的一条命令（`{ id, label, keywords, run }`） |
| 快捷键（`KEYBINDS_AREA`） | 可被用户在设置里改键的快捷键（`{ id, label, category, defaults, run }`） |
| 主题（`THEMES_AREA`） | 一个完整的 `DesktopTheme`（`name`/`label`/`colors`…），注册后出现在主题选择器里 |
| composer 扩展 / transcript 指令 / 挂载作用域的 chrome | 输入框扩展、模型可在回复里调用的内联组件、只在某个页面出现时挂载的控件 |

主题相关的 API 值得单独记：`useTheme()` 读当前外观（`theme` / `themeName` / `availableThemes` / `resolvedMode`），`setTheme` / `setMode` / `previewTheme` 改它；连了远端后端时用 `requestTheme(name)`（**解析不到的主题名会被拒绝，而不是静默重置别人的外观**）；只想给当前主题染色就用 `setAccentOverride` 或 `retintTheme` [[src:desktop-plugin-sdk]]。

**写 UI 时只用主题变量**（`var(--ui-*)`），不要写死 `#000` / `rgb(...)` —— 否则切主题后你的面板是唯一不跟着变的那个 [[src:desktop-plugin-sdk]]。

### 不写代码能改的那一半

桌面端的外观设置里有一批直接可用的开关，先把它们用完再考虑写插件 [[src:desktop]]：

- **VS Code Marketplace 主题导入** —— 外观设置里能搜 VS Code 主题市场，选中一个会下载、转换、安装成桌面主题；命令面板里的 *Install theme* 是同一个导入器，导入的主题也能在设置里删掉。
- **聊天字体 / 终端字体** —— 各自一个键（`desktop.font_family` / `terminal.font_family`），可填一个已安装字族名，也可以填 CSS font stack；聊天字体填了以后主题自带的字体栈仍在后面兜底（CJK 与 emoji 不会缺字）。
- **宠物漫游**、**启动时是否恢复上次会话**（`display.resume_last_session`）、**推理块显示与否**都在同一片设置区里。
- **窗口布局与栏色**跟着 profile 走：从桌面端导出的 profile 会把皮肤、明暗模式、自定义主题、栏色、窗口布局一起打进 `desktop.json`，所以别人导入你的 profile 后**看着也像你的**，不只是行为像。

### 安全模型：加载即全权

插件加载进渲染进程后**拥有应用的全部权限**（React 单例、整个 SDK、渲染进程里的 ESM 求值）。加载器提供的隔离只是**错误隔离** —— 插件崩了不会拖垮应用，但插件能做的事与应用能做的事一样多；那个可选的 `integrity` sha256 校验只能证明字节没变，**不是沙箱** [[src:desktop-plugin-sdk]]。所以「从哪拿插件」比「插件写得漂不漂亮」重要得多。

## 亲手验证

### 验证一：打包版的桌面临时调试端口是**关着**的（本机实测）

桌面端的渲染进程是 Chromium 页面，开发态会开一个调试端口；但**打包构建永远不开**，而且这是硬门：不管环境变量怎么写 [[src:desktop-plugin-sdk]]。本机对正在运行的正式应用实测：

```bash
curl -s --max-time 3 http://127.0.0.1:9222/json/version
```

**本机实测输出**：空（命令退出码 7，连接被拒）。即确认「正式应用不开调试端口」。

源码 `apps/desktop/electron/dev-cdp.ts` 里的判据（本机读源码）：

| 条件 | 结果 |
|---|---|
| 打包构建 | **永远关闭**，任何环境变量都不能打开 |
| 没设 `HERMES_DESKTOP_DEV_SERVER` | 关闭（用 `electron .` 跑 `dist/` 属于「打包版冒烟测试」，行为与打包版一致） |
| 设了 dev server | 开在 `9222`，或用 `HERMES_DESKTOP_CDP_PORT` 指定的端口 |
| `HERMES_DESKTOP_CDP_PORT=off`（或 `0`/`false`/`no`） | 关闭 |
| 端口 <1024 或 >65535 | 关闭（判为非法） |

端口只绑 loopback，地址故意不可配置。

### 验证二：起一个**隔离实例**，别碰你正在用的那个

要在开发态看 DOM，必须同时满足两件事：主进程带 `--dev` 构建、且设了 dev server 环境变量。本机实测的一串命令（在安装树的 `apps/desktop` 下跑）[[src:desktop-plugin-sdk]]：

```bash
cd ~/.hermes/hermes-agent/apps/desktop
node scripts/bundle-electron-main.mjs --dev          # 不带 --dev 时，调试端口不会开
HERMES_HOME=~/tmp-home \
HERMES_DESKTOP_DEV_SERVER=http://127.0.0.1:5174 \
HERMES_DESKTOP_CDP_PORT=9333 \
  ./node_modules/.bin/electron . --user-data-dir=~/tmp-ud
```

```bash
# 另开一个终端：读活体 DOM（仓库自带的一行脚本）
cd ~/.hermes/hermes-agent/apps/desktop
HERMES_DESKTOP_CDP_PORT=9333 node scripts/eval.mjs \
  'JSON.stringify({ title: document.title, chip: (document.querySelector("[data-l46=chip]")||{}).textContent || null })'
```

**为什么必须隔离**：`--user-data-dir` 单独给一个，是为了绕开 Electron 的单实例锁（否则第二个实例要么起不来、要么把你正在用的窗口顶掉）；单独一个 `HERMES_HOME` 是为了不让试验插件的崩溃或日志污染你的日常环境 [[src:desktop-plugin-sdk]]。

| 你观察到的 | 说明什么 |
|---|---|
| 启动日志里有 `renderer debugging on http://127.0.0.1:9333` | 应用**决定**开端口（决策日志） |
| 隔离实例里窗口可能很快自己退出 | 一个临时 `HERMES_HOME` 没有配好的后端，应用连不上 `hermes:api` 时会退出 —— DOM 要在端口一开就抓紧读 |

### 验证三：诚实标注 —— 「端口说开了但没监听」（本机未解决）

本机在这台 Windows 上连续三次尝试（不开 `--no-sandbox`、开 `--no-sandbox`、以及不重建主进程），现象都一样：

```bash
netstat -ano | grep 9333          # 本机实测：0 行（没有任何进程监听 9333）
timeout 3 bash -c 'exec 3<>/dev/tcp/127.0.0.1/9333'   # 本机实测：Connection refused
```

而应用日志里**已经有**那一行 `renderer debugging on http://127.0.0.1:9333`。也就是说：**日志里的「已开启」是决策，不等于端口真的绑上了**。本机没能把这条路径跑通，所以：

- 本课关于 `plugin.js` 能被加载、能改 DOM、热重载需要多久、插件报错时的表现、删除插件后的恢复 —— **这些仍只有官方文档与 SDK 源码作为依据，本机没有跑出「肉眼看到插件出现在界面上」的证据**。
- 上面的隔离实例命令是本机真跑过的（应用确实启动了、日志确实打印了那两行），**但因为端口没绑上，DOM 读取这一步本机没成功**。你如果在自己的机器上把端口跑通了，可以用第二步的命令自行核对。

> 这一节故意留下「没验证成」的记录，而不是写一句「实测通过」：调试端口能不能开，取决于你的 Electron/系统组合，本机这一台没开成。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 加载报 `unsupported import` | 磁盘插件只允许 `@hermes/plugin-sdk`、`react`、`react/jsx-runtime` 三个 specifier | 删掉其他 import，把逻辑挪进插件自己的后端 `plugin_api.py`，或改用 SDK 已有能力 [[src:desktop-plugin-sdk]] |
| 文件保存了，插件没反应 | 目录名与 `id` 不一致；或需要手动重载 | 让目录名等于导出的 `id`；用命令面板的 **Reload desktop plugins** [[src:desktop-plugin-sdk]] |
| `jsx()` 里用的组件抛 `ReferenceError` | 那个标识符没写进 import 行 | 逐个核对 `jsx()` 里出现的名字都在 import 里 [[src:desktop-plugin-sdk]] |
| 主题一换，自己的面板颜色就怪 | 代码里硬编码了颜色 | 一律用 `var(--ui-*)` 主题变量，背景交给应用 [[src:desktop-plugin-sdk]] |
| `curl http://127.0.0.1:9222/json/version` 一片空白 | 你跑的是打包版：**打包构建永远不开调试端口** | 这是设计；要读 DOM 就按「验证二」起带 dev server 的隔离实例 [[src:desktop-plugin-sdk]] |
| 隔离实例起不来，或你的窗口被顶掉 | 两个 Electron 实例共用同一个 `--user-data-dir`，撞上单实例锁 | 给隔离实例单独一个 `--user-data-dir` [[src:desktop-plugin-sdk]] |
| 隔离实例的窗口几秒后自己消失 | 临时 `HERMES_HOME` 没有可用后端（`ECONNREFUSED`），应用自行退出 | 端口一开就抓紧读 DOM；或先把那个 home 的 provider 配好 [[src:desktop-plugin-sdk]] |
| 端口自称开着，实际连不上 | 本机实测到的现象（见「验证三」），原因未定 | 先用 `netstat` 验端口是否真在监听，别只看应用日志 [[src:desktop-plugin-sdk]] |
| 改了插件的后端路由没生效 | `plugin_api.py` 这类后端路由在**进程启动时**挂载 | 重启应用或后端；只改前端 `plugin.js` 才享受热重载 [[src:desktop-plugin-sdk]] |
| 切 profile 后面板不见了 | 桌面半区是**应用级**的，不该随 profile 变化 | 排查是不是把桌面半区装进了 profile 的 `plugins/`；桌面代码只从本机 `desktop-plugins/` 加载 [[src:desktop-plugin-sdk]] |

## 试一试

- [ ] 把「先动手」的 `L46-DEMO` 按钮改成显示当前网关状态（提示：SDK 有只读状态）
- [ ] 再挂一个 `PALETTE_AREA` 命令：命令面板里输入名字能打开某个页面
- [ ] 用 `useTheme()` 写出一个能列出 `availableThemes` 并在点击时 `setTheme` 的面板组件
- [ ] 判断该用哪条路径改下面三件事：① 把界面字体换成 Atkinson Hyperlegible ② 让状态栏常驻一个「重启网关」按钮 ③ 让整站换成 VS Code 里的某个配色主题
- [ ] 写一个**故意坏的**插件（用一个不在允许清单里的 import），记录应用给什么反馈、坏插件会不会影响别的插件
- [ ] 把结果记到 `journal/` 里并提交

## 下一步

- [[L41]] —— 桌面插件的「agent 侧半区」要的 `plugin.yaml`、能力声明与审批
- [[L45]] —— 同一台机器上的另一套插件系统：Web 面板的主题与插件（**与桌面端无关**）
- [[L42]] —— 终端侧的两套：CLI 皮肤与 TUI 部件
- [[L44]] —— 想自己写整个前端，就从 API Server / ACP 那两条路走
- 想深入：在 `$HERMES_HOME/desktop-plugins/` 里放一个 `plugin.js` 之外，还可以看官方 SDK 页的「Two delivery modes」——磁盘插件、统一包、内置插件三条交付路径的差别 [[src:desktop-plugin-sdk]]

## 出处

- [[src:desktop-plugin-sdk]] Desktop Plugin SDK (@hermes/plugin-sdk) — https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
- [[src:desktop]] Hermes Desktop — https://hermes-agent.nousresearch.com/docs/user-guide/desktop
