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
| ✅ | L55 | 换一台电脑：把记忆、技能和会话带走 | 25 | 整机 `backup` / 单 profile 导出 / 多机共用一份 |
| ✅ | L56 | 公司机与个人机：一个内核，两个身份 | 30 | profile 隔离 / 收紧清单 / 能带回家的只有技能与人格 |

## 阶段 6 · 真实工作流案例（进阶）

**目标**：把前面学的拼成**能交付的活** —— 每课一个真实场景，产出可以被别人核对。

| 状态 | 课 | 标题 | 耗时 | 一句话 |
|---|---|---|---|---|
| ✅ | L60 | 先把目录看清楚：只读侦察与可核对清单 | 30 | — |
| ✅ | L61 | 不可逆的批量操作怎么安全做 | 35 | — |
| ✅ | L62 | 盯一件外部变化，只在变的时候通知你 | 35 | — |
| ✅ | L63 | 把一次调研变成一份带出处的报告 | 40 | — |
| ✅ | L64 | 把这次劳动固化成技能，下次一句话复用 | 30 | — |
| ✅ | L65 | 并行委派一批活，并验收子代理的产物 | 40 | — |
| ✅ | L66 | 给自己的项目发第一个 release | 35 | 推 tag → CI 建 release：五个动词、确定性资产、不可变发布与对账 |

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
| `v1.1-web` | 可交互静态站点上线（搜索/进度/出处徽标） | ✅ |
| `v1.2-seo` | 站点可达性：sitemap / robots / canonical / og / skip-link | ✅ |
| `v1.3-site` | 练习打卡 / 学习地图 / 键盘导航 | ✅ |
| `v1.4-content` | 出处 89→91、L44 本机复现、`/pitfalls.html` | ✅ |
| `v1.5-auto` | 外链存活检测 + 文档漂移哨兵 | ✅ |
| `v2.0-deliverable` | 学习报告导出 + 单文件离线版 | ✅ |
| `v2.1-ops` | 定时任务真跑起来（cron_ctl 开关）+ Docker 交 CI 验证 + README 路线图 SVG | ✅ |
| `v3.0-cases` | 阶段 6 真实工作流案例（38 课 / 8 阶段）+ 漂移哨兵进 CI + 自动归档在途闸门 | ✅ |
| `v3.1-ui` | 设计对比页（10 方案 × 10 维度等权平均）+ 语义 token 视觉系统 + 主题三态 | ✅ |
| `v3.3-topbar` | 顶栏 GitHub 入口（内联 SVG 标识，新标签页打开）+ 480px 以下收进度胶囊 | ✅ |
| `v3.4-release` | 发布体系：14 个 tag 全部有 release（确定性资产 + CHANGELOG + 不可变发布 + CI 自动发版） | ✅ |
| `v3.5-release` | 页脚显示当前版本（构建期从 CHANGELOG 现读）+ L66《给自己的项目发第一个 release》+ L00 命令的 shell 约定修复（41 课 / 95 出处） | ✅ |

## 维护待办（内容层）

- [x] 把带「官方文档表述（未本机实测）」说明的段落补全 —— 已完成，见 v1.4（L44 的 API Server 段已本机复现）
- [x] 给 `sources/registry.yaml` 补登记 `browser` / `web-search` —— 已完成，见 v1.4（出处 89 → 91）
> **常驻流程（不是待办）**：官方文档变了就跑 `python scripts/sync_sources.py` 刷新快照，并复核受影响课程的表述；
> **判据是「读者装得到的那个 release」**（见下面两小节）。哨兵（本机 cron + CI 的 `.github/workflows/drift.yml`）
> **2026-09-20 换过判据**：以前比「上游/本机 main 的 docs vs 快照」—— main 永远领先于最新 release，
> 所以天天报几十页；现在只问一句 **「上游有没有发比基线更新的 release？」**
> （`scripts/release_probe.py` 的 watch 模式；基线写在 `sources/registry.yaml` 的 `# baseline-release:`）。
> 历史：**2026-09-16 首次运行即发现 37 页正文已变**（基线 `05fac10a` → 上游 `816cb379`），见 issue #1，
> **2026-09-17 首次复核并关闭**（上游已走到 `36842e63`：39 页 / 486 增 94 删）；**2026-09-18 CI 又开
> issue #2（45 项），2026-09-20 第二次复核并关闭** —— 结论见下一小节：86 页漂移里只有 1 处该改课程。

### 官方文档漂移复核（2026-09-17 首次，issue #1 已关闭）

判据只有一条：**那个行为在本机装的 v0.21.3 源码里有没有**。有 → 快照过时，改课程；没有 → 上游在写
**未发布**内容，只登记，等下一个 release 再对照（版本对照看 `hermes --version` 的 `local …` 与
`upstream …` 两行；本机 v0.21.3 就是当前最新 release，快照 `05fac10a` 即它的文档提交）。

| 桶 | 页数 | 内容与处理 |
|---|---|---|
| 与本机行为不符 → **已改课程** | 2 | `delegation` → **L22**（450s / 1200s 失速线；本机 `tools/delegate_tool.py:77-78` + `delegate_tool_child_run.py` 的 tick）；`bot-mode` → **L32**（`message_agent` 的双条件门控；本机 `tools/bot_mode_probe.py::is_bot_mode_managed`，实测：只有裸 `profile.yaml` → `False`，任一 profile 写空 `ui_meta: {hermes-bots: {}}` → `True`） |
| 判定为**上游未发布**（本机无对应实现/常量） | 15 | `security`（`security.fake_ip_ranges` —— 正好治本机 Clash fake-IP 那个坑，但 v0.21.3 里 0 命中）、`context-files` + `prompt-assembly`（`SOUL.md` 命中注入模式只警告不阻断；本机 `_scan_context_content` 无 `user_authored` 参数）、`cron`（`[CRON_FAILURE]` 首行标记）、`cli-commands`（`--usage-file` 的 `total_including_auxiliary` / `turn_exit_reason`）、`programmatic`（`session.resume` 的 `inflight`）、`profiles` + `faq`（「裸目录不算 profile」的身份文件规则；本机 `_iter_named_profile_dirs` 只按目录名与墓碑过滤）、`updating`（`hermes update --no-gateway-restart`）、`credential-pools`（Anthropic 429 按模型冷却）、`kanban`（`crashed` 事件新增 `worker_output`）、`desktop` + `skills` + `plugins` + `desktop-plugin-sdk`（桌面端 Capabilities/Browse 改版、CDN 快照 `api/skills.json`、`hermes://` 安装链接） |
| 其余：已发布但课程未涉及，或纯措辞 | 22 | 例：`browser`（关浏览器的硬性要求**所有平台**都成立，课程没写「仅 Windows」，无需改）、`configuration` + `env-vars`（`UPPER_SNAKE` 一律进 `.env` + 写入黑名单，本机 `hermes_cli/config_env_routing.py`）、`mcp` + `mcp-config`（`lazy` 启动，本机 `tools/mcp_tool_discovery.py:111`）、`heartbeat`（网关侧 `NO_REPLY`/`[SILENT]` 静默，本机 `gateway/stream_consumer.py:556`）、`compression` + `prompt-cache`、`hooks`、`providers`、`sessions`、`slash-commands`、`web-search`、`gateway-messaging`、`goals`、`loops`、`api-server`、`cli`、`curator`、`session-storage`、`fallback-providers`、`tools-reference` |

**诚实边界**：判定粒度是「页面级 + 关键句」——第 3 桶里 `compression`/`prompt-cache` 的冷却下限、
`hooks` 的重复失败只报一次、`cli-commands` 的一次性运行退出码表只做了「课程是否涉及」的检查，
没有逐句定版。重放这次复核的方法：稀疏克隆上游 `website/docs` → 逐页按 LF 归一化算 `sha256` 与
`sources/citations.yaml` 比对 → 与 `sources/cache/<id>.md` 做 `difflib.unified_diff`（构建期产物
不进仓库，39 页 condensed diff 约 68 KB）。

### 官方文档漂移复核（2026-09-20 第二次，issue #2 已关闭）

**这次的前提变了 —— 也是本次最重要的结论**：本机安装树这次跟踪的是 **main**（`3adc1787`，文档
`0818892db3`，2026-09-19），比最新 release **`v2026.9.14`** 新若干天。于是「本机源码里有」不再等于
「读者装得到」——**判据必须换成 release tag**（`raw.githubusercontent.com/NousResearch/hermes-agent/v<tag>/<path>`
逐文件 grep），否则会把未发布的行为写进课程。上次复核时本机恰好就是 release 状态，所以没暴露这个坑。

**漂移规模与三分桶**（86 页，其中被课程引用 82 页）：

| 桶 | 页数 | 处理 |
|---|---|---|
| 纯链接重写（`](/user-guide/x)` → `](../user-guide/x.md)`） | 27 | 逐行验过：只有链接目标在变，与课程无关，不动 |
| 正文真变化 | 59 | 其中被课程引用 51 页、未被引用 8 页 |
| ↳ 与 release 行为不符 → **改课程** | **1** | **L14**：原文「所有上下文文件…是**内容**被拦，不是整个文件被拦」是错的 —— release 的 `agent/prompt_builder.py` 与快照 `context-files.md:181` 都写明命中即**整份**文件被顶掉（`[BLOCKED: … Content not loaded.]`）。已改成「整份失效 + `/context` 里看到的字样」（`updated: 2026-09-20`） |
| ↳ 上游已写、release 里**还**没有 → 只登记 | 14 条 | 见下表，等下一个 release 一次性刷快照 + 改课 |
| ↳ 课程未涉及 / 纯措辞与示例 | 其余 | 不动 |

**待下一个 release 对照的 14 条**（判据 = release tag 的源码/文档里 grep 不到 → 按「未发布」处理；
**第 15-19 条见下一小节的审计表** —— 那批是「课程已经在讲、但 release 里还没有」，处置相反：已从课程里删掉）：

> **可执行版**：`python scripts/pending_probe.py` —— 这两张表（14 + 5 = 19 条）都写进了
> `scripts/pending_probe.py` 的 `ITEMS` 表，上游一发新 release 跑一次就知道哪几条落地了
> （`--tag main` 是自检对照：对着 main 应该 19 条全落地）。CI 的 `drift.yml` 里也挂了这一步。

| # | 页面 | 上游写了什么 | release 探针结果（`v2026.9.14`） |
|---|---|---|---|
| 1 | `profiles` | OAuth 登录「从不复制」+ 新增「Every profile owns its credentials」：命名 profile 只认自己的 `auth.json`，不再回落读根库 | `hermes_cli/auth.py` 里 `111724` **0 命中**；快照仍写 `shared, not copied` → 未发布 |
| 2 | `multi-profile-gateways` | `gateway.multiplex_profiles` 默认改为 `true`（未设置时由启动预检决定） | release 里仍是 `Optional[bool] = None` + 文档写 `off by default` → 未发布 |
| 3 | `bot-mode` | 新建 Bot 默认「复制主 profile 的静态 API key」，OAuth 不复制 | release 无 `mirror_credentials`；快照写 `Shared keys … shares one OAuth/token pool` → 未发布 |
| 4 | `compression` | `compression.threshold_tokens` 默认从 `None` 改成 `256000`（触发点取比例与它的**较低**者） | release 默认值是 **`None`**（纯比例），快照第 388 行的「always `threshold × context_length`」对 release 仍然成立 → 机制没变、**默认值变了** |
| 5 | `cron` | 同一错误签名不再每次 ping：`cron.failure_repeat_alert_hours`（默认 6h）到期补一条提醒，`ack` 变永久静音 | release 里 `failure_repeat_alert_hours` / `DEFAULT_FAILURE_REPEAT_ALERT_HOURS` **0 命中**（有 `withheld` 逻辑但没有这个配置键） → 未发布 |
| 6 | `cron` | `hermes cron doctor` 把「历史迟到 / 补跑」也算 finding，一次成功补跑不会立刻清告警 | 快照无此句 → 未发布 |
| 7 | `delegation` | 失速改为**中断 + 放弃等待**（`status: "timeout"`），一次性运行同样生效 | 450s/1200s 阈值常量 release 里已有（`delegate_tool.py`），但处置方式改成中断是本版新增 → 未发布 |
| 8 | `delegation` | `/stop` 之后被停子代理**必定**带着最后一段产出回到对话里 | release 的 `async_delegation.py:952` 已写 `status='interrupted'`，但快照原话是「因为父代理也被中断，结果常常到不了用户面前」→ 未发布 |
| 9 | `delegation` | 新增 `delegation.oneshot_max_children`（默认 2） | release **0 命中** → 未发布 |
| 10 | `context-files` | 自己写的 `SOUL.md` 命中只警告、照常加载（`user_authored`）；`/context` 显示 `⚠ … loaded` | release 的 `prompt_builder.py` **0 命中** `user_authored` → 未发布（**「整份被拦」那条是 release 行为，已改课**） |
| 11 | `checkpoints` | 新增「Container Backends」：容器终端后端不拍检查点、`/rollback` 拒绝 diff/恢复 | release **0 命中** `unsupported_backend_reason` → 未发布 |
| 12 | `browser` | 「真 profile 会话前要退出浏览器」从 Windows 专属改成跨平台结论（认证库写锁 + 5 秒预算） | release 里搜不到那条跨平台表述（快照说 macOS/Linux 通常可在浏览器运行时复制） → 未发布 |
| 13 | `env-vars` | 「任何 `UPPER_SNAKE` 名字只进 `.env`、永不写进 `config.yaml`」+ 写入器黑名单 | release 的 `config.py` 已有 env 写入器黑名单，而快照本就写「env 变量进 `.env`、点号路径进 `config.yaml`」→ 只是措辞更硬 → **不动课程** |
| 14 | `pipe-script-output` / `deliverable-mode` | `hermes send` 的 home 解析与 `not configured` 逐文件清单；示例路径 `/tmp/...` → `~/.hermes/cache/scratch/...` | 提示文案与示例路径，不是行为反转 → **不动课程** |

> 过程留痕（值得记）：本次先按「本机 main 源码里有 → 改课程」应用了 20 处改动（覆盖 12 课），
> 随后用 release tag 三路探针逐条核验，**全部回滚**，只留 L14 那一处。教训写进 `.hermes.md` 与
> `source-drift-review` 技能：**先确认本机跟的是 release 还是 main，再决定判据**。

**为什么这次不重刷快照**：`sync_sources.py` 读的是本机安装树（现在是 main），刷下去会把「未发布」的
文档内容变成课程出处，直接违反 R3（读者要能反查到**自己装得到的**版本）。所以基线继续钉在
`05fac10a` / hermes v0.21.3，等下一个 release 出来再一次性刷快照 + 改课。
（哨兵已于同日换成 release 判据 —— 见下面的「这次还发现一个更重要的事实」，所以它不会再天天刷屏。）

**这次还发现一个更重要的事实**：本仓库的快照（`05fac10a`，2026-09-15）是**跟踪 main 的一次提交，
比 `v2026.9.14` 这个 release 还新** —— 与 release tag 的文档逐页比，**95 页里有 48 页不同，
且都是快照那边多出来的正文**（`session-storage` 的家目录隔离一节、`cli` 的 `skills.auto_load` 一节、
`toolsets-reference` 的 `connections` 行…，见 `python scripts/release_probe.py --docs`）。
也就是说 **「快照 == 读者装得到的那个 release」这个假设从来不成立**；`.hermes.md` 原来写的
「出处快照基线：hermes v0.21.3，文档提交 05fac10a」把它当成了 release 的文档，是错的（已改）。
判据因此拆成两条互不替代的问题：

| 问题 | 判据 | 工具 |
|---|---|---|
| 这句话该不该进课程？ | 那个行为在**最新 release** 的源码/文档里有没有 | 按 tag grep（`curl raw.githubusercontent.com/…/v<tag>/<path>`） |
| 快照该不该刷、该不该复核？ | 上游有没有发**比基线更新的 release** | `python scripts/release_probe.py`（watch 模式） |

**落地的四处改动**（都用单测钉住了）：
- 新增 `scripts/release_probe.py`：`--watch` 只做一次 `git ls-remote --tags`（便宜、可每天跑），
  `--docs` 逐页抓 release 的文档比哈希；基线名从 `sources/registry.yaml` 的 `# baseline-release:` 读。
- `scripts/drift_watch.py` 的默认来源从「比 docs 目录」改成「比 release」（`--source tree` 留作调试），
  于是 cron 与 CI 只有在**上游真发新版**时才响；
- `.github/workflows/drift.yml` 不再稀疏克隆上游 docs（少一个失败面），只跑一次 release 比对；
- 基线的 release 名进了 `sources/registry.yaml`（`# baseline-release: v2026.9.14`），复核完要一起更新。

**这次踩到的另一个坑（已修）**：`git ls-remote` 会走本机 git 配置里那个常挂的代理
（`http.proxy=127.0.0.1:7897`）—— 代理端口开着但不响应，于是哨兵随机报「跑不起来」。
`release_probe.py` 现在显式 `git -c http.proxy= -c https.proxy=` 并带重试（连跑三次 0 退出）。

**诚实边界（这一批的）**：定版粒度是「页面级 + 与本课相关的那几句」，不是逐句；59 页里 8 页无课程引用，
只做了「是否与课程有关」的扫描；第 13/14 条是措辞与示例，未逐句定版；release 探针只比了 `v2026.9.14`
这一个 tag，**没有追溯每条改动的引入时间**（所以「未发布」= 「这个 tag 里没有」，不等于「下个 release 一定有」）。

**重放方法**：① `hermes --version` 看本机跟踪的是 release 还是 main；② 逐页按 LF 归一化算 `sha256`
与 `sources/cache/<id>.md` 比对，先剥掉链接重写（把 `](...)` 归一化后再 diff）；③ 对每条「要改课程」
的结论，按 tag 取原始文件 grep 关键符号（`curl -s https://raw.githubusercontent.com/NousResearch/hermes-agent/v<tag>/<path>`），
再拿本机源码交叉验证；④ 产物（逐页 diff、release 探针文件）放 `$LOCALAPPDATA/Temp`，**不进仓库**。

### 审计：课程有没有引用 release 里还没有的行为（2026-09-21）

上一次复核问的是「课程有没有**过时**」；这一次问的是反过来那一半 —— **课程有没有超前**。
起因是发现「快照领先 release」（上一小节）：快照里有 **624 行正文是 release 文档没有的**，
分布在 48 页里，其中 **43 页被课程引用**。如果某句课程正文的依据只存在于这些「快照独有行」里，
那句就在讲读者装不到的版本。

**方法**：5 波子代理逐页判定「课程引用句的依据在 release 版里有没有」→ 我按 `v2026.9.14` 的
**源码**逐条复核（文档缺一句话不等于功能不存在 —— 反过来也一样：文档里的功能可能还没进代码）。

| 桶 | 数量 | 处置 |
|---|---|---|
| 只在 release 之后才有 → **改成 release 行为** | **5 处 / 4 课** | 见下表 |
| 文档后写、但 release 的**代码里已经有** | 5 处（不改课程） | `kanban` 的 `non-spawnable` 桶（tag `hermes_cli/kanban_db.py` 有 `skipped_nonspawnable`）、`security` 引号解析失败也 fail-closed（tag `tools/approval_detection.py:611`）、`browser.use_real_profile`（tag `hermes_cli/config_defaults.py:410`）、`/learn`（tag `hermes_cli/cli_commands_mixin.py:1881`）、委派契约不达标仍是 `completed`（tag `tools/delegate_tool_child_run.py:547` 写 `entry["schema_valid"]`，状态不降级） |
| 快照多出来的内容课程**没引用** | 其余 34 页 | 不动 |

**改成 release 行为的 5 处**（每处都核过「tag 的源码里确实没有」）：

| # | 课 | 原来写的 | tag 源码探针 |
|---|---|---|---|
| 15 | L31 三处（路由字段表 / 常见坑 / 试一试） | `coalesce` 事件去抖、字段与示例 | `gateway/platforms/webhook_coalesce.py` **在 tag 上不存在**，tag 的 `webhook.py` 里 `coalesce` **0 命中**（main 里有 11 处） → 整个功能是后加的 |
| 16 | L50「文件写入」 | 项目 `.env` / `.env.local` / `.envrc`「可以写，但读不回来」 | **反了**：tag 的 `agent/file_safety.py:188` 把它们列进 `_BLOCKED_PROJECT_ENV_BASENAMES`（**写被拦**）；「读拒绝、可写」是 main 的语义（`#45947`） |
| 17 | L50「approvals suggest」 | 「命令里出现的凭据会被打码」 | tag 的 `hermes_cli/approvals_suggest.py` 里 `mask` / `redact` **0 命中**（main 有 5 处） |
| 18 | L51「凭证池」 | 第三条路径「编号环境变量（`OPENROUTER_API_KEY_2`、`_3`…）会被自动发现成池条目」 | tag 的 `agent/credential_pool.py` 里 `numbered` **0 命中**（main 在 2618 行有） |
| 19 | L12 / L14 | `/context` 输出末尾的**逐文件** `Context files` 清单（loaded / truncated / shadowed / blocked / install-tree guard） | tag 的 `gateway/slash_commands_status.py` 里 `Context files` / `shadowed` / `install` 全 **0 命中**；`agent/context_file_sources.py` **在 tag 上不存在**。tag 的 `/context` 只给类别构成表 + 压缩阈值/余量 |

处置写法：**删掉/改成 release 能做的事**，不写「以后会有」的版本注脚（初学者课程里那种注脚只会干扰）；
被删掉的内容登记在这里，**下一个 release 出来时按上表的探针复核一遍，命中就恢复**。

**诚实边界**：定版粒度是「页面级 + 课程实际引用句」；只比了 `v2026.9.14` 一个 tag，没有追溯引入时间
（「release 里没有」= 这个 tag 里没有，不等于下个 release 一定有）；L31 那处删掉了一道**练习题**
（第 2 道，不是末尾）—— 按 `.hermes.md` 的约定，这意味着那一课读者的已存打勾可能错位一位，
所以是**就地替换**成一道 release 可做的幂等重放练习题，而不是删掉留个空位。

- [x] 「常见错误合集」页 —— 已完成，见 v1.4（`/pitfalls.html`，253 行坑表）
- [x] 新增 **L55「换一台电脑：把记忆、技能和会话带走」**（阶段 5，25 分钟）—— 换电脑/多机场景的完整路线：
      习惯层文件清单、`hermes backup`/`import` 整机搬（本机实测 748 → 745 文件）、`hermes profile export`
      的允许清单（**不含 `state.db`**，会话历史不跟着走）、远程 gateway / `skills.external_dirs` /
      外部 memory provider 三条多机路线、以及 `hermes sync`（CLI 有、文档快照未收录，只给实跑输出）。
      出处 **91 → 94**（新增 `profile-commands` / `profile-distributions` / `multi-connection-desktop`），
      课程 38 → **39 课**（2026-09-17）

## 维护待办（系统层）

- [x] **审计：课程里有没有引用「release 里还没有的行为」** —— 已完成（2026-09-21），结论见
      「审计：课程有没有引用 release 里还没有的行为」小节：43 页被引用的快照独有内容里，
      **5 处要改成 release 行为**（已改：L12 / L14 / L31 / L50 ×2 / L51）、5 处经源码复核确认
      release 里就有（不改）、其余 34 页课程没引用。
- [x] 给 `scripts/verify.py` 加 CI（已由 `.github/workflows/ci.yml` 落地：push / PR 跑 `python scripts/check.py`，全绿才允许合并）
- [x] journal 自动归档 —— 已完成，见 v1.5；cron 任务 `c2e058a277da` 每小时跑，**实测 17:00 真的自动提交了一条**（前提是网关在跑，见「需要人工决策」）
- [x] 用 SVG 替换 README 的 ASCII 路线图 —— 已完成：`scripts/build_roadmap_svg.py` 从课程 frontmatter 生成
  `docs/roadmap.svg`（1200×1518 / 22859 字节 / 纯标准库 / 字节可重现），已接进 `check.py`（第 6 项）与 19 条单测。
  **不装 Graphviz**：手绘感用确定性几何实现，零新增依赖
- [x] 哨兵判据换成 release —— 已完成（2026-09-20）：新增 `scripts/release_probe.py`（watch/docs 两模式，
  19 条单测），`drift_watch.py` 默认改走它，CI 的 `drift.yml` 不再克隆上游 docs；基线名在
  `sources/registry.yaml` 的 `# baseline-release:`。**实测**：`drift_watch.py --quiet` 零输出退出 0
  （上游没有更新的 release → 不打扰），模拟「基线 v2026.8.1」时退出 1 并打印复核四步。

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
| 本地预览 / Docker（CI 每次真构建+真访问）/ GitHub Pages | ✅ | `docs/deploy.md` |
| 练习打卡（`- [ ]` 可点击并保存） | ✅ | `web/assets/lib/exercises.js`（v1.3） |
| 学习地图 | ✅ | 站点 `/map.html`（v1.3）；`docs/learning-map.html` 仍在，作为本地单文件版 |
| 设计对比（10 方案 × 10 维度评分矩阵 + 落地令牌表） | ✅ | 站点 `/design.html`（v3.1）；数据源 `scripts/design_matrix.py` |
| 主题三态（跟随系统 / 亮 / 暗）+ 首帧不闪白 | ✅ | `web/partials/layout.html` 的内联主题脚本 + `web/assets/app.js`（v3.1） |
| 前置一键跳转（正文行与页脚都指向原课） | ✅ | `scripts/site_render.py::prereq_links`（v3.2）；门禁 R12 保证写法与 frontmatter 一致 |
| GitHub 入口（顶栏最右一枚标识 + 页脚同一枚，均内联 SVG、新标签页打开） | ✅ | `scripts/build_site.py::github_link` / `github_icon`（v3.3）；模板占位符 `{{github}}` 由 `topbar_values()` 统一供给 |

---

## 阶段路线图（v1.2 → v3.5，全部完成）

现状（2026-09-20 实测）：内容 **41 课**全部就绪、门禁 12 条 + `check.py` 七项（含「变更日志同步」）、
CI / Docker / Pages 三绿、发布体系落地（**15 个 tag 各有 release**，最新 `v3.5-release` 不可变、
页脚显示当前版本）、站点已公开、漂移哨兵判据换成「上游有没有新 release」。
下面各条**都必须能用一条命令验收**，否则不许进这个列表。

### v1.2 · 让公开站点能被搜到、能被分享（约半天，优先做）

站点刚公开，但没有任何给搜索引擎和社交平台看的元信息。

- [x] `build_site.py` 产出 `sitemap.xml`（v1.2 时 39 条；现随课程增至 47 条 = 49 页 − 404 − 离线版）与 `robots.txt`
- [x] 每个页面加 `<link rel="canonical">`；每页加 5 个 og 标签（`og:site_name` / `og:type` / `og:title` / `og:description` / `og:url`）
- [x] 跳转到正文的 skip link（`#main` 已存在），补 `aria-label` 到搜索按钮
- [x] 把 4 个 tag 推到远端、给仓库填 Website / Topics、建 `v1.1-web` Release（已完成）

**验收**（已全部通过）：`python scripts/build_site.py --check` 断言 sitemap 条目数 == 产物页数（39 = 40 页 - 404）、
每个页面恰好 5 个 `og:` 标签且都有 canonical；`git ls-remote --tags origin` 出现 4 个 tag；线上 `curl -sI .../sitemap.xml` → 200。
完成于 2026-09-16，tag `v1.2-seo`；构建产物 52 → 54 文件（+`sitemap.xml`、+`robots.txt`），
Python 测试 45 → 59 条。

### v1.3 · 站点交互补齐（约一天）

- [x] 练习打卡可点击并保存（独立存储键 `hermes-usage:exercises:v1`，与「课程完成」分开计）
- [x] 学习地图并入站点：新增 `/map.html`，与桌面部件共享 `tutorial_core.tutor_prompt()/map_rows()`
      （桌面部件输出保持字节不变）
- [x] 课间键盘导航（`←/→` 上一课下一课），搜索面板内 `Tab` / `Shift+Tab` 环绕且焦点不逸出

**验收**（已全部通过）：`python scripts/check.py` 全绿（Python 80 条 / 前端 58 条）；
浏览器手测清单固化为 [`docs/manual-qa.md`](docs/manual-qa.md) 的 13 条并逐条走通。
完成于 2026-09-16，tag `v1.3-site`。

**已知限制（不静默，写在这里）**：

- 练习按**课内位置**编号（`data-ex`）当存储键：在中间插删一道练习会让读者已存的勾整体错位。
  目前靠「练习只许在末尾追加」这条写作约定兜住（见 `.hermes.md` 坑表）；彻底修法是给题面加指纹，
  对不上就让该勾失效而不是错位——列为后续候选。
- 搜索面板在**零结果**时 `Tab` 仍被拦在面板内（靠 `Esc` 退出）。这是「焦点不逸出」的直接后果，
  对键盘用户比把焦点丢到遮罩后面的内容上更安全。
- 焦点停在练习方框上时按 `←/→` 仍会翻课（方向键在本站统一定义为「课间导航」）。
- 课程正文里若用 `- [x]` 预勾练习，JS 会用存储状态覆盖它；因此**练习一律写成 `- [ ]`**（当前 39 课皆如此）。

### v1.4 · 内容可考证的最后一块（约一天）

- [x] `sources/registry.yaml` 补登记两页（`browser` / `web-search`）→ `sync_sources.py`（89 → 91 条）
      → L21 的 6 处陈述换成精确引用，并按快照校准了 3 句（例：web-search 其实有 keyless 免费额度池）
- [x] L44 的 API Server 段：用**隔离的临时 `HERMES_HOME`** 本机复现（真实横幅 / `/health` / `/v1/models` / 401，
      进程与临时目录已清理），并如实标注官方文档写 `[API Server]`、实跑是 `[Api_Server] (model: …)`
- [x] 新增「常见错误合集」：`tutorial_core.pitfall_rows()` 构建期聚合各课的坑表 → `/pitfalls.html`
      （每行带回原课的 `[[Lxx]]` 链接；新页在根目录，链接映射必须带 `lessons/` 前缀，已有回归测试）

**验收**（已全部通过）：`sync_sources.py --check` 无漂移、出处 89 → **91** 条；`verify.py` 0 错 0 警；
`/pitfalls.html` 数据行 **253**（HTML 与解析层双路对账），263 个课号链接全部带 `lessons/` 前缀（0 处遗漏），
进 sitemap（41 条）；构建产物 41 → **42 页 / 58 文件**。完成于 2026-09-16，tag `v1.4-content`。

顺带修掉一条**登记错误**（外链检测脚本发现）：`prompt-cache` 原先与 `tips` 指向同一个 `guides/tips.md`，
即「提示缓存」借的是 Tips 页。已改为 `developer-guide/context-compression-and-caching.md`
（官方真正讲 prompt caching 的那一页）。L52 的 12 处缓存陈述本来引的就是 `[[src:compression]]`，内容无误。

### v1.5 · 自维护自动化（约半天）

- [x] journal 自动归档：cron 任务 `c2e058a277da`「HermesUsage 自动归档」已注册且 **active**（每小时，最近一次 16:00 ok）
      —— 但**网关没跑时不会自动触发**，需要人工决策，见下方「需要人工决策」
- [x] 官方文档漂移哨兵：`scripts/drift_watch.py`（跑 `--check` → 有漂移就开/跳过 issue；令牌取自 `GITHUB_TOKEN`
      或 Git Credential Manager；`--dry-run` 保证不触网不开 issue，已有测试钉死）
- [x] 外链存活检测 `scripts/check_links_external.py`（四分类 ok/blocked/broken/network，`--retries` 默认 2；
      **不进 CI**，只手动/定时跑）

**验收**（已通过）：`hermes cron list` 显示任务 active；`drift_watch.py --dry-run` 不触网、不开 issue，
实测**全量 91 条官方外链全部 200**（并做了负向对照：造 404 → `broken`、造坏域名 → `network`，
证明检测器真会报错）。新增单元测试 40 条。完成于 2026-09-16，tag `v1.5-auto`。

**已知限制**：本机域名走 Clash fake-IP，TLS 会间歇性抽风（实测同一域名可能连败十几次后自愈），
所以 `network` 结果**不能单次当真**，脚本默认重试 2 次且 `network` 不参与退出码；
这一层用状态码分不出「被墙」与「网络抖动」，是四分类的固有边界。

### v3.1 · 视觉系统与设计对比（约一天）

用户的要求是「按当前市面上最前沿的 UI 方案横向多维度对比，取平均分最高的那套应用到本站，
并把对比信息做成一个能点开的页面」。于是先有**可执行的评分表**，再有样式：

- [x] `scripts/design_matrix.py`：**10 套方案 × 10 个维度**的评分矩阵（唯一数据源）。
      10 个维度是本站真实存在的约束（中文长文阅读 / 信息架构 / 双主题与对比度 / 排版 /
      空间网格 / 动效与反馈 / 无障碍 / 零依赖可移植 / 体积预算 / 许可与可维护性），
      每项 1~5 分、**等权平均**，最高分即赢家。当前结果：**GitHub Primer 4.40**（第二名
      Spectrum 2 与 Carbon 并列 4.30；本站自评改造前 3.50 → 改造后 4.70，标了「参考」不参与排名）。
- [x] `/design.html`：矩阵、平均分条图（构建期 SVG）、每个方案的「赢在哪 / 为什么不能直接搬」、
      从落选方案里各采纳的一条、落地令牌表（18 个 token，值现读）、对比度实测 8 组、改造前后对照、
      17 条官方出处（Material 3 Expressive 与 Apple HIG 两页是渲染后的正文，用真实浏览器读的）。
- [x] `web/assets/app.css` 重写：按赢家的两条硬规则 —— ① 不在组件里写裸值（三层令牌：
      primitive → semantic → component）；② 无障碍当硬约束（焦点环、指针目标 ≥24px、
      `prefers-reduced-motion`、正文对比度 ≥7:1）。另外采纳 Tailwind v4 的 OKLCH/P3 色、
      Carbon 的动效分档、Geist 的留白优先、Radix 的 `:focus-visible` 口径、Ant Design 的中文排版口径。
- [x] 主题三态（跟随系统 / 亮 / 暗）+ 首帧不闪白（内联脚本排在样式表之前）+ 课页滚动进度线
      （纯 CSS 滚动驱动动画，`@supports` 保护）。

**验收**（已全部通过）：

- 页面上的每个数字都是**现算**的 —— 平均分/排名/赢家来自 `design_matrix`，
  token 取值链从 `app.css` 的 `:root` 现读，对比度用 WCAG 公式现算。
  `tests/test_design_matrix.py`（35 条）与 `tests/test_build_site.py` 的 `TestDesignPage`（18 条）
  做双路对账：**页面上的赢家 == 现算的最高分**，**页面印的 token 值 == app.css 里的值**，
  改样式表而不重算页面 → 构建直接失败（`token_value()` 找不到就抛错，不静默印旧值）。
- 对比度 8 组全部达标（正文 17.76:1、卡片内正文 16.71:1、次要文字 6.15:1、链接 6.5:1、
  焦点环 6.5:1）—— 这 8 行是构建期算出来印在页面上的，不是写死的。
- 真实浏览器实测（`python scripts/serve.py` + Chromium）：399×844 手机视口下
  **页面级零横向溢出**、矩阵表在自己的容器里横向滚动（720px 内容 / 366px 容器）、
  条形图可滑、抽屉与汉堡按钮正常；桌面视口下主题按钮三态循环（图标与 `aria-label` 跟着变、
  `localStorage` 记住选择）、Tab 焦点环 2px 实线、`prefers-reduced-motion: reduce` 下
  过渡与动画全部归零（0.12s → 1e-05s）、控制台零未捕获异常。
- `python scripts/check.py` 六项全绿；Python 测试 260 → **316 条**、前端 72 → **75 条**；
  构建产物 43 页 / 60 文件 → **52 页 / 70 文件**（新增 `/design.html` 与 `data/design.json`）。

**踩到并修掉的一个真坑（值得记下来）**：给主题加三态时把 `const THEME_CYCLE` 写在了
`boot();` 调用的**后面** —— `boot()` 第一句就读它，撞上 TDZ 抛 `ReferenceError`，
而它发生在 async 函数里、变成**未处理的 Promise 拒绝**：页面渲染完全正常、控制台不刷红，
但 `boot()` 里的搜索/目录高亮/练习打勾/进度按钮**一条都没跑**。
单测与构建期检查全绿，是真实浏览器里点主题按钮毫无反应才暴露的。
现在有一条结构守卫（`tests/js/app-module-order.test.js`：顶层 `const/let` 必须早于 `boot();`）
和一条注释钉住它。

### v3.2 · 前置一键跳转（约 20 分钟，2026-09-18）

用户的要求是「教程里每个『前置：Lxx』都要能点着跳过去」。原先「前置」在页面上是两处纯文字：
正文「你将学会」末尾那一行、以及课程页页脚那条（构建期由 frontmatter 的 `prereq` 生成）。

- [x] 正文 40 课的前置行改用交叉引用标记：`**前置**：[[L02]]、[[L10]]`（渲染期变成
      `<a class="xref" href="L02-what-happens-in-a-turn.html">L02</a>`）。走 `[[Lxx]]` 而不是
      相对 Markdown 链接是刻意的：这是仓库既有的课间引用机制，`build_site` 的链接改写器只认
      已登记仓库文档，写 `[L02](L02-….md)` 反而会让构建停下。
- [x] `scripts/site_render.py::prereq_links()`：frontmatter `prereq` → 链接串，由调用方给目标映射
      （课程页给同级文件名、单文件离线版给页内锚点 `#L02`）。查不到课号**直接报错**，
      不静默退化成纯文字 —— 死链在浏览器里没人会发现。页脚与 `offline.html` 两处都改用它。
- [x] 门禁新增 **R12**：前置行必须写成 `[[Lxx]]`（裸课号即失败）、且与 frontmatter 的 `prereq`
      完全一致、`prereq` 里的课号必须真实存在。规范写在脚本里，否则下一课又会写回裸课号。
- [x] `templates/lesson.md` 同步改写；`.hermes.md` 补这条硬规则与坑表一行。

**验收**（已全部通过）：`python scripts/check.py` 六项全绿；`python scripts/verify.py` 报
「40 课全部合规（0 个警告）」；Python 测试 316 → **324 条**（新增 8 条：`prereq_links` 四个用例、
正文前置行两条内容回归、构建产物两页断言）；站点产物仍是 52 页 / 70 文件。
反例也实测过：把 `[[L00]]` 改回裸 `L00`、或只改正文不改 frontmatter，R12 都会红并指出是哪一课。

### v3.3 · 顶栏 GitHub 入口（约 30 分钟，2026-09-18）

用户的要求是「界面上要有一个点一下就跳到 GitHub 仓库的标识，按市面上大多数开源项目的做法实现」。

- [x] `scripts/build_site.py`：新增 `GITHUB_MARK_PATH`（GitHub 官方 mark，取自 Primer 的 Octicons，MIT）
      + `github_icon()` / `github_link()` / `topbar_values()`；`web/partials/layout.html` 的顶栏右侧加
      `{{github}}`，位置在主题按钮之后（即顶栏最右端，开源项目放这个入口的通行位置）。
      六处 `render_template` 调用统一传 `**topbar_values(cfg)` —— 少传一处就会在构建期报「模板占位符没填」，
      不会静默少一枚图标。
- [x] 图标是**内联 SVG**（`fill="currentColor"`、`aria-hidden="true"`、不含任何外链）：断网也在，
      单文件离线版里那份也在。不用 `<img>` / 图标字体 —— 外链在无网时就是一个空方块，
      而页面看起来「只是少了个小图形」。
- [x] 链接属性：`target="_blank"` + `rel="noopener"`（新标签页打开，且新页面拿不到 `window.opener`）
      + `aria-label="在 GitHub 上查看本站源码（新标签页打开）"`；`site.json` 的 `repo_url` 留空时
      **不渲染**图标 —— 宁可不放，也不留一个点不动的控件。
- [x] 页脚那条「在 GitHub 上查看仓库」复用同一枚标识（`render_footer`），离线版跟着一起有。
- [x] 窄屏配套：`app.css` 新增 `@media (max-width: 480px)` 收掉进度胶囊。原因见下面的实测数字。

**验收**（已全部通过）：

- 真实浏览器（Chromium + `python scripts/serve.py`，CDP 改视口）在 1280 / 900 / 640 / 560 / 480 / 400 / 360px
  七档下实测：页面级零横向溢出；入口恒定 **34×24px**（复用 `.icon-btn` 的 34px 方形与
  `--target-min` 的 24px 指针目标下限）；图标 17×17px；svg 的 `computed fill` 与 `--fg` 一致
  （亮色 `oklch(0.209…)` / 暗色 `oklch(0.934…)`，切主题跟着换）；悬停 `text-decoration-line: none`
  （没有那条凭空多出来的下划线）；键盘 `:focus-visible` 有 2px 焦点环 + 2px offset。
- 点击实测：新开一个标签页且**只**新开一个，标题就是 `GitHub - mt-yu/HermesUsage: …`，
  当前页 `location.href` 不变（没有把读者从课程页顶走）。
- 窄屏那一档的原始数字（同一页面隐藏/显示这枚按钮对比量出来的）：
  360/400px 下站名本来就是 **2 行**（改这一版之前也是，不是这一版引入的 —— 但加上按钮会变成 3 行）；
  480px 是这一版唯一的真回归点（站名 1 行 → 2 行、顶栏 50.3 → 73px）。
  收掉进度胶囊后 480px 回到 1 行、顶栏 50.3px，360/400px 也回到「和改之前一样高」。
  560px 以上胶囊并不挤占站名宽度，所以**不**把断点开到常见的 640px —— 那等于白扔进度信息。
- `python scripts/check.py` 六项全绿；Python 测试 327 → **334 条**（`TestGithubEntrypoint` 7 条）；
  前端 75 条不变；站点产物仍是 52 页 / 70 文件。
- 一条既有断言按新契约改写：`TestDesignPage` 里「离线版不含 `<svg`」改成「不含 `.chart` / `.nav-icon`、
  且内联 SVG 恰好一枚（页脚那枚标识）」—— 旧写法会把「页脚多一枚图标」误报成「离线版开始内联整站」。

### v3.4 · 发布体系（约半天，2026-09-18）

- [x] `scripts/release.py` 五个动词：`notes` / `changelog` / `artifact` / `create` / `audit`
      （不依赖 `gh` CLI，脚本自己走 REST；令牌复用 `drift_watch.get_token()`）
- [x] 确定性资产：`zip_dir` 固定条目顺序 + `date_time=(1980,1,1,0,0,0)` + Unix `create_system`，
      构建时刻换成 tag 的 commit 时间 → 同一棵树两次打包字节相同（实测 v1.1-web 两次同哈希）
- [x] 资产 = `hermesusage-site-<tag>.zip` + 单版本 `SHA256SUMS`（GNU 两空格，`sha256sum -c` 可校验）
- [x] `CHANGELOG.md`（Keep a Changelog 1.1.0，脚本生成、倒序）；`check.py` 6 项 → **7 项**（新增「变更日志同步」）
- [x] `.github/workflows/release.yml`：推 `v*` tag → 跑 `check.py` → `release.py create`
- [x] 13 个历史 tag 全部回填 release（v0.2/v0.3 是 prerelease；v0.2/v0.3/v1.0 无站点、不附资产）
- [x] 仓库级「不可变发布」打开；`v3.4-release` 由 CI 建出并实测 `immutable: true`

**验收**（已全部通过，2026-09-18 实测）：

- `python scripts/check.py` → **7 项全绿**；`python -m unittest tests.test_release` → **66 条全绿**。
- `python scripts/release.py audit --check` → **退出 0（0 差异，本地 14 个 tag 与远端一致）**，
  每个有站点的 tag 都报「哈希一致」。
- 确定性：`artifact --tag v1.1-web --out A` / `--out B` 两次 zip 的 sha256 相同；
  `v3.3-topbar` 的包与另一位代理早先构建的那份**也字节一致**。
- 不可变发布：`PUT /repos/mt-yu/HermesUsage/immutable-releases` → 204，`GET` → `{"enabled": true}`；
  CI 建的 `v3.4-release` → `immutable: true`、资产 sha256 与本机重建一致、
  `DELETE …/releases/assets/<id>` → **422 `Cannot delete asset from an immutable release`**、
  release 页面出现 `Immutable` 标记。
- 诚实边界：**attestation 未验证**（REST 端点对两个资产都 404，本机无 `gh` CLI）；
  不给历史 tag 做 GPG 签名（本机无密钥）。两条都写进了 `docs/releases.md` 的「已知限制」。

**执行中真踩到的四个坑（都已修掉并补测试）**：

1. `GET /releases/tags/<tag>` **看不到草稿** → 上传中断（本机 TLS 抖）留下的空草稿谁也看不见，
   重跑还会再建一个。改为读带令牌的 `GET /releases` 列表 + `releases_for_tag()`，
   并让 `create` 在失败时**回滚自己刚建的草稿**、成功后清掉同 tag 的多余草稿。
2. 给草稿发 `make_latest` → `422 Latest release cannot be draft or prerelease`，挪到转正那一步。
3. 搁置太久的草稿转正后 `tag_name` 留在 `untagged-…` 占位名（还顺手在远端建了一个同名占位 tag，
   让 CI 的 `changelog --check` 变红）→ 转正时显式重发 `tag_name`，并在读回核验失败时退出 2。
4. `CHANGELOG` 的循环依赖：生成它的那次提交本身不可能出现在它生成的文件里 →
   加 `--assume-tag`（发布前就把本版那一节写进去）+ 把 `changelog:` 前缀当噪声。

### v3.5 · 站点页脚显示当前版本 + L66（约 1 小时，2026-09-18）

- [x] 页脚（全站每页 + 单文件离线版）新增「本站版本 `<tag>` · 更新日志」：版本号指向该版本的
      Release 页，`更新日志` 指向 `CHANGELOG.md`；样式继承页脚次要文字色，不抢正文
- [x] 版本号**构建期从 `CHANGELOG.md` 现读**（`build_site.current_release()`）——
      不用 `git describe`：Pages 的 CI 是浅克隆、没有 tag，那里会失败或给出错值；
      历史 tag 的树里没有这个文件 → **不显示**版本号（不猜）
- [x] `data/manifest.json` 增加 `release` 字段（读者下载即可核对产物属于哪个版本）；
      历史 tag 重建时**不加这个键**，所以那 10 个已发布资产的字节不变（实测 v1.1-web 重建后
      仍与远端 `f5334014…` 相同）
- [x] 新增 L66《给自己的项目发第一个 release》（阶段 6，35 分钟）：把发布体系讲成一条可复现的流程

**验收**（已全部通过，2026-09-18 实测）：

- `python scripts/check.py` → **7 项全绿**；站点自检 41 课 / 53 页 / 71 文件 / 3920 KB。
- 真实浏览器（Chromium + `scripts/serve.py`，CDP 改视口）在 360 / 400 / 480 / 640 / 1280px
  五档实测：**页面级零横向溢出**；版本号始终 **1 行 / 194px**；页脚高度 480px 及以上**不变**，
  360/400px 多一行（+38px，`flex-wrap` 的正常换行）；**顶栏高度不变**（480px 50px / 360·400px 73px）；
  版本号链接的计算色 = 页脚次要文字色 `oklch(0.738 0.021 257.5)`（不是链接蓝）。
- `offline.html` 页脚同样有版本号，单文件里外部 `script`/`link`/`img` 数 = **0**。
- 新增 6 条单测（`TestSiteVersion`）钉住契约：页脚里的版本 == `CHANGELOG.md` 最新的版本节、
  历史 tag 缺 CHANGELOG 时不显示也不报错、`manifest.json` 记录 release。
- 诚实边界：**顶栏不放版本号** —— 顶栏是一行 flex，多一枚控件会把站名在窄屏挤折行（见 `.hermes.md` 坑表）；
  版本号放在页脚，信息一样可达，代价只是一行。

### v2.0 · 让「学过」变成可交付（按需启动）

- [x] 学习报告导出：`web/assets/lib/report.js` 纯函数 → 首页/地图页「导出学习报告」按钮 → `hermes-usage-report.md`
      （完成状态 + 练习 `n/m` + 按阶段分表 + data 来源说明；构建期把每课练习数写进 `data/index.json`）
- [x] 单文件离线版：`site/offline.html`（**622 KB**，内联 CSS、页内锚点、零外部资源、无 JS）

**验收**（已全部通过，2026-09-16，tag `v2.0-deliverable`）：
- 离线版 636,484 字节（< 2 MB）、32 篇文章、568 个 `id` **无重复**、不含 `<script`、`<link`、任何 `src` 属性与相对上级引用（`../`）、
  内联 `<style>` 恰好一块；浏览器实测 0 个外部资源请求、32 条目录链接、点目录能跳到对应文章、正文交叉引用是页内锚点。
- 报告：真浏览器里捕获到的 Blob 为 `text/markdown`，内容含汇总行（例：`完成 3/32 课 · 剩余 680 分钟 · 练习 3/158`）、
  按阶段表格、L15 那行 `2/5`、幽灵课号被忽略。构建产物 42 → **43 页 / 60 文件**，`sitemap.xml` 41 条
  （= 页数 − `{404.html, offline.html}`，两个都不该被收录）。
- 报告里**没有**「时间线」：本课完成只存 `at` 但报告只呈现完成与否，避免把自述数据当成可校验的履历；
  想拿机器可读的数据仍用首页「导出进度 JSON」（与 `python scripts/progress.py` 的 `.state.json` 同构）。

**已知限制**：离线版是「逐字内联 app.css」，所以顶栏/搜索面板/进度卡那些样式在它里面是死代码（约 11 KB 用不上），
换来的是永不与站点漂移；「无外部资源」这条断言同时也在断言课程正文里没有 `<script`/`src="` 字样，
将来若有人在围栏代码里写 `<script>` 示例会红——已有专门的测试把这条前提显式钉住并指向是哪一课。

### 已知欠账（继续如实标注，不许写成「已验证」）

- Docker 路径**已由 CI 验证**（构建镜像 → 起容器 → 按路径 curl → 断言 charset），
  但「在作者本机 `docker compose up`」从未跑过（本机没装 Docker）—— 这最后一步仍在读者手里
- Netlify / Vercel 的配置文件已删除：与 Pages 重叠且无法被 `check.py`/CI 验证（理由见 `docs/deploy.md`）

## 已定案（2026-09-16，原「需要人工决策」）

- **定时任务：已启用，且加了人工开关。**
  网关装成 Windows 登录自启项（`hermes gateway install`；本机无管理员权限，
  Hermes 自动回退到「启动文件夹」方式 —— 实测走的就是这条回退路径）。
  `hermes cron status` 现在给的是 `✓ Gateway is running — cron jobs will fire automatically`。
  任务定义收进仓库：`scripts/cron_ctl.py` 的 `JOBS` 表；开关是
  `python scripts/cron_ctl.py status|on|off|run|install`（详见 `.hermes.md` 第 4 节）。
  当前 3 个任务：自动归档（每小时）、漂移哨兵（每天 09:00）、外链存活检测（每周一 09:00）——
  全是「无问题则零输出」，不会变成投递噪音。
- **部署路径：GitHub Pages 主用 + Docker 交给 CI 验证 + 删除 Netlify/Vercel 配置。**
  Docker 不再靠散文声称「应该能用」：`.github/workflows/docker.yml` 每次 push 真的
  `docker build`、起容器、按真实路径 curl 课程页/离线版/坑表页/CSS/JS/数据，并断言
  `Content-Type: text/html; charset=utf-8`（2026-09-16 首跑通过）。Netlify / Vercel 与 Pages
  完全重叠、配置只能写在各自后台（无法被 `check.py`/CI 验证），故删除配置文件，
  在 `docs/deploy.md` 留三行配方与「不提供」的理由。

> 残留的诚实标注：作者本机没有 Docker，「在你自己机器上 `docker compose up`」这最后一步
> 仍需你亲自跑一次（CI 用的就是同一份 `Dockerfile`）。
