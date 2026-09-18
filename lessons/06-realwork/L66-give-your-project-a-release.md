---
id: L66
title: "给自己的项目发第一个 release"
stage: 6
level: 进阶
minutes: 35
prereq: [L21, L24]
tags: ["release", "git-tag", "changelog", "artifact", "immutable"]
sources: [cli-commands, checkpoints, security]
updated: 2026-09-18
---

# L66 · 给自己的项目发第一个 release

> **一句话**：推一个 `v*` tag，CI 就替你跑门禁、建 release、挂上可校验的资产 —— 也讲清为什么发出去的版本不能靠「删了重发」来修。

## 你将学会

- 用 `python scripts/release.py notes --tag <tag>` 把某个 tag 的发布说明整篇打出来（纯本地读 git 历史，不触网）
- 说清五个动词 `notes` / `changelog` / `artifact` / `create` / `audit` 各管哪一步，并用 `--dry-run` 看清将要发出的请求体
- 亲手证明资产是确定性的：同一个 tag 打包两次 sha256 相同，读者用 `sha256sum -c <tag>-SHA256SUMS` 校验
- 按固定顺序走完一次发布：`check.py` → `changelog --write --assume-tag <tag>` → 用 `changelog:` 前缀提交 → 打注释 tag → 推 tag → 推 main → `audit --check`
- 认出「不可变发布」打开后的三条硬边界：资产不能删、tag 不能移、删掉 release 会烧掉这个 tag 名
- 用三个退出码分辨「成功」「校验不一致」「用法或前置错误」

**前置**：[[L21]]、[[L24]] · **预计耗时**：35 分钟

## 先动手

> 目标：**3 分钟内**看到一份真实的发布说明长什么样。下面这条命令只读本地的 git 历史与文件，不联网、不改任何东西。

```bash
python scripts/release.py notes --tag v1.1-web
```

你应该看到（本机 2026-09-18 实测，节选；`v1.1-web` 是本仓库的一个历史 tag）：

```
# v1.1-web · 教程站：可交互前端 + 快速部署

**发布日期**：2026-09-16
**本版内容**：32 课 · 出处 89 条 · 站点 40 页（另有 4 条归档/自动提交未列出）
**完整变更日志**：https://github.com/mt-yu/HermesUsage/blob/v1.1-web/CHANGELOG.md
**对比**：https://github.com/mt-yu/HermesUsage/compare/v1.0-tutorial...v1.1-web

## 新增
- feat: 本地预览服务器 serve.py + 一条命令的全量检查 check.py（`89e8bda`）
- feat: 完整样式表（三栏/亮暗主题/抽屉/代码块/出处徽标 + [hidden] 兜底）（`ae13040`）
…

---
本发布说明由 `python scripts/release.py notes --tag v1.1-web` 生成（提交前缀 → Keep a Changelog 分类）。
资产：`hermesusage-site-v1.1-web.zip`，校验 `sha256sum -c SHA256SUMS`
站点在线版：https://mt-yu.github.io/HermesUsage/
```

**形状固定，内容随 tag 变**：正文取 `<上一个 tag>..<这个 tag>` 之间的提交，按 commit message 的前缀归类到 Keep a Changelog 的小标题（`feat` → 新增、`fix` → 修复、`docs` → 文档…）；**空的分类不打印**，所以有的 tag 只有一两个小标题。

换一个没有站点的 tag，结尾那几行会换掉：

```bash
python scripts/release.py notes --tag v1.0-tutorial | tail -3
```

你应该看到：

```
本发布说明由 `python scripts/release.py notes --tag v1.0-tutorial` 生成（提交前缀 → Keep a Changelog 分类）。
本版尚未有站点，无构建资产
站点在线版：https://mt-yu.github.io/HermesUsage/
```

再往下走半步，看清「建 release」到底会发出什么请求 —— 这条是 `--dry-run`，**不取令牌、不发任何请求**：

```bash
python scripts/release.py create --tag v1.1-web --dry-run
```

你应该看到（本机 2026-09-18 实测，节选）：

```
[dry-run] tag=v1.1-web repo=mt-yu/HermesUsage prerelease=false make_latest=false
（不解析令牌、不发任何请求；没网也能跑）
（发布说明 1165 字符，30 行；完整内容：python scripts/release.py notes --tag v1.1-web）

1) GET  https://api.github.com/repos/mt-yu/HermesUsage/releases/tags/v1.1-web
   不存在 → POST https://api.github.com/repos/mt-yu/HermesUsage/releases
      body: {"tag_name": "v1.1-web", "name": "v1.1-web · 教程站：可交互前端 + 快速部署", "body": "<发布说明 1165 字符>", "draft": true, "prerelease": false, "make_latest": "false"}
…
2) POST https://uploads.github.com/repos/mt-yu/HermesUsage/releases/{id}/assets?name=hermesusage-site-v1.1-web.zip
…
3) PATCH https://api.github.com/repos/mt-yu/HermesUsage/releases/{id}
      body: {"draft": false}
      （发布前是草稿：资产传完才转正）
```

`echo "退出码：$?"` 应该是 `0`。注意第 1 步建的是 `"draft": true` —— 先草稿、传齐资产、最后一步才转正，这是官方推荐的三步，本仓库照做。

## 原理

### 发布 = 推一个 `v*` tag（本机不需要手点网页）

本仓库 2026-09-18 实测：推 tag 后由 `.github/workflows/release.yml` 触发（`on: push: tags: ["v*"]`），它先跑 `check.py`，再用 `python scripts/release.py create --tag <刚推的 tag>` 建 release。第一条**由 CI 建出来**的 release 是 `v3.4-release`。证据路径：`docs/releases.md` 的「状态（2026-09-18 实测）」、`.github/workflows/release.yml`、`scripts/release.py`（本机没有 `gh` CLI，脚本自己走 REST）。

```
你（或 agent）                      GitHub                         CI
  git push origin v1.1-web   ──▶  收到 tag 推送        ──▶  release.yml
                                                           ① python scripts/check.py
                                                           ② release.py create --tag …
                                                           （建草稿 → 传资产 → 转正）
  python scripts/release.py audit --check  ──▶  逐条对账：本地应有的 release == 远端
```

### 五个动词，五个问题

| 动词 | 回答哪个问题 | 触网 | 例子 |
|---|---|---|---|
| `notes` | 这个版本的说明长什么样？ | 否 | `python scripts/release.py notes --tag v1.1-web` |
| `changelog` | `CHANGELOG.md` 与 git 记录是否一致？ | 否 | `python scripts/release.py changelog --check`（默认就是校验）／`--write` 落盘 |
| `artifact` | 这个 tag 的资产是什么、哈希是多少？ | 否 | `python scripts/release.py artifact --tag v1.1-web` |
| `create` | 远端那条 release 建/更新成什么样？ | 是 | `python scripts/release.py create --tag v1.1-web --dry-run` |
| `audit` | 本地应有的每条 release 与远端是否逐条一致？ | 是 | `python scripts/release.py audit --check` |

四条口径（`python scripts/release.py <动词> --help` 是唯一不过期的一手说明）：

- **`--dry-run` 绝不触网**：只打印将发出的请求，不取令牌，没网也能跑。第一次对某个 tag 动手之前先看它。
- **退出码**：`0` 成功；`1` 校验失败（`changelog --check` 与磁盘不同步、`audit --check` 有差异）；`2` 用法或前置错误（未知 tag、取不到令牌、构建失败）。
- **它按脚本自身的位置定位仓库根**，所以在任何目录下跑都指向同一个仓库 —— 不要写「先 `cd` 到仓库根」。
- `create` 是**幂等**的：已存在的 release 重新 `create` 会保留原文（新正文 = 本次生成的说明 + `---` + `## 原始发布说明` + 原 body）。原文是给读者看的内容，自动化不许把它丢掉。

### 顺序不能换，因为有三条硬依赖

```bash
# 1. 全绿才谈发布（release 一旦建出来就有对外可见性）
python scripts/check.py
# 2. 归档这次改动（提交粒度 = 一个可回滚的语义单元）
python scripts/journal.py commit --kind stage --title "阶段X 完成" --scope L30,L31
# 3. 把「本版」这一节先写进 CHANGELOG —— 此刻 tag 还没打，用 --assume-tag 按「已存在」算
python scripts/release.py changelog --write --assume-tag v3.4-release
git commit -am "changelog: 收进 v3.4-release 这一节"
# 4. 打注释 tag（-a，不要轻量 tag；release 标题会取 tag 对象的 subject）
git tag -a v3.4-release -m "发布体系：Release + CHANGELOG + 不可变发布"
# 5. 先推 tag、再推 main（main 的 CI 也要看得到这个 tag）
git push origin v3.4-release && git push origin main
# 6. 之后什么都不用做：CI 看到 tag 自己建 release；最后对账
python scripts/release.py audit --check
```

1. **`check.py` 全绿在前**：release 有对外可见性，门禁红了还发就是把没验过的东西公开。
2. **第 3 步不能省、也不能挪到打 tag 之后**（本仓库 2026-09-18 实测踩过一轮）——原因是个循环依赖：

   | 做法 | 后果 |
   |---|---|
   | 打 tag 后再生成 | tag 里那份 `CHANGELOG.md` 缺「自己」这一节，而发布说明里的「完整变更日志」链接正指向 `/blob/<tag>/CHANGELOG.md` |
   | 先打 tag 再生成 | `changelog --check` 会红 —— 生成的文件不可能包含「生成它的那次提交」 |
   | 先 `--write --assume-tag`，再用 `changelog:` 前缀提交 | 脚本把 `changelog:` 当前缀当噪声（与 `journal:` 同类），两侧算出来的内容才逐字相同；换成 `docs:` 就又红了 |

3. **草稿 → 传齐资产 → 再发布**：不可变 release 被删除后，同名 tag 不能再重用（见下）。

### 为什么资产必须「确定性」

`python scripts/release.py artifact --tag <tag>` 产出两份东西：`hermesusage-site-<tag>.zip` 与 `<tag>-SHA256SUMS`（一行一个哈希，GNU 格式 `<sha256>  <文件名>` —— **两个空格**，所以 `sha256sum -c` 能直接校验）。

两个字节完全相同的前提是本仓库在 `scripts/release.py` 里做死的三件事（源码见该文件模块 docstring 的「确定性」一节）：

1. `zip_dir`：条目按名排序、时间戳固定 `(1980,1,1,0,0,0)`、`ZIP_DEFLATED`、`create_system=3`（不然 Windows 和 Linux 打的包不一样）；
2. `normalize_build_clock`：把「构建时刻」换成**该 tag 的 commit 时间**（`site/data/index.json` 的 `generated`、`manifest.json` 的 `built_at`、`sitemap.xml` 的 `lastmod` 兜底值）；
3. 临时树里跑的是**该 tag 自己的** `scripts/build_site.py`，历史 tag 不会被后来的渲染逻辑污染。

只有字节相同，「本机重跑 == 远端资产」这件事才能被 `audit --check` 逐条比出来。

### 不可变发布（immutable releases）锁什么

本仓库 2026-09-18 实测：仓库级开关已打开（`GET /repos/mt-yu/HermesUsage/immutable-releases` → `{"enabled": true}`），由 CI 建的 `v3.4-release` 报 `immutable: true`，直接 `DELETE /repos/…/releases/assets/<id>` 被拒（`422 Cannot delete asset from an immutable release`），release 页面标题下方出现 `Immutable` 标记。证据：`docs/releases.md` 的「不可变发布」与「状态（2026-09-18 实测）」两节。

锁住的是：

- **tag 不能移动**：钉死在某个 commit 上，release 存在期间也不能删除；
- **资产不能改、不能删**：挂上去的 zip 与 SHA256SUMS 被保护；
- **还能改的**：标题与说明文本、`pre-release` / `latest` 标记。

所以顺序永远是「先把历史 release 建完、`audit --check` 0 差异，最后才开开关」；出错就**发新 tag**，不删旧 release。

### Hermes 在这一步的位置

发布动作本身没有 agent 能替你兜底的护栏，值得知道三条边界：

- Hermes 的检查点（checkpoint）**默认是关闭的**（v2 起 opt-in）：`hermes chat --checkpoints` 打开，或配置 `checkpoints: {enabled: true}`。它写的是一个共享的 shadow git 仓库 `~/.hermes/checkpoints/store/`，**你项目的 `.git` 从不被碰**；触发时机是 `write_file` / `patch` 与破坏性终端命令（`rm`、`mv`、`sed -i`、输出重定向 `>`、`git reset`/`clean`/`checkout`）。`/rollback <N>` 能回到第 N 个检查点且保住你的手改 —— 但触发列表里**没有 `git push` / `git tag`**：已经推出去的 tag 不在它的保护范围里。[[src:checkpoints]]
- 危险命令审批那张表里也**没有** `git push` / `git tag`（表里是 `rm -r`、`> /etc/`、`docker stop` 这类模式），而用户可加的 `approvals.deny` 默认是空列表（文档给的示例是 `git push --force*`，需要你自己加）。换句话说：**推错一个 tag，默认状态下没有任何自动拦截**，护栏只有第 1 步的门禁和 `--dry-run`。[[src:security]]
- 想让 agent 替你跑这套流程，用一次性问答并显式指定工作目录：`hermes chat -q "…" --in <目录>`。`--in <dir>` 会在启动或恢复前切到该目录、并把会话留在那里（跳过记录的 cwd 恢复），`-q`/`--query` 在非交互（非 TTY）或被 `--oneshot` / `-Q` 指定时答完即退。[[src:cli-commands]]

## 亲手验证

### 验证一：同一个 tag 打包两次，哈希必须相同

```bash
OUT="$LOCALAPPDATA/Temp/l66-dist"     # 换成你自己的临时目录
python scripts/release.py artifact --tag v1.1-web --out "$OUT/a"
python scripts/release.py artifact --tag v1.1-web --out "$OUT/b"
sha256sum "$OUT/a/hermesusage-site-v1.1-web.zip" "$OUT/b/hermesusage-site-v1.1-web.zip"
```

你应该看到（本机 2026-09-18 实测）：两次 `artifact` 打印的 zip 路径不同、**sha256 相同**，`sha256sum` 那两行的哈希也一致：

```
已构建 hermesusage-site-v1.1-web.zip
  站点：32 课 / 40 页 / 52 文件 / 1642686 字节
  zip ：…\a\hermesusage-site-v1.1-web.zip（509710 字节）
  sha256：f53340146497d77010c1e7862ef61d38d10d088ece9489cfaeabae642a1565c5
f53340146497d77010c1e7862ef61d38d10d088ece9489cfaeabae642a1565c5 *…/a/hermesusage-site-v1.1-web.zip
f53340146497d77010c1e7862ef61d38d10d088ece9489cfaeabae642a1565c5 *…/b/hermesusage-site-v1.1-web.zip
```

`<tag>-SHA256SUMS` 里只有一行（另一份 `dist/SHA256SUMS` 是跨版本的累积清单，别拿它当校验依据）：

```bash
cat "$OUT/a/SHA256SUMS"
```

你应该看到（同一个哈希，文件名是光名，没有 tag 前缀）：

```
f53340146497d77010c1e7862ef61d38d10d088ece9489cfaeabae642a1565c5  hermesusage-site-v1.1-web.zip
```

### 验证二：读者视角 —— 从 release 页下资产再校验

```bash
mkdir -p "$LOCALAPPDATA/Temp/l66-dl" && cd "$LOCALAPPDATA/Temp/l66-dl"
curl -sLO --noproxy '*' https://github.com/mt-yu/HermesUsage/releases/download/v1.1-web/hermesusage-site-v1.1-web.zip
curl -sLO --noproxy '*' https://github.com/mt-yu/HermesUsage/releases/download/v1.1-web/v1.1-web-SHA256SUMS
sha256sum -c v1.1-web-SHA256SUMS; echo "退出码：$?"
```

你应该看到（本机 2026-09-18 实测）：

```
hermesusage-site-v1.1-web.zip: OK
退出码：0
```

注意两件事，它们是这节课最容易记错的地方：上传到 release 的清单**叫 `<tag>-SHA256SUMS`**（不是 `SHA256SUMS`）；`sha256sum -c` 要的是这份**单版本**清单，拿累积的 `dist/SHA256SUMS` 去校验，缺文件的行会报 `FAILED`。`--noproxy '*'` 是本机代理坑（`.hermes.md` §6），你的机器上未必需要。

### 验证三：触发一次失败 —— 未知 tag 与浅克隆失真

先给一个不存在的 tag（**不会**动远端，只会在本地判定前置条件失败）：

```bash
python scripts/release.py notes --tag v9.9-nope; echo "退出码：$?"
```

你应该看到：

```
未知 tag：v9.9-nope（本地 `git tag -l` 里没有它）
退出码：2
```

再看一个「命令成功但结论是空」的分支 —— 历史上有几个 tag 打的时候站点还不存在：

```bash
python scripts/release.py artifact --tag v1.0-tutorial; echo "退出码：$?"
```

你应该看到（退出码是 `0`，不是错误码 —— 这是正常结论）：

```
v1.0-tutorial 尚无站点（该版本还没有 web/ 与 build_site.py），不产出资产
退出码：0
```

最后触发一次**真实会红**的情况：`changelog --check` 依赖本地 tag 集合，浅克隆里一个 tag 都没有。用一个临时克隆演示（这一步要网，克隆的是公开仓库）：

```bash
cd "$LOCALAPPDATA/Temp" && git clone --depth 1 https://github.com/mt-yu/HermesUsage.git l66-shallow
cd l66-shallow && git tag -l | wc -l && python scripts/release.py changelog --check; echo "退出码：$?"
```

你应该看到（本机 2026-09-18 实测）：

```
0
CHANGELOG.md 与 git 记录不一致：首个不同行在第 13 行
  生成（脚本算出来）：无
  磁盘（当前文件）  ：### 文档
跑 `python scripts/release.py changelog --write` 覆盖，或改回 git 记录里的事实。
退出码：1
```

`git tag -l | wc -l` 打出 `0` —— 没有 tag，脚本就无从知道哪些内容「已发布」，于是把一切都算成「未发布」（`生成（脚本算出来）：无`）。这不是脚本的 bug，是**输入的缺失**：所以 CI 里跑这条检查必须带 `fetch-depth: 0`（`.github/workflows/ci.yml` 与 `release.yml` 都加了）。

### 验证四：对账 —— `audit --check` 退出 0 才算发完

这一步要网 + 令牌（`GITHUB_TOKEN`，取不到时脚本会走 `git credential fill`），它把本地应有的每条 release 与远端逐条比标题 / 正文 / 资产名 / 资产 sha256：

```bash
python scripts/release.py audit --check; echo "退出码：$?"
```

你应该看到（本机 2026-09-18 实测，节选；表格里每个有资产的 tag 都报「哈希一致」，最后一行给结论）：

```
tag               有 release  资产                                              本地 sha256 vs 远端          immutable  prerelease  latest
v1.1-web          有          hermesusage-site-v1.1-web.zip、v1.1-web-SHA256SUMS   f53340146497 = f53340146497  假         假          否
v3.4-release      有          hermesusage-site-v3.4-release.zip、v3.4-release-…    c73a6b28f194 = c73a6b28f194  真         假          是

对账结论：0 差异（本地 14 个 tag 与远端一致）
退出码：0
```

两个读法值得记住：**`immutable` 那一列**告诉你哪条 release 已经锁死；`latest` 那一列是脚本**显式指定**的（prerelease 一律不是 latest，只有版本最高的那个是），不留给 GitHub 按 semver 猜 —— 本仓库的 tag 名（`v3.3-topbar` 这种）容易被猜错。

## 常见坑

| 现象 | 真实原因 | 怎么解决 |
|---|---|---|
| `audit` 说某个 tag「缺 release」，但你在网页上明明见过它 | 那次发布**只建了草稿、没转正**。草稿不在公开的 `GET /releases` 列表里，也不能用 `GET /releases/tags/<tag>` 找到 —— 只有带令牌的列表能看到 | `create` 会把「只有草稿」单独标出来并给出 id；重跑 `create --tag <tag>`（脚本会沿用旧草稿，发布成功后清掉多余草稿） |
| `create` 报 `422 Latest release cannot be draft or prerelease.` | 给**草稿**发了 `make_latest` —— GitHub 不允许草稿或 prerelease 当 latest | 本仓库脚本已把它挪到「转正」那一步；自己写脚本时别在草稿阶段带这个字段 |
| 远端多出一个像 `untagged-e51889b73d0a…` 的 tag，CI 的 `changelog --check` 因此变红 | 搁置太久的草稿转正时 `tag_name` 没关联上，GitHub 顺手建了一个占位 tag | `git push origin --delete untagged-…` 删掉它，再重跑同一次工作流；`git ls-remote --tags origin` 应与本地 tag 一致 |
| 浅克隆里跑 `changelog --check` 报「首个不同行在第 13 行」，明明什么都没改 | 克隆里没有 tag，脚本把一切都算成「未发布」（见验证三） | 跑这条检查的地方保证 tag 取全：CI 用 `fetch-depth: 0`，本机用完整克隆 |
| 打开不可变发布后 `DELETE /repos/…/releases/assets/<id>` 返回 `422 Cannot delete asset from an immutable release` | 设计如此：资产锁死、tag 钉死 | 标题与说明文本仍可改（`create --tag <tag> --body-only`）；真要换资产只能删掉整条 release，并接受**同名 tag 不能再用** |
| 读者 `sha256sum -c` 报 `<文件名>: FAILED` | 拿的是累积清单 `dist/SHA256SUMS`（含其它版本的行），或下的是 GitHub 自动生成的 `Source code (zip)` | 用 release 页上的 `<tag>-SHA256SUMS`（只含本版一行）配我们自己的 `hermesusage-site-<tag>.zip`；源码包不受本仓库控制，不在校验范围内 |

上面每一条都在本仓库真跑过一轮，证据路径：`docs/releases.md` 的「状态（2026-09-18 实测）」与「排障」两节；这些是 GitHub REST 与本仓库脚本的行为，**没有官方文档出处**（所以它们不挂 `[[src:…]]`）。

## 试一试

- [ ] 在你自己的一个仓库里跑 `python scripts/release.py notes --tag <你最近的 tag>`（把脚本换成你项目里的等价物），数一数：生成的小标题有几个、被当噪声跳过的提交有几条
- [ ] 对同一个 tag 跑两次 `artifact` 到两个不同目录，`sha256sum` 比一次；不一致就说明打包路径没走确定性实现
- [ ] 从 release 页下 `<tag>-SHA256SUMS` 与 zip，`sha256sum -c` 一次并记下退出码；再故意把清单里一个字符改掉，看它变 `FAILED`
- [ ] 在一个浅克隆（`git clone --depth 1`）里跑 `changelog --check`，把输出与验证三贴出的三行对照
- [ ] 说出「为什么先 `changelog --write --assume-tag` 再打 tag」的理由，并且不准用「顺序规范」这四个字回答
- [ ] 把结果记到 `journal/` 里并提交（见 CONTRIBUTING.md 的会话总结流程）

## 下一步

- [[L24]] —— 检查点与回滚：本地内容怎么退回去，以及为什么这套手段救不了已经推出去的 tag
- [[L21]] —— 终端 / 文件 / 网页这些工具的边界，发布流程全靠它们
- [[L53]] —— 工具与命令失败时的官方排障清单
- [[L23]] —— 定时任务：本仓库的小时级自动归档会产出 `session: 自动归档 …` 噪声提交，发布说明按设计**不逐条列**它们
- [[L15]] —— 把「发布前先 `--dry-run`、发完必 `audit --check`」写成一个技能，下次不用重新解释
- 想深入：[[src:checkpoints]]（检查点存哪、什么时候触发）、[[src:security]]（审批表里有什么、没什么）、[[src:cli-commands]]（`-q` 与 `--in` 的准确语义）

## 出处

- [[src:cli-commands]] CLI Commands Reference — https://hermes-agent.nousresearch.com/docs/reference/cli-commands
- [[src:checkpoints]] Checkpoints and /rollback — https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback
- [[src:security]] Security — https://hermes-agent.nousresearch.com/docs/user-guide/security

本课的发布体系部分**没有官方文档出处**：GitHub 的 release 行为与本仓库的脚本都不在 Hermes 官方文档里。相关的每一条断言都来自本仓库实测，可自查的路径是 `docs/releases.md`、`scripts/release.py`（含 `python scripts/release.py <动词> --help`）、`CHANGELOG.md`、`.github/workflows/release.yml`，以及 release 页面本身：https://github.com/mt-yu/HermesUsage/releases
