"""
One-shot local HTTP server that serves a professional redirect page.

Flow:
  1. Python obtains the Enketo URL via API token.
  2. Browser opens http://localhost:{port}/{idx}.
  3. The page loads a hidden iframe pointing to {base_url}/accounts/login/?next=/
     — this silently refreshes the browser's KoboToolbox session cookie.
  4. When the iframe loads (or after a 2.5 s fallback), the page redirects
     to the Enketo URL.  The session cookie is now fresh, so Enketo accepts it.
  5. Server shuts itself down after all tabs are served (or after 60 s).
"""

import http.server
import json
import socket
import socketserver
import threading


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _build_page(enketo_url: str, login_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>QboToolbox — Opening Webform</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#f0f2f5;display:flex;align-items:center;
     justify-content:center;min-height:100vh}}
.card{{background:#fff;border-radius:12px;padding:48px 40px;text-align:center;
       box-shadow:0 4px 24px rgba(0,0,0,.09);max-width:380px;width:90%}}
h1{{font-size:20px;color:#1a1a2e;margin-bottom:8px}}
p{{color:#666;font-size:14px;margin-bottom:24px;line-height:1.5}}
.spinner{{width:36px;height:36px;border:3px solid #e0e0e0;
          border-top-color:#0078d4;border-radius:50%;
          animation:spin .8s linear infinite;margin:0 auto 24px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.btn{{display:inline-block;padding:10px 24px;background:#0078d4;color:#fff;
      text-decoration:none;border-radius:6px;font-size:14px;margin-top:8px}}
.btn:hover{{background:#006cbd}}
#error{{display:none}}
</style>
</head>
<body>
<div class="card">
  <div id="loading">
    <h1>Opening Webform</h1>
    <p>Please wait while your KoboToolbox form loads…</p>
    <div class="spinner"></div>
  </div>
  <div id="error">
    <h1>Session Expired</h1>
    <p>Your KoboToolbox browser session has expired.<br>
       Log in, then click <b>Edit Feature</b> in QGIS again.</p>
    <a href="{login_url}" class="btn" target="_blank">Log in to KoboToolbox</a>
  </div>
</div>
<iframe id="af" src="{login_url}" style="display:none"
        sandbox="allow-same-origin allow-forms allow-scripts"></iframe>
<script>
var done = false;
var enketoUrl = {json.dumps(enketo_url)};

function go() {{
  if (done) return;
  done = true;
  window.location.replace(enketoUrl);
}}

document.getElementById('af').onload = function() {{
  setTimeout(go, 350);
}};

// Fallback if iframe is blocked (X-Frame-Options)
setTimeout(go, 2500);
</script>
</body>
</html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    url_map = {}
    login_url = ""
    served = set()
    server_ref = None

    def do_GET(self):
        idx = self.path.strip("/").split("?")[0] or "0"
        enketo_url = self.url_map.get(idx, next(iter(self.url_map.values())))
        page = _build_page(enketo_url, self.login_url)
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _Handler.served.add(idx)
        if len(_Handler.served) >= len(_Handler.url_map):
            threading.Thread(target=_Handler.server_ref.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass


def launch(enketo_urls: list, base_url: str) -> int:
    """Start server, open browser tabs.  Returns number of tabs opened."""
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtGui import QDesktopServices

    port = _free_port()
    login_url = base_url.rstrip("/") + "/accounts/login/?next=/"

    _Handler.url_map = {str(i): url for i, url in enumerate(enketo_urls)}
    _Handler.login_url = login_url
    _Handler.served = set()

    server = socketserver.TCPServer(("localhost", port), _Handler)
    server.allow_reuse_address = True
    _Handler.server_ref = server

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Safety shutdown after 60 s
    def _watchdog():
        import time
        time.sleep(60)
        server.shutdown()

    threading.Thread(target=_watchdog, daemon=True).start()

    for i in range(len(enketo_urls)):
        QDesktopServices.openUrl(QUrl(f"http://localhost:{port}/{i}"))

    return len(enketo_urls)
