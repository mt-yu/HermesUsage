# HermesUsage 教程站（前端交互界面 + 快速部署）实施计划

> **For Hermes:** 用 subagent-driven-development 逐任务实施：每个任务一个新子代理，先规格复核再代码质量复核。

**Goal:** 给 `D:\Projects\ai_projects\HermesUsage` 这套 Hermes 教程做一个可交互的静态前端站点（按阶段浏览、全站搜索、进度打卡、`[[src:id]]` 出处可点可核对），并让它能用一条命令构建、一条命令本地预览、三种方式部署。

**Architecture:** `lessons/*.md` 是唯一内容源；新增 `scripts/tutorial_core.py`（唯一解析层）+ `scripts/site_render.py`（纯函数：Markdown→HTML、出处/交叉引用改写）+ `scripts/build_site.py`（构建器，产出 `site/`）；前端是 `web/` 下的手写 HTML 模板 + CSS + 原生 ES 模块（**不引入任何 npm 依赖、不需要打包器**），构建时被复制进 `site/`。部署 = 把 `site/` 这一堆静态文件放到任何 HTTP 服务器后面（本地 `serve.py` / Docker+nginx / Netlify / Vercel / GitHub Pages）。

**Tech Stack:** Python 3.11（PyYAML、Markdown）+ 原生 ES 模块 + Node 24 内置测试器（仅跑单元测试，`package.json` 无 dependencies）+ nginx:alpine（Docker 镜像）。

**时间预算（实测）：** 参照物是仓库现有规模 —— 32 课 / 456KB 正文 / 89 条出处。构建产物约 1.2MB。

---

## 1. 现状与假设（已实测，不要重复猜）

以下事实是本次规划时在目标机器上跑出来的，实施者可以信任：

| 事实 | 证据 |
|---|---|
| 仓库 32 课，路径形如 `lessons/01-core/L15-skills.md` | `ls lessons/*/*.md \| wc -l` → `32` |
| 每课 frontmatter 9 个必填字段，正文 8 个 `## ` 小节 | `scripts/verify.py:50-51` |
| 每课正文开头的 `> **一句话**：…` 32 课全都有 | `grep -l '一句话' lessons/*/*.md \| wc -l` → `32` |
| 出处共 89 条，`sources/citations.yaml` 每条含 `id/title/url/hermes_version/sha256/...` | `sources/citations.yaml` 头部 + `scripts/verify.py` |
| 基线：`hermes v0.21.3`、文档提交 `05fac10a`（2026-09-15） | `sources/citations.yaml:2-3` |
| 全仓库只有 **1 个** 指向仓库内的相对链接：`../../.hermes.md` | `grep -oh '](\.\.\?/[^)]*)' lessons/*/*.md` |
| 课程里没有图片、没有脚注 | `grep -c '!\[' lessons/*/*.md` 全 0 |
| 代码围栏语言只有：无语言 / bash / text / yaml / python / markdown / json / jsonc / javascript | `grep -h '^\`\`\`' lessons/*/*.md \| sort \| uniq -c` |
| 正文中**代码围栏与行内反引号之外**没有裸的 HTML 标签（不会渲染丢失） | 见附录 A 的检查脚本，输出 `0` |
| 本机 Python 3.11.15 已装 `yaml 6.0.3` / `markdown 3.10.2`；**没有 pytest** | `python -c "import markdown"` / `python -m pytest` 报 ModuleNotFoundError |
| 本机 Node v24.11.0，支持 `node --test` | `node --test --help` 可用 |
| **本机没有 docker**（`docker: command not found`） | 所以 Docker 相关任务只能做「同命令本机跑通」级别的验证 |
| 仓库**没有 git remote** | `git remote -v` 为空 → GitHub Pages 部署只能是「作者按文档做」，无法在本机验证 |
| `.gitignore` 已忽略 `build/`、`dist/`、`progress/.state.json` | 本计划新增 `site/` |

**读者画像（决定 UI 取舍）：** 第一次用 Hermes、英语一般、想快速看到「我该学哪一课」。所以首页第一屏必须是**可点的课程列表 + 进度条 + 下一课按钮**，不是营销落地页。

**上游约束（来自 `.hermes.md`，不可违反）：**

- R1 8 小节固定；R3 `[[src:id]]` 必须三处一致；R5 中文正文/英文代码；R6 不用「强大/优雅」；R8 写文件必须 `encoding="utf-8"` + `newline="\n"`。
- 「规范写在脚本里，不写在散文里」→ 站点也有自己的门禁：`python scripts/build_site.py --check`。
- 「没跑过 verify 的改动不算改完」→ 本计划的最终验收命令是 `python scripts/check.py`（内含 verify）。

---

## 2. 交付物与目录地图

**新增（进 git）：**

```
requirements.txt                      新增：pip 依赖（PyYAML / Markdown）
site.json                             站点配置：标题、tagline、repo_url、repo_docs 白名单
package.json                          只用来声明 "type": "module" + 提供 npm test（无依赖）
scripts/tutorial_core.py              ★ 唯一的课程/出处解析层（数据）
scripts/site_render.py                ★ 纯函数渲染层（Markdown→HTML、[[src:]]/[[Lxx]] 改写）
scripts/build_site.py                 ★ 构建器：lessons/ + web/ → site/；--check 自检
scripts/serve.py                      本地预览（标准库 http.server）
scripts/check.py                      ★ 一条命令跑完 verify + 单元测试 + 站点自检
web/partials/layout.html              页面骨架（占位符 {{...}}）
web/assets/app.css                    主题 + 布局 + 组件（完整可粘贴）
web/assets/app.js                     前端入口：搜索面板/目录/进度/主题/复制
web/assets/lib/util.js                纯函数：escapeHtml / debounce / formatMinutes
web/assets/lib/search.js              纯函数：tokenize / search / snippet（中文按二字切分）
web/assets/lib/progress.js            纯函数：toggleDone / completion / nextLesson / blocked
web/assets/lib/storage.js             localStorage 读写 + parseState 校验 + 下载
web/assets/lib/toc.js                 纯函数：pickActive / headingOffsets
tests/__init__.py                     让 `unittest discover -s tests -t .` 可用的包标记（必需，计划初稿漏了）
tests/test_tutorial_core.py           Python 单元测试（数据层）
tests/test_site_render.py             Python 单元测试（渲染层，含全仓库内容回归）
tests/test_build_site.py              Python 集成测试（构建到临时目录 + 链接自检）
tests/js/*.test.js                    Node 内置测试器跑的前端单元测试
Dockerfile / .dockerignore            镜像：构建站 → nginx 托管
docker-compose.yml                    一条命令起站
deploy/nginx.conf                     容器内的 nginx 配置（gzip / 缓存 / try_files）
netlify.toml / vercel.json            两个静态托管的零配置构建
docs/deploy.md                        部署手册（5 种方式 + 排障）
.github/workflows/ci.yml              每次 push/PR：python scripts/check.py
.github/workflows/pages.yml           main 分支：verify → build → 发布 GitHub Pages
```

**修改（进 git）：**

```
.gitignore              新增 site/（构建产物，不进 git）
.gitattributes          新增 *.css *.js *.mjs（eol=lf）
README.md               新增「在线看 / 本地看」段落 + 命令表 + 部署链接
.hermes.md              §1 目录地图、§3 检查命令、§6 坑表、§7 环境事实
ROADMAP.md              「维护待办（系统层）」勾掉 CI；新增「前端站点」小节
CONTRIBUTING.md         门禁命令统一成 python scripts/check.py
.hermes/skills/hermes-tutorial-authoring/SKILL.md   新增第 7 步：改完课要看站点是否重建
scripts/build_map.py    迁移到 tutorial_core（行为字节不变）
```

**构建产物（被 .gitignore 忽略）：**

```
site/index.html                 首页（静态渲染的课程列表 + 进度卡）
site/404.html
site/lessons/<slug>.html        32 个课程页
site/repo/<slug>.html           仓库规范页（.hermes.md / CONTRIBUTING.md / ROADMAP.md / sources/README.md / templates/lesson.md / progress/checklist.md）
site/assets/**                  从 web/assets 原样拷贝
site/data/index.json            课程元数据（前端导航/搜索/进度用）
site/data/citations.json        出处元数据（id → url/version/sha256）
site/data/search.json           全文检索数据（约 450KB，交给 nginx/Netlify gzip）
site/data/manifest.json         构建清单：每课源文件 sha256 + 出处基线 + 构建时间
site/.nojekyll                  GitHub Pages 下不要用 Jekyll 处理
```

**URL 方案（定死，不要改）：** `site/lessons/L15-skills.html`（`.html` 结尾，不是目录式 pretty URL —— 目录式需要 nginx 与各家托管的 try_files 配置各不相同，换来的是跨平台一致性）。

**两套链接前缀（最容易搞混的地方，务必分清）：**

| 用途 | 从首页出发 | 从课程页出发 |
|---|---|---|
| 指向另一课 | `lessons/L15-skills.html` | `L15-skills.html`（同级） |
| 指向仓库规范页 | `repo/hermes-md.html` | `../repo/hermes-md.html` |
| 指向站点资源 | `assets/app.css` | `../assets/app.css` |

代码里统一用 `link_for(lesson)` 函数参数解决，不要手写字符串拼接。

---

## 3. 数据流

```
lessons/*.md ──┐
               ├─► tutorial_core.load_lessons()  ─► list[dict]（含 summary/slug/page/url/body）
sources/       │
 citations.yaml├─► tutorial_core.load_citations()─► dict[id]{url,title,hermes_version,sha256}
 registry.yaml │
               └─► tutorial_core.source_baseline()─► {version, commit, generated}
                                   │
                                   ▼
                        site_render（纯函数）
        render_markdown  →  (html, toc)       ← 自己给 h2/h3 编号，不用 markdown 的 toc 扩展
        linkify_citations →  [[src:id]] → <a class="cite" href=官方URL title=版本+hash>
        linkify_xrefs     →  [[L13]]    → <a class="xref" href="L13-memory.html">
        render_template   →  {{title}} 占位符填充（残留一个就报错）
                                   │
                                   ▼
                        build_site.build()  →  site/**
                                   │
                                   ▼
                        浏览器：app.js
        fetch data/index.json  → 侧栏打勾 / 进度条 / 下一课
        fetch data/search.json（首次搜索才下载）→ 命令面板
        localStorage["hermes-usage:progress:v1"] ← 与 progress/.state.json 同结构
```

---

## 4. 任务清单

### 约定（每个任务都适用）

- 全部命令在仓库根目录 `D:\Projects\ai_projects\HermesUsage` 下、Git Bash 里执行。
- 写文件一律用 `write_file`；Python 里写文件必须 `encoding="utf-8", newline="\n"`（R8）。
- **中间提交**用普通 git（`test:` / `feat:` / `docs:` 前缀）；**整个计划的收尾**用 `python scripts/journal.py commit --kind session ...`（它会 `git add -A` 并提交）。
- 每个任务结尾的「验证」没通过就不要提交，先修。

---

### 任务 T1 — 依赖与忽略规则基线

**目标：** 声明依赖、忽略构建产物，并确认仓库当前是健康的（在健康的地基上动手）。

**文件：**
- 新建 `requirements.txt`
- 修改 `.gitignore`
- 修改 `.gitattributes`

**步骤 1：写 `requirements.txt`**

```
# 构建教程站的 Python 依赖（都是纯 Python，无编译）
PyYAML>=6.0,<7
Markdown>=3.5,<4
```

**步骤 2：`pip install` 并确认版本**

```bash
python -m pip install -r requirements.txt
python -c "import yaml, markdown; print('yaml', yaml.__version__, 'markdown', markdown.__version__)"
```

期望输出（版本号可能更高，但不能报 ImportError）：

```
yaml 6.0.3 markdown 3.10.2
```

**步骤 3：`.gitignore` 追加（放在「临时产物」段之后）**

```gitignore
# 站点构建产物（由 python scripts/build_site.py 生成，不进 git）
site/
```

**步骤 4：`.gitattributes` 追加（放在 `*.html` 那一段后面）**

```gitattributes
*.css  text eol=lf
*.js   text eol=lf
*.mjs  text eol=lf
```

**步骤 5：验证地基健康**

```bash
python scripts/verify.py
```

期望输出（最后两行）：

```
通过：32 课全部合规（0 个警告）
```

**步骤 6：提交**

```bash
git add requirements.txt .gitignore .gitattributes
git commit -m "feat: 教程站依赖声明与构建产物忽略规则"
```

---

### 任务 T2 — 第一条失败测试：frontmatter 解析

**目标：** 建立 `tests/` 骨架，并用 TDD 逼出 `scripts/tutorial_core.py` 的第一个函数。

**文件：**
- 新建 `tests/test_tutorial_core.py`

**步骤 1：写测试（此时 `tutorial_core` 还不存在 → 必须失败）**

```python
#!/usr/bin/env python3
"""tests/test_tutorial_core.py —— 解析层单元测试。

运行：python -m unittest discover -s tests -t . -p "test_*.py" -v
为什么不用 pytest：仓库只承诺 PyYAML + Markdown 两个依赖，pytest 不在其中（本机也没装）。
标准库 unittest 够用，且不增加任何安装步骤。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import tutorial_core as core  # noqa: E402

SAMPLE = """---
id: L99
title: 示例课
stage: 3
level: 进阶
minutes: 20
prereq: [L10]
tags: ["@引用", "示例"]
sources: [quickstart, agent-loop]
updated: 2026-09-16
---

# L99 · 示例课

> **一句话**：这一课用来验证解析层。

## 你将学会

- 解析 frontmatter
"""


class TestFrontmatter(unittest.TestCase):
    def test_parse_frontmatter_fields(self):
        fm = core.parse_frontmatter(SAMPLE)
        self.assertEqual(fm["id"], "L99")
        self.assertEqual(fm["stage"], 3)
        self.assertEqual(fm["prereq"], ["L10"])
        self.assertEqual(fm["sources"], ["quickstart", "agent-loop"])

    def test_parse_frontmatter_without_frontmatter_returns_empty(self):
        self.assertEqual(core.parse_frontmatter("# 只有正文\n"), {})

    def test_parse_frontmatter_with_broken_yaml_returns_empty(self):
        broken = "---\nid: L99\ntitle: [未闭合\n---\n\n# x\n"
        self.assertEqual(core.parse_frontmatter(broken), {})

    def test_split_frontmatter_returns_body(self):
        fm, body = core.split_frontmatter(SAMPLE)
        self.assertEqual(fm["id"], "L99")
        self.assertTrue(body.startswith("\n# L99 · 示例课"))


if __name__ == "__main__":
    unittest.main()
```

**步骤 2：跑测试，确认失败**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`ModuleNotFoundError: No module named 'tutorial_core'`（收集阶段就失败，这就是「红」）。

**步骤 3：不提交**（实现见 T3，红绿一起提交）

---

### 任务 T3 — 最小实现让 T2 变绿

**文件：** 新建 `scripts/tutorial_core.py`

**步骤 1：写实现**

```python
#!/usr/bin/env python3
"""scripts/tutorial_core.py —— 课程与出处解析层（唯一真相来源）。

为什么单独抽出这个文件
----------------------
在此之前，build_index.py / build_map.py / verify.py / progress.py 各自抄了一份
frontmatter 解析和阶段表。第五个消费者（静态站点构建器）出现时必须停下来：
再抄一份，必然出现「站点显示 31 课、门禁认为 32 课」这种自己骗自己的不一致。

本模块只做只读解析：不写文件、不打印日志、不 sys.exit。
构建器负责「怎么渲染」，门禁负责「合不合规」，这里只负责「仓库里到底有什么」。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("需要 PyYAML：python -m pip install -r requirements.txt")

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
SUMMARY_RE = re.compile(r"^>\s*\*\*一句话\*\*[：:]\s*(.+?)\s*$", re.M)

# 阶段表：站点首页、索引、学习地图都从这里取名字，别再各写一份
STAGES: dict[int, dict[str, str]] = {
    0: {"name": "认识 Hermes", "why": "先建立正确的心智模型"},
    1: {"name": "会用 Hermes", "why": "核心五件事：模型/工具/会话/记忆/技能"},
    2: {"name": "日常威力", "why": "把 agent 当主力用"},
    3: {"name": "自动化与多代理", "why": "它在你不在的时候也干活"},
    4: {"name": "扩展与改造", "why": "缺什么自己加"},
    5: {"name": "运维与安全", "why": "敢放在每天在用的机器上"},
    9: {"name": "毕业项目", "why": "自动化一件你真正在做的活"},
}


def stage_name(stage: int) -> str:
    return STAGES.get(stage, {}).get("name", f"阶段 {stage}")


def stage_why(stage: int) -> str:
    return STAGES.get(stage, {}).get("why", "")


def parse_frontmatter(text: str) -> dict[str, Any]:
    """解析 ---...--- 之间的 YAML；没有或坏掉都返回 {}（坏掉的由 verify.py 报错）。"""
    m = FM_RE.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """返回 (frontmatter, 正文)。渲染器只要正文。"""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    return parse_frontmatter(text), text[m.end():]


def lesson_summary(body: str) -> str:
    """抓「> **一句话**：…」—— 首页卡片与搜索结果用它，比截断正文可读。"""
    m = SUMMARY_RE.search(body)
    return m.group(1).strip() if m else ""


def lesson_slug(rel: str | Path) -> str:
    """lessons/01-core/L15-skills.md -> L15-skills（URL 用，稳定）。"""
    return Path(rel).stem


def lesson_page(rel: str | Path) -> str:
    """同级页面名：L15-skills.html（课程页里互相引用用这个）。"""
    return f"{lesson_slug(rel)}.html"


def lesson_url(rel: str | Path) -> str:
    """站点内绝对路径（相对站点根）：lessons/L15-skills.html。"""
    return f"lessons/{lesson_page(rel)}"
```

**步骤 2：跑测试，确认变绿**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望输出结尾：

```
Ran 4 tests in 0.0XXs

OK
```

**步骤 3：提交**

```bash
git add scripts/tutorial_core.py tests/test_tutorial_core.py
git commit -m "feat: 抽出 tutorial_core 解析层（frontmatter/split）"
```

---

### 任务 T4 — 摘要、slug、URL 的测试与实现

**文件：** 修改 `tests/test_tutorial_core.py`（追加类）、修改 `scripts/tutorial_core.py`（已含实现）

**步骤 1：追加测试**

```python
class TestDerivedFields(unittest.TestCase):
    def test_lesson_summary(self):
        _, body = core.split_frontmatter(SAMPLE)
        self.assertEqual(core.lesson_summary(body), "这一课用来验证解析层。")

    def test_lesson_summary_missing(self):
        self.assertEqual(core.lesson_summary("## 正文\n没有一句话摘要\n"), "")

    def test_slug_and_urls(self):
        rel = "lessons/01-core/L15-skills.md"
        self.assertEqual(core.lesson_slug(rel), "L15-skills")
        self.assertEqual(core.lesson_page(rel), "L15-skills.html")
        self.assertEqual(core.lesson_url(rel), "lessons/L15-skills.html")

    def test_slug_accepts_path_object(self):
        self.assertEqual(core.lesson_slug(Path("lessons/06-capstone/L90-capstone.md")), "L90-capstone")

    def test_stage_names(self):
        self.assertEqual(core.stage_name(3), "自动化与多代理")
        self.assertEqual(core.stage_name(42), "阶段 42")
        self.assertTrue(core.stage_why(1))
```

**步骤 2：跑测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 9 tests ... OK`（实现在 T3 已一并写好，这一步是补测试网）。

**步骤 3：提交**

```bash
git add tests/test_tutorial_core.py
git commit -m "test: 覆盖摘录/slug/URL/阶段名派生字段"
```

---

### 任务 T5 — `load_lessons()`：测试它和真仓库对得上

**文件：** 修改 `tests/test_tutorial_core.py`、修改 `scripts/tutorial_core.py`

**步骤 1：追加测试（对真实仓库断言，不是 mock）**

```python
class TestLoadLessonsOnRealRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lessons = core.load_lessons(REPO)

    def test_count_matches_repo(self):
        self.assertEqual(len(self.lessons), 32)

    def test_sorted_by_stage_then_id(self):
        keys = [(l["stage"], l["id"]) for l in self.lessons]
        self.assertEqual(keys, sorted(keys))

    def test_every_lesson_has_answerable_fields(self):
        for l in self.lessons:
            self.assertRegex(l["id"], r"^L\d{2,}$")
            self.assertTrue(l["title"])
            self.assertTrue(l["summary"], f"{l['id']} 缺「一句话」摘要")
            self.assertTrue(l["sources"], f"{l['id']} 没有出处")
            self.assertTrue(l["url"].startswith("lessons/"))
            self.assertTrue(l["body"].startswith("\n#"), f"{l['id']} 正文异常")

    def test_first_and_last(self):
        self.assertEqual(self.lessons[0]["id"], "L00")
        self.assertEqual(self.lessons[-1]["id"], "L90")
```

**步骤 2：在 `scripts/tutorial_core.py` 末尾追加实现**

```python
def load_lessons(repo: Path) -> list[dict[str, Any]]:
    """扫描 lessons/**/*.md，返回排序好的课程字典列表。

    没有 frontmatter 的文件直接跳过：它们要么是坏文件、要么不是课程，
    报错是 verify.py 的职责，构建器不该替它做判断。
    """
    rows: list[dict[str, Any]] = []
    for path in sorted((repo / "lessons").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        if not fm:
            continue
        rel = path.relative_to(repo).as_posix()
        rows.append(
            {
                "id": str(fm.get("id", "")),
                "title": str(fm.get("title", "")),
                "stage": int(fm.get("stage", 0)),
                "level": str(fm.get("level", "")),
                "minutes": int(fm.get("minutes", 0)),
                "prereq": [str(x) for x in (fm.get("prereq") or [])],
                "tags": [str(x) for x in (fm.get("tags") or [])],
                "sources": [str(x) for x in (fm.get("sources") or [])],
                "updated": str(fm.get("updated", "")),
                "summary": lesson_summary(body),
                "rel": rel,
                "slug": lesson_slug(rel),
                "page": lesson_page(rel),
                "url": lesson_url(rel),
                "path": path,
                "body": body,
            }
        )
    rows.sort(key=lambda r: (r["stage"], r["id"]))
    return rows


def group_by_stage(lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 stage 分组，保持传入顺序（load_lessons 已排好）。"""
    groups: list[dict[str, Any]] = []
    for lesson in lessons:
        if not groups or groups[-1]["stage"] != lesson["stage"]:
            groups.append(
                {
                    "stage": lesson["stage"],
                    "name": stage_name(lesson["stage"]),
                    "why": stage_why(lesson["stage"]),
                    "lessons": [],
                }
            )
        groups[-1]["lessons"].append(lesson)
    return groups
```

**步骤 3：跑测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 13 tests ... OK`。如果 `test_count_matches_repo` 失败并报出实际数字，**以实际数字为准改测试**（课程数量会随内容增长，不要为了测试去删课）。

**步骤 4：提交**

```bash
git add scripts/tutorial_core.py tests/test_tutorial_core.py
git commit -m "feat: load_lessons + group_by_stage 并加真仓库断言"
```

---

### 任务 T6 — `load_citations()` 与 `source_baseline()`

**文件：** 修改 `tests/test_tutorial_core.py`、修改 `scripts/tutorial_core.py`

**步骤 1：追加测试**

```python
class TestCitations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.citations = core.load_citations(REPO)

    def test_all_registered(self):
        self.assertGreaterEqual(len(self.citations), 89)

    def test_entry_shape(self):
        entry = self.citations["quickstart"]
        self.assertTrue(entry["url"].startswith("https://hermes-agent.nousresearch.com/docs"))
        self.assertEqual(len(str(entry["sha256"])), 64)
        self.assertTrue(entry["title"])

    def test_every_lesson_source_is_registered(self):
        for lesson in core.load_lessons(REPO):
            for sid in lesson["sources"]:
                self.assertIn(sid, self.citations, f"{lesson['id']} 引用了未登记的 {sid}")

    def test_baseline(self):
        b = core.source_baseline(REPO)
        self.assertEqual(b["version"], "0.21.3")
        self.assertTrue(b["commit"].startswith("05fac10a"))
        self.assertGreaterEqual(b["count"], 89)
```

**步骤 2：追加实现**

```python
BASELINE_RE = re.compile(r"^#\s*生成时间:\s*(\S+)\s+hermes v(\S+)", re.M)
COMMIT_RE = re.compile(r"@\s*([0-9a-f]{7,40})")


def load_citations(repo: Path) -> dict[str, dict[str, Any]]:
    """读 sources/citations.yaml：id → 出处元数据（URL / 版本 / 快照哈希）。"""
    path = repo / "sources" / "citations.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return {str(entry["id"]): entry for entry in data if isinstance(entry, dict) and "id" in entry}


def source_baseline(repo: Path) -> dict[str, Any]:
    """从 citations.yaml 的头部注释里取出「出处基线」——站点页脚要展示它。

    这行信息本来就写在文件头（sync_sources.py 生成的），
    让站点复用它，读者点开页脚就知道整站的事实基线是哪一版官方文档。
    """
    path = repo / "sources" / "citations.yaml"
    if not path.exists():
        return {"version": "", "commit": "", "generated": "", "count": 0}
    head = path.read_text(encoding="utf-8")[:800]
    m_time = BASELINE_RE.search(head)
    m_commit = COMMIT_RE.search(head)
    return {
        "version": m_time.group(2) if m_time else "",
        "generated": m_time.group(1) if m_time else "",
        "commit": (m_commit.group(1)[:8] if m_commit else ""),
        "count": len(load_citations(repo)),
    }
```

**步骤 3：跑测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 17 tests ... OK`。

**步骤 4：提交**

```bash
git add scripts/tutorial_core.py tests/test_tutorial_core.py
git commit -m "feat: load_citations + source_baseline（站点页脚复用出处基线）"
```

---

### 任务 T7 — 段内分组测试 + 数据层收尾

**文件：** 修改 `tests/test_tutorial_core.py`

**步骤 1：追加测试**

```python
class TestGrouping(unittest.TestCase):
    def test_groups_cover_all_stages(self):
        groups = core.group_by_stage(core.load_lessons(REPO))
        self.assertEqual([g["stage"] for g in groups], [0, 1, 2, 3, 4, 5, 9])
        self.assertEqual(sum(len(g["lessons"]) for g in groups), 32)
        self.assertEqual(groups[-1]["name"], "毕业项目")

    def test_group_keeps_lesson_order(self):
        groups = core.group_by_stage(core.load_lessons(REPO))
        stage1 = next(g for g in groups if g["stage"] == 1)
        self.assertEqual([l["id"] for l in stage1["lessons"]], ["L10", "L11", "L12", "L13", "L14", "L15"])
```

**步骤 2：跑测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 19 tests ... OK`。

**步骤 3：确认没有打扰现有门禁**

```bash
python scripts/verify.py --quiet && echo "门禁仍绿"
```

期望：`门禁仍绿`。

**步骤 4：提交**

```bash
git add tests/test_tutorial_core.py
git commit -m "test: 阶段分组覆盖与顺序"
```

**数据层完成。** `scripts/tutorial_core.py` 现在是全仓库唯一的解析入口（`build_map.py` 的迁移放到 T41，避免在大改中间动已验证的脚本）。

---

### 任务 T8 — 渲染层失败测试：注释剥离与练习打勾

**文件：** 新建 `tests/test_site_render.py`

**步骤 1：写测试**

```python
#!/usr/bin/env python3
"""tests/test_site_render.py —— 渲染层纯函数单元测试 + 全仓库内容回归。"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import site_render as R  # noqa: E402
import tutorial_core as core  # noqa: E402


class TestPreprocess(unittest.TestCase):
    def test_strips_template_comments(self):
        src = "前<!-- 这是给作者看的（含 [[src:xxx]]） -->后"
        self.assertEqual(R.strip_template_comments(src).strip(), "前后")

    def test_tasklist_becomes_visual_box(self):
        out = R.preprocess_tasklist("- [ ] 练习一\n- [x] 练习二\n")
        self.assertIn('<span class="task-box" data-checked="0" aria-hidden="true"></span> 练习一', out)
        self.assertIn('<span class="task-box" data-checked="1" aria-hidden="true"></span> 练习二', out)
        self.assertNotIn("[ ]", out)

    def test_tasklist_ignores_normal_bullets_and_code(self):
        out = R.preprocess_tasklist("- 普通条目\n\n```bash\n- [ ] 这不是练习\n```\n")
        self.assertNotIn("task-box", out)


if __name__ == "__main__":
    unittest.main()
```

**步骤 2：跑测试，确认失败**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`ModuleNotFoundError: No module named 'site_render'`。

---

### 任务 T9 — 实现 `site_render` 的预处理部分

**文件：** 新建 `scripts/site_render.py`

**步骤 1：写实现（先只放预处理 + 工具，渲染在 T11/T13 追加）**

```python
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


class SiteError(RuntimeError):
    """站点构建错误。消息必须带上下文（哪一课、哪个标记），否则等于没报错。"""


def escape(text: str) -> str:
    return html_mod.escape(str(text), quote=True)


def strip_template_comments(text: str) -> str:
    """删掉 HTML 注释：课程模板里的写作提示不该出现在读者眼前。"""
    return COMMENT_RE.sub("", text)


def preprocess_tasklist(text: str) -> str:
    """`- [ ] 练习` → 带方框的行。

    用 <span> 而不是 <input>：Markdown 的 HTML 块规则会把块级 <input> 当独立
    段落处理，把「练习」折到下一行；span 是行内元素，不会改变列表结构。
    """

    def repl(m: re.Match[str]) -> str:
        checked = "1" if m.group(2).lower() == "x" else "0"
        return f'{m.group(1)}<span class="task-box" data-checked="{checked}" aria-hidden="true"></span> {m.group(3)}'

    return TASKLIST_RE.sub(repl, text)


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
```

**步骤 2：跑测试，确认变绿**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 22 tests ... OK`。

**步骤 3：提交**

```bash
git add scripts/site_render.py tests/test_site_render.py
git commit -m "feat: site_render 预处理（注释剥离、练习方框、代码区保护）"
```

---

### 任务 T10 — 失败测试：标题编号与目录树

**目的：** **不要**用 Python-Markdown 的 `toc` 扩展 —— 它的 slugify 默认 `unicode=False`，中文标题会被过滤成 `_1`/`_2` 这类不可读 id，且跨版本行为不一致。我们自己编号：`s1`、`s2`…，确定、可测、与语言无关。

**文件：** 修改 `tests/test_site_render.py`

**步骤 1：追加测试**

```python
class TestHeadingIdsAndToc(unittest.TestCase):
    MD = "# 标题不进目录\n\n## 你将学会\n\n正文\n\n### 子节\n\n正文\n\n## 出处\n"

    def test_ids_are_sequential_and_language_free(self):
        html, toc = R.add_heading_ids("<h1>标题</h1>\n<h2>你将学会</h2>\n<h3>子节</h3>\n<h2>出处</h2>")
        self.assertIn('<h2 id="s1">你将学会</h2>', html)
        self.assertIn('<h3 id="s2">子节</h3>', html)
        self.assertIn('<h2 id="s3">出处</h2>', html)
        self.assertEqual([t["level"] for t in toc], [2, 3, 2])

    def test_toc_items_carry_text(self):
        _, toc = R.add_heading_ids("<h2>你将学会</h2>")
        self.assertEqual(toc, [{"id": "s1", "level": 2, "text": "你将学会"}])

    def test_toc_html_nests_by_level(self):
        toc = [{"id": "s1", "level": 2, "text": "A"}, {"id": "s2", "level": 3, "text": "A1"}]
        html = R.build_toc_html(toc)
        self.assertIn('<a href="#s1">A</a>', html)
        self.assertIn('<a href="#s2">A1</a>', html)
        self.assertLess(html.index("A</a>"), html.index("A1</a>"))

    def test_empty_toc_renders_empty_string(self):
        self.assertEqual(R.build_toc_html([]), "")
```

**步骤 2：跑测试，确认失败**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`AttributeError: module 'site_render' has no attribute 'add_heading_ids'`。

---

### 任务 T11 — 实现标题编号与目录 + `render_markdown`

**文件：** 修改 `scripts/site_render.py`（追加）

**步骤 1：追加实现**

```python
def add_heading_ids(fragment: str, prefix: str = "s") -> tuple[str, list[dict]]:
    """给 h2/h3 编上稳定 id，并返回扁平目录列表。

    目录只用 h2/h3：h1 是课程标题本身（页面顶部已经有了），再列一次是噪音。
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
    """把扁平目录列表变成嵌套 <ol>（h3 落到 h2 的下级）。"""
    if not toc:
        return ""
    out: list[str] = ['<nav class="page-toc" aria-label="本页目录"><p class="toc-title">本页目录</p><ol class="toc-l2">']
    open_sub = False
    for item in toc:
        if item["level"] == 3:
            if not open_sub:
                out.append('<ol class="toc-l3">')
                open_sub = True
        elif open_sub:
            out.append("</ol></li>")
            open_sub = False
        link = f'<a href="#{escape(item["id"])}">{escape(item["text"])}</a>'
        out.append(link if open_sub and item["level"] == 3 else f"<li>{link}")
        if item["level"] == 2:
            out.append("</li>" if not open_sub else "")
    if open_sub:
        out.append("</ol></li>")
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
```

**注意 `build_toc_html` 的嵌套实现容易写错**。用下面这条命令肉眼核对一次输出（这是本任务的一部分，不是可选）：

```bash
python -c "
import sys; sys.path.insert(0,'scripts')
import site_render as R
print(R.build_toc_html([{'id':'s1','level':2,'text':'A'},{'id':'s2','level':3,'text':'A1'},{'id':'s3','level':2,'text':'B'}]))
"
```

期望（缩进可以不同，但必须能看到 `A` 里嵌着 `A1`，`B` 与 `A` 平级）：

```
<nav class="page-toc" aria-label="本页目录"><p class="toc-title">本页目录</p><ol class="toc-l2"><li><a href="#s1">A</a><ol class="toc-l3"><a href="#s2">A1</a></ol></li><li><a href="#s3">B</a></li></ol></nav>
```

如果输出里 `B` 被套进了 `toc-l3`，说明闭合逻辑写错了：**修实现，不要改期望**。

**步骤 2：跑测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 26 tests ... OK`。

**步骤 3：提交**

```bash
git add scripts/site_render.py tests/test_site_render.py
git commit -m "feat: h2/h3 稳定编号 + 目录树 + render_markdown"
```

---

### 任务 T12 — 失败测试：出处徽标、交叉引用、模板填充

**文件：** 修改 `tests/test_site_render.py`

**步骤 1：追加测试**

```python
CITES = {
    "quickstart": {
        "title": "Quickstart",
        "url": "https://hermes-agent.nousresearch.com/docs/getting-started/quickstart",
        "hermes_version": "0.21.3",
        "sha256": "a" * 64,
    }
}


class TestMarkers(unittest.TestCase):
    def test_citation_becomes_link_with_provenance(self):
        out = R.linkify_citations("<p>跑一次 [[src:quickstart]] 就知道</p>", CITES, "L01")
        self.assertIn('class="cite"', out)
        self.assertIn('href="https://hermes-agent.nousresearch.com/docs/getting-started/quickstart"', out)
        self.assertIn("hermes v0.21.3", out)
        self.assertIn("aaaaaaaaaaaa", out)          # 哈希前缀，可核对
        self.assertNotIn("[[src:", out)

    def test_unknown_citation_raises_with_context(self):
        with self.assertRaises(R.SiteError) as ctx:
            R.linkify_citations("[[src:nope]]", CITES, "L01")
        self.assertIn("L01", str(ctx.exception))
        self.assertIn("nope", str(ctx.exception))

    def test_marker_inside_code_is_not_rewritten(self):
        html = '<pre><code>[[src:quickstart]]</code></pre><p>[[src:quickstart]]</p>'
        out = R.linkify_citations(html, CITES, "L01")
        self.assertIn("<code>[[src:quickstart]]</code>", out)
        self.assertIn('class="cite"', out)
        self.assertEqual(out.count('class="cite"'), 1)

    def test_xref_links_to_sibling_page(self):
        out = R.linkify_xrefs("<p>顺路看 [[L13]]</p>", {"L13": "L13-memory.html"}, "L15")
        self.assertIn('<a class="xref" href="L13-memory.html">L13</a>', out)

    def test_unknown_xref_raises(self):
        with self.assertRaises(R.SiteError):
            R.linkify_xrefs("[[L99]]", {"L13": "L13-memory.html"}, "L15")

    def test_render_template_fills_and_rejects_leftovers(self):
        out = R.render_template("<title>{{title}}</title><p>{{body}}</p>",
                                {"title": "T", "body": "B"}, "index.html")
        self.assertEqual(out, "<title>T</title><p>B</p>")
        with self.assertRaises(R.SiteError) as ctx:
            R.render_template("<p>{{whoops}}</p>", {}, "index.html")
        self.assertIn("whoops", str(ctx.exception))


class TestRepoDocSlug(unittest.TestCase):
    def test_slug_is_ascii_and_readable(self):
        self.assertEqual(R.repo_doc_slug(".hermes.md"), "hermes-md")
        self.assertEqual(R.repo_doc_slug("sources/README.md"), "sources-readme")
        self.assertEqual(R.repo_doc_slug("templates/lesson.md"), "templates-lesson")
```

**步骤 2：跑测试，确认失败**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`AttributeError ... has no attribute 'linkify_citations'`。

---

### 任务 T13 — 实现标记改写、模板填充、仓库文档 slug

**文件：** 修改 `scripts/site_render.py`（追加）

**步骤 1：追加实现**

```python
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
    """'.hermes.md' -> 'hermes-md'；'sources/README.md' -> 'sources-readme'。"""
    return re.sub(r"[^A-Za-z0-9]+", "-", rel).strip("-").lower()


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
```

**步骤 2：跑测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 33 tests ... OK`。

**步骤 3：追加「全仓库内容回归」测试**（防止以后新写的课把 HTML 标签裸放在正文里，导致整段在浏览器里消失）

```python
class TestLessonContentIsRenderable(unittest.TestCase):
    """课程正文本该是纯 Markdown：除代码围栏与行内反引号外，不该有裸 HTML 标签。"""

    RAW_HTML_RE = re.compile(r"<[a-zA-Z][a-zA-Z0-9_:-]*")

    def test_no_raw_html_outside_code(self):
        offenders = []
        for lesson in core.load_lessons(REPO):
            in_fence = False
            for lineno, line in enumerate(lesson["body"].split("\n"), 1):
                if line.lstrip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                stripped = re.sub(r"`[^`]*`", "", line)
                stripped = re.sub(r"<!--.*?-->", "", stripped)
                if self.RAW_HTML_RE.search(stripped):
                    offenders.append(f"{lesson['rel']}:{lineno}: {stripped.strip()[:80]}")
        self.assertEqual(offenders, [], "把尖括号内容放进反引号里，否则浏览器里会消失")

    def test_every_lesson_renders_sections(self):
        for lesson in core.load_lessons(REPO):
            html, toc = R.render_markdown(lesson["body"])
            self.assertGreaterEqual(len(toc), 8, f"{lesson['id']} 的目录少于 8 节")
            self.assertIn("<h1", html)
```

**步骤 4：跑测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 35 tests ... OK`。
若 `test_no_raw_html_outside_code` 失败：**修课程内容**（把那几处尖括号放进反引号），然后 `python scripts/verify.py` 确认门禁仍绿。

**步骤 5：提交**

```bash
git add scripts/site_render.py tests/test_site_render.py
git commit -m "feat: 出处徽标/交叉引用/模板填充 + 课程内容可渲染性回归测试"
```

---

### 任务 T14 — 失败测试：构建器产出与链接自检

**文件：** 新建 `tests/test_build_site.py`

**步骤 1：写测试**

```python
#!/usr/bin/env python3
"""tests/test_build_site.py —— 构建器集成测试：真的构建到临时目录，然后验收产物。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_site  # noqa: E402
import tutorial_core as core  # noqa: E402


class TestBuildOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.stats = build_site.build(cls.out, build_site.load_config())

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_stats_match_repo(self):
        self.assertEqual(self.stats["lessons"], 32)
        self.assertEqual(self.stats["pages"], 32 + 1 + len(core.load_lessons(REPO)[:0]) + 6)  # 课程 + 首页 + 6 个规范页

    def test_index_and_data_files_exist(self):
        for rel in ("index.html", "404.html", ".nojekyll",
                    "data/index.json", "data/citations.json", "data/search.json", "data/manifest.json",
                    "assets/app.css", "assets/app.js"):
            self.assertTrue((self.out / rel).is_file(), f"缺 {rel}")

    def test_every_lesson_has_a_page(self):
        for lesson in core.load_lessons(REPO):
            self.assertTrue((self.out / "lessons" / lesson["page"]).is_file(), lesson["id"])

    def test_index_json_shape(self):
        data = json.loads((self.out / "data" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["lessons"]), 32)
        first = data["lessons"][0]
        for key in ("id", "title", "stage", "minutes", "level", "prereq", "summary", "url"):
            self.assertIn(key, first)

    def test_search_json_shape(self):
        data = json.loads((self.out / "data" / "search.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["docs"]), 32)
        l23 = next(d for d in data["docs"] if d["id"] == "L23")
        self.assertIn("hermes cron", l23["text"])

    def test_lesson_page_contains_citation_link_and_toc(self):
        page = (self.out / "lessons" / "L01-first-conversation.html").read_text(encoding="utf-8")
        self.assertIn('class="cite"', page)
        self.assertIn('class="page-toc"', page)
        self.assertIn("hermes-agent.nousresearch.com", page)

    def test_repo_doc_pages_rendered(self):
        self.assertTrue((self.out / "repo" / "hermes-md.html").is_file())
        self.assertTrue((self.out / "repo" / "sources-readme.html").is_file())

    def test_manifest_records_source_hashes(self):
        manifest = json.loads((self.out / "data" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["lessons"]), 32)
        self.assertEqual(len(manifest["lessons"][0]["sha256"]), 64)
        self.assertTrue(manifest["baseline"]["version"])

    def test_no_broken_links(self):
        self.assertEqual(build_site.check_links(self.out), [])

    def test_no_unfilled_placeholders_in_pages(self):
        for page in self.out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("{{", text, page.as_posix())


if __name__ == "__main__":
    unittest.main()
```

**步骤 2：跑测试，确认失败**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`ModuleNotFoundError: No module named 'build_site'`。

---

### 任务 T15 — 实现 `build_site.py`（第一部分：配置、数据、页面片段）

**文件：** 新建 `scripts/build_site.py`

**步骤 1：写 `site.json`（先建配置文件，构建器要读它）**

```json
{
  "title": "Hermes Agent 初学者教程",
  "tagline": "从「装好了但不知道干什么」到「知道自己在指挥什么」——可考证、可自维护、可回滚。",
  "repo_url": "",
  "repo_docs": [
    ".hermes.md",
    "CONTRIBUTING.md",
    "ROADMAP.md",
    "sources/README.md",
    "templates/lesson.md",
    "progress/checklist.md"
  ]
}
```

`repo_url` 留空是刻意的：本机还没有 git remote（`git remote -v` 为空）。为空时页脚的「查看仓库」按钮隐藏，不影响构建。

**步骤 2：写 `scripts/build_site.py`**

```python
#!/usr/bin/env python3
"""scripts/build_site.py —— 把 lessons/ + web/ 编译成可部署的静态站点 site/。

设计取舍（读之前先看这三条）
----------------------------
1. **构建期渲染，不在浏览器里渲染 Markdown。** 产物是一堆真 HTML：JS 关掉也能读，
   搜索引擎能收录，而且 verify 那一套「用脚本检查产物」才有对象可查。
2. **不用打包器、不装 npm 依赖。** 前端是原生 ES 模块，浏览器直接吃；
   Node 只用来跑单元测试（node --test），所以部署机器上不需要 node_modules。
3. **构建失败要给得出人话。** 未登记的出处、指向不存在课程的交叉引用、
   模板占位符没填、链接指向不存在的文件 —— 全部 exit 1 并指出是哪一课哪一行。

用法
----
  python scripts/build_site.py              # 构建到 site/
  python scripts/build_site.py --check      # 构建到临时目录并做链接/数量自检（不碰 site/）
  python scripts/build_site.py --out D:/x   # 指定输出目录
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import site_render as R  # noqa: E402
import tutorial_core as core  # noqa: E402

WEB = REPO / "web"
SITE = REPO / "site"
CONFIG = REPO / "site.json"

DEFAULT_CONFIG: dict = {
    "title": "Hermes Agent 初学者教程",
    "tagline": "",
    "repo_url": "",
    "repo_docs": [],
}


# --------------------------------------------------------------------------- 配置与数据

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    return cfg


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def index_data(lessons: list[dict]) -> dict:
    return {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "lessons": [
            {
                "id": l["id"],
                "title": l["title"],
                "stage": l["stage"],
                "stage_name": core.stage_name(l["stage"]),
                "level": l["level"],
                "minutes": l["minutes"],
                "prereq": l["prereq"],
                "tags": l["tags"],
                "sources": l["sources"],
                "summary": l["summary"],
                "updated": l["updated"],
                "url": l["url"],
            }
            for l in lessons
        ],
        "stages": [
            {"stage": s, "name": v["name"], "why": v["why"]} for s, v in sorted(core.STAGES.items())
        ],
    }


def citations_data(citations: dict) -> dict:
    return {
        "count": len(citations),
        "items": {
            sid: {
                "title": e.get("title", ""),
                "url": e.get("url", ""),
                "hermes_version": str(e.get("hermes_version", "")),
                "sha256": str(e.get("sha256", "")),
                "local": e.get("local", ""),
                "retrieved_at": str(e.get("retrieved_at", "")),
            }
            for sid, e in sorted(citations.items())
        },
    }


def search_data(lessons: list[dict]) -> dict:
    return {
        "docs": [
            {
                "id": l["id"],
                "title": l["title"],
                "stage": l["stage"],
                "minutes": l["minutes"],
                "tags": l["tags"],
                "summary": l["summary"],
                "url": l["url"],
                "text": R.search_text(l["body"]),
            }
            for l in lessons
        ]
    }


def manifest_data(lessons: list[dict], baseline: dict) -> dict:
    """构建清单：让「这个站点是哪次内容构建出来的」这件事可核对。"""
    return {
        "built_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "baseline": baseline,
        "lessons": [
            {"id": l["id"], "rel": l["rel"], "url": l["url"], "sha256": sha256_file(l["path"])}
            for l in lessons
        ],
    }
```

**步骤 3（同一任务，第二部分）：在 `scripts/site_render.py` 追加 `search_text`**

```python
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
```

**步骤 4：语法检查（此时还没有 `build()`，import 只验证语法）**

```bash
python -c "import sys; sys.path.insert(0,'scripts'); import build_site, site_render; print('语法 OK')"
```

期望：`语法 OK`。

**步骤 5：提交**

```bash
git add site.json scripts/build_site.py scripts/site_render.py
git commit -m "feat: build_site 配置与数据层（index/citations/search/manifest）"
```

---

### 任务 T16 — 实现 `build_site.py`（第二部分：页面片段与主流程）

**文件：** 修改 `scripts/build_site.py`（追加）

**步骤 1：追加侧栏、首页、课程页、规范页的渲染**

```python
# --------------------------------------------------------------------------- 页面片段

def link_sibling(lesson: dict) -> str:
    """课程页 → 另一课（同级目录）。"""
    return lesson["page"]


def link_from_root(lesson: dict) -> str:
    """首页 → 课程。"""
    return lesson["url"]


def render_sidebar(groups: list[dict], current_id: str, link_for, cfg: dict) -> str:
    out = ['<nav class="nav-lessons" aria-label="课程导航">']
    for g in groups:
        out.append('<section class="nav-stage">')
        out.append(
            f'<h2 class="nav-stage-title"><span class="nav-stage-no">阶段 {g["stage"]}</span>'
            f'<span>{R.escape(g["name"])}</span></h2>'
            f'<p class="nav-stage-why">{R.escape(g["why"])}</p><ul>'
        )
        for ls in g["lessons"]:
            current = ' class="is-current"' if ls["id"] == current_id else ""
            out.append(
                f'<li data-lesson="{ls["id"]}"{current}>'
                f'<a href="{link_for(ls)}">'
                f'<span class="nav-check" aria-hidden="true">○</span>'
                f'<span class="nav-id">{ls["id"]}</span>'
                f'<span class="nav-title">{R.escape(ls["title"])}</span>'
                f'<span class="nav-min">{ls["minutes"]}′</span></a></li>'
            )
        out.append("</ul></section>")
    if cfg.get("repo_docs"):
        out.append('<section class="nav-stage nav-repo"><h2 class="nav-stage-title">'
                   '<span>规范与出处</span></h2><ul>')
        for rel in cfg["repo_docs"]:
            slug = R.repo_doc_slug(rel)
            href = ("../repo/" if current_id else "repo/") + f"{slug}.html"
            out.append(f'<li><a href="{href}"><span class="nav-title">{R.escape(rel)}</span></a></li>')
        out.append("</ul></section>")
    out.append("</nav>")
    return "".join(out)


def render_home(groups: list[dict], lessons: list[dict], cfg: dict, link_for, baseline: dict) -> str:
    total_min = sum(l["minutes"] for l in lessons)
    hours = total_min // 60
    out = [
        f'<h1>{R.escape(cfg["title"])}</h1>',
        f'<p class="lead">{R.escape(cfg.get("tagline", ""))}</p>',
        '<section class="card progress-card" id="progress-card">',
        f'<p class="pc-line"><b id="done-count">0</b> / {len(lessons)} 课完成'
        f'<span class="muted"> · 全量约 {hours} 小时 · <span id="min-left">{total_min} 分钟</span> 待学</span></p>',
        '<div class="bar"><i id="bar-fill" style="width:0%"></i></div>',
        '<p class="muted pc-note">进度只存在你这台机器的浏览器里（localStorage），不上传任何数据；'
        '也可以导出 JSON 与 <code>python scripts/progress.py</code> 的本地状态对照。</p>',
        '<p class="pc-actions">'
        '<button class="btn primary" id="next-lesson">我该学哪一课？</button>'
        '<button class="btn" id="export-progress">导出进度 JSON</button>'
        '<button class="btn" id="import-progress">导入进度 JSON</button>'
        '<input type="file" id="import-file" accept="application/json,.json" hidden>'
        '</p>',
        '<p class="muted pc-out" id="pc-out" hidden></p>',
        "</section>",
    ]
    for g in groups:
        out.append('<section class="card">')
        out.append(
            f'<h2 class="stage-h">阶段 {g["stage"]} · {R.escape(g["name"])}'
            f'<span class="muted"> {len(g["lessons"])} 课 · {sum(l["minutes"] for l in g["lessons"])} 分钟</span></h2>'
            f'<p class="stage-why">{R.escape(g["why"])}</p><ul class="lesson-grid">'
        )
        for ls in g["lessons"]:
            out.append(
                f'<li data-lesson="{ls["id"]}"><a href="{link_for(ls)}">'
                f'<span class="nav-check" aria-hidden="true">○</span>'
                f'<span class="lc-head"><b>{ls["id"]} {R.escape(ls["title"])}</b>'
                f'<span class="muted">{ls["minutes"]} 分钟 · {R.escape(ls["level"])}</span></span>'
                f'<span class="lc-summary">{R.escape(ls["summary"])}</span></a></li>'
            )
        out.append("</ul></section>")
    out.append(
        f'<p class="muted site-note">出处基线：hermes v{baseline["version"]} · 文档提交 {baseline["commit"]}'
        f' · {baseline["count"]} 条官方来源。站点的每一课都能在 '
        f'<code>sources/cache/&lt;src-id&gt;.md</code> 里找到原文快照。</p>'
    )
    return "".join(out)


def render_lesson_article(ls: dict, html: str, toc_html: str, prev, nxt, link_for) -> str:
    prereq = "、".join(ls["prereq"]) if ls["prereq"] else "无"
    nav = ['<nav class="prevnext">']
    nav.append(
        f'<a class="btn" href="{link_for(prev)}">← {prev["id"]} {R.escape(prev["title"])}</a>'
        if prev else "<span></span>"
    )
    nav.append(
        f'<a class="btn" href="{link_for(nxt)}">{nxt["id"]} {R.escape(nxt["title"])} →</a>'
        if nxt else "<span></span>"
    )
    nav.append("</nav>")
    return "".join([
        f'<article class="lesson" data-lesson="{ls["id"]}">',
        html,
        '<p class="lesson-meta">'
        f'前置：{R.escape(prereq)} · {ls["minutes"]} 分钟 · {R.escape(ls["level"])} · '
        f'更新于 {R.escape(ls["updated"])} · 源码 <code>{R.escape(ls["rel"])}</code></p>',
        '<p class="lesson-actions">'
        f'<button class="btn primary" id="mark-done" data-lesson="{ls["id"]}">标记本课完成</button>'
        '<a class="btn" href="../index.html">回首页</a></p>',
        "</article>",
        "".join(nav),
    ])


def rewrite_repo_links(html: str, lesson: dict, cfg: dict) -> str:
    """把课程里指向仓库文件的相对链接改写到站点内的规范页。

    现在仓库里只有一处这样的链接（`../../.hermes.md`），但规则要立住：
    指向未收录文件的链接直接报错，否则读者会点到一个 404 却没人发现。
    """
    whitelist = {R.repo_doc_slug(rel): rel for rel in cfg.get("repo_docs", [])}

    def repl(m: re.Match[str]) -> str:
        href = m.group(1)
        if href.startswith(("http://", "https://", "mailto:", "#", "/")):
            return m.group(0)
        target = href.split("#", 1)[0]
        if not target.endswith((".md", ".txt")):
            return m.group(0)
        resolved = (lesson["path"].parent / target).resolve()
        try:
            rel = resolved.relative_to(REPO).as_posix()
        except ValueError:
            raise R.SiteError(f"{lesson['rel']}: 相对链接指到仓库之外：{href}")
        slug = R.repo_doc_slug(rel)
        if slug not in whitelist:
            raise R.SiteError(
                f"{lesson['rel']}: 相对链接指向未收录的仓库文件 {rel}"
                f"（要么把它加进 site.json 的 repo_docs，要么改掉这个链接）"
            )
        return f'href="../repo/{slug}.html"'

    return re.sub(r'href="([^"]+)"', repl, html)
```

**步骤 2：追加主构建流程与 CLI**

```python
# --------------------------------------------------------------------------- 主流程

def render_repo_doc(rel: str, cfg: dict, layout: str, groups: list[dict]) -> tuple[str, str]:
    """仓库规范页：.hermes.md / CONTRIBUTING.md 等，用同一套渲染管线。

    返回 (slug, 页面 HTML)。这些文件没有 frontmatter，标题取第一个 H1。
    """
    path = REPO / rel
    if not path.is_file():
        raise R.SiteError(f"site.json 里登记的仓库文档不存在：{rel}")
    slug = R.repo_doc_slug(rel)
    html, toc = R.render_markdown(path.read_text(encoding="utf-8"))
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else rel
    page = R.render_template(
        layout,
        {
            "title": f"{title} · {cfg['title']}",
            "desc": f"仓库文件 {rel}",
            "prefix": "../",
            "site_title": R.escape(cfg["title"]),
            "lesson_id": "",
            "sidebar": render_sidebar(groups, "__repo__", link_sibling, cfg),
            "content": f'<article class="lesson repo-doc">{html}</article>',
            "toc": R.build_toc_html(toc),
            "footer": render_footer(cfg),
        },
        rel,
    )
    return slug, page


def render_footer(cfg: dict) -> str:
    parts = [f'<span>{R.escape(cfg["title"])}</span>',
             '<span class="muted">内容 CC BY 4.0 · 代码 MIT</span>']
    if cfg.get("repo_url"):
        parts.append(f'<a href="{R.escape(cfg["repo_url"])}" target="_blank" rel="noopener">在 GitHub 上查看仓库</a>')
    return '<div class="footer-inner">' + "".join(parts) + "</div>"


def build(out: Path, cfg: dict) -> dict:
    lessons = core.load_lessons(REPO)
    if not lessons:
        raise R.SiteError("lessons/ 下没有课程，先写课再建站")
    citations = core.load_citations(REPO)
    baseline = core.source_baseline(REPO)
    groups = core.group_by_stage(lessons)
    id_to_page = {l["id"]: l["page"] for l in lessons}

    layout = (WEB / "partials" / "layout.html").read_text(encoding="utf-8")

    site = Path(out)
    if site.exists():
        shutil.rmtree(site)
    (site / "lessons").mkdir(parents=True)
    (site / "repo").mkdir()
    (site / "data").mkdir()
    shutil.copytree(WEB / "assets", site / "assets")
    (site / ".nojekyll").write_text("", encoding="utf-8", newline="\n")

    # 课程页
    for i, ls in enumerate(lessons):
        where = ls["rel"]
        html, toc = R.render_markdown(ls["body"])
        html = rewrite_repo_links(html, ls, cfg)
        html = R.linkify_citations(html, citations, where)
        html = R.linkify_xrefs(html, id_to_page, where)
        page = R.render_template(
            layout,
            {
                "title": f'{ls["id"]} · {ls["title"]} · {cfg["title"]}',
                "desc": ls["summary"] or ls["title"],
                "prefix": "../",
                "site_title": R.escape(cfg["title"]),
                "lesson_id": ls["id"],
                "sidebar": render_sidebar(groups, ls["id"], link_sibling, cfg),
                "content": render_lesson_article(
                    ls, html, "", lessons[i - 1] if i else None,
                    lessons[i + 1] if i + 1 < len(lessons) else None, link_sibling,
                ),
                "toc": R.build_toc_html(toc),
                "footer": render_footer(cfg),
            },
            where,
        )
        (site / "lessons" / ls["page"]).write_text(page, encoding="utf-8", newline="\n")

    # 首页
    home = R.render_template(
        layout,
        {
            "title": cfg["title"],
            "desc": cfg.get("tagline", ""),
            "prefix": "",
            "site_title": R.escape(cfg["title"]),
            "lesson_id": "",
            "sidebar": render_sidebar(groups, "", link_from_root, cfg),
            "content": render_home(groups, lessons, cfg, link_from_root, baseline),
            "toc": "",
            "footer": render_footer(cfg),
        },
        "index.html",
    )
    (site / "index.html").write_text(home, encoding="utf-8", newline="\n")

    # 仓库规范页
    repo_pages = [render_repo_doc(rel, cfg, layout, groups) for rel in cfg.get("repo_docs", [])]
    for slug, page in repo_pages:
        (site / "repo" / f"{slug}.html").write_text(page, encoding="utf-8", newline="\n")

    # 数据
    write_json(site / "data" / "index.json", index_data(lessons))
    write_json(site / "data" / "citations.json", citations_data(citations))
    write_json(site / "data" / "search.json", search_data(lessons))
    write_json(site / "data" / "manifest.json", manifest_data(lessons, baseline))

    # 404
    (site / "404.html").write_text(
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<title>页面不存在 · {R.escape(cfg["title"])}</title>'
        '<style>body{font:16px/1.6 system-ui,sans-serif;margin:4rem auto;max-width:36rem;padding:0 1rem}'
        'a{color:#3b5bdb}</style></head><body><h1>页面不存在</h1>'
        '<p>你要找的课程可能改了名字。</p><p><a href="/index.html">回课程首页</a></p></body></html>\n',
        encoding="utf-8",
        newline="\n",
    )

    files = [p for p in site.rglob("*") if p.is_file()]
    return {
        "lessons": len(lessons),
        "pages": len(list(site.rglob("*.html"))),
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "baseline": baseline,
    }


LINK_ATTR_RE = re.compile(r'(?:href|src)="([^"]+)"')


def check_links(out: Path) -> list[str]:
    """站内自检：每个 href/src 都要能在产物里找到对应文件。

    站内链接断一条，读者的体验就是「点了个 404」，而作者在自己的浏览器里
    往往正好点不到那一条。所以交给脚本，在 CI 里跑。
    """
    problems: list[str] = []
    for page in sorted(out.rglob("*.html")):
        for raw in LINK_ATTR_RE.findall(page.read_text(encoding="utf-8")):
            if raw.startswith(("http://", "https://", "mailto:", "data:", "//", "#", "/")):
                continue
            target = raw.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            if not (page.parent / target).resolve().exists():
                problems.append(f"{page.relative_to(out).as_posix()} → {raw}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="构建教程静态站点")
    ap.add_argument("--out", default=str(SITE), help="输出目录（默认 site/）")
    ap.add_argument("--check", action="store_true", help="构建到临时目录并自检，不写 site/")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    cfg = load_config()

    try:
        if args.check:
            with tempfile.TemporaryDirectory() as tmp:
                stats = build(Path(tmp) / "site", cfg)
                problems = check_links(Path(tmp) / "site")
        else:
            stats = build(Path(args.out), cfg)
            problems = check_links(Path(args.out))
    except R.SiteError as e:
        print(f"构建失败：{e}", file=sys.stderr)
        return 1

    if problems:
        print(f"站内链接自检失败：{len(problems)} 条")
        for p in problems[:30]:
            print(f"  - {p}")
        return 1

    if not args.quiet:
        print(
            f"站点自检通过：{stats['lessons']} 课 / {stats['pages']} 页 / "
            f"{stats['files']} 文件 / {stats['bytes'] / 1024:.0f} KB"
            f"（出处基线 hermes v{stats['baseline']['version']}）"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**步骤 3：跑集成测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

此时会因为 `web/partials/layout.html` 与 `web/assets/*` 还不存在而失败（`FileNotFoundError`）。**这是预期顺序**：模板与样式是 T17/T18。为了让本任务结束时测试能绿，先创建最小可用的模板与资源占位：

**步骤 4：创建 `web/partials/layout.html`（先最小版，T17 再补全交互元素）**

```html
<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<meta name="description" content="{{desc}}">
<link rel="stylesheet" href="{{prefix}}assets/app.css">
<script type="module" src="{{prefix}}assets/app.js"></script>
</head>
<body data-prefix="{{prefix}}" data-lesson="{{lesson_id}}">
<header class="topbar">
  <button class="icon-btn" id="nav-toggle" aria-label="打开课程导航" aria-expanded="false">☰</button>
  <a class="brand" href="{{prefix}}index.html">{{site_title}}</a>
  <button class="search-btn" id="search-open"><span>搜索课程</span><kbd>Ctrl K</kbd></button>
  <div class="topbar-right">
    <span class="progress-pill" id="progress-pill">0/32</span>
    <button class="icon-btn" id="theme-toggle" aria-label="切换主题">◐</button>
  </div>
</header>
<div class="layout">
  <aside class="sidebar" id="sidebar">{{sidebar}}</aside>
  <main class="content" id="main">{{content}}</main>
  <aside class="toc-side" id="toc-side">{{toc}}</aside>
</div>
<footer class="footer">{{footer}}</footer>
<div class="palette" id="palette" hidden>
  <div class="palette-box" role="dialog" aria-modal="true" aria-label="搜索课程">
    <input id="palette-input" type="search" placeholder="输入关键词（中文或英文均可）…" autocomplete="off">
    <ol id="palette-results"></ol>
    <p class="palette-hint">↑↓ 选择 · Enter 打开 · Esc 关闭</p>
  </div>
</div>
</body>
</html>
```

**步骤 5：创建最小的 `web/assets/app.css` 与 `web/assets/app.js`（T18/T24 会替换成完整版，这里只为了让构建能跑）**

`web/assets/app.css`：

```css
/* 占位：完整样式见任务 T18 */
body { font: 16px/1.6 system-ui, sans-serif; }
```

`web/assets/app.js`：

```js
// 占位：完整逻辑见任务 T24
console.debug("hermes-usage site");
```

**步骤 6：跑集成测试**

```bash
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

期望：`Ran 45 tests ... OK`（35 个 + 10 个集成测试）。如果 `test_stats_match_repo` 的 `pages` 断言对不上，用实际值修测试里的期望数字（课程数会增长）。

**步骤 7：提交**

```bash
git add scripts/build_site.py scripts/site_render.py web/partials/layout.html web/assets/app.css web/assets/app.js tests/test_build_site.py
git commit -m "feat: build_site 页面渲染主流程 + 集成测试"
```

---

### 任务 T17 — 真机构建一次，肉眼验收

**目的：** 让「构建器能产出站点」这件事在有浏览器的机器上被真的看过一次。

**步骤 1：构建**

```bash
python scripts/build_site.py
```

期望输出：

```
站点自检通过：32 课 / 39 页 / 51 文件 / 1200 KB（出处基线 hermes v0.21.3）
```

（页数 = 32 课程页 + 1 首页 + 6 规范页；文件数/体积随实现略有浮动，只要是同一量级即可。）

**步骤 2：抽查产物**

```bash
ls site site/lessons | head -20
head -c 400 site/lessons/L01-first-conversation.html
python -c "import json;d=json.load(open('site/data/index.json',encoding='utf-8'));print(len(d['lessons']), d['lessons'][0]['id'], d['lessons'][-1]['id'])"
```

期望：
- `site/lessons/` 下有 32 个 `.html`
- 课程页开头是 `<!doctype html>`
- 最后一行输出 `32 L00 L90`

**步骤 3：肉眼确认三件事（用浏览器打开，或者用 grep 断言）**

```bash
# ① 出处徽标带官方 URL
grep -o 'class="cite" href="[^"]*"' site/lessons/L01-first-conversation.html | head -3
# ② 交叉引用变成了链接
grep -o 'class="xref" href="[^"]*"' site/lessons/L15-skills.html | head -3
# ③ 目录为空（首页没有 h2/h3 目录）但课程页有
grep -c 'page-toc' site/index.html || true
grep -c 'page-toc' site/lessons/L23-cron-loops-goals.html
```

期望：①② 能列出若干条；③ 第一行 `0`，第二行 `1`。

**步骤 4：在浏览器里打开 `site/index.html`** —— 此时样式还很丑（T18 会补），但要确认**没有控制台报错**（现在 app.js 只是占位，不该报错）。

**步骤 5：不提交**（构建产物被 .gitignore 忽略）

---

### 任务 T18 — 完整样式表 `web/assets/app.css`

**文件：** 重写 `web/assets/app.css`

**要求：** 把下面的文件**完整**写入（不是片段）。它定义了整套视觉：亮/暗两套配色、三栏布局（侧栏 288px + 正文 + 目录 220px）、移动端抽屉、代码块与复制按钮、出处徽标、搜索面板。深色由 JS 解析成具体主题后设到 `<html data-theme>`，所以 CSS 里只需要 light/dark 两块，不需要 `prefers-color-scheme` 的第三份拷贝。

```css
/* HermesUsage 教程站样式
   设计约束：正文可读性优先（中文 16px/1.85、行宽 74ch）；不依赖任何外部字体或 CDN。 */

:root {
  --bg: #ffffff;
  --fg: #1b1f24;
  --muted: #6b7280;
  --line: #e5e7eb;
  --card: #f8fafc;
  --accent: #3b5bdb;
  --accent-soft: #eef2ff;
  --code-bg: #f4f6f8;
  --radius: 10px;
  --sidebar-w: 292px;
  --toc-w: 220px;
  --measure: 74ch;
}
:root[data-theme="dark"] {
  --bg: #0f1115;
  --fg: #e6e8eb;
  --muted: #9aa4b2;
  --line: #242a33;
  --card: #161a21;
  --accent: #7aa2ff;
  --accent-soft: #1b2233;
  --code-bg: #151a21;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 84px; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.85 system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre, kbd { font-family: ui-monospace, SFMono-Regular, Consolas, "Cascadia Mono", monospace; }
.muted { color: var(--muted); }

/* 顶栏 */
.topbar {
  position: sticky; top: 0; z-index: 40;
  display: flex; align-items: center; gap: 12px;
  padding: 10px 18px;
  background: color-mix(in srgb, var(--bg) 92%, transparent);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(6px);
}
.brand { font-weight: 600; color: var(--fg); }
.topbar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.icon-btn, .btn, .search-btn {
  font: inherit; cursor: pointer; color: var(--fg);
  background: transparent; border: 1px solid var(--line); border-radius: 8px;
  padding: 4px 10px;
}
.icon-btn:hover, .btn:hover, .search-btn:hover { border-color: var(--accent); color: var(--accent); }
.btn.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn.primary:hover { color: #fff; opacity: .9; }
.search-btn { display: flex; align-items: center; gap: 8px; color: var(--muted); min-width: 220px; }
.search-btn kbd { font-size: 11px; border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
.progress-pill {
  font-size: 12px; color: var(--muted);
  border: 1px solid var(--line); border-radius: 999px; padding: 2px 10px;
}
#nav-toggle { display: none; }

/* 三栏布局 */
.layout {
  display: grid;
  grid-template-columns: var(--sidebar-w) minmax(0, 1fr) var(--toc-w);
  gap: 28px;
  max-width: 1440px;
  margin: 0 auto;
  padding: 20px 20px 40px;
  align-items: start;
}
.sidebar { position: sticky; top: 68px; max-height: calc(100vh - 88px); overflow: auto; font-size: 13.5px; }
.content { min-width: 0; max-width: var(--measure); }
.toc-side { position: sticky; top: 68px; max-height: calc(100vh - 88px); overflow: auto; font-size: 13px; }

/* 侧栏 */
.nav-stage { margin-bottom: 16px; }
.nav-stage-title { display: flex; gap: 6px; font-size: 12.5px; margin: 0 0 2px; color: var(--muted); font-weight: 600; }
.nav-stage-no { color: var(--accent); }
.nav-stage-why { margin: 0 0 6px; color: var(--muted); font-size: 12px; }
.nav-stage ul { list-style: none; margin: 0; padding: 0; }
.nav-stage li a {
  display: grid; grid-template-columns: 14px 34px 1fr auto; gap: 6px; align-items: baseline;
  padding: 4px 6px; border-radius: 6px; color: var(--fg);
}
.nav-stage li a:hover { background: var(--card); text-decoration: none; }
.nav-stage li.is-current a { background: var(--accent-soft); color: var(--accent); }
.nav-id { color: var(--muted); font-variant-numeric: tabular-nums; }
.nav-min { color: var(--muted); font-size: 11.5px; }
.nav-check { color: var(--muted); }
.nav-stage.is-done .nav-check, li.is-done .nav-check { color: var(--accent); }
li.is-done .nav-title { color: var(--muted); text-decoration: line-through; }

/* 首页 */
h1 { font-size: 26px; line-height: 1.35; margin: 8px 0 12px; }
.lead { color: var(--muted); margin-top: 0; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 16px 18px; margin-bottom: 18px; }
.stage-h { font-size: 17px; margin: 0 0 4px; }
.stage-why { color: var(--muted); margin: 0 0 12px; font-size: 13.5px; }
.lesson-grid { list-style: none; margin: 0; padding: 0; }
.lesson-grid li + li { border-top: 1px solid var(--line); }
.lesson-grid li a { display: grid; grid-template-columns: 16px 1fr; gap: 10px; padding: 9px 4px; color: var(--fg); }
.lesson-grid li a:hover { background: var(--bg); text-decoration: none; }
.lc-head { display: flex; justify-content: space-between; gap: 12px; }
.lc-summary { grid-column: 2; color: var(--muted); font-size: 13px; }
.lesson-grid li.is-done .lc-head b { color: var(--muted); text-decoration: line-through; }
.progress-card .bar { height: 8px; border-radius: 4px; background: var(--line); overflow: hidden; margin: 10px 0; }
.progress-card .bar > i { display: block; height: 100%; background: var(--accent); transition: width .25s; }
.pc-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 0; }
.pc-out { margin: 10px 0 0; font-size: 13px; }

/* 课程页 */
.lesson h1 { font-size: 24px; }
.lesson h2 { font-size: 19px; margin-top: 34px; padding-top: 12px; border-top: 1px solid var(--line); }
.lesson h3 { font-size: 16.5px; margin-top: 24px; }
.lesson blockquote { margin: 14px 0; padding: 10px 14px; border-left: 3px solid var(--accent); background: var(--card); border-radius: 0 8px 8px 0; }
.lesson blockquote p { margin: 0; }
.lesson table { width: 100%; border-collapse: collapse; display: block; overflow-x: auto; margin: 14px 0; font-size: 14px; }
.lesson th, .lesson td { border: 1px solid var(--line); padding: 7px 10px; text-align: left; vertical-align: top; }
.lesson th { background: var(--card); }
.lesson pre {
  position: relative; background: var(--code-bg); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 14px 16px; overflow-x: auto; font-size: 13.5px; line-height: 1.7;
}
.lesson :not(pre) > code { background: var(--code-bg); border: 1px solid var(--line); border-radius: 5px; padding: 1px 5px; font-size: 13.5px; }
.lesson ul, .lesson ol { padding-left: 22px; }
.lesson li { margin: 4px 0; }
.task-box {
  display: inline-block; width: 13px; height: 13px; margin-right: 4px;
  border: 1.5px solid var(--muted); border-radius: 3px; vertical-align: -1px;
}
.task-box[data-checked="1"] { background: var(--accent); border-color: var(--accent); }
.copy-btn {
  position: absolute; top: 6px; right: 6px; font-size: 11.5px; padding: 2px 8px;
  color: var(--muted); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; cursor: pointer;
}
.copy-btn:hover { color: var(--accent); border-color: var(--accent); }
.cite {
  font-size: 11.5px; color: var(--accent); background: var(--accent-soft);
  border-radius: 5px; padding: 0 5px; margin: 0 2px; white-space: nowrap;
}
.xref { font-weight: 600; }
.lesson-meta { color: var(--muted); font-size: 13px; margin-top: 26px; }
.lesson-actions, .prevnext { display: flex; gap: 10px; justify-content: space-between; margin-top: 18px; }
.prevnext span:empty { display: none; }
.repo-doc h1 { font-size: 22px; }

/* 目录 */
.page-toc ol { list-style: none; margin: 0; padding-left: 10px; }
.page-toc a { color: var(--muted); display: block; padding: 3px 0; border-left: 2px solid transparent; padding-left: 8px; }
.page-toc a.active { color: var(--accent); border-left-color: var(--accent); }
.toc-title { font-weight: 600; font-size: 12.5px; margin: 0 0 6px; padding-left: 8px; }

/* 搜索面板 */
.palette { position: fixed; inset: 0; background: rgba(15, 17, 21, .45); z-index: 60; display: flex; justify-content: center; padding-top: 12vh; }
.palette-box { width: min(680px, 92vw); background: var(--bg); border: 1px solid var(--line); border-radius: 12px; padding: 12px; box-shadow: 0 20px 60px rgba(0,0,0,.25); height: fit-content; }
#palette-input { width: 100%; font: inherit; padding: 9px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--card); color: var(--fg); }
#palette-results { list-style: none; margin: 10px 0 0; padding: 0; max-height: 52vh; overflow: auto; }
#palette-results li { padding: 8px 10px; border-radius: 8px; cursor: pointer; }
#palette-results li[aria-selected="true"] { background: var(--accent-soft); }
#palette-results .pr-meta { color: var(--muted); font-size: 12.5px; }
#palette-results mark { background: transparent; color: var(--accent); font-weight: 600; }
.palette-hint { color: var(--muted); font-size: 12px; margin: 8px 2px 0; }

/* 页脚 */
.footer { border-top: 1px solid var(--line); margin-top: 40px; }
.footer-inner { max-width: 1440px; margin: 0 auto; padding: 18px 20px; display: flex; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--muted); }

/* 响应式：<=1180px 收掉右侧目录；<=900px 侧栏变抽屉 */
@media (max-width: 1180px) {
  .layout { grid-template-columns: var(--sidebar-w) minmax(0, 1fr); }
  .toc-side { display: none; }
}
@media (max-width: 900px) {
  .layout { grid-template-columns: minmax(0, 1fr); padding: 16px 14px 32px; }
  #nav-toggle { display: inline-block; }
  .search-btn { min-width: 0; }
  .search-btn span { display: none; }
  .sidebar {
    position: fixed; top: 0; bottom: 0; left: 0; width: 86vw; max-width: 340px;
    background: var(--bg); border-right: 1px solid var(--line);
    padding: 16px; z-index: 50; transform: translateX(-102%); transition: transform .2s;
    max-height: none;
  }
  .sidebar.is-open { transform: none; }
}
@media print {
  .topbar, .sidebar, .toc-side, .prevnext, .lesson-actions, .footer { display: none; }
  .layout { display: block; padding: 0; }
  .lesson pre { white-space: pre-wrap; }
}
```

**验证：**

```bash
python scripts/build_site.py && python scripts/serve.py --no-build --port 8137 &
sleep 2
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://127.0.0.1:8137/assets/app.css
```

期望：`200 text/css; charset=utf-8`。
然后浏览器打开 `http://127.0.0.1:8137/`：应看到三栏布局、课程卡片列表、右下没有内容溢出。**用 Ctrl+C 或 `kill %1` 停掉服务器。**

**提交：**

```bash
git add web/assets/app.css
git commit -m "feat: 教程站样式表（三栏布局/亮暗主题/响应式抽屉）"
```

---

### 任务 T19 — 前端单元测试脚手架（`package.json` + `util.js`）

**文件：**
- 新建 `package.json`
- 新建 `web/assets/lib/util.js`
- 新建 `tests/js/util.test.js`

**步骤 1：写 `package.json`**

```json
{
  "name": "hermes-usage-site",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "description": "HermesUsage 教程站前端。刻意没有 dependencies：浏览器直接加载原生 ES 模块，Node 只用来跑单元测试。",
  "scripts": {
    "test": "node --test \"tests/js/*.test.js\"",
    "build": "python scripts/build_site.py",
    "serve": "python scripts/serve.py --open"
  }
}
```

`"type": "module"` 是必需的：没有它，Node 会把 `.js` 当 CommonJS，测试里 `import` 直接报错。仓库里没有其他 `.js` 文件，所以这个声明不会影响别的东西。

**步骤 2：写失败测试 `tests/js/util.test.js`**

```js
// tests/js/util.test.js —— 跑法：node --test "tests/js/*.test.js"
import test from "node:test";
import assert from "node:assert/strict";

import { escapeHtml, formatMinutes, clamp } from "../../web/assets/lib/util.js";

test("escapeHtml 转义五个字符", () => {
  assert.equal(escapeHtml(`<a href="x">&'</a>`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
});

test("escapeHtml 对非字符串输入也安全", () => {
  assert.equal(escapeHtml(42), "42");
  assert.equal(escapeHtml(null), "null");
});

test("formatMinutes 超过 60 分钟换成小时", () => {
  assert.equal(formatMinutes(45), "45 分钟");
  assert.equal(formatMinutes(60), "1 小时 0 分钟");
  assert.equal(formatMinutes(135), "2 小时 15 分钟");
});

test("clamp 夹在区间内", () => {
  assert.equal(clamp(5, 0, 3), 3);
  assert.equal(clamp(-1, 0, 3), 0);
  assert.equal(clamp(2, 0, 3), 2);
});
```

**步骤 3：跑测试，确认失败**

```bash
node --test "tests/js/*.test.js"
```

期望：报 `Cannot find module .../web/assets/lib/util.js`。

**步骤 4：写实现 `web/assets/lib/util.js`**

```js
// web/assets/lib/util.js —— 无依赖的小工具。纯函数，方便 node --test 直接跑。

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export function formatMinutes(min) {
  const n = Number(min) || 0;
  if (n < 60) return `${n} 分钟`;
  return `${Math.floor(n / 60)} 小时 ${n % 60} 分钟`;
}

export function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, n));
}

export function debounce(fn, ms = 120) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
```

**步骤 5：跑测试，确认变绿**

```bash
node --test "tests/js/*.test.js"
```

期望：

```
# tests 4
# pass 4
# fail 0
```

**步骤 6：提交**

```bash
git add package.json web/assets/lib/util.js tests/js/util.test.js
git commit -m "feat: 前端测试脚手架（node --test，无 npm 依赖）+ util"
```

---

### 任务 T20 — 搜索：中文分词与打分

**文件：** 新建 `tests/js/search.test.js`、`web/assets/lib/search.js`

**步骤 1：写失败测试**

```js
// tests/js/search.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { tokenize, search, snippet } from "../../web/assets/lib/search.js";

test("tokenize 把中文切成二字片段", () => {
  assert.deepEqual(tokenize("技能系统"), ["技能", "能系", "系统"]);
});

test("tokenize 保留英文单词并小写化", () => {
  assert.deepEqual(tokenize("Skills 与 记忆"), ["skills", "与", "记忆"]);  // 单字中文合法，见上一条测试
});

test("tokenize 单字中文与数字也保留", () => {
  assert.deepEqual(tokenize("看 L15 课"), ["看", "l15", "课"]);
});

test("tokenize 去重", () => {
  assert.deepEqual(tokenize("技能 技能"), ["技能"]);
});

const INDEX = {
  docs: [
    { id: "L15", title: "技能系统：让它学会你的活法", stage: 1, summary: "技能是按需加载的说明书",
      text: "技能放在 ~/.hermes/skills/ 下，项目级技能需要 hermes skills trust .",
      tokens: "技能 能系 系统 技能 放在 skills 项目 目级 级技 技能 需要 hermes skills trust" },
    { id: "L23", title: "定时与循环", stage: 2, summary: "cron 与 loops",
      text: "hermes cron list 看作业，hermes cron resume 启用",
      tokens: "定时 时与 与循 循环 cron 与 loops hermes cron list 看作 作业 hermes cron resume 启用" },
  ],
};

test("search 命中全文里的关键词", () => {
  const hits = search(INDEX, "cron");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].id, "L23");
});

test("search 中文按二字片段命中", () => {
  const hits = search(INDEX, "项目技能");
  assert.equal(hits[0].id, "L15");
});

test("search 标题命中排在正文命中前面", () => {
  const hits = search(INDEX, "技能");
  assert.equal(hits[0].id, "L15");
});

test("search 无关键词或匹配不上时返回空数组", () => {
  assert.deepEqual(search(INDEX, ""), []);
  assert.deepEqual(search(INDEX, "zzzz"), []);
});

test("snippet 截取命中附近文本", () => {
  const doc = INDEX.docs[1];
  const s = snippet(doc, ["resume"], 20);
  assert.ok(s.includes("resume"), s);
  assert.ok(s.startsWith("…") || s.length >= 10);
});
```

**步骤 2：跑测试确认失败**

```bash
node --test "tests/js/*.test.js"
```

期望：`Cannot find module .../web/assets/lib/search.js`。

**步骤 3：写实现 `web/assets/lib/search.js`**

```js
// web/assets/lib/search.js —— 纯前端全文检索。
//
// 为什么不用 lunr/Fuse.js：本仓库刻意不引入 npm 依赖与打包器，
// 而这里的语料只有 32 课（约 450KB），一个 60 行的评分函数足够，
// 而且它是纯函数，能被 node --test 直接覆盖。
//
// 中文处理：不引词典，直接按「二字片段」切分（用「项目技能」能命中
// 「项目级技能」这种真实场景），英文按单词切。

const CJK = /[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/;

export function tokenize(text) {
  const out = [];
  for (const chunk of String(text || "").toLowerCase().split(/[^\p{L}\p{N}]+/u)) {
    if (!chunk) continue;
    if (!CJK.test(chunk) || chunk.length === 1) { out.push(chunk); continue; }
    for (let i = 0; i < chunk.length - 1; i++) out.push(chunk.slice(i, i + 2));
  }
  return [...new Set(out)];
}

export function search(index, query, limit = 20) {
  const terms = tokenize(query);
  if (!terms.length) return [];
  const results = [];
  for (const doc of index.docs || []) {
    const head = `${doc.title || ""} ${(doc.tags || []).join(" ")} ${doc.summary || ""}`.toLowerCase();
    const body = String(doc.tokens || "").toLowerCase();
    let score = 0;
    for (const term of terms) {
      if (head.includes(term)) score += 8;
      const freq = body.split(term).length - 1;
      if (freq > 0) score += Math.min(freq, 5);
    }
    if (score > 0) {
      results.push({ id: doc.id, title: doc.title, url: doc.url, stage: doc.stage, score, snippet: snippet(doc, terms) });
    }
  }
  return results.sort((a, b) => b.score - a.score || String(a.id).localeCompare(String(b.id))).slice(0, limit);
}

export function snippet(doc, terms, width = 80) {
  const text = doc.text || doc.summary || "";
  let at = -1;
  for (const term of terms) {
    const i = text.toLowerCase().indexOf(term);
    if (i >= 0 && (at < 0 || i < at)) at = i;
  }
  if (at < 0) return text.slice(0, width) + (text.length > width ? "…" : "");
  const start = Math.max(0, at - Math.floor(width / 3));
  return (start > 0 ? "…" : "") + text.slice(start, start + width) + (start + width < text.length ? "…" : "");
}
```

**步骤 4：跑测试确认变绿**

```bash
node --test "tests/js/*.test.js"
```

期望：`# tests 14 / # pass 14 / # fail 0`。

**步骤 5：提交**

```bash
git add web/assets/lib/search.js tests/js/search.test.js
git commit -m "feat: 前端搜索（中文二字切分 + 标题加权）"
```

---

### 任务 T21 — 进度：勾选、完成度、下一课

**文件：** 新建 `tests/js/progress.test.js`、`web/assets/lib/progress.js`

**步骤 1：写失败测试**

```js
// tests/js/progress.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { emptyState, isDone, toggleDone, completion, nextLesson, blocked } from "../../web/assets/lib/progress.js";

const LESSONS = [
  { id: "L00", title: "什么是 Hermes", minutes: 10, prereq: [] },
  { id: "L01", title: "五分钟装好", minutes: 15, prereq: ["L00"] },
  { id: "L02", title: "一次对话发生了什么", minutes: 15, prereq: ["L00"] },
];

test("emptyState 与 progress/.state.json 同构", () => {
  assert.deepEqual(emptyState(), { version: 1, done: {} });
});

test("toggleDone 不可变地翻转状态", () => {
  const s0 = emptyState();
  const s1 = toggleDone(s0, "L00", "2026-09-16T10:00:00+08:00");
  assert.equal(isDone(s0, "L00"), false, "原状态不能被改");
  assert.equal(isDone(s1, "L00"), true);
  assert.equal(s1.done.L00.at, "2026-09-16T10:00:00+08:00");
  const s2 = toggleDone(s1, "L00");
  assert.equal(isDone(s2, "L00"), false);
});

test("completion 统计完成数与剩余分钟", () => {
  const state = toggleDone(emptyState(), "L00");
  const c = completion(LESSONS, state);
  assert.deepEqual(c, { finished: 1, total: 3, minutesLeft: 30, percent: 33 });
});

test("nextLesson 跳过前置未完成的课", () => {
  const state = toggleDone(emptyState(), "L00");
  assert.equal(nextLesson(LESSONS, state).id, "L01");
});

test("nextLesson 全部完成时返回 null", () => {
  let state = emptyState();
  for (const l of LESSONS) state = toggleDone(state, l.id);
  assert.equal(nextLesson(LESSONS, state), null);
});

test("blocked 列出没做完的前置", () => {
  assert.deepEqual(blocked(LESSONS[1], emptyState()), ["L00"]);
  assert.deepEqual(blocked(LESSONS[0], emptyState()), []);
});
```

**步骤 2：跑测试确认失败**（`Cannot find module .../progress.js`）

```bash
node --test "tests/js/*.test.js"
```

**步骤 3：写实现 `web/assets/lib/progress.js`**

```js
// web/assets/lib/progress.js —— 学习进度的纯逻辑。
//
// 数据结构刻意与 progress/.state.json 完全一致（{"done": {"L00": {"at": "...", "note": ""}}}），
// 这样站点导出的 JSON 能直接给 python scripts/progress.py 用，不需要转换层。

export function emptyState() {
  return { version: 1, done: {} };
}

export function isDone(state, id) {
  return Boolean(state && state.done && state.done[id]);
}

export function toggleDone(state, id, at = new Date().toISOString()) {
  const done = { ...((state && state.done) || {}) };
  if (done[id]) delete done[id];
  else done[id] = { at, note: "" };
  return { version: 1, done };
}

export function completion(lessons, state) {
  const done = (state && state.done) || {};
  const finished = lessons.filter((l) => done[l.id]).length;
  const minutesLeft = lessons.filter((l) => !done[l.id]).reduce((n, l) => n + (l.minutes || 0), 0);
  return {
    finished,
    total: lessons.length,
    minutesLeft,
    percent: lessons.length ? Math.round((finished / lessons.length) * 100) : 0,
  };
}

export function blocked(lesson, state) {
  const done = (state && state.done) || {};
  return (lesson.prereq || []).filter((p) => !done[p]);
}

export function nextLesson(lessons, state) {
  const done = (state && state.done) || {};
  const open = lessons.filter((l) => !done[l.id]);
  return open.find((l) => (l.prereq || []).every((p) => done[p])) || open[0] || null;
}
```

**步骤 4：跑测试确认变绿**

```bash
node --test "tests/js/*.test.js"
```

期望：`# tests 20 / # pass 20`。

**步骤 5：提交**

```bash
git add web/assets/lib/progress.js tests/js/progress.test.js
git commit -m "feat: 进度纯逻辑（与 progress/.state.json 同构）"
```

---

### 任务 T22 — 存储与导入校验

**文件：** 新建 `tests/js/storage.test.js`、`web/assets/lib/storage.js`

**步骤 1：写失败测试**

```js
// tests/js/storage.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { loadState, saveState, parseState, STORAGE_KEY } from "../../web/assets/lib/storage.js";

function fakeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    _map: map,
  };
}

test("loadState 在没有数据时返回空状态", () => {
  assert.deepEqual(loadState(fakeStorage()), { version: 1, done: {} });
});

test("saveState 之后 loadState 能读回", () => {
  const s = fakeStorage();
  saveState({ version: 1, done: { L00: { at: "x", note: "" } } }, s);
  assert.equal(s._map.has(STORAGE_KEY), true);
  assert.equal(loadState(s).done.L00.at, "x");
});

test("loadState 容忍坏 JSON（浏览器存储被手改过）", () => {
  assert.deepEqual(loadState(fakeStorage({ [STORAGE_KEY]: "{不是 json" })), { version: 1, done: {} });
});

test("loadState 在 storage 抛错时也不崩（隐私模式）", () => {
  const throwing = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.deepEqual(loadState(throwing), { version: 1, done: {} });
  assert.equal(saveState({ version: 1, done: {} }, throwing), false);
});

test("parseState 接受合法状态并统计导入课数", () => {
  const r = parseState('{"done": {"L00": {"at": "2026-09-16T10:00:00", "note": "跑通了"}}}');
  assert.equal(r.ok, true);
  assert.equal(r.imported, 1);
  assert.equal(r.state.done.L00.note, "跑通了");
});

test("parseState 拒绝非对象与坏 JSON", () => {
  assert.equal(parseState("[]").ok, false);
  assert.equal(parseState("not json").ok, false);
  assert.equal(parseState('{"done": "L00"}').ok, false);
});

test("parseState 丢弃非法课号", () => {
  const r = parseState('{"done": {"L00": {}, "javascript": {}, "L01": {}}}');
  assert.deepEqual(Object.keys(r.state.done).sort(), ["L00", "L01"]);
});
```

**步骤 2：跑测试确认失败**（缺模块）

**步骤 3：写实现 `web/assets/lib/storage.js`**

```js
// web/assets/lib/storage.js —— localStorage 读写 + 导入校验 + 文件下载。
//
// 失败一律降级为「空状态 / false」，绝不抛异常：站点在 file:// 下打开、
// 或用户在隐私模式里用，都应该照常能读书，只是进度存不下来。

import { emptyState } from "./progress.js";

export const STORAGE_KEY = "hermes-usage:progress:v1";
export const THEME_KEY = "hermes-usage:theme:v1";

export function loadState(storage = globalThis.localStorage) {
  try {
    const raw = storage && storage.getItem(STORAGE_KEY);
    if (!raw) return emptyState();
    const parsed = parseState(raw);
    return parsed.ok ? parsed.state : emptyState();
  } catch {
    return emptyState();
  }
}

export function saveState(state, storage = globalThis.localStorage) {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function parseState(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return { ok: false, error: "不是合法的 JSON" };
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { ok: false, error: "顶层必须是对象" };
  }
  if (data.done != null && (typeof data.done !== "object" || Array.isArray(data.done))) {
    return { ok: false, error: "done 必须是对象" };
  }
  const clean = emptyState();
  for (const [id, value] of Object.entries(data.done || {})) {
    if (!/^L\d{2,}$/.test(id)) continue;
    clean.done[id] = {
      at: typeof value?.at === "string" ? value.at : "",
      note: typeof value?.note === "string" ? value.note : "",
    };
  }
  return { ok: true, state: clean, imported: Object.keys(clean.done).length };
}

export function loadTheme(storage = globalThis.localStorage, fallback = "auto") {
  try {
    return storage.getItem(THEME_KEY) || fallback;
  } catch {
    return fallback;
  }
}

export function saveTheme(theme, storage = globalThis.localStorage) {
  try {
    storage.setItem(THEME_KEY, theme);
  } catch {
    /* 存不下就算了：主题不是关键数据 */
  }
}

export function download(filename, text) {
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

**步骤 4：跑测试确认变绿**

```bash
node --test "tests/js/*.test.js"
```

期望：`# tests 27 / # pass 27`。

**步骤 5：提交**

```bash
git add web/assets/lib/storage.js tests/js/storage.test.js
git commit -m "feat: 进度存储与导入校验（含隐私模式降级）"
```

---

### 任务 T23 — 目录高亮（scrollspy）

**文件：** 新建 `tests/js/toc.test.js`、`web/assets/lib/toc.js`

**步骤 1：写失败测试**

```js
// tests/js/toc.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { pickActive } from "../../web/assets/lib/toc.js";

const OFFSETS = [
  { id: "s1", top: 0 },
  { id: "s2", top: 600 },
  { id: "s3", top: 1200 },
];

test("滚动到两个标题之间时高亮上一个", () => {
  assert.equal(pickActive(OFFSETS, 700, 90), "s2");
  assert.equal(pickActive(OFFSETS, 100, 90), "s1");
});

test("页面顶部之前仍然高亮第一个", () => {
  assert.equal(pickActive(OFFSETS, -500, 90), "s1");
});

test("滚到底部时高亮最后一个", () => {
  assert.equal(pickActive(OFFSETS, 99999, 90), "s3");
});

test("没有标题时返回 null", () => {
  assert.equal(pickActive([], 0, 90), null);
});
```

**步骤 2：跑测试确认失败**

**步骤 3：写实现 `web/assets/lib/toc.js`**

```js
// web/assets/lib/toc.js —— 目录高亮（scrollspy）。

export function headingOffsets(root, selector = "h2[id], h3[id]") {
  return [...root.querySelectorAll(selector)].map((el) => ({
    id: el.id,
    top: el.getBoundingClientRect().top + window.scrollY,
  }));
}

export function pickActive(offsets, scrollY, margin = 90) {
  if (!offsets.length) return null;
  let active = offsets[0].id;
  for (const item of offsets) {
    if (item.top - margin <= scrollY) active = item.id;
    else break;
  }
  return active;
}
```

**步骤 4：跑测试确认变绿**

```bash
node --test "tests/js/*.test.js"
```

期望：`# tests 31 / # pass 31`。

**步骤 5：提交**

```bash
git add web/assets/lib/toc.js tests/js/toc.test.js
git commit -m "feat: 目录高亮纯函数"
```

---

### 任务 T24 — 前端入口 `web/assets/app.js`（把一切接起来）

**文件：** 重写 `web/assets/app.js`

**要求：** 这是唯一的 DOM 胶水层，没有单元测试，但必须有**明确的降级**：任何一步失败（fetch 失败、`localStorage` 不可用、元素不存在）都不能让页面白屏 —— 静态 HTML 已经能读，JS 只做增强。

```js
// web/assets/app.js —— 站点交互入口。
//
// 原则：静态 HTML 已经能完整阅读，本文件只做「增强」——
// 搜索、进度、目录高亮、复制代码、主题。任何一处失败都要安静降级，不能白屏。

import { escapeHtml, debounce, formatMinutes } from "./lib/util.js";
import { search, tokenizeToQuery } from "./lib/search.js";
import { toggleDone, completion, nextLesson, isDone, blocked } from "./lib/progress.js";
import { loadState, saveState, parseState, loadTheme, saveTheme, download } from "./lib/storage.js";
import { pickActive, headingOffsets } from "./lib/toc.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const PREFIX = document.body.dataset.prefix || "";

let lessons = [];
let state = loadState();
let searchIndex = null;

boot();

async function boot() {
  applyTheme(loadTheme());
  wireThemeToggle();
  wireNavDrawer();
  wirePalette();
  wireToc();
  wireCopyButtons();

  try {
    const res = await fetch(`${PREFIX}data/index.json`);
    lessons = (await res.json()).lessons || [];
  } catch {
    return; // 拿不到索引就只保留静态阅读
  }
  wireProgressButtons();
  paint();
}

/* ---------------------------------------------------------------- 进度 */

function paint() {
  const done = state.done || {};
  for (const li of $$("[data-lesson]")) {
    li.classList.toggle("is-done", Boolean(done[li.dataset.lesson]));
  }
  const stats = completion(lessons, state);
  const count = $("#done-count");
  const bar = $("#bar-fill");
  const left = $("#min-left");
  const pill = $("#progress-pill");
  if (count) count.textContent = String(stats.finished);
  if (bar) bar.style.width = `${stats.percent}%`;
  if (left) left.textContent = formatMinutes(stats.minutesLeft);
  if (pill) pill.textContent = `${stats.finished}/${stats.total}`;

  const btn = $("#mark-done");
  if (btn) btn.textContent = isDone(state, btn.dataset.lesson) ? "取消完成标记" : "标记本课完成";
}

function commit(next) {
  state = next;
  if (!saveState(state)) {
    const out = $("#pc-out");
    if (out) {
      out.hidden = false;
      out.textContent = "这个浏览器不允许保存本地进度（隐私模式？），进度只在本次会话有效。";
    }
  }
  paint();
}

function wireProgressButtons() {
  const mark = $("#mark-done");
  if (mark) mark.addEventListener("click", () => commit(toggleDone(state, mark.dataset.lesson)));
  for (const li of $$("[data-lesson]")) {
    const check = li.querySelector(".nav-check");
    if (!check || li.querySelector("#mark-done")) continue;
    // 侧栏/首页的圆圈可以直接点：把「打勾」这件最高频的事放到最顺手的地方
    check.style.cursor = "pointer";
    check.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      commit(toggleDone(state, li.dataset.lesson));
    });
  }

  const next = $("#next-lesson");
  if (next) {
    next.addEventListener("click", () => {
      const target = nextLesson(lessons, state);
      const out = $("#pc-out");
      if (!target) {
        if (out) { out.hidden = false; out.textContent = "全部课程都完成了。去 L90 毕业项目吧。"; }
        return;
      }
      const miss = blocked(target, state);
      if (out) {
        out.hidden = false;
        out.textContent = miss.length
          ? `${target.id} ${target.title} 的前置还没完成：${miss.join("、")}`
          : `下一课：${target.id} · ${target.title}（${target.minutes} 分钟）—— 正在打开…`;
      }
      if (!miss.length) location.href = `${PREFIX}${target.url}`;
    });
  }

  const exportBtn = $("#export-progress");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      download("progress.state.json", `${JSON.stringify(state, null, 2)}\n`);
    });
  }

  const importBtn = $("#import-progress");
  const fileInput = $("#import-file");
  if (importBtn && fileInput) {
    importBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      const parsed = parseState(await file.text());
      const out = $("#pc-out");
      if (!parsed.ok) {
        if (out) { out.hidden = false; out.textContent = `导入失败：${parsed.error}`; }
        return;
      }
      commit(parsed.state);
      if (out) { out.hidden = false; out.textContent = `已导入 ${parsed.imported} 课的完成状态。`; }
    });
  }
}

/* ---------------------------------------------------------------- 搜索 */

function wirePalette() {
  const palette = $("#palette");
  const input = $("#palette-input");
  const list = $("#palette-results");
  const openBtn = $("#search-open");
  if (!palette || !input || !list) return;
  let cursor = 0;

  const close = () => { palette.hidden = true; input.value = ""; list.innerHTML = ""; };
  const open = async () => {
    palette.hidden = false;
    input.focus();
    if (!searchIndex) {
      try {
        const res = await fetch(`${PREFIX}data/search.json`);
        searchIndex = await res.json();
        // 检索用的「二字片段串」在客户端算一次（32 课，开销可忽略），
        // 复用 search.js 的分词函数，避免两处逻辑漂移
        for (const doc of searchIndex.docs) doc.tokens = tokenizeToQuery(doc.text);
      } catch {
        searchIndex = { docs: [] };
      }
    }
    render();
  };

  function render() {
    const hits = searchIndex ? search(searchIndex, input.value) : [];
    cursor = Math.min(cursor, Math.max(hits.length - 1, 0));
    list.innerHTML = hits.length
      ? hits.map((h, i) => `
        <li data-url="${escapeHtml(PREFIX + h.url)}" aria-selected="${i === cursor}">
          <div><b>${escapeHtml(h.id)} ${escapeHtml(h.title)}</b></div>
          <div class="pr-meta">${escapeHtml(h.snippet)}</div>
        </li>`).join("")
      : `<li class="pr-meta">${input.value ? "没有匹配的课程" : "输入关键词开始搜索（例如：cron、技能、回滚）"}</li>`;
  }

  input.addEventListener("input", debounce(render, 80));
  input.addEventListener("keydown", (e) => {
    const items = $$("li[data-url]", list);
    if (e.key === "ArrowDown") { cursor = Math.min(cursor + 1, items.length - 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { cursor = Math.max(cursor - 1, 0); render(); e.preventDefault(); }
    else if (e.key === "Enter" && items[cursor]) location.href = items[cursor].dataset.url;
    else if (e.key === "Escape") close();
  });
  list.addEventListener("click", (e) => {
    const li = e.target.closest("li[data-url]");
    if (li) location.href = li.dataset.url;
  });
  if (openBtn) openBtn.addEventListener("click", open);
  palette.addEventListener("click", (e) => { if (e.target === palette) close(); });
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
    if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) { open(); e.preventDefault(); return; }
    if (e.key === "/" && !typing) { open(); e.preventDefault(); return; }
    if (e.key === "Escape" && !palette.hidden) close();
  });
}

/* ---------------------------------------------------------------- 目录 */

function wireToc() {
  const toc = $("#toc-side");
  if (!toc || !toc.querySelector("a")) return;
  const offsets = headingOffsets(document);
  if (!offsets.length) return;
  const links = new Map($$("a", toc).map((a) => [a.getAttribute("href").slice(1), a]));
  const onScroll = () => {
    const active = pickActive(offsets, window.scrollY);
    for (const [id, a] of links) a.classList.toggle("active", id === active);
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

/* ---------------------------------------------------------------- 代码复制 */

function wireCopyButtons() {
  for (const pre of $$(".lesson pre")) {
    const code = pre.querySelector("code");
    if (!code) continue;
    const btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "复制";
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code.innerText);
        btn.textContent = "已复制";
      } catch {
        btn.textContent = "复制失败";
      }
      setTimeout(() => { btn.textContent = "复制"; }, 1200);
    });
    pre.append(btn);
  }
}

/* ---------------------------------------------------------------- 主题与抽屉 */

function applyTheme(theme) {
  const resolved = theme === "auto"
    ? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : theme;
  document.documentElement.dataset.theme = resolved === "dark" ? "dark" : "light";
}

function wireThemeToggle() {
  const btn = $("#theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    saveTheme(next);
    applyTheme(next);
  });
}

function wireNavDrawer() {
  const toggle = $("#nav-toggle");
  const sidebar = $("#sidebar");
  if (!toggle || !sidebar) return;
  toggle.addEventListener("click", () => {
    const open = sidebar.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => {
    if (!sidebar.classList.contains("is-open")) return;
    if (sidebar.contains(e.target) || toggle.contains(e.target)) return;
    sidebar.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  });
}
```

**同一个任务里还要补一个导出**（否则上面的 `import` 会失败）：在 `web/assets/lib/search.js` 末尾追加

```js
export function tokenizeToQuery(text) {
  return tokenize(text).join(" ");
}
```

并在 `tests/js/search.test.js` 追加一条断言：

```js
test("tokenizeToQuery 输出可被 search 直接消费的片段串", async () => {
  const { tokenizeToQuery } = await import("../../web/assets/lib/search.js");
  assert.equal(tokenizeToQuery("技能系统"), "技能 能系 系统");
});
```

然后 `node --test "tests/js/*.test.js"` 期望仍是 `# tests 31 / # pass 31`（tokenizeToQuery 的断言在 T20 阶段就已加过，这里不要重复添加）。

**手工验收（这一步必须真在浏览器里做，不要跳）：**

```bash
python scripts/build_site.py && python scripts/serve.py --open
```

逐条确认（每条都是「看到什么」而不是「感觉对」）：

1. 首页顶栏右侧显示 `0/32`；点某课左侧的 ○ 圆圈 → 该课标题变灰并加删除线，顶栏数字变 `1/32`，进度条有宽度。
2. 按 `Ctrl+K`（或 `/`）弹出搜索：输入 `cron` → 结果里出现 `L23`；输入 `技能` → 出现 `L15` 与 `L40`；`↑↓` 能移动高亮，`Enter` 能打开。
3. 打开任意课程页：右侧出现「本页目录」（8 个小节），滚动时高亮跟着变。
4. 鼠标悬停在正文里的 `src:quickstart` 徽标上 → tooltip 显示 `Quickstart（hermes v0.21.3 · 快照 sha256 0c6e2ab63a68…）`；点击 → 新标签打开官方文档。
5. 点任意 `[[L13]]` 变成的链接 → 跳到该课页面（不是 404）。
6. 任意代码块右上角出现「复制」；点击后变成「已复制」，剪贴板里是命令。
7. 点顶栏 `◐` → 主题切换；刷新后保持。
8. 把窗口拖窄到手机宽度 → 侧栏收起，左上汉堡按钮能拉出抽屉。
9. 首页点「导出进度 JSON」→ 浏览器下载 `progress.state.json`；把它改两课后用「导入进度 JSON」再导入 → 打勾状态变成文件里的内容。
10. 浏览器控制台 **没有** 未捕获错误。

**提交：**

```bash
git add web/assets/app.js web/assets/lib/search.js tests/js/search.test.js
git commit -m "feat: 前端交互入口（搜索面板/进度/目录高亮/复制/主题/抽屉）"
```

---

### 任务 T25 — 本地预览服务器 `scripts/serve.py`

**文件：** 新建 `tests/js/` 无关；新建 `scripts/serve.py`

**步骤 1：写实现**

```python
#!/usr/bin/env python3
"""scripts/serve.py —— 本地预览站点（只用标准库，不装任何东西）。

为什么不用 `python -m http.server`：
1. 它不知道 `.mjs`/`.js` 的 MIME，ES 模块会被浏览器拒绝执行；
2. 它没有 no-store，调试时会被浏览器缓存骗；
3. 它不会先构建。

用法
----
  python scripts/serve.py                # 构建（若 site/ 不存在）并启动到 127.0.0.1:8000
  python scripts/serve.py --port 8137 --open
  python scripts/serve.py --no-build     # 直接用现有 site/
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".webp": "image/webp",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **MIME}
    server_version = "hermes-usage-preview/1"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        # 只报非 200：预览时噪音少一半
        status = args[1] if len(args) > 1 else ""
        if "200" not in str(status):
            super().log_message(fmt, *args)


def main() -> int:
    ap = argparse.ArgumentParser(description="本地预览教程站")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--dir", default=str(SITE))
    ap.add_argument("--no-build", action="store_true", help="不先跑 build_site.py")
    ap.add_argument("--open", action="store_true", help="启动后打开浏览器")
    args = ap.parse_args()

    root = Path(args.dir)
    if not args.no_build:
        rc = subprocess.run([sys.executable, str(REPO / "scripts" / "build_site.py")]).returncode
        if rc != 0:
            print("构建失败，先修好再预览。", file=sys.stderr)
            return rc
    if not (root / "index.html").is_file():
        print(f"没有 {root}/index.html —— 先跑 python scripts/build_site.py", file=sys.stderr)
        return 1

    handler = functools.partial(Handler, directory=str(root))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        url = f"http://{args.host}:{args.port}/"
        print(f"教程站已启动：{url}    （Ctrl+C 停止）")
        if args.open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**步骤 2：验证（自动化部分）**

```bash
python scripts/serve.py --no-build --port 8137 &
sleep 2
curl -s -o /dev/null -w "首页 %{http_code} %{content_type}\n" http://127.0.0.1:8137/
curl -s -o /dev/null -w "课程页 %{http_code} %{content_type}\n" http://127.0.0.1:8137/lessons/L15-skills.html
curl -s -o /dev/null -w "JS %{http_code} %{content_type}\n" http://127.0.0.1:8137/assets/app.js
curl -s -o /dev/null -w "JSON %{http_code} %{content_type}\n" http://127.0.0.1:8137/data/index.json
curl -s http://127.0.0.1:8137/data/index.json | python -c "import json,sys;print('课程数', len(json.load(sys.stdin)['lessons']))"
kill %1
```

期望输出（MIME 是重点：JS 必须是 `text/javascript`，否则 ES 模块加载失败）：

```
首页 200 text/html; charset=utf-8
课程页 200 text/html; charset=utf-8
JS 200 text/javascript; charset=utf-8
JSON 200 application/json; charset=utf-8
课程数 32
```

**步骤 3：提交**

```bash
git add scripts/serve.py
git commit -m "feat: 本地预览服务器（正确 MIME + no-store）"
```

---

### 任务 T26 — 总检查脚本 `scripts/check.py`

**目的：** `.hermes.md` 承诺「一条命令知道改得对不对」。加了站点后，这条命令要把新东西一起管起来。

**文件：** 新建 `scripts/check.py`

**步骤 1：写实现**

```python
#!/usr/bin/env python3
"""scripts/check.py —— 一条命令跑完所有检查。

顺序是有意的，从便宜到贵、从内容到产物：
  1. 内容门禁（verify.py 的 11 条规则）
  2. 索引同步（llms.txt 是否与课程集一致）
  3. Python 单元测试（解析层 / 渲染层 / 构建器）
  4. 前端单元测试（Node 内置测试器；没装 node 就跳过并提示）
  5. 站点构建自检（临时目录构建 + 站内链接全解析）

用法
----
  python scripts/check.py            # 全绿退出 0
  python scripts/check.py --skip-node
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(label: str, cmd: list[str]) -> bool:
    print(f"\n=== {label} ===")
    print("$ " + " ".join(cmd))
    rc = subprocess.run(cmd, cwd=REPO).returncode
    print(f"--- {label}: {'通过' if rc == 0 else f'失败（退出码 {rc}）'}")
    return rc == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="HermesUsage 全量检查")
    ap.add_argument("--skip-node", action="store_true")
    args = ap.parse_args()

    steps: list[tuple[str, list[str]]] = [
        ("内容门禁 verify.py", [PY, "scripts/verify.py", "--quiet"]),
        ("索引同步 build_index.py", [PY, "scripts/build_index.py", "--check"]),
        ("Python 单元测试", [PY, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-p", "test_*.py"]),
        ("站点构建自检 build_site.py --check", [PY, "scripts/build_site.py", "--check"]),
    ]
    if not args.skip_node:
        node = shutil.which("node")
        if node:
            steps.insert(3, ("前端单元测试 node --test", [node, "--test", "tests/js/*.test.js"]))
        else:
            print("[提示] 没找到 node，跳过前端单元测试（python scripts/check.py --skip-node 可显式跳过）")

    results = [(label, run(label, cmd)) for label, cmd in steps]

    print("\n=== 汇总 ===")
    for label, ok in results:
        print(f"  {'✓' if ok else '✗'} {label}")
    failed = [label for label, ok in results if not ok]
    if failed:
        print(f"\n未通过：{len(failed)} 项 —— {', '.join(failed)}")
        return 1
    print(f"\n全部通过：{len(results)} 项检查全绿。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**步骤 2：运行**

```bash
python scripts/check.py
```

期望输出（末尾）：

```
=== 汇总 ===
  ✓ 内容门禁 verify.py
  ✓ 索引同步 build_index.py
  ✓ Python 单元测试
  ✓ 前端单元测试 node --test
  ✓ 站点构建自检 build_site.py --check

全部通过：5 项检查全绿。
```

**步骤 3：故意制造一次失败，确认它真的会红**（不做这步等于没验证过门禁）

```bash
# 临时把 render 的出处改写关掉（改一行代码）再跑，应当失败
python - <<'PY'
from pathlib import Path
p = Path("scripts/site_render.py")
s = p.read_text(encoding="utf-8")
Path("scripts/site_render.py.bak").write_text(s, encoding="utf-8")
p.write_text(s.replace('raise SiteError(f"{where}: 引用了未登记的出处', 'pass  # '), encoding="utf-8", newline="\n")
PY
python -m unittest discover -s tests -t . -p "test_*.py" 2>&1 | tail -3
mv scripts/site_render.py.bak scripts/site_render.py   # 恢复
```

期望：看到 `FAILED (failures=1)` 或 `ERROR`（证明测试确实在盯着这个行为），恢复后再跑一次 `python -m unittest discover -s tests -t . -p "test_*.py"` 应回到 `OK`。

**步骤 4：提交**

```bash
git add scripts/check.py
git commit -m "feat: 一条命令的全量检查（门禁+测试+站点自检）"
```

---

### 任务 T27 — 容器部署：Dockerfile / nginx / compose

**先读这条：** 本机 **没有 docker**（`docker: command not found`）。所以这一任务的自检方式是「把 Dockerfile 里的命令在本机原样跑一遍」，`docker build` 只能在有 docker 的机器上验证 —— 实施时必须在 `journal/` 里写明「Docker 部分未在本机验证」，不要声称验证过。

**文件：** 新建 `deploy/nginx.conf`、`Dockerfile`、`.dockerignore`、`docker-compose.yml`

**步骤 1：`deploy/nginx.conf`**

```nginx
# 容器内的 nginx：静态托管 site/
server {
    listen 80;
    listen [::]:80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;
    charset utf-8;

    gzip on;
    gzip_comp_level 6;
    gzip_min_length 1024;
    gzip_types text/html text/css text/javascript application/javascript application/json image/svg+xml;

    # 资源带内容指纹的时代没到（构建不做 hash 文件名），所以用短缓存
    location /assets/ {
        add_header Cache-Control "public, max-age=3600";
        try_files $uri =404;
    }
    location /data/ {
        add_header Cache-Control "public, max-age=300";
        try_files $uri =404;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }

    error_page 404 /404.html;
}
```

**步骤 2：`Dockerfile`（多阶段：构建站 → nginx 托管，最终镜像只含静态文件）**

```dockerfile
# syntax=docker/dockerfile:1
# 阶段 1：构建。内容门禁不过就不出镜像 —— 坏内容不该有办法上线。
FROM python:3.11-slim AS build
WORKDIR /repo
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python scripts/verify.py --quiet && python scripts/build_site.py

# 阶段 2：托管。只有 nginx + 静态文件，没有 Python、没有源码。
FROM nginx:1.27-alpine AS serve
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/site /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://127.0.0.1/index.html > /dev/null || exit 1
```

**步骤 3：`.dockerignore`**

```
.git
.github
site
node_modules
__pycache__
**/__pycache__
progress/.state.json
progress/.scratch
*.bak
.DS_Store
```

**步骤 4：`docker-compose.yml`**

```yaml
# 一条命令起站：docker compose up -d --build → http://localhost:8080
services:
  tutorial:
    build: .
    image: hermes-usage-tutorial:local
    container_name: hermes-usage-tutorial
    ports:
      - "8080:80"
    restart: unless-stopped
```

**步骤 5：把镜像里跑的每一步在本机验证一遍**

```bash
python -m pip install -r requirements.txt
python scripts/verify.py --quiet && python scripts/build_site.py
ls site/index.html site/404.html site/.nojekyll
```

期望：最后一条命令打印三个路径，且 `build_site.py` 输出 `站点自检通过：32 课 / …`。

**步骤 6：提交**

```bash
git add Dockerfile .dockerignore docker-compose.yml deploy/nginx.conf
git commit -m "feat: 容器部署（多阶段构建 + nginx + compose）"
```

---

### 任务 T28 — 静态托管配置（Netlify / Vercel）

**文件：** 新建 `netlify.toml`、`vercel.json`

**步骤 1：`netlify.toml`**

```toml
# Netlify：连上仓库就能自动构建（构建期装 Python 依赖 → 生成 site/ → 发布该目录）
[build]
  command = "python -m pip install -r requirements.txt && python scripts/build_site.py"
  publish = "site"

[build.environment]
  PYTHON_VERSION = "3.11"

[[headers]]
  for = "/assets/*"
  [headers.values]
    Cache-Control = "public, max-age=3600"

[[headers]]
  for = "/data/*"
  [headers.values]
    Cache-Control = "public, max-age=300"

[[redirects]]
  from = "/*"
  to = "/404.html"
  status = 404
```

**步骤 2：`vercel.json`**

```json
{
  "buildCommand": "python scripts/build_site.py",
  "installCommand": "python -m pip install -r requirements.txt",
  "outputDirectory": "site",
  "cleanUrls": false,
  "trailingSlash": false,
  "headers": [
    {
      "source": "/data/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=300" }]
    }
  ]
}
```

**步骤 3：验证两份配置的语法**

```bash
python -c "import json,pathlib; json.load(open('vercel.json',encoding='utf-8')); print('vercel.json OK')"
python -c "
import sys
try:
    import tomllib
except ModuleNotFoundError:
    sys.exit('Python 3.11 应自带 tomllib')
d = tomllib.load(open('netlify.toml','rb'))
print('netlify.toml OK', d['build']['publish'])
"
```

期望：

```
vercel.json OK
netlify.toml OK site
```

**步骤 4：提交**

```bash
git add netlify.toml vercel.json
git commit -m "feat: Netlify/Vercel 零配置构建（publish=site）"
```

---

### 任务 T29 — CI 与 GitHub Pages 工作流

**文件：** 新建 `.github/workflows/ci.yml`、`.github/workflows/pages.yml`

**步骤 1：`.github/workflows/ci.yml`**

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: python -m pip install -r requirements.txt
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - name: 全量检查（门禁 + 单元测试 + 站点自检）
        run: python scripts/check.py
```

**步骤 2：`.github/workflows/pages.yml`**

```yaml
name: pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: python -m pip install -r requirements.txt
      - name: 门禁 + 构建（坏内容不进 Pages）
        run: python scripts/verify.py && python scripts/build_site.py
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

站点全部资源路径都是相对的（`../assets/…`），所以部署在 `https://<user>.github.io/HermesUsage/` 这种子路径下也能正常工作，不需要配 `base`。

**步骤 3：验证 YAML 语法（本机没有 actionlint，用 Python 解析）**

```bash
python - <<'PY'
import yaml, pathlib
for p in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    print(p.as_posix(), "OK", list(d.get("jobs", {}).keys()))
PY
```

期望：

```
.github/workflows/ci.yml OK ['check']
.github/workflows/pages.yml OK ['build', 'deploy']
```

**步骤 4：提交**

```bash
git add .github/workflows
git commit -m "ci: 全量检查工作流 + GitHub Pages 发布"
```

---

### 任务 T30 — 部署手册 `docs/deploy.md`

**文件：** 新建 `docs/deploy.md`

**要求：** 读者是「只想让站点跑起来」的人。每种方式都给：一条命令、期望输出、怎么停、常见失败原因。**必须诚实标注本机未验证的部分**（Docker、GitHub Pages）。

````markdown
# 部署这份教程站

站点是**纯静态文件**（`site/`），不需要数据库、不需要常驻 Python 进程。
构建只需要 Python 3.11 + 两个纯 Python 依赖（见 `requirements.txt`）。

```bash
python -m pip install -r requirements.txt
python scripts/build_site.py
# 站点自检通过：32 课 / 39 页 / … 文件 / … KB（出处基线 hermes v0.21.3）
```

产物结构：`site/index.html`（首页）、`site/lessons/*.html`（32 课）、`site/repo/*.html`（规范页）、
`site/data/*.json`（导航与检索数据）、`site/assets/*`（样式与前端脚本）。

---

## 方式一：本地预览（零依赖，最快）

```bash
python scripts/serve.py --open
```

```
教程站已启动：http://127.0.0.1:8000/    （Ctrl+C 停止）
```

- 换端口：`python scripts/serve.py --port 8137`
- 跳过重新构建：`python scripts/serve.py --no-build`
- 停止：在终端按 `Ctrl+C`

**别用 `python -m http.server` 代替它**：那个服务器的 MIME 表不认 `.js` 是
`text/javascript`，浏览器会拒绝加载 ES 模块，页面交互会全哑。

## 方式二：Docker（一条命令，适合丢到服务器上）

```bash
docker compose up -d --build     # → http://localhost:8080
docker compose logs -f tutorial  # 看访问日志
docker compose down              # 停掉
```

镜像分两阶段：构建阶段跑 `verify.py`（内容门禁不过就构建失败），
运行阶段只有 `nginx:alpine` + 静态文件。

> 状态：本仓库作者的本机没有 Docker，**这套配置尚未在真实 Docker 里跑过**。
> 如果 `docker build` 报错，请按报错行号判断是 Python 依赖还是 nginx 配置问题，
> 并更新本文件。

## 方式三：Netlify

1. 仓库推到 GitHub/GitLab 后，在 Netlify 里「Add new site → Import an existing project」。
2. 构建命令与发布目录已写在 `netlify.toml`，不需要在界面上填：
   - build: `python -m pip install -r requirements.txt && python scripts/build_site.py`
   - publish: `site`

## 方式四：Vercel

```bash
npm i -g vercel
vercel        # 首次会问几个问题，构建配置读 vercel.json
vercel --prod # 发布
```

`vercel.json` 已声明 `installCommand` / `buildCommand` / `outputDirectory`，无需手工配置。

## 方式五：GitHub Pages（仓库自带的 Actions）

1. 仓库推到 GitHub，且**默认分支是 `main`**。
2. 仓库 Settings → Pages → Build and deployment → Source 选 **GitHub Actions**。
3. 之后每次 push 到 `main`，`.github/workflows/pages.yml` 会：
   `pip install -r requirements.txt` → `verify.py` → `build_site.py` → 上传 `site/` → 发布。
4. 站点地址：`https://<用户名>.github.io/<仓库名>/`。

> 状态：本机**没有 git remote**（`git remote -v` 为空），因此这条路径也**未在生产上验证过**。
> 首次 push 后请在 Actions 页面确认 `pages` 工作流全绿。

---

## 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'markdown'` | 没装依赖 | `python -m pip install -r requirements.txt` |
| 页面能开但没有交互（搜索/打勾都不响应） | 静态服务器把 `.js` 的 MIME 给错了 | 用 `python scripts/serve.py` 或 nginx 配置里的默认 MIME |
| `构建失败：… 引用了未登记的出处 [[src:xxx]]` | 课程里写了没登记的出处 | 在 `sources/registry.yaml` 登记后 `python scripts/sync_sources.py` |
| `站内链接自检失败：N 条` | 有内部链接指向不存在的文件 | 按输出的「页面 → 目标」逐条修 |
| 站点是旧的 | `site/` 是上次构建的产物 | 重新 `python scripts/build_site.py`（CI 每次都会重建） |
| 中文在 Netlify/Vercel 上乱码 | 托管方没按 UTF-8 处理 | 本项目所有产物都是 UTF-8；若出现乱码，检查是否手改了 `site/` 里的文件 |
````

**验证：**

```bash
python -c "import pathlib;print(len(pathlib.Path('docs/deploy.md').read_text(encoding='utf-8').splitlines()),'行')"
```

期望：打印行数（约 100 行），不报错。

**提交：**

```bash
git add docs/deploy.md
git commit -m "docs: 部署手册（本地/Docker/Netlify/Vercel/Pages + 排障）"
```

---

### 任务 T31 — README 与宪章同步

**目的：** 新增了 `web/`、`tests/`、`site/`、`scripts/*.py` 之后，仓库存档的「目录地图」和「改完必跑的命令」必须同步 —— 否则下一个人（或 AI）会以为这些东西不存在。

**文件：** 修改 `README.md`、`.hermes.md`、`ROADMAP.md`、`CONTRIBUTING.md`、`.hermes/skills/hermes-tutorial-authoring/SKILL.md`

**步骤 1：`README.md` 在「用这个仓库的 4 条命令」之后追加一节**

```markdown
---

## 在线看 / 本地看（交互站点）

课程除了 Markdown 原文，还有一份**可搜索、带进度打卡、出处可点开核对**的静态站点：

```bash
python -m pip install -r requirements.txt   # PyYAML + Markdown，都是纯 Python
python scripts/serve.py --open              # 构建并打开 http://127.0.0.1:8000/
```

站点能力：按阶段浏览 32 课、全站搜索（`Ctrl+K`，支持中文）、进度打勾与导出/导入 JSON、
8 小节目录跳转、代码块一键复制、`src:…` 出处徽标悬停显示官方版本与快照哈希。

部署（Docker / Netlify / Vercel / GitHub Pages）：见 [docs/deploy.md](docs/deploy.md)。

```bash
python scripts/check.py      # 一条命令：内容门禁 + 单元测试 + 站点自检
```
```

同时把该节上方的「用这个仓库的 4 条命令」标题改成「用这个仓库的命令」，并在代码块里补一行：

```bash
python scripts/build_site.py               # 重建静态站点 site/（前端改动后必跑）
```

**步骤 2：`.hermes.md` 更新三处**

§1 目录地图里替换 `docs/learning-map.html` 那一行段，插入：

```
web/                              站点前端源码（模板 / CSS / 原生 ES 模块；无 npm 依赖）
                                  注意：站点源码在 web/，构建产物在 site/（site/ 不进 git）
tests/                            Python 单元测试（unittest）与前端测试（tests/js，node --test）
site/                             构建产物（由 scripts/build_site.py 生成，已 gitignore）
scripts/build_site.py             生成静态站点 + 站内链接自检
scripts/serve.py                  本地预览（正确 MIME，别用 python -m http.server 顶替）
scripts/check.py                  一条命令跑完全部检查（CI 与提交前用这个）
```

§3 的检查命令替换成：

```bash
python scripts/build_index.py      # 新增/删除课程后：重建 llms.txt
python scripts/verify.py           # 内容门禁：11 条规则全绿才算改完
python scripts/check.py            # 全量：门禁 + 单元测试 + 站点自检（最省事的入口）
python scripts/build_site.py       # 改了 web/ 或课程后：重建站点
```

并追加一段说明：

> **站点与课程的关系**：`lessons/` 是唯一内容源，`site/` 是它的编译产物。
> 改课程后 `python scripts/check.py` 会验证站点能重建、站内链接无死链。
> 不要手改 `site/` 里的任何文件（它在 .gitignore 里，改了也会被下次构建覆盖）。

§6 坑表追加两行：

```
| 站点页面交互全哑（搜索、打勾没反应） | 用了 `python -m http.server`，`.js` 的 MIME 不对，ES 模块被浏览器拒绝 | 改用 `python scripts/serve.py` |
| 站点里出现 `{{footer}}` 这样的字面量 | 模板占位符没填 | build_site.py 会直接报错并指出占位符名，补 `render_template` 的 values |
```

**步骤 3：`ROADMAP.md`**

- 「维护待办（系统层）」的第一条 `- [ ] 给 scripts/verify.py 加 CI…` 改成 `- [x] 给 scripts/verify.py 加 CI（.github/workflows/ci.yml：check.py 全绿才允许合并）`
- 文件末尾新增一节：

```markdown
## 站点（前端）

| 能力 | 状态 | 位置 |
|---|---|---|
| 按阶段浏览 + 进度打卡 | ✅ | `web/assets/app.js` + `site/index.html` |
| 全站搜索（中文二字切分） | ✅ | `web/assets/lib/search.js` |
| `src:` 出处徽标（悬停看版本与哈希） | ✅ | `scripts/site_render.py` |
| 本地预览 / Docker / Netlify / Vercel / Pages | ✅ | `docs/deploy.md` |
| 练习打卡（`- [ ]` 可点击并保存） | ⬜ | 现在是只读方框，交互待做 |
| 学习地图与站点合并（去掉重复的两套渲染） | ⬜ | `scripts/build_map.py` 仍是独立渲染 |
```

**步骤 4：`CONTRIBUTING.md`** 把「改完跑什么」统一成一条：

```bash
python scripts/check.py     # 全绿才提交；只看内容改动时可用 python scripts/verify.py
```

**步骤 5：`.hermes/skills/hermes-tutorial-authoring/SKILL.md`** 在「### 5. 通过门禁」追加第 5 步与一条坑：

```markdown
### 5.5 顺带确认站点能重建

课程是站点唯一的内容源，改完课必须确认站点还能编译：

```bash
python scripts/build_site.py     # 期望：站点自检通过：32 课 / … 页 / … 文件
```

站点源码在 `web/`（模板与前端），产物在 `site/`（gitignore，别手改）。
出处标记、交叉引用、仓库内相对链接写错时，构建会直接失败并指出是哪一课。
```

坑表追加：

```
- **`site/` 是产物，不是源码**：要么改 `lessons/`，要么改 `web/`；
  手改 `site/` 会在下次构建时丢失。
```

**步骤 6：验证（文档改了也要过门禁）**

```bash
python scripts/check.py
```

期望：`全部通过：5 项检查全绿。`

**步骤 7：提交**

```bash
git add README.md .hermes.md ROADMAP.md CONTRIBUTING.md .hermes/skills/hermes-tutorial-authoring/SKILL.md
git commit -m "docs: 站点相关文档同步（README/宪章/路线图/贡献/技能）"
```

---

### 任务 T32 — 让 `build_map.py` 复用解析层（DRY 收口）

**目的：** `build_map.py` 里还留着一份 frontmatter 解析与阶段表。既然 `tutorial_core` 已经是唯一入口，就把它接过去 —— 但要**行为字节不变**。

**文件：** 修改 `scripts/build_map.py`

**步骤 1：先留基线，改完做字节对比（这一步不能省）**

```bash
python scripts/build_map.py --stdout > /tmp/map-before.html
wc -c /tmp/map-before.html
```

期望：打印一个字节数（当前约 17KB 量级），记下来。

**步骤 2：改 `scripts/build_map.py`**

- 删除文件里的 `FM_RE`、`STAGES` 定义；
- 顶部加：`sys.path.insert(0, str(Path(__file__).resolve().parent))` + `import tutorial_core as core`；
- `render()` 里对阶段名的取用改成 `core.stage_name(stage)` / `core.stage_why(stage)`；
- **保持 `STAGES` 里 `level` 的语义**：现渲染用 `_lvl` 但实际未使用（`name, why, _lvl = STAGES[...]`），所以直接不取即可，输出不变；
- `load_rows()` 可以选择保留原地解析（它只取 7 个字段），但更干净的做法是改用 `core.load_lessons(REPO)` 并映射字段：`summary` 字段本来就是同一份 `> **一句话**`（build_map 从 fm 取 `summary`，而 frontmatter 里没有 `summary` 键 → 现有实现取到的是空串；迁移时**必须保持空串行为**，即 `"summary": ""`，否则标签属性会变化）。

**步骤 3：对比字节**

```bash
python scripts/build_map.py --stdout > /tmp/map-after.html
diff /tmp/map-before.html /tmp/map-after.html && echo "行为不变 ✅"
python scripts/build_map.py     # 重新生成 docs/learning-map.html
git diff --stat docs/learning-map.html
```

期望：
- `diff` 无输出，打印 `行为不变 ✅`；
- `git diff --stat docs/learning-map.html` 空（内容没变）。

如果 diff 有输出：**要么改回实现的语义，要么承认这是有意的行为改进并在提交信息里写清楚**——两者都行，但不许「不知道为什么会不一样」。

**步骤 4：跑全量检查**

```bash
python scripts/check.py
```

期望：`全部通过：5 项检查全绿。`

**步骤 5：提交**

```bash
git add scripts/build_map.py
git commit -m "refactor: build_map 复用 tutorial_core（输出字节不变）"
```

---

## 5. 端到端验收

全部任务完成后，按顺序执行：

```bash
python scripts/check.py
```

期望：

```
=== 汇总 ===
  ✓ 内容门禁 verify.py
  ✓ 索引同步 build_index.py
  ✓ Python 单元测试
  ✓ 前端单元测试 node --test
  ✓ 站点构建自检 build_site.py --check

全部通过：5 项检查全绿。
```

```bash
python scripts/build_site.py
```

期望：

```
站点自检通过：32 课 / 39 页 / 51 文件 / 1200 KB（出处基线 hermes v0.21.3）
```

```bash
python scripts/serve.py --open
```

在浏览器里走一遍 T24「手工验收」的 10 条。

```bash
python scripts/journal.py commit --kind release --title "教程站：交互前端 + 快速部署" \
    --scope web,site \
    --summary "新增静态站点（按阶段浏览/全文搜索/进度打卡/出处徽标）+ 5 种部署方式 + 全量检查命令" \
    --learned "中文标题不能依赖 markdown 的 toc 扩展（slugify 会吞掉中文）；静态站点的自检必须落到链接层面"
git tag -a v1.1-web -m "教程站：可交互前端 + 快速部署"
```

最后确认工作区干净：

```bash
git status --short      # 期望：无输出（site/ 被忽略，不是未跟踪文件）
```

---

## 6. 风险、权衡与待定问题

**R1 新增了两个 Python 依赖（Markdown）。** 取舍：浏览器端渲染（vendored marked.js）能省掉这个依赖，但产物就不再是「真 HTML」—— 关掉 JS 只能看到空白，站内链接、出处徽标都没法用脚本自检，而这套仓库的核心卖点恰恰是「用脚本自检」。选择「构建期渲染」。缓解：依赖都是纯 Python 无编译，且已写进 `requirements.txt` 与部署文档。

**R2 `site/` 不进 git。** 好处：课程改动不会产生几 MB 的 HTML diff，符合「单一内容源」。代价：想手工部署的人必须先跑一次构建（一条命令）。若以后需要「push 即上线、托管方不跑构建」的场景，再考虑加一个把 `site/` 提交到 `gh-pages` 分支的工作流（GitHub Actions 可无 checkout 主仓推送）——现在不做（YAGNI）。

**R3 `data/search.json` 约 450KB。** 只在用户第一次打开搜索面板时按需下载，且 nginx/Netlify 都会 gzip（实际传输约 120KB）。若以后课量到 100+，改成按阶段分片。

**R4 进度存在浏览器本地。** 换浏览器/换机器就看不到自己的勾。刻意如此：站点是公开静态托管时，任何「服务端记录进度」都需要账号体系，超出当前目标。导出/导入 JSON 覆盖了「换机器」这个真实需求，且格式与 `python scripts/progress.py` 的 `.state.json` 完全一致。

**R5 前端交互层没有自动化测试。** `app.js` 只有浏览器行为（点击、滚动、剪贴板），本仓库不引入 Playwright 之类的重型依赖。缓解：静态部分（搜索、进度、分词、目录）全是纯函数并被 28 条 `node --test` 覆盖；DOM 胶水层靠 T24 的 10 条手工验收清单，并且**任何一处 JS 失效都不会白屏**（静态 HTML 已能读全文）。

**R6 Docker 与 GitHub Pages 在本机无法验证。** 本机没有 docker、没有 git remote。处置：配置照写、在 `docs/deploy.md` 里显式标注「未在真实环境验证」、`journal` 里如实记录。**不要**在提交信息或文档里声称它们验证过。

**R7 链接自检只覆盖站内相对链接。** 外部官方 URL 是否 200 由 `sync_sources.py --check` 那一套负责（它检查快照哈希），本站不做外链存活探测（会很慢且被限流）。取舍已记在此处。

**待定问题（实施前或实施中需要用户拍板，未拍板就用默认值）：**

1. **`repo_url` 留空还是填上？** 默认留空（页脚不显示「在 GitHub 上查看仓库」）。若用户已有远端仓库，把 `site.json` 的 `repo_url` 填成 `https://github.com/<owner>/HermesUsage`，并考虑把课程里 `[.hermes.md](../../.hermes.md)` 这类链接改成指向站内规范页（当前已自动改写到 `repo/hermes-md.html`）。
2. **是否公开部署？** 部署到 GitHub Pages/Netlify 意味着站点可被搜索引擎收录。默认：只做本地预览 + 提供配置，不代用户发布。
3. **练习打卡（`- [ ]` 可点击）要不要现在做？** 默认不做（现在是只读方框，已列入 ROADMAP 的 ⬜）。
4. **要不要保留 `docs/learning-map.html` 这个桌面端行内部件？** 默认保留（它服务于 Hermes 桌面应用里的对话场景，与站点受众不同）；两者共享 `tutorial_core` 数据源，不再各自解析。

---

## 7. 明确不做（YAGNI 边界）

- ❌ 不引入 React/Vue/Vite/Astro/VitePress（多一个工具链就多一处漂移，而需求只是「看课 + 搜索 + 打勾」）。
- ❌ 不做账号、评论、收藏、学习统计上报（与「不收集用户数据」冲突，且需要后端）。
- ❌ 不做语法高亮（要引 Pygments 或客户端高亮库；当前只有 9 种语言的代码块，等宽字体 + 边框够读）。
- ❌ 不改 `scripts/verify.py` 的 11 条规则（站点不变量由 `build_site.py --check` 承担；verify 保持「不装 Markdown 也能跑」的零依赖特性）。
- ❌ 不做 i18n / 英文版（教程正文本身就是中文教学目标）。
- ❌ 不做 service worker / 离线 PWA（`site/` 本来就是静态文件，浏览器缓存已够用）。

---

## 附录 A：规划阶段用过的一次性检查脚本

用于确认「33 个课程文件在代码围栏与行内反引号之外没有裸 HTML 标签」（结论：0 处，正文可安全渲染）：

```bash
python - <<'PY'
import re, pathlib
bad = []
for p in sorted(pathlib.Path("lessons").rglob("*.md")):
    text = p.read_text(encoding="utf-8")
    in_fence = False
    for i, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = re.sub(r"`[^`]*`", "", line)
        stripped = re.sub(r"<!--.*?-->", "", stripped)
        if re.search(r"<[a-zA-Z][a-zA-Z0-9_:-]*", stripped):
            bad.append((p.as_posix(), i, stripped.strip()[:100]))
print("裸尖括号命中：", len(bad))
for b in bad:
    print(" ", b)
PY
```

同一逻辑已被固化成常驻测试（T13 的 `TestLessonContentIsRenderable`），所以这个脚本用完即可丢。

## 附录 B：命令速查（实施后用得到的全部命令）

```bash
# 构建与预览
python scripts/build_site.py                 # → site/
python scripts/build_site.py --check         # 临时目录构建 + 站内链接自检
python scripts/serve.py --open               # 构建并预览 http://127.0.0.1:8000/
python scripts/check.py                      # 门禁 + Python 单测 + 前端单测 + 站点自检

# 分项
python scripts/verify.py                     # 内容门禁（11 条规则）
python -m unittest discover -s tests -t . -p "test_*.py" -v
node --test "tests/js/*.test.js"

# 容器与归档
docker compose up -d --build                 # 需要 docker（本机没有）
python scripts/journal.py commit --kind release --title "…" --scope web,site
git tag -a v1.1-web -m "教程站：可交互前端 + 快速部署"
```

---

## 附录 C：实施修订记录（实测回填，2026-09-16）

计划初稿在真实环境里跑过之后，有三处必须修正 —— 后续任务直接按修正后的版本做：

1. **`tests/__init__.py` 是必需的**（初稿漏了）。`unittest discover -s tests -t .`
   要求起始目录是可导入的包，缺它直接 `ImportError: Start directory is not importable`，
   一条测试也跑不到。已创建（内容是说明性 docstring），不要删。
2. **`node --test tests/js` 在本机跑不通**。Node ≥ 22 起，`--test` 的位置参数按
   glob(7) 解释，**不再展开目录**（实测 Node v24：`Error: Cannot find module ...\tests\js`）。
   全仓库统一改用带引号的形式：`node --test "tests/js/*.test.js"`。
   受影响处已全部改好：`package.json` 的 `test` 脚本、T26 `check.py` 的 argv、附录 B。
3. **前端测试的累计计数以实测为准**：4（util）→ 14（+search 10）→ 20（+progress 6）→
   27（+storage 7）→ 31（+toc 4）。另外 T20 初稿里 `tokenize("Skills 与 记忆")` 的期望
   与它相邻那条「单字中文也保留」的测试自相矛盾；实现（保留单字）是对的，
   已把断言改成 `["skills", "与", "记忆"]`。

另记：数据层实施时，T4 与 T7 的测试从第一跑就是绿的（它们依赖的函数在 T3/T5 已随计划一次写完）。
这不是问题，但按 TDD 纪律需要知道 —— 只有「测试从没见过红」才需要停下来检查。

4. **`stats["pages"]` 实测是 40，不是 T14/T17 里写的 39**：32 课程页 + index.html + 6 规范页 + 404.html
   都是 `.html`。文件数也是 52（40 html + 4 json + assets 7 + .nojekyll），体积 1589 KB。
   断言要写「组成」（课程页 32、规范页 == len(repo_docs)、首页与 404 存在），不要抄魔法数字。
5. **T16 的 `render_repo_doc` 有两个真 bug，会让 `--check` 报 200 条死链**（第一次实测就是
   `站内链接自检失败：200 条`），已修：
   - 规范页侧栏误用了 `link_sibling`，32 条课程链接全指向 `site/repo/L01-….html`
     （6 个规范页 × 32 = 192 条）。需要 `link_from_repo()` → `../lessons/<page>`。
   - 规范页正文里的仓库相对链接（`scripts/verify.py`、`.hermes/skills/`、`ROADMAP.md`…）原样渲染即 404。
     需要 `rewrite_repo_doc_links()`：登记过的仓库文档 → 对应规范页；课程 md → 课程页；
     其余（脚本/目录）在 `repo_url` 为空时去掉 href 只留文字，`repo_url` 有值时指向 GitHub。
   `check_links()` 保持严格，**不给链接加豁免**。
6. **样式与模板的交互坑（无浏览器时看不见）**：`layout.html` 里搜索面板用 `<div class="palette" hidden>`，
   而 CSS 给 `.palette` 设了 `display: flex` —— 这会盖掉 `hidden` 自带的 `display: none`，
   结果是**一进页面搜索面板就摊在全屏上**。已加一条 `[hidden] { display: none !important; }` 兜住。
   凡是「用 `hidden` 属性做显隐」的元素，CSS 里都不许再声明 display。
