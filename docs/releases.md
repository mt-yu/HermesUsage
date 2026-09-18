# 发布这个仓库

「发布」在这里有三件事：给一个**已经全绿的提交**起一个名字（tag）、把这个名字对应的
**可校验的资产**发出去、让机器把**说明**写出来。三件事都由 `scripts/release.py` 一条命令完成，
远端动作由 `.github/workflows/release.yml` 自动触发。

本文只讲**规范与操作**：做了什么、为什么这么做、出错怎么查。它**不进站点**
（`site.json` 的 `repo_docs` 里没有任何 `docs/` 下的文件，`docs/deploy.md` 同样不在）。

> 状态（2026-09-18 实测）：**14 个 tag 全部有 release**，`python scripts/release.py audit --check` 退出 0；
> 仓库级「不可变发布」开关已打开（`GET /repos/mt-yu/HermesUsage/immutable-releases` → `{"enabled": true}`）。
> 第一条**由 CI 建出**的 release 是 `v3.4-release`（推 tag 触发 `release` 工作流，成功）：
> `immutable: true`、资产 sha256 与本机重新构建的字节一致、删除资产被 GitHub 拒（422
> `Cannot delete asset from an immutable release`）。attestation 未验证，见文末「已知限制」第 6 条。

---

## 五个动词（`scripts/release.py` 的子命令）

| 动词 | 干什么 | 示例 |
|---|---|---|
| `notes` | 读 `<tag>` 到**上一个 tag** 之间的提交，按提交前缀归类，生成该版本的**发布说明正文**（纯本地，不触网） | `python scripts/release.py notes --tag v1.1-web` |
| `changelog` | 把全部 release 的说明拼成 Keep a Changelog 1.1.0 格式的 `CHANGELOG.md`（倒序，最新在前）；默认是**校验**模式 | `python scripts/release.py changelog --check` |
| `artifact` | 为某个**有站点**的 tag 打包**确定性 zip** `hermesusage-site-<tag>.zip` 与 `SHA256SUMS` | `python scripts/release.py artifact --tag v1.1-web` |
| `create` | 在 GitHub 上建或更新这个 tag 的 release：标题/正文取自 `notes`，资产取自 `artifact` | `python scripts/release.py create --tag v1.1-web --dry-run` |
| `audit` | 把本地应有的每条 release（标题、正文、资产、哈希）与远端**逐条对账** | `python scripts/release.py audit --check` |

完整开关（`--prev` / `--json` / `--write` / `--out` / `--prerelease` / `--no-prerelease` / `--latest` /
`--no-latest` / `--body-only` / `--dry-run` / `--quiet`）以
`python scripts/release.py <动词> --help` 的输出为准 —— 那才是唯一不会过期的一手说明。

两条全局约定，越界就是 bug：

- **`--dry-run` 绝不触网**，只打印将要发出的请求。第一次对某个 tag 动手之前先看它。
- 退出码：`0` 成功；`1` 校验失败（`changelog --check` 与 `CHANGELOG.md` 不同步、`audit --check` 有差异）；
  `2` 用法或前置错误（未知 tag、取不到令牌、构建失败）。

所有子命令**按脚本自身的位置定位仓库根**，在任何目录下跑都指向同一个仓库 —— 不要写「先 `cd` 到仓库根」。

> 状态（2026-09-18 实测）：脚本已落地并通过 **66 条单测**（`python -m unittest tests.test_release`）。
> 本节的命令行为以 `python scripts/release.py <动词> --help` 与 `tests/test_release.py` 为准。

---

## tag 口径

**命名：`v<主>.<次>-<slug>`**（`.hermes.md` §4），例如 `v1.1-web`、`v3.3-topbar`。不用 `v1.1.0` 三段的
semver 形式，也不用日期。

**什么时候打**：

- 一个**可回滚的语义单元**做完 —— 提交粒度是「一次会话 / 一个功能」，tag 粒度是「一批这样的提交」。
- **阶段收尾**——一批课程写完、一次体系改造落地。

打 tag 之前，工作区必须是干净的，且 `python scripts/check.py` 退出 0（见下节第 1 步）。

**当前 14 个 tag**（`git tag -l` 可直接列出）：

```
v0.2-orient  v0.3-core  v1.0-tutorial  v1.1-web  v1.2-seo  v1.3-site  v1.4-content
v1.5-auto    v2.0-deliverable  v2.1-ops  v3.0-cases  v3.1-ui  v3.3-topbar
v3.4-release
```

**远端的 tag 必须与本地一致**：`git ls-remote --tags origin` 里多出任何一个名字（哪怕长得像
`untagged-e51889b73d0a…` 这种占位名）都会让 CI 的 `changelog --check` 红 —— 见「排障」。

**历史 tag 不改名**，即使命名口径后来变了：

1. 它们**已经公开**——站点、release、外部引用都指向这些名字；
2. 改 tag = **重写历史**，直接违背 `.hermes.md` 第 0 节的「可回滚」；
3. 一个 tag 一旦发过，就是「在那一天发布过这个东西」的事实记录，不是可以随便整理的标签。

---

## 发布流程（推荐顺序）

```bash
# 1. 全绿才谈发布
python scripts/check.py
#   预期输出：一行 "全部通过：N 项检查全绿。"（N 由 check.py 当前登记的步骤数决定，
#   以你实际运行打印的 N 为准；本仓库正在把发布资产校验并入这一步，N 会变）

# 2. 归档这次改动（提交粒度 = 一个可回滚的语义单元）
python scripts/journal.py commit --kind stage --title "阶段X 完成" --scope L30,L31

# 3. 把「本版」那一节写进 CHANGELOG —— 此刻 tag 还没打，用 --assume-tag 按「已存在」算
python scripts/release.py changelog --write --assume-tag v3.4-release
git commit -am "changelog: 收进 v3.4-release 这一节"

# 4. 打注释 tag（-a，不要轻量 tag；release 的标题会取 tag 对象的 subject）
git tag -a v3.4-release -m "发布体系：Release + CHANGELOG + 不可变发布"

# 5. 先推 tag、再推 main（顺序有讲究：main 的 CI 也要看得到这个 tag）
git push origin v3.4-release && git push origin main

# 6. 之后什么都不用做：CI 看到 tag 自己建 release
```

**第 3 步为什么不能省、也不能换个顺序**（2026-09-18 实测踩过一轮）：

- 先生成再打 tag 是**错**的：tag 里那份 `CHANGELOG.md` 会缺「自己」这一节，而发布说明里的
  「完整变更日志」链接正指向 `/blob/<tag>/CHANGELOG.md`；
- 先打 tag 再生成，`changelog --check` 会红 —— 生成的文件不可能包含「生成它的那次提交」；
- 所以那次提交的前缀**必须是 `changelog:`**：脚本把 `changelog:` 当前缀当噪声（与 `journal:` 同类），
  两侧算出来的内容才逐字相同。换成 `docs:` 就又红了。

第 5 步由 `.github/workflows/release.yml` 承担：`push: tags: ["v*"]` 触发，跑
`check.py` → `python scripts/release.py create --tag "<刚推的 tag>"`。工作流不引第三方 action、
不用 `gh` CLI —— 建 release 的 REST 调用在 `release.py` 里（本机没有 `gh`，CI 里也不用）。

> 状态（2026-09-18 实测）：工作流已落地。`v3.4-release` 这一条**就是 CI 建出来的** ——
> 推送 tag 后 `release` 工作流跑绿灯，release 对象 `immutable: true`。
> 第一次跑是**红的**，原因值得记住：远端当时残留一个占位名 tag
> （`untagged-e51889b73d0a…`，见「排障」第 4 行），CI 取全 tag 后 `changelog --check` 判不一致。
> 删掉那个 tag、重跑同一次工作流即绿。

---

## 本地补建 / 回填一条 tag

```bash
python scripts/release.py create --tag v1.1-web --dry-run   # 先看请求体，不动远端
python scripts/release.py create --tag v1.1-web             # 真建
# 预期形态：打印这个 tag 的 release 标题、用了多少条提交、资产名与哈希，
# 最后一行是成功/失败结论。本文件不写具体输出样例。

# 只想改一条已存在 release 的正文（不动资产、不动 tag）：
python scripts/release.py create --tag v1.1-web --body-only
```

> 已经在远端建过的 release，重新 `create` **保留原文**：新正文 = 这次生成的说明 + `---` +
> `## 原始发布说明` + 原 body。原文是面向读者的内容，任何自动化都不许把它丢掉。

另一个入口是手动触发工作流（带 `tag` 输入）——在 GitHub 的 Actions 页面里对 `release` 工作流点
`Run workflow`，或走 REST：
`POST /repos/mt-yu/HermesUsage/actions/workflows/release.yml/dispatches`（请求体带
`{"ref":"main","inputs":{"tag":"<tag>"}}`，需要 `workflow` 权限的令牌）。端点定义见
<https://docs.github.com/en/rest/actions/workflows>。

---

## 发布说明从哪来

**唯一来源是这个仓库的提交历史。** `release.py` 取 `<上一个 tag>..<这个 tag>` 的提交，
**按 commit message 的前缀**归类成 Keep a Changelog 的八个分类：

| 分类 | 中文小标题 | 提交前缀 |
|---|---|---|
| `added` | 新增 | `feat` `stage` `session`（`is_noise` 的除外） |
| `fixed` | 修复 | `fix` |
| `docs` | 文档 | `docs` |
| `changed` | 变更 | `refactor` `perf` `revert` `change` |
| `deprecated` | 弃用 | `deprecate` |
| `removed` | 移除 | `remove` |
| `security` | 安全 | `security` |
| `internal` | 工程（内部） | `ci` `chore` `release` 及**无前缀**的提交 |

- 空分类**不打印**（没有「## 移除」的空标题）。
- **`journal:` 前缀的提交，以及 `session: 自动归档 …` 的自动提交，不逐条列出**：
  前者是归档镜像（内容与 `journal/` 里的文件重复），后者是无人值守自动提交的噪声
  （见 `.hermes.md` §4 的自动归档闸门）。它们只在统计行里按数量出现。
- 未知前缀 / 无前缀 → 落进 `internal`（工程内部），不会漏掉，也不会冒充成「新增」。

发布说明正文由 `python scripts/release.py notes --tag <tag>` 生成，形态如下（占位符用 `<>` 标出）：

```markdown
# <release_title>

**发布日期**：<tag 的 commit 日期 YYYY-MM-DD>
**本版内容**：<N> 课 · 出处 <M> 条[ · 站点 <P> 页]
**完整变更日志**：https://github.com/mt-yu/HermesUsage/blob/<tag>/CHANGELOG.md
**对比**：https://github.com/mt-yu/HermesUsage/compare/<prev>...<tag>     ← 第一个 tag 没有这一行

## 新增
- <subject>（`<short sha>`）

## 修复
…

---
本发布说明由 `python scripts/release.py notes --tag <tag>` 生成（提交前缀 → Keep a Changelog 分类）。
[资产：`<asset_name>`，校验 `sha256sum -c SHA256SUMS`]     ← 无资产的 tag 换成「本版尚未有站点，无构建资产」
站点在线版：https://mt-yu.github.io/HermesUsage/
```

`<P>` 站点页数只在 `dist/<tag>-build.json` 存在时给出；没有就不写这一项，不猜。
`CHANGELOG.md` 由 `python scripts/release.py changelog --write` 生成（倒序，最新在前），
`changelog --check` 校验它与 release 说明是否同步 —— 不同步就是退出码 `1`。

---

## 资产

有站点的 tag，附带两个上传资产：

| 资产 | 内容 |
|---|---|
| `hermesusage-site-<tag>.zip` | 该 tag 下**站点源码/产物**的压缩包（名称由 `asset_name(tag)` 决定，固定这个形状） |
| `SHA256SUMS` | 一行一个哈希，GNU 格式：`<sha256>  <文件名>`（**两个空格**，所以 `sha256sum -c` 能直接校验） |

```bash
# 打包（可重跑）
python scripts/release.py artifact --tag v1.1-web
# 预期形态：打印写出的 zip 与 SHA256SUMS 路径、zip 的 sha256。本文件不写具体哈希值。
# 落盘位置由 --out 决定；默认值以 python scripts/release.py artifact --help 为准。
# 产物目录不进 git（dist/ 已在 .gitignore 里）。

# 校验下载到的资产
sha256sum -c SHA256SUMS
# 预期输出：本目录下每个资产一行 "<文件名>: OK"；有任何 <文件名>: FAILED 就是没对上
```

**确定性**：`zip_dir` 打包时条目按名排序、时间戳固定为 `(1980,1,1,0,0,0)`、压缩方式 `ZIP_DEFLATED`。
所以**同一棵树两次打包出来的字节完全相同** —— 这是「哈希可被比对」的前提。校验方法就是打包两次比哈希：

```bash
python scripts/release.py artifact --tag v1.1-web --out /tmp/a
python scripts/release.py artifact --tag v1.1-web --out /tmp/b
# 预期形态：两次打印的 zip sha256 一致。不一致说明打包路径没走 zip_dir，是 bug。

# 不要用默认 zip 工具核对"确定性"：
# 它会把当前时间写进 zip 头，两次的字节必然不同 —— 这不是本仓库的资产。
```

**哪些 tag 没有资产**：`v0.2-orient`、`v0.3-core`、`v1.0-tutorial` **没有**，因为这三个 tag 下
根本还没有站点（`git ls-tree -r <tag> -- web/` 在这三个 tag 上是空的，`v1.1-web` 起才有）。
无资产的 tag 不加占位文件，发布说明里如实写「本版尚未有站点，无构建资产」——

**宁缺毋滥**：不为了「看起来完整」而挂一个空包，那只会多一个要维护的谎言。

---

## prerelease 与 latest

| 规则 | 依据 |
|---|---|
| **主版本 == 0 → `prerelease: true`**（`v0.2-orient`、`v0.3-core` 是预发布） | 社区对 0.x 的通行口径：接口/结构还在变，别让读者当成稳定版 |
| 主版本 ≥ 1 → 正常发布 | 同上 |
| **`make_latest` 只给版本最高的那个 tag**（当前是 `v3.3-topbar`；打出新 tag 后随之更新） | 官方行为：草稿与 prerelease **不能**设为 latest；REST 的 `make_latest` 默认是 `true`；网页端不勾「Set as latest release」时，GitHub 会**按 semver 自动猜** |

自动猜在我们这种 tag 名（`v3.3-topbar` 这种非标准 semver 后缀）下容易猜错，所以**显式指定**，
不留给默认值：`--latest` / `--no-latest` 是 `create` 的显式开关，prerelease 一律 `--no-latest`。

参考：<https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository>、
<https://docs.github.com/en/rest/releases/releases>（`make_latest` 与 `prerelease` 字段的说明）。

---

## 不可变发布（immutable releases）

**它锁的是什么**（官方定义，非本仓库发明）：一个 release 变成不可变之后 ——

- **tag 不能移动**：它被钉死在某个 commit 上，release 存在期间**也不能删除**；
- **资产不能改、不能删**：所有挂上去的文件（我们的 zip 与 `SHA256SUMS`）被保护；
- **标题和说明文本仍然可以改**，`pre-release` / `latest` 标记也仍然可以改；
- 建这个 release 时会**自动生成一份 release attestation**（包含 tag、commit SHA、资产的
  密码学可验证记录），供别人核对「我拿到的东西 == 仓库发布的东西」；
- release 页面标题下方会出现 `Immutable` 标记。

**怎么开**（仓库级）：

1. GitHub → 仓库主页 → **Settings** → 向下找到 **Releases** 段 → 勾 **Enable release immutability**。
   官方明确写了：**只对之后的 release 生效**（旧的不追溯）。
2. REST 等价做法（端点名取自官方 REST 参考，不是编的）：
   - 查是否已开：`GET /repos/mt-yu/HermesUsage/immutable-releases`
     → `{"enabled": true, "enforced_by_owner": false}`；没开时返回 `404`。需要 admin 读权限。
   - 打开：`PUT /repos/mt-yu/HermesUsage/immutable-releases` → `204`。需要 admin 写权限。
   - 关闭：`DELETE /repos/mt-yu/HermesUsage/immutable-releases` → `204`。
   - 官方示例带的头是 `X-GitHub-Api-Version: 2026-03-10`。本仓库脚本默认不带这个头 ——
     真按 REST 打开时，**以官方文档的版本说明为准**，别照抄本文件的猜测。
   - 文档：<https://docs.github.com/en/rest/repos/repos>（搜 “immutable releases”）。

官方文档：<https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases>
（会被重定向到 `/en/code-security/concepts/supply-chain-security/immutable-releases`）、
<https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository>。

> ⚠️ **顺序不能反，先看完这条再动手**：
> 1. **先把 13 个历史 release 建完并逐个校验，最后才打开开关**（`audit --check` = 0 差异是打开的前提）。
>    开关一旦生效，新 release 的资产与 tag 就锁死了；顺序反了就是把没校验过的东西**永久**钉住。
> 2. **不可变 release 被删除后，同名 tag 不能再重用**（官方原文：可以删 tag，但**不能再用同一个 tag 名**；
>    甚至仓库删掉重建也拦着）。所以建 release 一律走官方推荐的三步：
>    **建草稿 → 传齐全部资产 → 再发布**。名字在这里是**一次性**的。
>
> 状态（2026-09-18 实测）：开关**已打开**（`PUT /repos/mt-yu/HermesUsage/immutable-releases` → `204`，
> 随后 `GET` → `{"enabled": true, "enforced_by_owner": false}`）。打开之后由 CI 建的第一条
> `v3.4-release` 实测：`immutable: true`；资产 `sha256` 与本机 `artifact` 重新构建的**字节完全一致**；
> 直接 `DELETE /repos/…/releases/assets/<id>` 被拒 —— `422 Cannot delete asset from an immutable release`；
> release 页面标题下方出现 `Immutable` 标记。
> ⚠️ **attestation 未验证**：官方文档说不可变发布会自动生成 release attestation，但本机拿不到 ——
> `GET /repos/mt-yu/HermesUsage/attestations/<资产 sha256>` 对两个资产都返回 `404`，本机又没有 `gh` CLI
> （`gh release verify` 跑不了）。它可能是按别的 subject 摘要存的，我们没有可验证的路径，所以这里**不断言它存在**。

---

## 校验与对账

一条命令对账，这是发布体系的**唯一真相检查**：

```bash
python scripts/release.py audit --check
echo "退出码：$?"     # 0 = 0 差异；1 = 有差异
# 预期形态：逐 tag 打印比对结果（标题 / 正文 / 资产名 / 资产 sha256 四项），
# 最后一行给出差异条数。本文件不写具体条数 —— 那个数字属于某一次运行，不属于规范。
```

手工核对（不信脚本、或想给读者演示时用）：

```bash
# ① 看这条 release 的对象：注意 "immutable" 字段（GitHub 在 release 对象里就有这个布尔字段）
curl -s --noproxy '*' -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/mt-yu/HermesUsage/releases/tags/v1.1-web

# ② 令牌从哪来（工作流外）：脚本自己按 GITHUB_TOKEN → GH_TOKEN → git credential fill 的顺序取
export GITHUB_TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n 's/^password=//p')
#    本机实测能取到 40 字符的令牌。不要 echo / 不要落盘 / 不要写进任何提交。

# ③ 下载资产再对哈希（--noproxy 是本机的代理坑，见排障）
curl -sLO --noproxy '*' https://github.com/mt-yu/HermesUsage/releases/download/<tag>/hermesusage-site-<tag>.zip
curl -sLO --noproxy '*' https://github.com/mt-yu/HermesUsage/releases/download/<tag>/SHA256SUMS
sha256sum -c SHA256SUMS      # 预期：一行 "<文件名>: OK"

# ④ 页面上肉眼确认：release 标题下方有 "Immutable"
curl -sL --noproxy '*' https://github.com/mt-yu/HermesUsage/releases/tag/<tag> | grep -c Immutable

# ⑤ 看 attestation（只有不可变 release 才有；<sha256> 用资产的哈希）
curl -s --noproxy '*' -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/mt-yu/HermesUsage/attestations/<sha256>
#    端点名取自官方 REST 参考「REST API endpoints for artifact attestations」：
#    https://docs.github.com/en/rest/users/attestations
```

**官方 CLI 路线**（在装了 GitHub CLI 的机器上；**本机没有 `gh`，下面两条在本机跑不了**）：

```bash
gh release verify <tag>                 # 确认这个 release 存在且是不可变的
gh release verify-asset <tag> <文件路径>  # 确认本地文件与 release 资产完全一致
# 官方注意：源码包（GitHub 自动生成的 zip/tar.gz）不能用它校验，因为那是"被请求时才生成"的
```

> 状态（2026-09-18 实测）：14 个 tag 全部有 release 后 `audit --check` 退出 **0**（0 差异）；
> 每个有站点的 tag 都报「哈希一致」，`v3.3-topbar` 是 `latest`，`v0.2-orient` / `v0.3-core` 是 prerelease。

---

## 回滚

**规则只有一条：不重写历史。**

| 情况 | 做什么 | 不做什么 |
|---|---|---|
| 发出去才发现说明写错了 | 改标题/说明文本（**不可变 release 也允许改这两样**） | 不动 tag、不动资产 |
| 发出去才发现内容错、要退回旧版本 | **发一个新 tag**（例如 `v3.4-release` 有问题 → 出 `v3.5-fix`），在说明里写清它取代谁 | 不移动/删除旧 tag，不 `--force` 推 |
| 某条 release 是彻底建错的（错 tag、错资产） | 先想清楚：删 release 会**烧掉这个 tag 名**（不可变时官方禁止重用同名 tag），确认这个代价可以接受再删 | 不把「删了重建」当成日常修错手段 |
| 只是本地代码要回退 | `git revert <sha>`（保留历史）或 `git checkout <sha> -- <file>`（单文件），见 `CONTRIBUTING.md` §4 | 不用 `git reset --hard` / force push —— journal 里记的 commit 号会失效 |

本地与远端的分工：**git 侧的回滚手段（revert / checkout 文件）负责内容**，
**release 侧没有回滚，只有「再发一个」**。把错误版本永远留在 release 列表里，
比悄悄改掉它更符合本仓库的「可考证」定位。

---

## 为什么没有 `.github/release.yml`，也不用 `--generate-notes`

官方口径很明确：**自动生成的发布说明 = 这个版本里合并的 pull request 列表 + 贡献者列表 +
一条完整 changelog 链接**；`.github/release.yml` 能配的只是**按 PR 的 label 归类**
（`changelog.categories[*].labels`）以及排除某些 label / 作者。

而本仓库**不用 PR 流**——所有提交都是直接进 `main` 的。于是：

- `--generate-notes`（或网页上的 Generate release notes）在这里会产出**空说明**；
- `.github/release.yml` 的每一条分类都靠 PR label 命中，本仓库**永远命中不到**。

**留一份永远命中不到的配置，就是留一份无法验证的第二真相**——它既不会在 CI 里红，也不会有人
发现它早就失效。（`docs/deploy.md` 里拒绝 Netlify / Vercel 配置，用的是同一条理由。）

所以本仓库的发布说明只有**一个来源**：`scripts/release.py notes` 按提交前缀分类。它可被单测覆盖、
可被 `audit --check` 对账、可以离线重放。**如果将来真的引入 PR 流，先把它接进 CI 真跑一次，
再回来改本节**——别只写散文。

---

## 已知限制

如实列，不含糊：

1. **tag 未做 GPG 签名**（本机没有密钥）。`git tag -v <tag>` 拿不到有效签名，
   所以「想验证这个 tag 出自谁手」的读者**做不到**——目前只能靠 GitHub 账号 + 不可变 release
   （tag 被钉死在 commit 上、有 attestation）来间接保证。
2. **attestation 只随「不可变 release」生成**。开关打开之前建的 release 没有 attestation；
   历史 13 条里，除最后那条由 CI 在开关打开后创建的之外，都不会有。
3. **GitHub 自动生成的 `Source code (zip)` / `(tar.gz)` 不受本仓库控制**，字节可能随上游归档服务
   变化，官方也不支持用它做校验（原文：这类源码包"只在被请求下载时才生成"）。
   → **要一个冻结点，就下我们自己的 `hermesusage-site-<tag>.zip`**。
4. **本机没有 `gh` CLI**：官方的 `gh release verify` / `gh release verify-asset` 在本机跑不了，
   只能用本文件「校验与对账」里的 REST + `sha256sum` 路线。
5. **发布脚本与 CI 工作流的状态以实测为准**：`scripts/release.py` 与 `.github/workflows/release.yml`
   的落地情况、以及不可变开关的开启状态，见本文各处的「状态（2026-09-18 实测）」。
6. **release attestation 拿不到**：官方说不可变发布会自动生成 release attestation，
   但本机两条路都走不通 —— `GET /repos/mt-yu/HermesUsage/attestations/<资产 sha256>` 对两个资产
   都返回 `404`（可能按别的 subject 摘要存），`gh release verify` 因为本机没有 `gh` CLI 跑不了。
   **所以我们不宣称它存在**，也不把「可验证的来源证明」写成已完成项。
7. **`changelog --check` 依赖本地的 tag 集合**：浅克隆（没有 tag）会让它把一切都算成「未发布」而失真。
   `ci.yml` / `release.yml` 因此都加了 `fetch-depth: 0`；你在别处跑这条检查时也要保证 tag 取全。

---

## 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| `audit --check` 退出码 `1` | 本地应有的状态与远端实际不一致（标题/正文/资产名/资产哈希四项之一） | 按输出里点名的 tag 逐个处理：只差正文用 `create --tag <tag> --body-only`；差资产就重跑 `artifact` 再 `create` |
| `create` 报 `2`（用法或前置错误） | 未知 tag、取不到令牌、或站点构建失败 | 先 `git tag -l` 确认 tag 名；再确认 `git credential fill` 能取到 40 字符令牌；构建失败看 `build_site.py` 的输出 |
| `create` 返回 403 / 404 | 令牌权限不够（建 release 需要 `contents: write`） | 换有 `repo` 权限的令牌；CI 里检查工作流的 `permissions: contents: write` |
| 推 tag 后 CI 没有建 release | 工作流没被触发，或跑红了 | 看 Actions 里 `release` 工作流的运行记录；本地补建：`python scripts/release.py create --tag <tag>` |
| 打开不可变后改不了/删不掉资产 | 设计如此（资产是锁死的） | 改标题与说明文本是允许的；真要换资产只能删掉整条 release，并接受**同名 tag 不能再用** |
| `sha256sum -c` 报 `FAILED` | 下载不完整，或者下的不是我们的资产（比如 GitHub 自动生成的源码包） | 重新下载 release 页上的 `hermesusage-site-<tag>.zip` + `SHA256SUMS` 两份；源码包不在校验范围内 |
| `git push origin <tag>` 或 curl 报 `schannel: failed to receive handshake` / `TLS connect error`，但浏览器能上网 | 本机代理（`127.0.0.1:7897`）挂了但端口还开着 | curl 加 `--noproxy '*'`；git 用 `git -c http.proxy= -c https.proxy= push origin <tag>`；长期做法见 `.hermes.md` §6 |
| 打包两次哈希不同 | 没走 `zip_dir` 的确定性打包（或者用的是系统 zip 工具） | 只用 `python scripts/release.py artifact`；它固定条目顺序与时间戳 `(1980,1,1,0,0,0)` |
| 发布说明里出现空的小标题，或少了某条提交 | 前缀不在映射表里（落进 `internal`），或它是 `journal:` / `session: 自动归档 …` 噪声 | 空分类不打印是设计；噪声不逐条列是设计。真要出现在正文里，就改提交前缀，别改脚本 |
| 中文乱码 / 文件里多个 `^M` | 写文件时用了默认编码或 CRLF | 一律 UTF-8 无 BOM + LF（Python 写文件显式 `encoding="utf-8"`、`newline="\n"`） |
| **`audit` 说某个 tag「缺 release」，但你在网页上明明见过它** | 那次发布**只建了草稿、没转正**（或转正后 `tag_name` 仍是占位名）。草稿既不在 `GET /releases` 里（公开视角），也不能用 `GET /releases/tags/<tag>` 找到 —— 只能用**带令牌**的 `GET /releases` 列表看 | `audit` 已把「只有草稿」单独标出来并给出 id；删掉重跑 `create` 即可（脚本现在会自动沿用旧草稿、发布成功后清掉多余草稿） |
| 上传中途 TLS 断（`SSL: UNEXPECTED_EOF_WHILE_READING` / `远程主机强迫关闭了一个现有的连接`），重跑会不会残留垃圾 | 不会：`create` 在**建完草稿后任何一步失败**都会当场回滚自己刚建的那条草稿，并在输出里写「已删除本次新建的草稿（失败回滚）」 | 直接重跑同一条命令；本机 TLS 常抖，重跑两三次是常态（实测 v3.4-release 第一次就是抖掉的） |
| `create` 报 `422 Latest release cannot be draft or prerelease.` | 给**草稿**发了 `make_latest`（GitHub 不允许草稿/prerelease 当 latest） | 脚本已把它挪到「转正」那一步（`publish_payload`），你不需要手动处理；自己写脚本时注意这条 |
| 远端多出一个像 `untagged-e51889b73d0a…` 的 tag，CI 的 `changelog --check` 因此变红 | 那是「草稿被转正但 `tag_name` 没关联上」时 GitHub 建的占位 tag（转正时显式带上 `tag_name` 已能避免） | `git push origin --delete untagged-…` 删掉它，然后重跑同一次工作流；`git ls-remote --tags origin` 应与本地 14 个 tag 一致 |
| 打完 tag 后 `changelog --check` 报「首个不同行在 `## [未发布]` 附近」 | 打 tag 前没跑 `changelog --write --assume-tag <tag>`；或者那次提交的前缀不是 `changelog:` | 按「发布流程」第 3 步重来：`--write --assume-tag` → 用 `changelog:` 前缀提交 → 再打 tag |
