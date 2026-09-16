# syntax=docker/dockerfile:1
# 阶段 1：构建。内容门禁不过就不出镜像 —— 坏内容不该有办法上线。
FROM python:3.11-slim AS build
WORKDIR /repo
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python scripts/verify.py --quiet && python scripts/build_site.py

# 阶段 2：托管。只有 nginx + 静态文件，没有 Python、没有源码。
FROM nginx:1.27-alpine AS serve
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/site /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://127.0.0.1/index.html > /dev/null || exit 1
