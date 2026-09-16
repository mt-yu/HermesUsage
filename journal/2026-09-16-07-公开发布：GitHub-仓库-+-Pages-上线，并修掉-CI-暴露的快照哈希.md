---
date: 2026-09-16
kind: release
scope: docs,scripts
title: 公开发布：GitHub 仓库 + Pages 上线，并修掉 CI 暴露的快照哈希跨平台 bug
commit: 4a18703
---

# 2026-09-16 · 公开发布：GitHub 仓库 + Pages 上线，并修掉 CI 暴露的快照哈希跨平台 bug

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

仓库 mt-yu/HermesUsage 公开；站点 mt-yu.github.io/HermesUsage 上线（pages 工作流绿）；site.json 填 repo_url；README 徽章与在线入口；修 sync_sources 按 LF 算哈希 + R10 增加 CRLF 断言

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

本地全绿的哈希门禁必须验 git checkout 出来的字节（git cat-file blob），不能只看工作区文件；Windows 工作区 CRLF / 仓库 LF 的错位会让 CI 单方面红

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
