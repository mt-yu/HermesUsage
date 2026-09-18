---
date: 2026-09-18
kind: fix
scope: release
title: changelog: 前缀算噪声（CHANGELOG 的循环依赖）
commit: b5ee88d
---

# 2026-09-18 · changelog: 前缀算噪声（CHANGELOG 的循环依赖）

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

把 changelog: 前缀并入 is_noise：重新生成 CHANGELOG 的那次提交本身不可能出现在它生成的文件里，而它又在 tag 区间内 —— 不排除掉，changelog --check 在 tag 上永远红一行。补 1 条单测。

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

先打 tag 再生成 = 错；--assume-tag 生成后提交的那个提交也必须对 changelog 不可见，否则循环依赖还在。

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
