"""Exercise the gateway with a fake daemon; never use real credentials."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest


def test_browser_runs_and_chat_use_server_provider():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed for the studio gateway")
    received = []

    class Daemon(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(b"preview")

        def do_POST(self):
            received.append((self.path, self.headers.get("Authorization"),
                             json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(202)
            self.end_headers()
            self.wfile.write(b'{"runId":"test-run"}')

        def log_message(self, *args):
            pass

    daemon = HTTPServer(("127.0.0.1", 0), Daemon)
    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    env = {**os.environ, "PORT": str(port), "OD_INTERNAL_PORT": str(daemon.server_port),
           "OD_API_TOKEN": "test-daemon", "STUDIO_HANDOFF_SECRET": "test-signing",
           "SIP_ORIGIN": "https://sip.example", "STUDIO_OPENAI_API_KEY": "test-server-key",
           "STUDIO_MODEL": "test-model"}
    gateway = Path(__file__).resolve().parents[1] / "marketing/open-design/gateway.mjs"
    process = subprocess.Popen([node, str(gateway)], env=env, stdout=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            for _ in range(100):
                try:
                    if client.get("/").status_code == 401:
                        break
                except httpx.ConnectError:
                    time.sleep(0.05)
            else:
                pytest.fail("gateway did not start")
            preview = client.get("/api/projects/example/raw/post.html",
                                 headers={"Authorization": "Bearer test-daemon"})
            assert preview.status_code == 200
            assert preview.headers["Content-Security-Policy"] == "frame-ancestors 'self' https://sip.example"
            assert "X-Frame-Options" not in preview.headers
            for route in ("/api/runs", "/api/chat"):
                assert client.post(route, json={"message": "hello"}).status_code == 401
                response = client.post(route, headers={"Authorization": "Bearer test-daemon"},
                    json={"message": "hello", "agentId": "amr", "model": "browser-model",
                          "byokProvider": {"apiKey": "browser-key"}})
                assert response.status_code == 202
                assert "test-server-key" not in response.text
                route_seen, auth, body = received[-1]
                assert route_seen == route
                assert auth == "Bearer test-daemon"
                assert body["message"] == "hello"
                assert body["agentId"] == "byok-opencode"
                assert body["model"] == "test-model"
                assert body["byokProvider"]["apiKey"] == "test-server-key"
    finally:
        process.terminate()
        process.wait(timeout=10)
        daemon.shutdown()
        daemon.server_close()
