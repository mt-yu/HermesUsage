# 部署这份教程站

站点是**纯静态文件**（`site/`），不需要数据库、不需要常驻 Python 进程。
构建只需要 Python 3.11 + 两个纯 Python 依赖（见 `requirements.txt`）。

```bash
python -m pip install -r requirements.txt
python scripts/build_site.py
# 站点自检通过：32 课 / 40 页 / 52 文件 / 1589 KB（出处基线 hermes v0.21.3）
```

产物结构：`site/index.html`（首页）、`site/lessons/*.html`（32 课）、`site/repo/*.html`（规范页）、
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

> 状态：本仓库作者的本机没有 Docker，**这套配置尚未在真实 Docker 里跑过**。
> 如果 `docker build` 报错，请按报错行号判断是 Python 依赖还是 nginx 配置问题，
> 并更新本文件。

## 方式三：Netlify

1. 仓库推到 GitHub/GitLab 后，在 Netlify 里「Add new site → Import an existing project」。
2. 构建命令与发布目录已写在 `netlify.toml`，不需要在界面上填：
   - build: `python -m pip install -r requirements.txt && python scripts/build_site.py`
   - publish: `site`

## 方式四：Vercel

```bash
npm i -g vercel
vercel        # 首次会问几个问题，构建配置读 vercel.json
vercel --prod # 发布
```

`vercel.json` 已声明 `installCommand` / `buildCommand` / `outputDirectory`，无需手工配置。

## 方式五：GitHub Pages（仓库自带的 Actions）

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

## 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'markdown'` | 没装依赖 | `python -m pip install -r requirements.txt` |
| 页面能开但没有交互（搜索/打勾都不响应） | 静态服务器把 `.js` 的 MIME 给错了 | 用 `python scripts/serve.py` 或 nginx 配置里的默认 MIME |
| `构建失败：… 引用了未登记的出处 [[src:xxx]]` | 课程里写了没登记的出处 | 在 `sources/registry.yaml` 登记后 `python scripts/sync_sources.py` |
| `站内链接自检失败：N 条` | 有内部链接指向不存在的文件 | 按输出的「页面 → 目标」逐条修 |
| 站点是旧的 | `site/` 是上次构建的产物 | 重新 `python scripts/build_site.py`（CI 每次都会重建） |
| 中文在 Netlify/Vercel 上乱码 | 托管方没按 UTF-8 处理 | 本项目所有产物都是 UTF-8；若出现乱码，检查是否手改了 `site/` 里的文件 |
