#!/usr/bin/env python3
"""scripts/serve.py —— 本地预览站点（只用标准库，不装任何东西）。

为什么不用 `python -m http.server`：
1. 它不知道 `.mjs`/`.js` 的 MIME，ES 模块会被浏览器拒绝执行；
2. 它没有 no-store，调试时会被浏览器缓存骗；
3. 它不会先构建。

用法
----
  python scripts/serve.py                # 构建（若 site/ 不存在）并启动到 127.0.0.1:8000
  python scripts/serve.py --port 8137 --open
  python scripts/serve.py --no-build     # 直接用现有 site/
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".webp": "image/webp",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **MIME}
    server_version = "hermes-usage-preview/1"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        # 只报非 200：预览时噪音少一半
        status = args[1] if len(args) > 1 else ""
        if "200" not in str(status):
            super().log_message(fmt, *args)


def main() -> int:
    ap = argparse.ArgumentParser(description="本地预览教程站")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--dir", default=str(SITE))
    ap.add_argument("--no-build", action="store_true", help="不先跑 build_site.py")
    ap.add_argument("--open", action="store_true", help="启动后打开浏览器")
    args = ap.parse_args()

    root = Path(args.dir)
    if not args.no_build:
        rc = subprocess.run([sys.executable, str(REPO / "scripts" / "build_site.py")]).returncode
        if rc != 0:
            print("构建失败，先修好再预览。", file=sys.stderr)
            return rc
    if not (root / "index.html").is_file():
        print(f"没有 {root}/index.html —— 先跑 python scripts/build_site.py", file=sys.stderr)
        return 1

    handler = functools.partial(Handler, directory=str(root))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        url = f"http://{args.host}:{args.port}/"
        print(f"教程站已启动：{url}    （Ctrl+C 停止）")
        if args.open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
