---
date: 2026-09-20
kind: docs
scope: release,docs
title: docs/releases.md 的 tag 清单同步到 15（v3.5-release 已发）
commit: fd1ecb2
---

# 2026-09-20 · docs/releases.md 的 tag 清单同步到 15（v3.5-release 已发）

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

文档里的『当前 14 个 tag』是活清单，发完 v3.5-release 后必须同步；坑表那句改成『全部 tag』免得每次发版都要改

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

活清单式的计数（当前 N 个 tag）每次发版都会过期，能写成『全部』就写成『全部』

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
