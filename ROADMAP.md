# 学习路线图 / Roadmap

> 两条路线在这一份文件里交汇：
> **学习者的路线**（✅ 打勾 → 形成能力）和 **维护者的路线**（⬜ 待建 → 形成内容）。
> 每门课的状态只有四种：`✅ 已就绪` / `🚧 编写中` / `⬜ 待建` / `🧪 待验证`。

## 怎么用

```bash
python scripts/progress.py        # 我的学习进度（个人状态，不进 git）
python scripts/progress.py next   # 下一课学什么
```

维护者视角：`⬜` 的课就是工作队列。开工前先读 [`.hermes.md`](.hermes.md)，
严格照 [`templates/lesson.md`](templates/lesson.md) 的 8 小节写，写完跑
`python scripts/build_index.py && python scripts/verify.py`。

---

## 阶段 0 · 认识 Hermes（先建立正确的心智模型）

**目标**：知道 Hermes 是什么、不是什麽；能自己装好并跑通一次对话；能说清一次对话内部发生了什么。
**验收**：不看笔记，向别人解释「Hermes 的 agent loop 是什么」。

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L00 | Hermes 是什么：三个心智模型 | 10 | 会用工具的循环 + 技能记忆自改进 + 一个内核多种外壳 |
| ✅ | L01 | 五分钟装好并说第一句话 | 15 | 装、选 provider、跑通一次可验证的对话 |
| ✅ | L02 | 一次对话里到底发生了什么 | 15 | 系统提示 + 历史 + 工具结果的循环 |
| ✅ | L03 | 文件地图：哪个文件管什么 | 15 | SOUL / USER / MEMORY / .hermes.md / config.yaml 各管一件事 |

## 阶段 1 · 会用 Hermes（核心五件事）

**目标**：知道它在跟谁说话（模型）、能做什么（工具）、对话边界在哪（会话）、怎么记住你（记忆）、
你怎么给它定规矩（上下文文件）、怎么让它变强（技能）。
**验收**：能独立给一个项目配好 `.hermes.md` + 装/写一个技能 + 让它跨会话记住一条约定。

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L10 | 模型与 Provider：你到底在跟谁说话 | 20 | 模型/供应商/环境变量/最小 64K 上下文 |
| ✅ | L11 | 工具与工具集：它到底能做什么 | 20 | toolset 是权限边界，`hermes tools` 是开关 |
| ✅ | L12 | 会话与斜杠命令：一次对话的边界 | 20 | `/new` `/compress` `/resume` 与 session 存储 |
| ✅ | L13 | 记忆系统：它怎么记住你 | 20 | MEMORY.md / USER.md / 冻结快照 / session_search |
| ✅ | L14 | 上下文文件：你怎么给它下规矩 | 20 | `.hermes.md` vs `AGENTS.md` vs SOUL.md，@引用 |
| ✅ | L15 | 技能系统：让它学会你的活法 | 25 | 渐进式披露、frontmatter、自建技能 |

## 阶段 2 · 日常威力（把 agent 当主力用）

**目标**：从「能对话」升级到「能把活干完」，并且知道自己随时能撤回。

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L20 | 提问与指挥：把模糊需求变成可验证任务 | 20 | 判据式提问、让它自证 |
| ✅ | L21 | 让它动真格：终端 / 文件 / 浏览器 / 网页 | 25 | 各工具的边界与组合拳 |
| ✅ | L22 | 委派：delegate_task 并行子代理 | 20 | 什么该自己干、什么该外包 |
| ✅ | L23 | 定时与循环：cron / loops / goals | 25 | 无人值守的三种形态 |
| ✅ | L24 | 检查点与回滚：干坏事了怎么办 | 15 | checkpoints + git 双保险 |
| ✅ | L25 | 配方库：20 个可直接抄的工作流 | 30 | 抄完就能用 |

## 阶段 3 · 自动化与多代理（进阶）

**目标**：让 Hermes 在你不在的时候干活，并被外部事件驱动。

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L30 | 钩子 hooks：在生命周期节点插入你的代码 | 20 | 可观测与可拦阻 |
| ✅ | L31 | 事件驱动：webhooks 让外部事件触发 Hermes | 20 | GitHub push → agent 干活 |
| ✅ | L32 | 多代理：kanban 看板与 bot mode | 25 | 多个 profile 协作 |
| ✅ | L33 | 网关：把 Hermes 变成机器人 | 25 | 21+ 消息平台，同一内核 |
| ✅ | L34 | 无人值守流水线：cron + webhook + skill | 30 | 把零件拼成产线 |

## 阶段 4 · 扩展与改造（进阶）

**目标**：Hermes 不够用时，你自己给它加能力（而不是等官方）。

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L40 | 写一个技能：SKILL.md 规范与实战 | 25 | 最低成本的扩展 |
| ✅ | L41 | 写一个插件：工具 / 钩子 / 中间件 | 30 | 真正扩展内核的方式 |
| ✅ | L42 | 桌面插件 / TUI 部件 / 皮肤 | 25 | 改外观与交互 |
| ✅ | L43 | MCP 集成：接上外部工具服务器 | 25 | 零核心足迹地接工具 |
| ✅ | L44 | 当作库来用：Python / ACP / API Server | 25 | 把 Hermes 嵌进你的程序 |

## 阶段 5 · 运维与安全（进阶）

**目标**：敢把它放在自己每天在用的机器上。

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L50 | 安全模型与审批：危险命令怎么拦住 | 20 | 默认值与收紧方式 |
| ✅ | L51 | 密钥、凭证池与多 profile | 20 | `.env` 只放密钥 + 轮换 + 隔离 |
| ✅ | L52 | 成本与缓存：prompt caching 心法 | 20 | 为什么中途改工具集很贵 |
| ✅ | L53 | 排障手册：它变笨了 / 工具不见了 | 25 | 官方诊断清单本土化 |
| ✅ | L54 | 升级、备份与迁移 | 15 | 敢升、能退 |

## 毕业项目 · Capstone

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L90 | 毕业项目：自动化一件你真正在做的活 | 60 | 从需求到无人值守 |

---

## 里程碑（git tag）

| tag | 含义 | 状态 |
|---|---|---|
| `v0.1-foundation` | 骨架 + 出处体系 + 门禁脚本 | ✅ |
| `v0.2-orient` | 阶段 0 全部就绪 | ✅ |
| `v0.3-core` | 阶段 1 全部就绪（核心五件事） | ✅ |
| `v1.0-tutorial` | 阶段 0-5 + 毕业项目全部就绪 | ✅ |

## 维护待办（内容层）

- [ ] 把带「官方文档表述（未本机实测）」说明的段落补全（实测当前只剩一处：`lessons/04-extend/L44-as-a-library.md:102` 的 API Server 启动横幅；L33 已无此标记）
- [ ] 给 `sources/registry.yaml` 补登记 `browser` / `web-search` 两页，让 L21 的浏览器与检索内容有更精确的出处（当前借用 tools-reference）
- [ ] 官方文档漂移后：`python scripts/sync_sources.py` 并复核受影响的课程表述
- [ ] 阶段完成后补一个「常见错误合集」页（跨课程的坑聚合）

## 维护待办（系统层）

- [x] 给 `scripts/verify.py` 加 CI（已由 `.github/workflows/ci.yml` 落地：push / PR 跑 `python scripts/check.py`，全绿才允许合并）
- [ ] journal 自动归档：`hermes cron` 定时跑 `scripts/journal.py digest`
- [ ] 用 Graphviz / 手绘风格 SVG 替换 README 的 ASCII 路线图

## 站点（前端）

课程除了 Markdown 原文，还有一份静态站点。构建与检查：

```bash
python scripts/build_site.py     # 产出 site/（已 gitignore）
python scripts/serve.py --open   # 本地预览 http://127.0.0.1:8000/
python scripts/check.py          # 全量检查，含站点构建自检与站内链接检查
```

| 能力 | 状态 | 位置 |
|---|---|---|
| 按阶段浏览 + 进度打卡 | ✅ | `web/assets/app.js` + `site/index.html` |
| 全站搜索（中文二字切分） | ✅ | `web/assets/lib/search.js` |
| `src:` 出处徽标（悬停看版本与哈希） | ✅ | `scripts/site_render.py` |
| 本地预览 / Docker / Netlify / Vercel / Pages | ✅ | `docs/deploy.md` |
| 练习打卡（`- [ ]` 可点击并保存） | ⬜ | 现在是只读方框，交互待做 |
| 学习地图与站点合并（去掉重复的两套渲染） | ⬜ | `scripts/build_map.py` 仍是独立渲染 |

---

## 下一阶段路线图（v1.2 → v2.0）

现状（2026-09-16 实测）：内容 32 课全部就绪、门禁 11 条 + `check.py` 五项、CI 与 Pages 双绿、
站点已公开。下面各条**都必须能用一条命令验收**，否则不许进这个列表。

### v1.2 · 让公开站点能被搜到、能被分享（约半天，优先做）

站点刚公开，但没有任何给搜索引擎和社交平台看的元信息。

- [x] `build_site.py` 产出 `sitemap.xml`（39 条 = 首页 + 32 课 + 6 规范页，404 排除）与 `robots.txt`
- [x] 每个页面加 `<link rel="canonical">`；每页加 5 个 og 标签（`og:site_name` / `og:type` / `og:title` / `og:description` / `og:url`）
- [x] 跳转到正文的 skip link（`#main` 已存在），补 `aria-label` 到搜索按钮
- [x] 把 4 个 tag 推到远端、给仓库填 Website / Topics、建 `v1.1-web` Release（已完成）

**验收**（已全部通过）：`python scripts/build_site.py --check` 断言 sitemap 条目数 == 产物页数（39 = 40 页 - 404）、
每个页面恰好 5 个 `og:` 标签且都有 canonical；`git ls-remote --tags origin` 出现 4 个 tag；线上 `curl -sI .../sitemap.xml` → 200。
完成于 2026-09-16，tag `v1.2-seo`；构建产物 52 → 54 文件（+`sitemap.xml`、+`robots.txt`），
Python 测试 45 → 59 条。

### v1.3 · 站点交互补齐（约一天）

- [ ] 练习打卡可点击并保存（独立存储键 `hermes-usage:exercises:v1`，与「课程完成」分开计）
- [ ] 学习地图并入站点：新增 `/map.html`，与桌面部件 `docs/learning-map.html` 共享同一个渲染函数
      （现在两套渲染各写一遍）
- [ ] 课间键盘导航（`←/→` 上一课下一课），搜索面板内 `Tab` 循环

**验收**：`python scripts/check.py` 全绿；新增纯函数（练习状态、课间导航）有 `node --test` 覆盖；
浏览器手测清单从 10 条扩到 13 条（练习勾选、地图页、键盘导航）。

### v1.4 · 内容可考证的最后一块（约一天）

- [ ] `sources/registry.yaml` 补登记两页（官方文档确实有：`user-guide/features/browser.md`、
      `user-guide/features/web-search.md`）→ `sync_sources.py` → 更新 L21 的 `sources:` 并复核表述
      （L21 现在借的是 `tools-reference`，不够精确）
- [ ] L44 的「官方文档表述（非本机实测）」段落：本机复现，或在文中给出「为什么不复现 + 复现命令」
- [ ] 新增「常见错误合集」：构建期聚合 32 课的「常见坑」表格 → 站点 `/pitfalls.html`

**验收**：`sync_sources.py --check` 无漂移且出处从 89 条增加到 91 条；`verify.py` 全绿；
`/pitfalls.html` 的条目数 == 各课坑表行数之和，每行带课号链接。

### v1.5 · 自维护自动化（约半天）

- [ ] journal 自动归档：`hermes cron` 启用 `scripts/journal.py autocommit`（脚本已有，只是没启用）
- [ ] 官方文档漂移哨兵：定时 `sync_sources.py --check`，发现漂移自动开 GitHub issue
- [ ] 外链存活检测 `scripts/check_links.py --external`（对 89 条官方 URL 低频探测，不进 CI 以免被限流）

**验收**：`hermes cron list` 显示任务为启用；手动制造一次文档漂移能自动开出 issue 并把链接打出来。

### v2.0 · 让「学过」变成可交付（按需启动）

- [ ] 学习报告导出：32 课完成状态 + 练习勾选 + 时间线 → `report.md`（可反向被 `progress.py` 校验）
- [ ] 单文件离线版 `hermes-usage-offline.html`（内联 CSS/JS + 全部课程，双击即可读，适合发给不会 git 的人）

**验收**：离线版 < 2 MB 且断网可读；`report.md` 里的完成课数与 `progress/.state.json` 一致。

### 已知欠账（继续如实标注，不许写成「已验证」）

- Docker / Netlify / Vercel 三条部署路径**未在真实环境验证**（本机无 docker、无那两家账号）
- `site/` 产物目前没有 SEO 元信息（v1.2 的目标）
