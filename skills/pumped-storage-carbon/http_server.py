#!/usr/bin/env python3
"""把核算 SKILL 暴露为最小 HTTP 服务，便于智能体平台以“自定义工具”接入。

启动：
  python http_server.py --port 8790

接口：
  GET  /health
  POST /calculate   body 与 cli.py 的输入 JSON 相同
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pareto-explorer"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "carbon-report"))

from carbon_core import METHOD_VERSION, InputError, evaluate_payload
from pareto_core import ParetoError, analyze_pareto
from report_core import build_markdown

MAX_BODY = 20 * 1024 * 1024  # 20 MB，足够全年 8760 点


class Handler(BaseHTTPRequestHandler):
    server_version = "PHS-Carbon/1.0"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/health":
            self._send(200, {"ok": True, "method_version": METHOD_VERSION})
        else:
            self._send(404, {"ok": False, "error": {"code": "E_NOT_FOUND", "message": "未知路径"}})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        route = self.path.rstrip("/")
        if route not in ("/calculate", "/pareto", "/report"):
            self._send(404, {"ok": False, "error": {"code": "E_NOT_FOUND", "message": "未知路径"}})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._send(413, {"ok": False, "error": {"code": "E_SIZE", "message": "请求体为空或过大"}})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if route == "/calculate":
                result = evaluate_payload(payload)
            elif route == "/pareto":
                result = analyze_pareto(payload)
            else:
                result = {"ok": True, "markdown": build_markdown(payload)}
        except json.JSONDecodeError as exc:
            self._send(400, {"ok": False, "error": {"code": "E_JSON", "message": str(exc)}})
            return
        except (InputError, ParetoError) as exc:
            self._send(422, {"ok": False, "error": exc.to_dict()})
            return
        except KeyError as exc:
            self._send(422, {"ok": False, "error": {"code": "E_INPUT", "message": f"报告输入缺少字段：{exc}"}})
            return
        except ValueError as exc:
            self._send(422, {"ok": False, "error": {"code": "E_INPUT", "message": str(exc)}})
            return
        except Exception as exc:  # 兜底，避免服务端 500 无正文
            self._send(500, {"ok": False, "error": {"code": "E_INTERNAL", "message": str(exc)}})
            return
        self._send(200, result)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[http] {self.address_string()} {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"蓄能碳效参谋 HTTP 服务已启动：http://{args.host}:{args.port}")
    print("GET /health  |  POST /calculate")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
