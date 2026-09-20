---
date: 2026-09-20
kind: docs
scope: release,skills
title: 发布技能补三条实测细节（notes 要本地 tag / 单版本 SHA256SUMS 由 create 写 / --out 用原生路径）
commit: 7a3eb50
---

# 2026-09-20 · 发布技能补三条实测细节（notes 要本地 tag / 单版本 SHA256SUMS 由 create 写 / --out 用原生路径）

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

v3.5-release 发布过程中踩到的三处：notes 需本地 tag、artifact 不写 <tag>-SHA256SUMS、MSYS 路径传 --out 会落错地方

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

本地只跑 artifact 后找不到单版本清单是正常的（create 才写）；MSYS 路径不能传给原生 Python 参数

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
