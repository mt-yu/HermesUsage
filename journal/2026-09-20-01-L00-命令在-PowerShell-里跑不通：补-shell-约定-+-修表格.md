---
date: 2026-09-20
kind: fix
scope: L00,L01,L12
title: L00 命令在 PowerShell 里跑不通：补 shell 约定 + 修表格管道转义
commit: 3398733
---

# 2026-09-20 · L00 命令在 PowerShell 里跑不通：补 shell 约定 + 修表格管道转义

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

L00「先动手」写明 Windows 用 Git Bash，并补上 hermes --help 的真实预期输出（此前只有命令没有输出）；「常见坑」第 1 行收录 PowerShell 里 head/grep 的报错原文与替代写法（Select-Object -First N / Select-String）；「亲手验证」「试一试」给出不依赖管道的写法。顺带修同类缺陷：tutorial_core._table_cells 改成按 code span 切格（裸管道不再切坏单元格，也不会让整行被静默丢弃），L01 安装命令与 L12 /compress 的转义管道改回裸管道，读者照抄不再是错的命令。tests 补 2 条解析规则单测、金丝雀计数 340→341、L00 4→5。

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

课程正文是 bash 语法，而 Windows 新手默认打开的是 PowerShell（head/grep/wc 都不存在）——凡是要读者动手跑的命令块，之前必须写明用哪个 shell，管道还要给 PowerShell 替代。另：表格单元格里的管道写在 code span 内就行；用反斜杠转义能保住单元格，但站点上会多显示一个反斜杠，读者照抄得到一条跑不通的命令。

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
