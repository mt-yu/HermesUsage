# 部署这份教程站

站点是**纯静态文件**（`site/`），不需要数据库、不需要常驻 Python 进程。
构建只需要 Python 3.11 + 两个纯 Python 依赖（见 `requirements.txt`）。

```bash
python -m pip install -r requirements.txt
python scripts/build_site.py
# 站点自检通过：41 课 / 53 页 / 71 文件 / 3920 KB（出处基线 hermes v0.21.3）
```

产物结构：`site/index.html`（首页）、`site/lessons/*.html`（41 课）、`site/repo/*.html`（规范页）、
`site/data/*.json`（导航与检索数据）、`site/assets/*`（样式与前端脚本）。

---

## 方式一：本地预览（零依赖，最快）

```bash
python scripts/serve.py --open
```

```
教程站已启动：http://127.0.0.1:8000/    （Ctrl+C 停止）
```

- 换端口：`python scripts/serve.py --port 8137`
- 跳过重新构建：`python scripts/serve.py --no-build`
- 停止：在终端按 `Ctrl+C`

**别用 `python -m http.server` 代替它**：那个服务器的 MIME 表不认 `.js` 是
`text/javascript`，浏览器会拒绝加载 ES 模块，页面交互会全哑。

## 方式二：Docker（一条命令，适合丢到服务器上）

```bash
docker compose up -d --build     # → http://localhost:8080
docker compose logs -f tutorial  # 看访问日志
docker compose down              # 停掉
```

镜像分两阶段：构建阶段跑 `verify.py`（内容门禁不过就构建失败），
运行阶段只有 `nginx:alpine` + 静态文件。

> 状态：**由 CI 验证**（`.github/workflows/docker.yml`）—— 每次 push 都会真的
> `docker build`、起容器、再按真实路径 curl 首页/课程页/离线版/坑表页/CSS/JS/数据，
> 并断言 HTML 响应带 `charset=utf-8`（中文不乱码）。作者本机没装 Docker
> （装它要 WSL2 + 重启），所以「在你自己机器上 `docker compose up`」这最后一步
> 仍需你亲自跑一次；报错请按行号判断是 Python 依赖还是 nginx 配置问题，并更新本文件。

## 方式三：GitHub Pages（仓库自带的 Actions，本项目实际在用）

**线上地址**：<https://mt-yu.github.io/HermesUsage/>（本仓库实际在用）

1. 仓库推到 GitHub，且**默认分支是 `main`**。
2. Settings → Pages → Build and deployment → Source 选 **GitHub Actions**
   （命令行等价做法：`POST /repos/<owner>/<repo>/pages -d '{"build_type":"workflow"}'`，需要 `repo` 权限的令牌）。
3. 之后每次 push 到 `main`，`.github/workflows/pages.yml` 会：
   `pip install -r requirements.txt` → `verify.py` → `build_site.py` → 上传 `site/` → 发布。
4. 站点地址：`https://<用户名>.github.io/<仓库名>/`。

> 状态：**已验证** —— 2026-09-16 首次发布，`pages` 工作流跑通，线上页面返回 200。
> 公开站点的前提是仓库公开（或账号支持私有仓库的 Pages）。
> 注意：站点所有资源路径都是相对的，因此部署在 `/<仓库名>/` 这种子路径下也能正常工作。

---

## 为什么没有 Netlify / Vercel 的配置

这两个平台能做的事，GitHub Pages 已经做完了（push 即构建、免费、自带 HTTPS），
而它们的构建配置只能写在各自的后台里 —— **无法被本仓库的 `check.py` 与 CI 验证**，
留着就是两份会悄悄漂移、又没人能测的配置。所以本项目不提供它们的配置文件
（2026-09-16 删除了 `netlify.toml` 与 `vercel.json`）。

真要临时用，三行就够（两边都是「装依赖 → 跑构建 → 发布 `site/`」）：

| 要填的字段 | 值 |
|---|---|
| 构建命令 | `pip install -r requirements.txt && python scripts/build_site.py` |
| 发布目录 | `site` |
| Python 版本 | `3.11` |

如果你打算让某一家常驻，请**先把它接进 CI**（照 `.github/workflows/docker.yml` 的样子
真构建一次）再写进本文件 —— 别只写散文。

---

## 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'markdown'` | 没装依赖 | `python -m pip install -r requirements.txt` |
| 页面能开但没有交互（搜索/打勾都不响应） | 静态服务器把 `.js` 的 MIME 给错了 | 用 `python scripts/serve.py` 或 nginx 配置里的默认 MIME |
| `构建失败：… 引用了未登记的出处 [[src:xxx]]` | 课程里写了没登记的出处 | 在 `sources/registry.yaml` 登记后 `python scripts/sync_sources.py` |
| `站内链接自检失败：N 条` | 有内部链接指向不存在的文件 | 按输出的「页面 → 目标」逐条修 |
| 站点是旧的 | `site/` 是上次构建的产物 | 重新 `python scripts/build_site.py`（CI 每次都会重建） |
| 中文在某个静态托管上乱码 | 托管方没按 UTF-8 处理 | 本项目所有产物本身是 UTF-8（HTML 自带 charset；Docker 的 nginx 由 `charset utf-8;` 保证）；若乱码，先确认不是手改了 `site/` 里的文件 |
