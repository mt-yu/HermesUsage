---
date: 2026-09-20
kind: session
scope: scripts,ROADMAP,sources
title: 漂移哨兵改成问正确的问题：上游有没有发新 release（release_probe.py + 基线）
commit: ebb79cf
---

# 2026-09-20 · 漂移哨兵改成问正确的问题：上游有没有发新 release（release_probe.py + 基线）

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

48/95 页：本仓库快照其实比 v2026.9.14 的文档新，所以「快照 == release 文档」不成立；新增 release_probe.py（--watch 哨兵 / --docs 逐页比对，19 条单测），drift_watch 默认改走 release 源，CI drift.yml 不再克隆上游 docs，基线名进 registry.yaml；顺手记录待办：审计课程有没有超前引用

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

问对问题比多做检查重要 —— 旧哨兵每天报 86 页，逐页定版后课程该改的是 1 处；判据（读者装得到的 release）与哨兵（比 main）不一致时，噪音会淹没信号

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
