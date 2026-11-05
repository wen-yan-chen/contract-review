"""本地预览服务器：托管项目根目录，供前端读取 data/*.json。

用法：
  python serve.py            # 默认 8080
  python serve.py --port 9000
"""

import argparse
import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # D:\contest-32


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # 静默，避免刷屏


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    handler = functools.partial(Handler, directory=str(ROOT))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/web/"
        print(f"服务已启动: {url}")
        print(f"根目录: {ROOT}")
        print("Ctrl+C 停止")
        if not args.no_browser:
            webbrowser.open(url)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
