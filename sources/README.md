# 出处（Sources）—— 本教程的“可考证”底座

这套教程里每一句关于 Hermes 的事实性陈述，都必须能回答三个问题：

| 问题 | 答案放在哪 |
|---|---|
| 出自官方文档哪一页？ | `citations.yaml` 的 `url` |
| 我读到的是哪个版本？ | `source_commit`（官方仓库 git SHA）+ `hermes_version` |
| 现在还是这样吗？ | `sha256` + `python scripts/sync_sources.py --check` |

## 为什么不是直接贴链接

链接会失效、页面会改版、内容会漂移。只贴 URL 的教程，半年后没人知道
写的时候官方说的是什么。所以这里做的是**带哈希的快照**：

```
registry.yaml   ← 人工维护：id -> 官方文档路径（只维护这一层映射）
citations.yaml  ← 自动生成：id -> URL + 版本 + sha256 + 快照时间
cache/<id>.md   ← 官方文档原文快照（离线可读、可 diff、可 git 追溯）
```

`registry.yaml` 是唯一需要人工编辑的文件。URL、哈希、版本号全部由脚本从
官方文档源码计算，杜绝手抄出错。

## 来源的权威性来源（provenanceof the provenance）

官方文档源码随 Hermes 安装一起落地在本机：

```
$HERMES_HOME/hermes-agent/website/docs/     # Docusaurus 源码（Markdown）
$HERMES_HOME/hermes-agent/                  # 一个 git 仓库
```

所以出处链条是完整可复核的：

```
本仓库 lessons/*.md 的 [[src:id]]
  └─ sources/citations.yaml      (id -> url + sha256 + commit)
       └─ sources/cache/id.md    (快照内容，哈希自证)
            └─ website/docs/xxx.md @ <commit>   (官方仓库该提交下的原文)
                 └─ https://github.com/NousResearch/hermes-agent
```

任何读者都可以：

```bash
python scripts/sync_sources.py --check   # 用你本机的官方文档源码复核哈希
git log --oneline -- sources/cache/      # 看官方文档是在哪次提交后变的
```

## 版权与许可

`sources/cache/` 下是 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
官方文档（MIT License）的原文快照，仅用于引用核对，**不作为本仓库原创内容**。
`.gitattributes` 已把它们标记为 `linguist-vendored`。贡献者请勿改写 `cache/`
里的任何一个字节——要更新就重新跑 `sync_sources.py`。

## 常用命令

```bash
python scripts/sync_sources.py            # 同步快照 + 重新生成 citations.yaml
python scripts/sync_sources.py --check    # 官方文档漂移检测（CI 用这个）
python scripts/sync_sources.py --list-missing   # 检查 registry 里有没有写错的路径
python scripts/verify.py                  # 检查课程引用是否都能解析
```
