---
date: 2026-09-21
kind: session
scope: scripts,ROADMAP,docs
title: 待发布清单做成可执行脚本：pending_probe.py（19 条，一条命令回答「落地了吗」）
commit: 5dddbbd
---

# 2026-09-21 · 待发布清单做成可执行脚本：pending_probe.py（19 条，一条命令回答「落地了吗」）

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

ROADMAP 里那 19 条「上游已写、本 release 还没有」写进 scripts/pending_probe.py 的 ITEMS 表（code/doc/file 三种探针），--tag main 作对照应 19 条全落地；接进 CI drift.yml（有新 release 才跑）与技能第 4/6 步；单测含两条金丝雀：needle 必须在 main 侧命中、roadmap_token 必须在 ROADMAP.md 里出现 —— 这两条当场抓出我自己写错的 needle 与 token

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

清单写进脚本才算清单：人记的 19 条会腐烂，而写成数据表后 ① 一条命令回答「落地了吗」 ② 金丝雀能在 CI 里替你盯着「文档与脚本是不是还一致」

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
