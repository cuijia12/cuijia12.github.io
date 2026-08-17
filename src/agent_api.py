"""串口助手本机 Agent API 与命令行客户端。

服务只监听 127.0.0.1，并要求使用 config.json 中的 agent_api_token。
GUI 进程负责真正执行串口和 T5L 操作，避免跨线程调用 Tk。
"""
import argparse
import json
import os
import queue
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DEFAULT_PORT = 18765
ACTION_PATHS = {
    "/api/status": "status",
    "/api/serial/open": "serial.open",
    "/api/serial/close": "serial.close",
    "/api/serial/send": "serial.send",
    "/api/serial/receive": "serial.receive",
    "/api/t5l/download": "t5l.download",
    "/api/t5l/stop": "t5l.stop",
}


class AgentAPIController:
    def __init__(self, token, port=DEFAULT_PORT):
        self.token = token
        self.port = int(port)
        self.requests = queue.Queue()
        self.httpd = None
        self.thread = None
        self.error = ""

    def start(self):
        controller = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "SerialAssistantAgentAPI/1.0"

            def log_message(self, _format, *_args):
                return

            def send_json(self, status, body):
                encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def authorized(self):
                return self.headers.get("X-Serial-Token", "") == controller.token

            def do_GET(self):
                if self.path == "/health":
                    self.send_json(200, {"ok": True, "service": "serial-assistant", "api": "1.0"})
                    return
                if self.path != "/api/status":
                    self.send_json(404, {"ok": False, "error": "接口不存在"}); return
                self.dispatch("status", {})

            def do_POST(self):
                action = ACTION_PATHS.get(self.path)
                if not action or action == "status":
                    self.send_json(404, {"ok": False, "error": "接口不存在"}); return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 2 * 1024 * 1024:
                        raise ValueError("请求内容超过 2MB")
                    payload = json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(payload, dict): raise ValueError("JSON 必须是对象")
                except Exception as error:
                    self.send_json(400, {"ok": False, "error": f"JSON 格式错误：{error}"}); return
                self.dispatch(action, payload)

            def dispatch(self, action, payload):
                if not self.authorized():
                    self.send_json(401, {"ok": False, "error": "Token 无效"}); return
                event = threading.Event(); box = {}
                controller.requests.put((action, payload, event, box))
                if not event.wait(30):
                    self.send_json(504, {"ok": False, "error": "GUI 执行超时"}); return
                status = 200 if box.get("ok") else 400
                self.send_json(status, box)

        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError as error:
            self.error = str(error); return False
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="AgentAPI", daemon=True)
        self.thread.start(); return True

    def process_pending(self, callback):
        while True:
            try: action, payload, event, box = self.requests.get_nowait()
            except queue.Empty: break
            try:
                result = callback(action, payload)
                box.update({"ok": True, "result": result})
            except Exception as error:
                box.update({"ok": False, "error": str(error)})
            finally: event.set()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown(); self.httpd.server_close(); self.httpd = None


def config_path():
    base = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


def load_connection(path=None):
    path = path or config_path()
    with open(path, "r", encoding="utf-8") as file: config = json.load(file)
    token = config.get("agent_api_token")
    if not token: raise RuntimeError(f"配置中没有 Agent API Token：{path}")
    return int(config.get("agent_api_port", DEFAULT_PORT)), token


def request_api(action, payload=None, config=None):
    port, token = load_connection(config)
    path = next((path for path, name in ACTION_PATHS.items() if name == action), None)
    if not path: raise RuntimeError(f"未知操作：{action}")
    data = None if action == "status" else json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                     headers={"X-Serial-Token": token, "Content-Type": "application/json"},
                                     method="GET" if action == "status" else "POST")
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try: return json.loads(body)
        except json.JSONDecodeError: raise RuntimeError(body) from error


def main(argv=None):
    parser = argparse.ArgumentParser(description="串口助手 Agent API 客户端")
    parser.add_argument("--config", help="config.json 路径")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="查询串口和 T5L 状态")
    opened = commands.add_parser("open", help="打开串口")
    opened.add_argument("port"); opened.add_argument("--baud", default="115200")
    opened.add_argument("--data-bits", default="8"); opened.add_argument("--parity", default="无")
    opened.add_argument("--stop-bits", default="1")
    closed = commands.add_parser("close", help="关闭串口"); closed.add_argument("port")
    sent = commands.add_parser("send", help="发送字符或 HEX 数据")
    sent.add_argument("port"); sent.add_argument("data"); sent.add_argument("--hex", action="store_true")
    sent.add_argument("--checksum", default="None")
    received = commands.add_parser("receive", help="读取串口最新接收数据")
    received.add_argument("port"); received.add_argument("--limit", type=int, default=20)
    received.add_argument("--clear", action="store_true", help="读取后清空 Agent 接收缓存")
    download = commands.add_parser("download", help="启动 T5L 下载")
    download.add_argument("--port", required=True); download.add_argument("--baud", default="115200")
    download.add_argument("--folder"); download.add_argument("--file", action="append", dest="files")
    commands.add_parser("stop-download", help="停止 T5L 下载")
    args = parser.parse_args(argv)
    if args.command == "status": action, payload = "status", {}
    elif args.command == "open": action, payload = "serial.open", vars(args)
    elif args.command == "close": action, payload = "serial.close", vars(args)
    elif args.command == "send": action, payload = "serial.send", vars(args)
    elif args.command == "receive": action, payload = "serial.receive", vars(args)
    elif args.command == "download": action, payload = "t5l.download", vars(args)
    else: action, payload = "t5l.stop", {}
    payload.pop("command", None); payload.pop("config", None)
    result = request_api(action, payload, args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
