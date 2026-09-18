---
date: 2026-09-18
kind: stage
scope: release
title: 发布体系：13 个 tag 全部有 release（确定性资产 + CHANGELOG + 不可变发布）
commit: 71d0027
---

# 2026-09-18 · 发布体系：13 个 tag 全部有 release（确定性资产 + CHANGELOG + 不可变发布）

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

新增 scripts/release.py（五个动词：notes/changelog/artifact/create/audit，1281 行）、tests/test_release.py（63 条）、.github/workflows/release.yml（推 v* tag 由 CI 调脚本建 release）、docs/releases.md（发布规范）、CHANGELOG.md（脚本生成）。check.py 6 项升到 7 项（新增「变更日志同步」）。回填 .hermes.md/README/CONTRIBUTING/ROADMAP。

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

三处实测踩坑：① GET /releases/tags/<tag> 看不到草稿，上传中断留下的空草稿谁也看不见（改用带令牌的列表 + releases_for_tag，失败当场回滚、成功清残骸）；② 草稿上带 make_latest 会被 422 拒（移到转正那步）；③ 搁置太久的草稿转正后 tag_name 留在 untagged- 占位名（转正时显式再给一次 tag_name）。远端现状：13 个 release、audit --check 退出 0；不可变发布开关已打开（enabled:true）

## 引用到的官方出处

- [[src:quickstart]] — 我在这页确认了 XXX

## 下一步

- [ ] 

## 回滚指引

```bash
git log --oneline                      # 找到要回退到的提交
git revert <sha>                       # 安全回滚（保留历史）
git checkout <sha> -- <file>           # 只回滚某个文件
```
