# 计划：按开源社区推荐方案建立发布体系（Release / CHANGELOG / 不可变发布 / CI 自动化）

- 日期：2026-09-18
- 目标：把「Releases」从一个手写的单条记录，变成**可复现、可校验、可自维护**的发布体系。
- 验收一句话：`python scripts/check.py` 全绿（7 项）＋ `python scripts/release.py audit --check` 对远端 0 差异。

## 0. 现状（只读核实过的事实，2026-09-18 10:50）

| 事实 | 证据 |
|---|---|
| 仓库只有 **1 个 Release**（`v1.1-web`，2026-09-16 07:39 UTC 发布，`updated_at == published_at`） | `GET /repos/mt-yu/HermesUsage/releases` |
| 本地/远端有 **13 个 tag**（`v0.2-orient` … `v3.3-topbar`），除 v1.1-web 外都没有 Release | `git tag -l`；API `tags` |
| v1.1-web 的 release **没有任何上传资产**（`assets: []`），可下载的 zip 是 GitHub 按 tag 现生成的（实测两次下载 sha256 相同：`7543a177…`，1,343,529 字节） | API + 实测下载 |
| Deployments **34 条**（github-pages，最近一条 2026-09-18T02:12Z = `66d645e`），是 push 触发 Pages 部署的记录，与 Release 无关 | API `deployments` + `pages.yml` |
| `v1.1-web` 是**注释 tag**：tag 对象 `224e738` → commit `ea6f010` | `git rev-parse v1.1-web^{tag}` |
| 只有 tag ≥ v1.1-web 有 `web/` 与 `build_site.py`（v0.2-orient / v0.3-core / v1.0-tutorial 没有站点） | `git ls-tree <tag> web/` |
| 提交前缀分布：`journal 25 / feat 20 / docs 19 / session 12 / fix 6 / stage 3 / release 3 / ci 1 / chore 1`；`journal:` 是归档镜像，`session: 自动归档 N 个文件变动` 是自动提交噪声 | `git log --format='%s'` |
| **本机无 `gh` CLI / 无 docker**；`python` = Hermes venv 3.11（PyYAML/Markdown，无 pytest）；node 24（`node --test "tests/js/*.test.js"`，位置参数按 glob 解释） | 环境事实 |
| 令牌可得：`git credential fill` 给出 `mt-yu` + 40 字符令牌（**不打印、不落盘、不进提交**） | 实测 |
| 本机代理 `127.0.0.1:7897` 已挂：脚本一律 `urllib.request.ProxyHandler({})`（`drift_watch.py` 既有做法） | 既有代码 + 实测 |
| GitHub **支持「不可变发布」（immutable releases）**：开关打开后，新发布的 release 其**资产不可改删、tag 不可移动/删除**，且自动生成 release attestation | `docs.github.com/en/code-security/.../immutable-releases` |
| 该仓库**不用 PR 流**（全部直接提交到 main）→ GitHub 的 "Generate release notes" / `.github/release.yml` 在这里产出**空说明** | 提交历史 + 官方文档 |

## 1. 定案（不再讨论，实施者照此执行）

| 决策 | 结论 | 理由 |
|---|---|---|
| tag 命名 | **不改**历史 13 个 tag，继续用宪章里的 `v<主>.<次>-<slug>` | 改 tag = 重写历史，违背「可回滚」与远端已发布事实 |
| 发布说明来源 | **自己的脚本按 commit 前缀分类生成**（Keep a Changelog 分类法） | 无 PR 流时 GitHub 自动生成是空的 |
| `.github/release.yml` | **不建** | 它只按 label 归类 PR，本仓库永远命中不到 → 一份无法验证的配置 |
| 资产 | 每个有站点的 tag 附 **确定性 zip**（`hermesusage-site-<tag>.zip`）+ `SHA256SUMS` | 自动生成的源码包不受我们控制；自有资产才能被哈希校验、被 attestation 覆盖 |
| 无站点的 tag（v0.2/v0.3/v1.0） | **不附资产**，说明里如实写明「该版本尚无站点」 | 宁缺毋滥 |
| prerelease | `主版本 == 0` → `prerelease: true` | 社区对 0.x 的通行口径 |
| latest | 只给版本最高的那个 tag 显式 `make_latest: true`（当前 `v3.3-topbar`） | 避免 GitHub 按 semver 猜错 |
| 已有 release 的正文 | 更新时**保留原文**，新正文 = 生成说明 + `---` + `## 原始发布说明` + 原 body | 原文是读者面向的内容，不能丢 |
| 不可变发布 | **先建完 13 个历史 release 并逐个校验，再打开仓库开关**；最后一个 `v3.4-release` 由 CI 在开关打开后创建，用来证明「真的锁上了」 | 开关一旦生效，资产/说明就锁死；顺序反了会把错误永久化 |
| 站点页面 | **不动 `site.json` 的 `repo_docs`**（`docs/releases.md` 不进站点） | 与 `docs/deploy.md` 同待遇（它也不进站点），避免牵动页数断言 |

## 2. 冻结的接口（`scripts/release.py`）

**所有子命令按脚本自身位置定位仓库根，不依赖 cwd。**（项目铁律）

```
python scripts/release.py notes     --tag <tag> [--prev <tag>] [--json]
python scripts/release.py changelog [--write | --check]            # 默认 --check
python scripts/release.py artifact  --tag <tag> [--out DIR] [--json]
python scripts/release.py create    --tag <tag> [--prerelease|--no-prerelease]
                                    [--latest|--no-latest] [--body-only] [--dry-run]
python scripts/release.py audit     [--tag <tag>] [--check] [--json]
```

- 全局：`--dry-run`（**绝不触网**，只打印将发出的请求）、`--quiet`。
- 退出码：`0` 成功；`1` 校验失败（`changelog --check` 不同步 / `audit --check` 有差异）；`2` 用法或前置错误（未知 tag、无令牌、构建失败）。
- 令牌：`GITHUB_TOKEN` → `GH_TOKEN` → `git credential fill`。**复用 `drift_watch.get_token`**（`sys.path.insert(0, str(REPO/"scripts"))` 后导入），不复制第二份实现。
- 网络：`urllib.request.build_opener(ProxyHandler({}))`；UA 用 `HermesUsage-release/1.0 (+https://github.com/mt-yu/HermesUsage)`。
- 输出：中文正文，命令/参数/路径保持英文。

**模块级纯函数（测试与文档按这些名字引用，不许改名）：**

| 函数 | 契约 |
|---|---|
| `tag_order(tags) -> list[str]` | 按 tag 提交的祖先深度（`git rev-list --count <tag>^{commit}`）升序；深度相同再按 creatordate |
| `previous_tag(tag) -> str \| None` | `tag_order` 里该 tag 的前一个；第一个 tag → `None` |
| `classify(subject) -> str` | 见下表；未知/无前缀 → `internal` |
| `is_noise(subject) -> bool` | `journal:` 前缀，或 `session:` 且含 `自动归档` |
| `stats_at(tag) -> dict` | `{"lessons": N, "sources": M, "pages": P?}`（`pages` 只在 `dist/<tag>-build.json` 存在时给出） |
| `release_title(tag) -> str` | `<tag> · <tag 对象的 subject>`（subject 为空则只留 tag；长度 > 100 截断） |
| `build_notes(tag, prev, data) -> str` | 见「发布说明模板」 |
| `render_changelog(releases) -> str` | Keep a Changelog 1.1.0，倒序 |
| `asset_name(tag) -> str` | `hermesusage-site-<tag>.zip` |
| `sha256sums_line(digest, name) -> str` | `<sha256>  <name>`（两个空格，GNU 格式，`sha256sum -c` 可校验） |
| `should_prerelease(tag) -> bool` | 主版本 == 0 |
| `zip_dir(src, dest, root) -> None` | **确定性**：条目按名排序、`date_time` 固定 `(1980,1,1,0,0,0)`、`ZIP_DEFLATED`；同一棵树两次打包字节相同 |

**Keep a Changelog 分类映射（唯一来源，notes 与 changelog 共用）：**

| 分类 | 中文小标题 | 前缀 |
|---|---|---|
| `added` | 新增 | `feat` `stage` `session`（`is_noise` 的除外） |
| `fixed` | 修复 | `fix` |
| `docs` | 文档 | `docs` |
| `changed` | 变更 | `refactor` `perf` `revert` `change` |
| `deprecated` | 弃用 | `deprecate` |
| `removed` | 移除 | `remove` |
| `security` | 安全 | `security` |
| `internal` | 工程（内部） | `ci` `chore` `release` 及无前缀者 |

空分类不打印。`is_noise` 的提交只在「统计」行里报数量，不逐条列出。

**发布说明模板（逐字，占位符 `<>`）：**

```markdown
# <release_title>

**发布日期**：<tag 的 commit 日期 YYYY-MM-DD>
**本版内容**：<N> 课 · 出处 <M> 条[ · 站点 <P> 页]
**完整变更日志**：https://github.com/mt-yu/HermesUsage/blob/<tag>/CHANGELOG.md
**对比**：https://github.com/mt-yu/HermesUsage/compare/<prev>...<tag>     ← prev 为 None 时整行不出现

## 新增
- <subject>（`<short sha>`）

## 修复
…

---
本发布说明由 `python scripts/release.py notes --tag <tag>` 生成（提交前缀 → Keep a Changelog 分类）。
[资产：`<asset_name>`，校验 `sha256sum -c SHA256SUMS`]     ← 无资产时换成「本版尚未有站点，无构建资产」
站点在线版：https://mt-yu.github.io/HermesUsage/
```

## 3. 任务与文件归属

| 波 | 任务 | 唯一拥有者 | 创建/修改的文件 |
|---|---|---|---|
| 1 | T1 脚本 + 单测 | 子代理 A | `scripts/release.py`（新）、`tests/test_release.py`（新） |
| 1 | T2 CI 工作流 | 子代理 B | `.github/workflows/release.yml`（新） |
| 1 | T3 发布规范文档 | 子代理 C | `docs/releases.md`（新） |
| 2 | T4 宪章/入口回填 + 门禁接入 | 子代理 D | `scripts/check.py`、`.hermes.md`、`README.md`、`CONTRIBUTING.md`、`ROADMAP.md` |
| 2 | T5 生成 CHANGELOG.md | **主代理**（跑 T1 的脚本） | `CHANGELOG.md`（生成，新） |
| 3 | T6 执行与验收 | **主代理**（不许委派） | 无源码改动；远端 release、tag、线上核验、journal 提交 |

**T2 工作流契约（T2 只写这一个文件）：**

- `name: release`；触发：`push: tags: ["v*"]` + `workflow_dispatch`（输入 `tag`，必填）。
- `permissions: contents: write, id-token: write`；`concurrency: {group: release-${{ github.ref_name }}, cancel-in-progress: false}`。
- 步骤：`actions/checkout@v4 (fetch-depth: 0)` → `actions/setup-python@v5 (3.11, cache: pip)` → `pip install -r requirements.txt` → `python scripts/check.py` → `python scripts/release.py create --tag "$TAG"`（`env: GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`）。
- 不引第三方 action，不用 `gh` CLI（脚本自己走 REST）。

**T4 必做的字面值清剿**：`grep -rn '六项\|6 项\|五项\|5 项' --include='*.md' .`（check.py 从 6 步变 7 步），
以及 `grep -rn 'check.py' README.md ROADMAP.md CONTRIBUTING.md docs/*.md .hermes.md` 里一切「N 项」表述。

## 4. 主代理侧验收（每波必跑，自己复跑，不看子代理的转述）

1. `python scripts/check.py`（波 1 后允许 6 步版；波 2 后必须是 7 步且全绿）。
2. `python -m unittest tests.test_release -v`（单跑新测试）。
3. `python scripts/release.py changelog --check`（T5 生成后必须为 0）。
4. `python scripts/release.py notes --tag v1.1-web`（人工读一遍措辞与事实）。
5. `python scripts/release.py artifact --tag v1.1-web` **跑两次** → 两次 zip 的 sha256 必须相同（确定性）。
6. `python scripts/release.py create --tag v1.1-web --dry-run` → 打印的请求体人工核对（不改远端）。
7. 真建 13 个 release → `python scripts/release.py audit --check` = 0 差异。
8. 打开不可变发布开关 → push tag `v3.4-release` → **等 CI 自己把 release 建出来** → 核验：
   `immutable: true`、资产 sha256 == 本地、`GET /repos/.../attestations/<sha256>` 有记录、
   尝试 `DELETE` 资产被拒（403/422）。
9. 线上核验：`curl -sL https://github.com/mt-yu/HermesUsage/releases/tag/v3.4-release` 含「Immutable」；
   下载一次资产并 `sha256sum -c`。

## 5. 不在本次范围

- 不给历史 tag 改名 / 重打（重写历史）。
- 不引入 GPG 签名 tag（本机无密钥；写进 `docs/releases.md` 的「已知限制」）。
- 不把 `docs/releases.md` / `CHANGELOG.md` 渲染进站点。
- 不动 `site/` 产物与前端。

## 6. 需要的收尾（主代理）

- `python scripts/journal.py commit --kind stage --title "发布体系：Release + CHANGELOG + 不可变发布 + CI 自动化" --scope release ...`
- `git tag -a v3.4-release` → push（**这一步是「不可变发布」的真实验证**）。
- 恢复定时任务：`hermes cron resume c2e058a277da`（**工作区干净后再恢复**）。

## 修订记录（回填）

- 2026-09-18 计划立案。无修订。
