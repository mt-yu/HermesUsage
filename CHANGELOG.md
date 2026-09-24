# 更新日志

本文件由脚本生成，**不要手改** —— 内容是 `python scripts/release.py changelog --write`
从 git 提交记录（提交前缀 → Keep a Changelog 分类）现算的；手改会在下一次
`python scripts/release.py changelog --check` 被判为「与 git 不一致」。

格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。
`journal:` 提交与 `session: 自动归档 …` 是归档/自动提交噪声，只在发布说明的统计行里计数，不逐条列出。

## [未发布]

无

## [v3.6.2-ui-diy] - 2026-09-24

### 修复
- fix: 按 release v2026.9.21 复核两处引用精度（`c72ca0b`）

### 文档
- docs: 站点自检的 KB 数按真实构建校正（4271 -> 4285；L46 回填加了两行坑表）（`cd8f8f8`）

## [v3.6.1-ui-diy] - 2026-09-24

### 修复
- fix: L46 的 CDP 路径真复现：显式 --remote-debugging-port + 四条实测回填（`6ba79cd`）

## [v3.6-ui-diy] - 2026-09-24

### 新增
- session: DIY 界面三课：L42 重写 + L45 Web 面板 + L46 桌面端（`ed5d321`）
- session: 待发布清单做成可执行脚本：pending_probe.py（19 条，一条命令回答「落地了吗」）（`5dddbbd`）
- session: 审计「课程有没有超前」：5 处改成 release 行为（L12/L14/L31/L50×2/L51）（`135b4e5`）
- session: 漂移哨兵改成问正确的问题：上游有没有发新 release（release_probe.py + 基线）（`ebb79cf`）
- session: 官方文档漂移第二次复核：86 页漂移 → 改课 1 处、登记 14 条（判据改成 release tag）（`df8aed5`）

### 修复
- fix: pending_probe 一条都没落地时不该提示改基线（顺手补一条断言）（`f148828`）
- fix: journal.py 归档崩在 summary 以数字开头（re.sub 替换串别插用户文本）（`7858685`）

### 文档
- docs: ROADMAP 记下「为什么不开未发布功能预告课」的决定（`342e185`）
- docs: docs/releases.md 的 tag 清单同步到 15（v3.5-release 已发）（`fd1ecb2`）
- docs: 发布技能补三条实测细节（notes 要本地 tag / 单版本 SHA256SUMS 由 create 写 / --out 用原生路径）（`7a3eb50`）

## [v3.5-release] - 2026-09-20

### 新增
- stage: v3.5 发布：页脚版本号 + L66 收官（41 课）（`394cf69`）
- session: L66 给自己的项目发第一个 release（收尾 + 计数器同步）（`e8e4dd6`）

### 修复
- fix: L00 命令在 PowerShell 里跑不通：补 shell 约定 + 修表格管道转义（`3398733`）

### 文档
- docs: L00 先动手附上 PowerShell 替代写法；顺手把 PowerShell 命令跑通验证（`fd2046e`）
- docs: 把「命令块要写 shell 约定」「表格管道别转义」写进项目技能与宪章（`bdcc6d5`）
- docs: 站点页脚显示当前版本 + L66 验收与计数回填（`2119699`）
- docs: 发布体系实测收口：不可变发布已开、CI 建出 v3.4-release、四处已回填（`83c9bc3`）

## [v3.4-release] - 2026-09-18

### 新增
- stage: 发布体系：13 个 tag 全部有 release（确定性资产 + CHANGELOG + 不可变发布）（`71d0027`）

### 修复
- fix: changelog: 前缀算噪声（CHANGELOG 的循环依赖）（`b5ee88d`）
- fix: CHANGELOG 收进本版那一节（--assume-tag）+ CI 取全 tag（`edd61d7`）

### 文档
- docs: 把顶栏入口的实测结论写进技能与手工验收清单（`5d57e54`）

## [v3.3-topbar] - 2026-09-18

### 新增
- session: 顶栏 GitHub 入口（内联 SVG 标识 + 480px 断点）（`0962a02`）

### 修复
- fix: 修侧栏「入口」竖排：普通条目改「图标 + 一行文字」（`cd07a14`）
- fix: 每课的「前置：Lxx」都可点击跳转（门禁新增 R12）（`157c456`）

## [v3.1-ui] - 2026-09-18

### 新增
- session: 站点视觉系统重写 + 新增设计对比页（10 方案 × 10 维度等权平均）（`4457bff`）
- session: 新增 L56 公司机与个人机：一个内核，两个身份（`8747423`）
- session: L55 补最后一击实测：换机后的 agent 认得你（`6555979`）
- session: 官方文档漂移首次复核：39 页逐个定版，L22 / L32 各修一处（`8bcbb63`）

### 文档
- docs: 漂移复核流程固化成项目技能 source-drift-review（`6b903bd`）

## [v3.0-cases] - 2026-09-17

### 新增
- feat: 自动归档加「别卷走在途改动」闸门（journal.py autocommit）（`beea79d`）
- feat: 阶段 6「真实工作流案例」六课（L60-L65）+ 随之更新的索引/地图/路线图（`c2751cd`）
- feat: 登记阶段 6「真实工作流案例」（STAGES 单一来源）+ 建 lessons/06-realwork/（`a484a29`）

### 文档
- docs: 随课数订正文档数字（README 徽章与图注 38 课/8 阶段、deploy 样例输出、manual-qa 第 1/16 条）（`5d47735`）
- docs: CI 漂移哨兵落地后的两处回填（写课技能补 --in DIR 实测坑；ROADMAP 记录首次发现 37 页已变）（`0b52817`）

### 工程（内部）
- ci: 漂移哨兵接进 CI 的定期任务（每天 09:00）（`0973d1b`）

## [v2.1-ops] - 2026-09-16

### 新增
- feat: README 路线图换成由课程生成的 SVG（scripts/build_roadmap_svg.py）（`c2b2fb5`）
- feat: 部署路径定案 —— Docker 改由 CI 真构建+真访问验证；删除 Netlify/Vercel 配置（`aa804ad`）
- feat: 定时任务总开关 cron_ctl.py + 两个运维脚本的 --quiet 静默模式（`0aada26`）

### 修复
- fix: 修 CI 红 —— 测试别再写死平台相关的默认目录（Linux 是 ~/.hermes）（`54a5e19`）

### 文档
- docs: 补细自动归档的恢复时机（实测 17:57 恢复、18:00 就被卷走）（`cadde48`）
- docs: 手工验收清单 15→17 条（SVG 两条并入主表格）；deploy.md 样例输出更新为当前构建数字（`7183632`）
- docs: ROADMAP 两条人工决策落成「已定案」+ 能力表按实况订正（`936e068`）
- docs: 把「常驻流程」从待办里摘出来（ROADMAP 现在只剩 1 条真待办）（`088a1bb`）
- docs: ROADMAP 消除自相矛盾（老待办勾选/转为常驻流程）+ 补齐 v1.1→v2.0 里程碑索引（`8f819c9`）

## [v2.0-deliverable] - 2026-09-16

### 新增
- feat: v2.0 单文件离线版（622KB，零外部资源）+ 链接改写/检查跳过代码区（`e3c9607`）
- feat: v2.0 学习报告导出（每课练习数进 index.json + report.js 纯函数 + 下载按钮；.md 用 text/markdown）（`1d8634f`）

### 文档
- docs: v2.0 回填（离线版与报告验收、手工清单 13→15、坑表补登代码区保护）（`eb34dd5`）
- docs: 回填 v1.4/v1.5/v2.0（勾选、已知限制、需要人工决策清单）（`887caae`）

## [v1.5-auto] - 2026-09-16

### 新增
- feat: v1.5 运维脚本（官方外链存活检测 + 文档漂移哨兵，各带单元测试）（`046ba2e`）

### 修复
- fix: prompt-cache 登记路径修正（原来指向 Tips 页，与 tips 重复）（`f0502fa`）

## [v1.4-content] - 2026-09-16

### 新增
- feat: v1.4 常见错误合集页 /pitfalls.html（构建期聚合 253 行坑表，带回原课链接）（`9711d7e`）

### 文档
- docs: L21 补精确出处（browser/web-search，89→91）+ L44 的 API Server 段改为本机实测（`a8f0e34`）

## [v1.3-site] - 2026-09-16

### 新增
- feat: v1.3 交互补齐（练习题持久化 + 学习地图页 + 课间键盘导航 + 搜索面板 Tab 环绕）（`adaf1bc`）

### 文档
- docs: v1.3 收尾（手工验收清单 13 条 + ROADMAP 勾选与 4 条已知限制 + 练习书写约定）（`ed24bd1`）

## [v1.2-seo] - 2026-09-16

### 新增
- feat: v1.2 站点可达性（sitemap/robots/canonical/og/skip-link + 构建器自检断言）（`d8f4d03`）

### 修复
- fix: 快照哈希按 LF 计算（修 Linux/CI 上 R10 必红）；citations.yaml 以 LF 落盘；R10 增加 CRLF 断言（`d46024d`）

### 文档
- docs: ROADMAP 勾选 v1.2 完成（`5665a69`）
- docs: 坑表补登「本地代理挂掉导致 git/curl TLS 全挂、浏览器却正常」（`ad3976e`）
- docs: 写入下一阶段路线图（v1.2 站点可达性 → v2.0 可交付），并修正过期的 L33 待办（`2e3c13d`）
- docs: 环境事实补登（本机无 docker / 无 git remote，这两条路径无法本机验证）（`56dd3eb`）

### 工程（内部）
- release: 公开发布：GitHub 仓库 + Pages 上线，并修掉 CI 暴露的快照哈希跨平台 bug（`4a18703`）
- release: 公开发布到 GitHub Pages（site.json 填 repo_url，文档标注 Pages 已验证）（`a44b57d`）

## [v1.1-web] - 2026-09-16

### 新增
- feat: 本地预览服务器 serve.py + 一条命令的全量检查 check.py（`89e8bda`）
- feat: 完整样式表（三栏/亮暗主题/抽屉/代码块/出处徽标 + [hidden] 兜底）（`ae13040`）
- feat: 站点构建器 build_site（40 页产物 + 站内链接自检，45 条测试）（`528ec07`）
- feat: 部署配置与手册（Docker/nginx/Netlify/Vercel/CI/GitHub Pages）（`9ec3810`）
- feat: 站点渲染层 site_render（自编号目录/出处徽标/交叉引用，共 35 条测试）（`5f6aada`）
- feat: 前端纯函数库 search/progress/storage/toc/util（31 条 node 测试，零 npm 依赖）（`7867989`）
- feat: 站点数据层 tutorial_core（唯一解析层 + 19 条 unittest）（`37031cf`）

### 修复
- fix: 进度绑定收口到 li[data-lesson]（否则 body[data-lesson] 会写入幽灵记录）+ 剪贴板兜底（`6f1a400`）

### 文档
- docs: 回填实测数字与两条实施坑（pages=40、hidden 属性被 display 盖掉）（`ebe670c`）
- docs: 教程站（前端 + 快速部署）实施计划（`c96f424`）

### 工程（内部）
- release: 教程站：可交互前端 + 五种部署方式（`3377a22`）

## [v1.0-tutorial] - 2026-09-16

### 新增
- stage: 阶段2-5 与毕业项目补齐 共 22 课（`9628d9d`）
- feat: 可视化学习地图 + 无人值守归档 + 进度清单（`f132930`）

## [v0.3-core] - 2026-09-16

### 新增
- stage: 阶段1 核心五件事完成 6 课（`df67eae`）

## [v0.2-orient] - 2026-09-16

### 新增
- stage: 阶段0 认识 Hermes 完成 4 课（`3cb918b`）

### 工程（内部）
- chore: 建立教程仓库骨架与出处体系（`8e61e79`）
