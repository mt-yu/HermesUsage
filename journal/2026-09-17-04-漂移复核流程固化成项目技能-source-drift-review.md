---
date: 2026-09-17
kind: docs
scope: (仓库运维)
title: 漂移复核流程固化成项目技能 source-drift-review
commit: 6b903bd
---

# 2026-09-17 · 漂移复核流程固化成项目技能 source-drift-review

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

新增 .hermes/skills/source-drift-review/SKILL.md：何时用、三条铁律（定版判据=本机装的版本；两套哨兵比的对象不同；否定断言优先复核）、六步（查版本→稀疏克隆→逐页 diff+课程引用映射→三种探针定版→三分桶处置→收口）、以及踩过的坑（别用 search_files 扫安装树、临时产物放 Temp、判据要写进记录）。在 hermes-tutorial-authoring 的 related_skills 与坑表里挂上交叉引用。check.py 六项全绿。

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

踩坑实录：用 search_files 扫 $HERMES_HOME/hermes-agent 时，命中目录的 AGENTS.md 会被当子目录提示灌进上下文（一次两份长文）；本机安装树 grep 必须用 rg + -g '!tests/**'。

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
