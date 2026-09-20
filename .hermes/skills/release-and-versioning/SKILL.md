---
name: release-and-versioning
description: "Use when publishing this repo (打 tag / 建 Release / 更新 CHANGELOG / 发布对账) or when `release.py changelog --check` or the `release` workflow fails. Gives the exact order, the four verbs, and the five ways this has actually broken."
version: 1.0.0
author: HermesUsage
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [release, tag, changelog, github-api, immutable-releases, supply-chain]
    related_skills: [session-journal, hermes-tutorial-authoring, source-drift-review]
---

# 发布与版本（tag → GitHub Release）

本仓库的发布 = **推一个 `v*` tag**。其余全是自动的：`.github/workflows/release.yml`
跑 `scripts/check.py`，再用 `scripts/release.py create` 建 release、传确定性资产。
规范与排障的人类可读版本是 `docs/releases.md`；本技能是**操作顺序 + 踩过的坑**。

## 五个动词（唯一脚本 `scripts/release.py`）

| 动词 | 干什么 |
|---|---|
| `notes --tag <tag>` | 按「上一个 tag..这个 tag」的提交、按前缀分类，渲染发布说明（离线；**本地得先有那个 tag**，否则报「未知 tag」，所以想预览就先 `git tag -a` 再推） |
| `changelog [--write [--assume-tag T] \| --check]` | 生成 / 校验 `CHANGELOG.md` |
| `artifact --tag <tag>` | 打包**确定性** zip + `SHA256SUMS` + 构建回执（落 `dist/`，不进 git） |
| `create --tag <tag>` | 幂等建/更新 release：草稿 → 传资产 → 转正 → 读回核验 |
| `audit [--check]` | 本地应有的 release 与远端**逐条**对账（标题/资产名/资产哈希/immutable） |

任何 `--dry-run` 都不触网、不取令牌。

## 发布顺序（一步都不能换位）

```bash
python scripts/check.py                                          # ① 全绿才谈发布
python scripts/journal.py commit --kind stage --title "阶段X 完成"  # ② 归档
python scripts/release.py changelog --write --assume-tag v3.5-x   # ③ 本版那一节先写进 CHANGELOG
git commit -am "changelog: 收进 v3.5-x 这一节"                      #    ← 前缀必须是 changelog:
git tag -a v3.5-x -m "<release 标题的副题>"                           # ④ 打注释 tag（先本地建：`notes` 要用它）
python scripts/release.py notes --tag v3.5-x                      #    预览发布说明（离线），不满意就删 tag 重打（没推之前删是安全的）
python scripts/release.py create --tag v3.5-x --dry-run            #    预览将发出的请求（离线）
git push origin v3.5-x && git push origin main                    # ⑤ 推 tag（CI 建 release）+ 再推 main
python scripts/release.py audit --check                          # ⑥ 事后 0 差异
```

## 铁律

1. **`CHANGELOG.md` 由脚本生成，禁手改。** 手改会在 `check.py` 第 4 项红（它会打印首个不同行）。
2. **打 tag 前必须 `changelog --write --assume-tag <tag>`，且那次提交的前缀必须是 `changelog:`。**
   原因：生成 CHANGELOG 的那次提交不可能出现在它自己生成的文件里，而它又在 tag 的区间内 ——
   `changelog:` 被当噪声（与 `journal:` 同类）才让两侧逐字相同。换别的前缀就又红了。
3. **先 `check.py` 全绿再打 tag**：release 一旦建出来就有对外可见性。
4. **草稿不能带 `make_latest`**（422 `Latest release cannot be draft or prerelease`）；它只在转正那一步发。
5. **转正时必须显式重发 `tag_name`**：搁置太久的草稿转正后 `tag_name` 会留在 `untagged-…` 占位名，
   既让 `audit` 判「缺 release」，还会在远端多建一个同名的**占位 tag**（进而让 CI 的 `changelog --check` 红）。
6. **历史 tag 不改名、不重打、不 force push**；出错就发新 tag，并接受旧的那条留在列表里。
7. **不可变发布（immutable releases）一开，资产与 tag 就锁死**，且删掉 release 后**同名 tag 不能再用**。
   所以顺序永远是「先建完、`audit --check` 0 差异，最后才开开关」。
8. **每次往 main 推真实提交（非 `journal:`/`changelog:`/`session: 自动归档` 噪声）后，都要
   `changelog --write` 并用 `changelog:` 前缀提交一次**：CHANGELOG 的「未发布」节就是最新 tag
   之后的真实提交列表，忘了它就红 CI。

## 坑（每条都真踩过）

| 现象 | 真因 | 处理 |
|---|---|---|
| 上传中断（`SSL: UNEXPECTED_EOF_WHILE_READING` / `Errno 10054`）后重跑，`audit` 说「只建了草稿」 | 草稿**既不在 `GET /releases` 公开列表、也不能用 `GET /releases/tags/<tag>` 找到**（发布前不与 tag 关联）。旧版脚本因此重跑一次就多一个看不见的空壳 | 现在 `create` 会沿用旧草稿、失败时回滚自己刚建的草稿、发布成功后清掉同 tag 的多余草稿；`audit` 把「只有草稿」单独标出来并给出 id |
| 远端出现 `untagged-e51889b73d0a…` 这样的 tag | 上面第 5 条那条路径顺手让 GitHub 建了个占位 tag | `git push origin --delete untagged-…`；`git ls-remote --tags origin` 应与本地 tag 一致 |
| CI 红在「变更日志同步」，本机全绿 | CI 是**浅克隆**（没有 tag）→ 脚本把一切都算成「未发布」 | `ci.yml` / `release.yml` 的 `actions/checkout` 都要 `fetch-depth: 0` |
| 本机 CI 都红，日志说 `## [untagged-…]` 是新的一节 | 远端多了占位 tag（见上） | 删 tag 后**重跑同一次工作流**（`POST /actions/runs/<id>/rerun`） |
| 两次 `artifact` 的 zip 哈希不同 | 没走 `zip_dir`（条目顺序 / `date_time=(1980,1,1,0,0,0)` / Unix `create_system`），或用了系统 `zip` | 只用 `release.py artifact`；用 `--out A` / `--out B` 两次比 sha256 自证 |
| 读者 `sha256sum -c SHA256SUMS` 报 FAILED | 传的是累积清单 `dist/SHA256SUMS`（含别的版本的行） | 脚本上传的是 `dist/<tag>-SHA256SUMS`（只含本版一行） |
| `notes` / release 正文里少了归档提交 | `journal:`、`session: 自动归档 …`、`changelog:` 是噪声，只在统计行计数 | 这是设计；想让某条提交出现在正文里就换前缀，别改脚本 |
| `artifact` 跑完，`dist/<tag>-SHA256SUMS` 却**不存在**，看着像构建失败 | 那个「只含本版一行」的清单是 **`create`（上传）那一步才写**的（`release.py` 的 `upload_files`）；`artifact` 只写 zip + `<tag>-build.json` + **累积**的 `dist/SHA256SUMS`（audit 用来比哈希） | 本地验哈希看 `dist/SHA256SUMS` 里那一行或 `build.json` 的 `sha256`；要拿到那 100 字节的单版本清单就跑 `create`（或从远端 release 下回来 `sha256sum -c`） |
| `artifact --out` 传了 MSYS 路径（`/tmp/…`、`$TMPDIR/…`）后又「找不到文件」 | 落盘的是**原生** Python，`/tmp` 这类路径它当盘符相对路径解释，写到别处去了 | 给 `--out` 传原生路径（`C:/Users/<你>/…`）；同理 `git -C` / `node` 的参数也不能用 MSYS 路径 |

## 环境事实

- 本机**没有 `gh` CLI**：一切走 REST（脚本自己用 `urllib` + `ProxyHandler({})`，绕开挂掉的本地代理）。
- 令牌：`get_token()`（`GITHUB_TOKEN` → `git credential fill`），**不打印、不落盘、不进提交**。
- `dist/` 是 gitignore 的：资产字节只由 tag 决定，任何机器重跑 `artifact` 都能复现，所以不需要进 git。
- **attestation 目前拿不到**：`GET /repos/<o>/<r>/attestations/<资产 sha256>` 返回 404（可能按别的
  subject 摘要存），本机没有 `gh release verify` 可用 —— 不要把它写成「已验证」。
