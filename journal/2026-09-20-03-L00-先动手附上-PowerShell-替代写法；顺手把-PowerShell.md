---
date: 2026-09-20
kind: docs
scope: L00
title: L00 先动手附上 PowerShell 替代写法；顺手把 PowerShell 命令跑通验证
commit: fd2046e
---

# 2026-09-20 · L00 先动手附上 PowerShell 替代写法；顺手把 PowerShell 命令跑通验证

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

L00「先动手」在 bash 命令块后面补一个 powershell 代码块（hermes --version / hermes --help | Select-Object -First 40），并说明替换规则 | head -N -> | Select-Object -First N；「常见坑」第 1 行补「数行（wc -l）没有同口径替代」。实测：Select-Object -First N 与 Select-String 在真 PowerShell 里可用（Measure-Object -Line 记 218 行、wc -l 记 223 行，口径不同，所以没写成等价）。技能补一条：围栏代码块不能写在引用块里（站点会渲染成行内代码）。

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

Python-Markdown 的 fenced_code 不处理 blockquote 内的围栏代码块：写在引用块里会在站点上挤成一段行内代码，而 check.py 全绿不会报——改完课要看构建出的 HTML。另：PowerShell 的 Select-Object -First N 与 Select-String 可替代 head/grep，但 wc -l 没有同口径替代。

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
