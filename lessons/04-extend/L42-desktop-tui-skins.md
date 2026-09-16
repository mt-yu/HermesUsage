---
id: L42
title: 桌面插件 / TUI 部件 / 皮肤
stage: 4
level: 进阶
minutes: 25
prereq: [L41]
tags: ["皮肤", "TUI", "桌面插件", "petdex", "主题"]
sources: [skins, tui, pets, desktop-plugin-sdk]
updated: 2026-09-16
---

# L42 · 桌面插件 / TUI 部件 / 皮肤

> **一句话**：这一课改的是「外观与交互」—— 先用 YAML 换皮肤，再用 `display.*` 调 TUI 的版式，最后往桌面应用的侧栏和状态栏里挂自己的 `plugin.js`。

## 你将学会

- 用 `hermes skin list` / `hermes skin use` 切换皮肤，并写一个只改几个键的自定义皮肤
- 用 `display.interface` / `display.details_mode` / `display.sections` 调 TUI 的版式与展开状态
- 说清宠物（petdex）的启用条件和它的渲染降级规则
- 写一个桌面插件：`desktop-plugins/<id>/plugin.js`、`jsx()` 而非 JSX、只允许三个 import
- 亲手触发两次边界情况：未装宠物时的 doctor 输出、切换一个不存在的皮肤

**前置**：L41 · **预计耗时**：25 分钟

## 先动手

皮肤是纯配置，改完立刻可见 —— 先用一条命令看看有哪些、再切一个 [[src:skins]]：

```bash
hermes skin list
```

**你应该看到**（本机实测输出）：

```
* default          builtin  Classic Hermes — gold and kawaii
  ares             builtin  War-god theme — crimson and bronze
  mono             builtin  Monochrome — clean grayscale
  slate            builtin  Cool blue — developer-focused
  daylight         builtin  Light theme for bright terminals with dark text and cool blue accents
  warm-lightmode   Warm light mode — dark brown/gold text for light terminal backgrounds
  poseidon         builtin  Ocean-god theme — deep blue and seafoam
  sisyphus         Sisyphean theme — austere grayscale with persistence
  charizard        Volcanic theme — burnt orange and ember
```

切到 `ares`：

```bash
hermes skin use ares
```

**你应该看到**（本机实测输出，路径是你当前 HERMES_HOME 下的 `config.yaml`）：

```
✓ Set display.skin = ares in C:\Users\28189\AppData\Local\Temp\hermes-l40-check\config.yaml
✓ active skin → ares (live within ~1s)
```

会话里可以不走命令行，直接用斜杠命令切，并且是**当场重绘** [[src:skins]]：

```
/skin                # 看当前皮肤 + 列表
/skin ares
/skin mytheme        # 切到 ~/.hermes/skins/mytheme.yaml
```

## 原理

### 皮肤：一套「没写的键都从 default 继承」的 YAML

内置皮肤一共 9 个，`default` 是那个熟悉的金色 Hermes；`ares` / `poseidon` / `charizard` 这类还会改 spinner 动词和 ASCII banner [[src:skins]]。

自定义皮肤放 `~/.hermes/skins/<名字>.yaml`，**只写你要改的键**，其余自动继承 `default` [[src:skins]]：

```yaml
# ~/.hermes/skins/cyberpunk.yaml
name: cyberpunk
description: Neon terminal theme

colors:
  banner_border: "#FF00FF"
  banner_title: "#00FFFF"
  banner_accent: "#FF1493"

spinner:
  thinking_verbs: ["jacking in", "decrypting", "uploading"]
  wings:
    - ["⟨⚡", "⚡⟩"]

branding:
  agent_name: "Cyber Agent"
  response_label: " ⚡ Cyber "

tool_prefix: "▏"
```

可调的键分四组 [[src:skins]]：

| 组 | 管什么 | 例子 |
|---|---|---|
| `colors:` | 全 CLI 的颜色值，十六进制 | `banner_border`、`ui_ok`、`ui_error`、`prompt`、`completion_menu_bg` |
| `spinner:` | 等待面、思考面、思考动词、两侧小翼 | `thinking_verbs`、`waiting_faces` |
| `branding:` | agent 名字、欢迎语、回应标签、提示符 | `agent_name`、`prompt_symbol` |
| 顶层杂项 | 工具前缀、逐工具 emoji、自定义 banner | `tool_prefix`、`tool_emojis`、`banner_logo` |

也可以只微调当前皮肤的某一个颜色 [[src:skins]]：

```bash
hermes skin set ui_tool "#00FFFF"
```

### TUI：同一内核的另一个外壳

`hermes --tui` 启动 TUI；也可以用 `HERMES_TUI=1` 或把 `display.interface: tui` 写成默认，显式参数永远优先（`hermes --cli` 可以单次退回经典界面）[[src:tui]]。

切换点在于它把运行信息分组折叠，且版式可以按节控制 [[src:tui]]：

```yaml
display:
  skin: default              # 任何内置或自定义皮肤
  personality: helpful
  details_mode: collapsed    # hidden | collapsed | expanded（全局折叠默认值）
  sections:
    thinking: expanded       # 永远展开
    tools: expanded
    activity: collapsed      # 把 activity 面板重新打开（它默认是 hidden）
  mouse_tracking: all        # off | wheel | buttons | all
```

运行时用斜杠命令改，不用重启 [[src:tui]]：

```
/details cycle                     # 全局轮换 hidden → collapsed → expanded
/details tools collapsed           # 只把工具调用折起来
/details thinking expanded
```

TUI 与经典 CLI **共用同一份会话存储**（`~/.hermes/state.db`），一个里开的会话可以在另一个里续；TUI 默认自带进程内 gateway，不需要额外配置 [[src:tui]]。皮肤和 personality 在两端通用，`/skin ares` 之后 TUI 立刻重绘；TUI 额外尊重 banner 调色板、UI 颜色、提示符字形与颜色、会话显示、补全菜单、选择背景、`tool_prefix`、`help_header` [[src:tui]]。

### 宠物：装、选、开，三个条件缺一不可

宠物是纯装饰，但它有一套明确的启用条件。所有设置都在 `display.pet` 下 [[src:pets]]：

```yaml
display:
  pet:
    enabled: false      # 总开关（选中一只宠物后会变 true）
    slug: ""            # 当前宠物；留空 = 用第一只已安装的
    render_mode: auto   # auto | kitty | iterm | sixel | unicode | off
    scale: 0.33         # 唯一的尺寸旋钮
    unicode_cols: 0     # 强行指定终端列宽（0 = 由 scale 推导）
```

终端渲染会先探测图形协议（kitty / Ghostty / WezTerm / iTerm2 / sixel），探测不到就自动降级成 truecolor Unicode 半块；**在管道或重定向里（没有 TTY）按设计直接关闭终端渲染** [[src:pets]]。桌面端把它画成浮动精灵，在 Settings → Appearance 里开关 [[src:pets]]。

命令行全套 [[src:pets]]：

```bash
hermes pets list                # 逛画廊
hermes pets install boba --select
hermes pets show                # 在当前终端预览（Ctrl+C 停）
hermes pets scale 0.5
hermes pets off
hermes pets doctor              # 诊断
```

会话内用 `/pet`、`/pet list`、`/pet <slug>`、`/pet scale 0.5`、`/pet off` [[src:pets]]。

### 桌面插件：一个 `plugin.js`，没有构建步骤

桌面插件的磁盘形态是 `$HERMES_HOME/desktop-plugins/<id>/plugin.js`，**目录名必须等于插件导出的 `id`**，明文 ESM、不编译、保存后几秒内热重载 [[src:desktop-plugin-sdk]]：

```javascript
// ~/.hermes/desktop-plugins/hello/plugin.js
import { host, haptic, useValue } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

function HelloPane() {
  const gateway = useValue(host.state.gateway)
  return jsxs('div', {
    className: 'flex h-full flex-col gap-2 p-3 text-sm',
    children: [
      jsx('div', { className: 'font-medium', children: 'Hello, Hermes' }),
      jsx('div', { className: 'text-(--ui-text-tertiary)', children: `gateway: ${gateway}` })
    ]
  })
}

export default {
  id: 'hello',
  name: 'Hello',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'hello',
      data: { placement: 'right', width: '260px' },
      render: () => jsx(HelloPane, {})
    })
  }
}
```

两条硬约束 [[src:desktop-plugin-sdk]]：

1. **磁盘插件不编译，所以 JSX 语法解析不了** —— 用 `jsx()` / `jsxs()`（或 `React.createElement`）
2. **只有三个 import 能解析**：`@hermes/plugin-sdk`、`react`、`react/jsx-runtime`，其他一律在加载时报错

能力分五层：`host.state.*`（只读状态）、`host.*`（toast / 导航 / 重启网关等动作）、`host.request`（网关 JSON-RPC）、`ctx.rest` / `ctx.socket`（你自己的后端命名空间 `/api/plugins/<id>`）、`ui.*`（应用自己的组件与主题变量）[[src:desktop-plugin-sdk]]。

它和 agent 侧插件的合体形态是「统一包」：把桌面半区放到 `$HERMES_HOME/plugins/<id>/desktop/plugin.js`，同一份仓库同时发两边 [[src:desktop-plugin-sdk]]。

安全模型要说清楚：**加载进来的插件拥有应用的全部权限**（React 单例、整个 SDK、渲染进程里的 ESM 求值）。加载器给的隔离只是**错误隔离** —— 插件崩不了应用，但能做到应用能做的任何事。那个可选的 `integrity` sha256 校验只证明字节没变，**不是沙箱** [[src:desktop-plugin-sdk]]。

## 亲手验证

### 验证一：没装宠物时，doctor 不会给你 `✓ ready`

```bash
hermes pets doctor
```

**本机实测输出**（一台没装任何宠物的 Windows 机器）：

```
petdex doctor
  pets dir:        C:\Users\28189\AppData\Local\hermes\pets
  installed:       0 (none)
  display.pet.enabled:     False
  display.pet.slug:        (unset)
  active (resolved):       (none)
  display.pet.render_mode: auto
  detected graphics:       unicode
  effective mode (TTY):    off
  → no pets installed. Run: hermes pets install boba
  (run the suggestions above to finish setup)
```

| 你观察到的 | 说明什么 |
|---|---|
| 没有 `✓ ready` 这一行 | doctor 把「装好 + 已选 + 已启用 + Pillow 可用」四个条件都满足时才打 `✓ ready` [[src:pets]] |
| `detected graphics: unicode` 与 `effective mode (TTY): off` 同时出现 | 探测到了协议（这里是半块降级），但当前是**非 TTY 环境**（脚本/重定向），所以终端渲染被设计性关闭 [[src:pets]] |
| `installed: 0 (none)` | 宠物目录是 profile 级的 `<HERMES_HOME>/pets/`；用 petdex npm CLI 装会落到 `~/.codex/pets`，Hermes 看不到 [[src:pets]] |

装一只再看一遍，`installed`、`display.pet.enabled`、`effective mode (TTY)` 三行都会变，`✓ ready` 才会出现 [[src:pets]]。

### 验证二：`hermes skin use` 不校验皮肤名

```bash
hermes skin use no-such-skin
```

**本机实测输出**：

```
✓ Set display.skin = no-such-skin in C:\Users\28189\AppData\Local\Temp\hermes-l40-check\config.yaml
✓ active skin → no-such-skin (live within ~1s)
```

| 你观察到的 | 说明什么 |
|---|---|
| 名字不存在，命令照样成功退出 | 命令行只负责写值，**不做存在性校验** —— 别把「命令成功」当成「配置正确」 |
| 想改回正常状态 | `hermes skin use default`（或 `hermes skin list` 里挑一个） |
| 想确认到底生效了哪个 | `hermes config get display.skin`，以及会话里跑 `/skin` 看当前皮肤 |

皮肤 YAML 里缺的键会从 `default` 继承，所以「少写几个键」是安全的；但**名字写错**要靠你自己发现 [[src:skins]]。

> 说明：本节皮肤切换与 pet 诊断的命令、输出都是本机实测。桌面插件那半区本机没有跑桌面应用，所以 `plugin.js` 的路径、导入约束和报错原文引自官方文档 [[src:desktop-plugin-sdk]]，未在本机复现。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 改了 `config.yaml` 里的皮肤，界面没变 | 配置文件是启动时读的；会话内要实时切换得用斜杠命令 | 会话里 `/skin ares`（当场重绘），或新开一个会话 [[src:tui]] |
| 桌面插件加载报 `unsupported import` | 磁盘插件只允许 `@hermes/plugin-sdk`、`react`、`react/jsx-runtime` 三个 specifier | 删掉其他 import，把逻辑挪进插件自己的后端或改用 SDK 提供的能力 [[src:desktop-plugin-sdk]] |
| `jsx()` 里用的组件渲染时抛 `ReferenceError` | 那个标识符没写进 import 行 | 逐个核对 `jsx()` 里出现的名字都在 import 里 [[src:desktop-plugin-sdk]] |
| `ctx.rest` 返回 404 | 插件的后端没挂上（缺 `dashboard/manifest.json` 里的 `"api": "plugin_api.py"`，或插件没在 `plugins.enabled` 里） | 补 manifest、确认已启用，然后重启网关；`~/.hermes/logs/errors.log` 里会有 `Failed to load plugin <id> API routes` [[src:desktop-plugin-sdk]] |
| 主题切换后颜色怪 | 代码里硬编码了 `#000` / `rgb(...)` | 一律用主题变量 `var(--ui-*)`，背景交给应用 [[src:desktop-plugin-sdk]] |
| 宠物装了还是不显示 | 必须同时满足「已安装 + 已选中（`enabled: true`）」；管道/重定向里没有 TTY，终端渲染按设计关闭 | `hermes pets install <slug> --select`，再在新终端里 `hermes pets show` [[src:pets]] |
| `hermes pets list` 找不到自己用 petdex npm CLI 装的宠物 | 那个 CLI 装到 `~/.codex/pets`，Hermes 用自己的 `<HERMES_HOME>/pets/` | 通过 `hermes pets install` 装 [[src:pets]] |
| TUI 里鼠标拖选行为不对（tmux 下疯狂弹提示） | `mouse_tracking` 的档位选择 | 改成 `wheel`（只留滚动+点击，去掉 hover）[[src:tui]] |

## 试一试

- [ ] 写一个自定义皮肤 `~/.hermes/skins/<你的名字>.yaml`，只改三个颜色 + `thinking_verbs`，用 `/skin <你的名字>` 切过去
- [ ] 在 TUI 里用 `/details tools collapsed` 与 `/details tools expanded` 各跑一轮，说明 `display.sections` 覆盖了什么
- [ ] 装一只宠物（`hermes pets install boba --select`）后重跑 `hermes pets doctor`，说出多出来的行分别代表什么
- [ ] 写一个只挂 `statusBar.right` 一个按钮的桌面插件（`jsx()` 写法），保存后确认它热重载进界面
- [ ] 判断：这三件事分别该改皮肤、改 `display.*` 配置，还是写桌面插件？① 把成功提示改成绿色以外的颜色 ② 让工具调用默认折叠 ③ 在标题栏加一个「重启网关」按钮
- [ ] 把结果记到 `journal/` 里并提交

## 下一步

- [[L41]] —— 桌面插件的「后端半区」要的 `register(ctx)`、能力声明与审批
- [[L40]] —— 其实很多「外观需求」用一个技能就能解决，先看那一课
- [[L43]] —— 接上一台外部工具服务器，而不是自己写 UI
- [[L44]] —— 把 Hermes 嵌进你自己的程序，自己写前端
- 想深入：[[src:desktop-plugin-sdk]] 的「Two delivery modes」—— 磁盘插件、统一包、内置插件三条交付路径的差别

## 出处

- [[src:skins]] Skins & Themes — https://hermes-agent.nousresearch.com/docs/user-guide/features/skins
- [[src:tui]] TUI — https://hermes-agent.nousresearch.com/docs/user-guide/tui
- [[src:pets]] Pets (Petdex Mascots) — https://hermes-agent.nousresearch.com/docs/user-guide/features/pets
- [[src:desktop-plugin-sdk]] Desktop Plugin SDK (@hermes/plugin-sdk) — https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
