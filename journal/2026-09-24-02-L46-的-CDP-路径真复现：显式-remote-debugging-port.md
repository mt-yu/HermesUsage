---
date: 2026-09-24
kind: fix
scope: L46
title: L46 的 CDP 路径真复现：显式 --remote-debugging-port + 四条实测回填
commit: 6ba79cd
---

# 2026-09-24 · L46 的 CDP 路径真复现：显式 --remote-debugging-port + 四条实测回填

## 目标

这次会话开始时我想做什么（一句话）。

## 实际做了什么

根因定位：应用自己 append switch 那条路在本机不生效，显式传 --remote-debugging-port=9333 后 1 秒绑上；隔离实例实测插件加载 8 秒、改文件热重载 3 秒、坏插件不崩且旧组件保留、删目录后组件消失；新增坑「sed -i 改写不触发热重载」；ROADMAP 诚实边界段改成已复现

## 学到的东西

> 这一节是 journal 存在的理由。**留给未来的自己**：
> 什么踩坑了、什么反直觉、哪条命令救了我。

桌面插件的热重载对文件写入方式敏感：sed -i 这种重写方式不触发监视，普通覆写 3 秒生效

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
