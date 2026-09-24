---
id: L42
title: 终端外观：皮肤 / TUI 部件 / 宠物
stage: 4
level: 进阶
minutes: 30
prereq: [L41]
tags: ["皮肤", "TUI", "TUI 部件", "宠物", "主题"]
sources: [skins, tui, pets, extending-the-cli]
updated: 2026-09-24
---

# L42 · 终端外观：皮肤 / TUI 部件 / 宠物

> **一句话**：这一课改「终端里的外观」—— YAML 换皮肤、`display.*` 与 `/details` 调 TUI 版式，再用一个 wrapper CLI 把自定义部件挂到状态栏正上方。

## 你将学会

- 用 `hermes skin list` / `hermes skin use` 切换皮肤，并写一个只改几个键的自定义皮肤
- 用 `display.interface` / `display.details_mode` / `display.sections` / `display.mouse_tracking` 调 TUI 版式，`/details` 当场生效不重启
- 说清宠物（petdex）的三个启用条件、`hermes pets doctor` 的输出该怎么读
- 写一个 wrapper CLI：覆写 `_get_extra_tui_widgets()` 与 `process_command()`，把自己的面板挂到状态栏正上方
- 说清 CLI 皮肤 / TUI 部件 / Web 面板 / 桌面端是**四套互不相通**的机制，各自的入口文件在哪

**前置**：[[L41]] · **预计耗时**：30 分钟

## 先动手

皮肤是纯配置，改完立刻可见 —— 先用一条命令看看有哪些、再切一个 [[src:skins]]：

```bash
hermes skin list
```

**你应该看到**（本机实测输出，2026-09-24）：

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

行首的 `*` 是当前生效的皮肤。切到 `ares`：

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

> `hermes skin` 一共三个动词，`hermes skin --help` 自己会告诉你 [[src:skins]]（下面是本机实测输出的节选）：

```
usage: hermes skin [-h] {list,use,set} ...

Manage Hermes skins. `set` tweaks one color of the active skin in place.

positional arguments:
  {list,use,set}
    list          List available skins
    use           Switch the active skin
    set           Set one color of the active skin (e.g. `skin set ui_tool '#00FFFF'`)
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

也可以只微调当前皮肤的某一个颜色（这是 `hermes skin --help` 自己给的例子）[[src:skins]]：

```bash
hermes skin set ui_tool "#00FFFF"
```

两条容易忽略的规则：名字写错的皮肤会自动回落到 `default`；`/skin` 的切换是**会话级**的，要变成永久默认得写进 `config.yaml` 的 `display.skin` [[src:skins]]。

### TUI：同一内核的另一个外壳

`hermes --tui` 启动 TUI；也可以用 `HERMES_TUI=1` 或把 `display.interface: tui` 写成默认，显式参数永远优先（`hermes --cli` 可以单次退回经典界面）[[src:tui]]。

它的特别之处在于把运行信息分组折叠，且版式可以按节控制 [[src:tui]]：

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
/mouse wheel                       # 鼠标档位：只留滚动+点击，去掉 hover
```

TUI 与经典 CLI **共用同一份会话存储**（`~/.hermes/state.db`），一个里开的会话可以在另一个里续；TUI 默认自带进程内 gateway，不需要额外配置 [[src:tui]]。皮肤和 personality 在两端通用，`/skin ares` 之后 TUI 立刻重绘；TUI 额外尊重 banner 调色板、UI 颜色、提示符字形与颜色、会话显示、补全菜单、选择背景、`tool_prefix`、`help_header` [[src:tui]]。

### TUI 部件：不是配置项，是子类化 `HermesCLI` 的 wrapper CLI

`display.*` 能改的是「已有部件怎么显示」。要**加一个自己的部件**，配置里没有这个键 —— 得写一个继承 `HermesCLI` 的小程序，覆写它留出来的钩子 [[src:extending-the-cli]]。

`HermesCLI` 在 `cli.py`，钩子定义在 `hermes_cli/cli_tui_mixin.py`（`cli.py` 里的 `HermesCLI` 混入了这个 mixin）。文档明确提醒：**不要覆写 `run()`** —— 这些钩子存在的意义就是让你不必绑死内部实现 [[src:extending-the-cli]]。

五个扩展缝 [[src:extending-the-cli]]：

| 钩子 | 干什么 | 什么时候用 |
|---|---|---|
| `_get_extra_tui_widgets()` | 往布局里注入 widget | 要一个常驻 UI 元素（面板、状态行、迷你播放器） |
| `_register_extra_tui_keybindings(kb, *, input_area)` | 加快捷键 | 要热键（切换面板、控制条） |
| `_build_tui_layout_children(**widgets)` | 完全控制 widget 顺序 | 要重排或包装既有 widget（很少用） |
| `process_command()` | 加自定义斜杠命令 | 要 `/mycommand`（老钩子） |
| `_build_tui_style_dict()` | 自定义 prompt_toolkit 样式 | 要自己的颜色或样式（老钩子） |

前三个是新的受保护钩子，后两个一直就有 [[src:extending-the-cli]]。

**默认布局顺序**（从上到下）[[src:extending-the-cli]]：

```
输出区 → spacer → extra widgets → 状态栏 → 图片栏 → 输入区 → 语音状态 → 补全菜单
```

注意第 3 项：你注入的 widget 渲染在**状态栏正上方** —— 不在底部，也不在顶部。所以「一个贴着输入区的小面板」这种直觉在这里是不成立的。

本机实测（Windows 11 + Git Bash，2026-09-24）：写一个覆写 `_get_extra_tui_widgets()` 与 `process_command()` 的 `my_cli.py`，在 TUI 里输入 `/panel` 后：

```
L42-PANEL-STATE: visible
```

面板文本 `L42-PANEL-VISIBLE` 出现在状态栏那一行的**正上方**：

```
L42-PANEL-VISIBLE
☤ deepseek-v4-pro │ ctx -- │ [░░░░░░░░░░] -- │ 5s │ ⏲ 0s
```

再输入一次 `/panel`，打印 `L42-PANEL-STATE: hidden`，面板整行消失。钩子确实被调用的另一个证据：调试时把面板内容写错，traceback 的调用栈里会出现 `hermes_cli/cli_tui_mixin.py:403` 的 `*self._get_extra_tui_widgets(),` —— 本机读安装树源码确认，这一行就排在 `status_bar` 之前，与「extra widgets 在状态栏正上方」一致。

> 一个精确度说明：本机安装树（跟踪 main）的源码里，extra widgets 与状态栏之间还夹着三个**条件性** widget —— `_pet_widget` / `_stash_panel_widget` / `_subagent_dock_widget`（`cli_tui_mixin.py:404-406`，没装宠物、没有子代理时它们是 `None`）。所以「紧贴状态栏」在没有它们时成立；官方文档给的是简化后的顺序。

最小可跑版本（**用 `ConditionalContainer` 包一层**，不要给 `Window` 传 `filter=`，原因见「常见坑」）：

```python
#!/usr/bin/env python3
"""my_cli.py —— 只加一个可切换面板的 wrapper CLI。"""
from cli import HermesCLI          # ← 必须在安装树根目录下运行才 import 得到
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, FormattedTextControl, Window


class MyCLI(HermesCLI):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._panel_visible = False

    def _get_extra_tui_widgets(self):
        """返回要插进布局的 prompt_toolkit widget 列表。"""
        return [
            ConditionalContainer(
                content=Window(
                    FormattedTextControl(lambda: f"model: {self.model}"),
                    height=1,
                ),
                filter=Condition(lambda: self._panel_visible),
            ),
        ]

    def process_command(self, cmd: str) -> bool:
        """/panel 切换面板；其余命令交回父类。"""
        if cmd.strip().lower() == "/panel":
            self._panel_visible = not self._panel_visible
            state = "visible" if self._panel_visible else "hidden"
            print(f"L42-PANEL-STATE: {state}")
            self._invalidate()          # 触发 prompt_toolkit 重绘
            return True
        return super().process_command(cmd)


if __name__ == "__main__":
    MyCLI().run()
```

文件放哪都行，但**必须在安装树根目录里运行**（`cli.py` 就在那里，`from cli import ...` 才找得到）[[src:extending-the-cli]]。两个平台的跑法不一样，见「亲手验证」的验证三。

面板里能读到的现场状态：`self.agent`、`self.model`、`self.conversation_history` 都是现成的 [[src:extending-the-cli]]。加键位则覆写 `_register_extra_tui_keybindings(kb, *, input_area)`，`input_area` 就是主输入框，可以直接读写用户正在敲的内容 [[src:extending-the-cli]]：

```python
def _register_extra_tui_keybindings(self, kb, *, input_area):
    cli_ref = self

    @kb.add("f2")
    def _toggle_panel(event):
        cli_ref._panel_visible = not cli_ref._panel_visible
        cli_ref._invalidate()
```

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

## 亲手验证

### 验证一：没装宠物时，doctor 不会给你 `✓ ready`

```bash
hermes pets doctor
```

**本机实测输出**（一台没装任何宠物的 Windows 机器，2026-09-24）：

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

### 验证三：把面板挂到状态栏正上方（TUI 部件）

先把上面那个 `my_cli.py` 存到任意目录，然后**在安装树根目录里**运行它。文档给的跑法是 Linux/macOS 的 [[src:extending-the-cli]]：

```bash
cd ~/.hermes/hermes-agent
source .venv/bin/activate
python my_cli.py
```

本机（Windows + Git Bash）**没有** `.venv/bin/activate` —— venv 在 `venv/Scripts/` 下，实测跑法：

```bash
cd "$LOCALAPPDATA/hermes/hermes-agent"
./venv/Scripts/python.exe my_cli.py
```

TUI 起来后输入 `/panel`，**你应该看到**：

```
L42-PANEL-STATE: visible
```

以及面板文字出现在状态栏那一行的正上方：

```
L42-PANEL-VISIBLE
☤ deepseek-v4-pro │ ctx -- │ [░░░░░░░░░░] -- │ 5s │ ⏲ 0s
```

再输入一次 `/panel`，面板消失：

```
L42-PANEL-STATE: hidden
```

| 你观察到的 | 说明什么 |
|---|---|
| 面板文字在状态栏**正上方**，不在底部 | `_get_extra_tui_widgets()` 返回的列表被插在 `spacer` 之后、`status_bar` 之前 [[src:extending-the-cli]] |
| `/panel` 能切换可见性，且没有「未知命令」提示 | `process_command()` 覆写生效：命中自己的命令返回 `True`，其余交给 `super().process_command(cmd)` [[src:extending-the-cli]] |
| 刻意写错面板内容时，traceback 里有 `hermes_cli/cli_tui_mixin.py:403` | 那一行就是 `*self._get_extra_tui_widgets(),`：钩子确实被 TUI 的布局构建调用了 |

改完状态如果界面慢一拍才刷新，就是漏了 `self._invalidate()` [[src:extending-the-cli]]。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| 照官方文档第一个示例写 `Window(..., filter=Condition(...))`，程序直接崩：`TypeError: Window.__init__() got an unexpected keyword argument 'filter'` | `Window` 根本没有 `filter` 形参；本 release 把 `prompt_toolkit` 钉在 `3.0.52`（安装树 `pyproject.toml:66`），本机实测其 `Window.__init__` 参数里确实没有 `filter` | 换成同页另一种写法：`ConditionalContainer(content=Window(...), filter=Condition(...))` [[src:extending-the-cli]] |
| 文档给的 `source .venv/bin/activate` 在本机报 `No such file or directory` | 本机 venv 是 `venv/Scripts/`，**没有** `.venv/bin/activate` | 在安装树根目录下跑 `./venv/Scripts/python.exe my_cli.py` |
| `from cli import HermesCLI` 报 `ModuleNotFoundError: No module named 'cli'` | 安装树根目录才是 `cli.py` 所在处，运行时它需要在 `sys.path` 上 | 先 `cd` 到安装树根再运行；`my_cli.py` 本身放哪都行 [[src:extending-the-cli]] |
| 覆写了钩子，界面没变化 / 慢一拍 | prompt_toolkit 不会因为你改了 Python 属性就自动重绘 | 状态改完调 `self._invalidate()` [[src:extending-the-cli]] |
| 自定义快捷键按了没反应，或把输入搞坏了 | 撞上内置键位：`Enter`（提交）、`Escape Enter`（换行）、`Ctrl-C`（中断）、`Ctrl-D`（退出）、`Tab`（接受补全建议） | 用 F2 及以上的功能键或 Ctrl 组合 [[src:extending-the-cli]] |
| 以为 TUI 能像 Web 面板那样装插件（翻找 `plugin.js` / shell slot / tab） | TUI 没有插件 API —— 只有 `HermesCLI` 上那五个钩子 | 要插件系统得去 Web 面板或桌面端（见本课「下一步」）；TUI 里能做的只有插 widget / 加键位 / 加斜杠命令 [[src:extending-the-cli]] |
| 改了 `config.yaml` 里的皮肤，界面没变 | 配置文件是启动时读的；会话内要实时切换得用斜杠命令 | 会话里 `/skin ares`（当场重绘），或新开一个会话 [[src:tui]] |
| 皮肤名打错，命令照样成功 | 命令行不做存在性校验 | `hermes config get display.skin` + 会话里 `/skin` 复核 [[src:skins]] |
| 宠物装了还是不显示 | 必须同时满足「已安装 + 已选中（`enabled: true`）」；管道/重定向里没有 TTY，终端渲染按设计关闭 | `hermes pets install <slug> --select`，再在新终端里 `hermes pets show` [[src:pets]] |
| `hermes pets list` 找不到自己用 petdex npm CLI 装的宠物 | 那个 CLI 装到 `~/.codex/pets`，Hermes 用自己的 `<HERMES_HOME>/pets/` | 通过 `hermes pets install` 装 [[src:pets]] |
| TUI 里鼠标拖选行为不对（tmux 下疯狂弹提示） | `mouse_tracking` 的档位选择 | 改成 `wheel`（只留滚动+点击，去掉 hover）[[src:tui]] |

## 试一试

- [ ] 写一个自定义皮肤 `~/.hermes/skins/<你的名字>.yaml`，只改三个颜色 + `thinking_verbs`，用 `/skin <你的名字>` 切过去
- [ ] 在 TUI 里用 `/details tools collapsed` 与 `/details tools expanded` 各跑一轮，说明 `display.sections` 覆盖了什么
- [ ] 装一只宠物（`hermes pets install boba --select`）后重跑 `hermes pets doctor`，说出多出来的行分别代表什么
- [ ] 写一个只挂 `statusBar.right` 一个按钮的桌面插件（`jsx()` 写法，做法见 [[L46]]），保存后确认它热重载进界面
- [ ] 判断：这三件事分别该改皮肤、改 `display.*` 配置，还是写桌面插件？① 把成功提示改成绿色以外的颜色 ② 让工具调用默认折叠 ③ 在标题栏加一个「重启网关」按钮
- [ ] 把结果记到 `journal/` 里并提交（见 CONTRIBUTING.md 的会话总结流程）
- [ ] 写一个只覆写 `_get_extra_tui_widgets()` 的 wrapper CLI，让面板文字显示当前模型名（提示：`self.model`；跑起来后确认它出现在状态栏那一行的正上方）
- [ ] 再覆写 `_register_extra_tui_keybindings(kb, *, input_area)`，用 `F2` 切换同一个面板（提示：改完状态要 `self._invalidate()`）
- [ ] 判断：把 `hermes dashboard` 的主题 YAML 放到 `~/.hermes/skins/` 会不会生效？为什么？

## 下一步

### 收尾：四套外观系统互不相通

这一课改的是**终端**。Hermes 一共四套外观/扩展机制，谁也管不到谁：

| 你想改的 | 属于哪一套 | 动什么 | 官方文档 |
|---|---|---|---|
| 终端里的颜色 / spinner / banner / 提示符 | CLI 皮肤 | `~/.hermes/skins/<名字>.yaml` + `display.skin`，会话里 `/skin` | `user-guide/features/skins.md` [[src:skins]] |
| TUI 里某一节折叠状态、鼠标行为 | TUI 配置 | `display.details_mode` / `display.sections` / `display.mouse_tracking`，会话里 `/details`、`/mouse` | `user-guide/tui.md` [[src:tui]] |
| 往 TUI 里加一个自己的部件 / 键位 / 斜杠命令 | TUI 部件（wrapper CLI） | 子类化 `HermesCLI`，覆写那五个钩子 | `developer-guide/extending-the-cli.md` [[src:extending-the-cli]] |
| 浏览器里 `hermes dashboard` 的配色、标签页、往里插组件 | Web 面板 | `~/.hermes/dashboard-themes/*.yaml`（主题）+ 插件目录（`manifest.json` + JS bundle：tab / shell slot） | `user-guide/features/extending-the-dashboard.md` |
| 桌面应用侧栏/状态栏里的按钮 | 桌面端 | `$HERMES_HOME/desktop-plugins/<id>/plugin.js`（`@hermes/plugin-sdk`，不编译、无构建步骤） | `developer-guide/desktop-plugin-sdk.md` |

三条边界记牢：

- TUI 部件**没有**插件 API、没有 shell slot、没有 tab、没有 `plugin.js` —— 它只有那五个 Python 钩子，所以你能加的只有「往 TUI 布局里插一个 prompt_toolkit widget / 加一个键位 / 加一条斜杠命令」[[src:extending-the-cli]]。
- 反过来，`hermes skin` 也管不到 Web 面板和桌面端的外观 —— 皮肤是 CLI 的颜色与品牌文本，`/skin` 只重绘终端 [[src:skins]]。
- 官方文档自己就把这两件事分开写：`extending-the-dashboard.md` 顶部有一个 **Not the desktop app** 的提示框，写明 dashboard 插件系统（`window.__HERMES_PLUGIN_SDK__` + `manifest.json` + 预构建 JS bundle）与桌面 SDK（`@hermes/plugin-sdk`，单个 ESM 文件、无构建步骤）是两套无关的东西，唯一共用的是后端 `plugin_api.py` 的 `/api/plugins/<name>` 命名空间 —— 原文：https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard 。
- 唯一真正跨界的是**宠物**：同一只 sprite 在 CLI、TUI、桌面端都会画（桌面端是浮动精灵，Settings → Appearance 里开关）。装饰品跨界，机制不跨界 [[src:pets]]。

那么 Web 面板和桌面端这两套机制具体怎么写？各自单独一课：

- [[L45]] —— Web 面板：`hermes dashboard` 的 YAML 主题（`~/.hermes/dashboard-themes/`）与插件（tab / shell slot / `/api/plugins/<name>` 后端路由）
- [[L46]] —— 桌面端：`$HERMES_HOME/desktop-plugins/<id>/plugin.js`、`jsx()` 而非 JSX、只有三个 import 能解析
- [[L43]] —— 当你要接的是别人的工具服务器，而不是改外观
- [[L41]] —— `register(ctx)` 那一层：扩展内核行为的插件是怎么写的
- 想深入：[[src:extending-the-cli]] 的 Hook reference 与 Layout diagram —— 每个钩子的签名，以及 `_build_tui_layout_children(**widgets)` 的完整默认列表

## 出处

- [[src:skins]] Skins & Themes — https://hermes-agent.nousresearch.com/docs/user-guide/features/skins
- [[src:tui]] TUI — https://hermes-agent.nousresearch.com/docs/user-guide/tui
- [[src:pets]] Pets (Petdex Mascots) — https://hermes-agent.nousresearch.com/docs/user-guide/features/pets
- [[src:extending-the-cli]] Extending the CLI — https://hermes-agent.nousresearch.com/docs/developer-guide/extending-the-cli
