"""Static target and headless browser only. No workbench, verifier, credentials or Docker client."""

import glob
import http.server
import json
import os
import select
import socket
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

if sys.argv[-1:] == ["image-check"]:
    sys.exit(0)

if sys.argv[-1:] == ["init"]:
    files = json.loads(os.environ.pop("SOURCE_FILES"))
    for name in ("index.html", "cart.js", "styles.css"):
        target = Path("/site") / name
        target.write_text(files[name])
        target.chmod(0o444)
    sys.exit(0)


class Target(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        name = {"/retail/": "index.html", "/retail/cart.js": "cart.js",
                "/retail/styles.css": "styles.css"}.get(self.path.split("?")[0])
        if name is None:
            self.send_error(404)
            return
        body = (Path("/site") / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", {"index.html": "text/html", "cart.js": "text/javascript",
                                         "styles.css": "text/css"}[name])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'none'; img-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.create_connection(("127.0.0.1", 9222), timeout=3) as remote:
            connections = [self.request, remote]
            while True:
                ready, _, _ = select.select(connections, [], [], 5)
                for source in ready:
                    data = source.recv(65536)
                    if not data:
                        return
                    (remote if source is self.request else self.request).sendall(data)


threading.Thread(target=http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Target).serve_forever,
                 daemon=True).start()
socketserver.ThreadingTCPServer.allow_reuse_address = True
threading.Thread(target=socketserver.ThreadingTCPServer(("0.0.0.0", 9223), Relay).serve_forever,
                 daemon=True).start()
binary = glob.glob("/ms-playwright/chromium-*/chrome-linux*/chrome")[0]
process = subprocess.Popen([binary, "--headless", "--no-sandbox", "--disable-dev-shm-usage",
                            "--disable-background-networking", "--disable-extensions",
                            "--no-first-run", "--remote-debugging-port=9222",
                            "--user-data-dir=/tmp/browser", "about:blank"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
raise SystemExit(process.wait(timeout=900))
