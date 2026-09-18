---
date: 2026-09-18
kind: fix
scope: release
title: CHANGELOG 收进本版那一节（--assume-tag）+ CI 取全 tag
commit: edd61d7
---

# 2026-09-18 · CHANGELOG 收进本版那一节（--assume-tag）+ CI 取全 tag

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

新增 release.py changelog --assume-tag（发布前那次提交就把 v3.4 那一节写进 CHANGELOG，tag 打上后 --check 逐字相同）；ci.yml 的 checkout 加 fetch-depth: 0（浅克隆没有 tag，check.py 第 4 项会误判）；补 2 条单测。

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

先打 tag 再生成 CHANGELOG 这个顺序是错的：tag 里那份文件永远缺自己那一节，而发布说明的「完整变更日志」链接正指向它。正确顺序 = --write --assume-tag → 提交 → 打 tag → 推 tag。

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
