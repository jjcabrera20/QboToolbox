"""
One-shot local HTTP server that serves a professional loading page then
redirects the browser to obtain the Enketo edit URL using its OWN session.

Why: Python-obtained Enketo tokens load the form but lack submission-edit
permissions — resulting in 403 on "Enviar".  Browser-obtained tokens carry
full user permissions.  We route the browser through:

  {base_url}/accounts/login/?next=/api/v2/assets/{uid}/data/{id}/enketo/edit/?return_url=false

Since the user is already logged in, KoboToolbox skips the login page and
redirects the browser directly to the JSON containing the Enketo URL.
Modern browsers (Chrome, Firefox, Edge) render the URL as a clickable link
— one click opens the form and submission works.
"""

import http.server
import socket
import socketserver
import threading
import urllib.parse


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _loading_page(redirect_url: str) -> str:
    safe = redirect_url.replace("'", "%27")
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
.card{{background:#fff;border-radius:12px;padding:48px 40px;
       text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.09);
       max-width:400px;width:90%}}
h1{{font-size:20px;color:#1a1a2e;margin-bottom:10px}}
p{{color:#666;font-size:14px;line-height:1.6;margin-bottom:6px}}
.note{{color:#999;font-size:12px;margin-top:16px}}
.spinner{{width:36px;height:36px;border:3px solid #e0e0e0;
          border-top-color:#0078d4;border-radius:50%;
          animation:spin .8s linear infinite;margin:16px auto}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style>
</head>
<body>
<div class="card">
  <h1>Opening Webform</h1>
  <p>Redirecting to KoboToolbox…</p>
  <div class="spinner"></div>
  <p class="note">You are already logged in — KoboToolbox will show a<br>
  link to your form. Click it to open and edit the record.</p>
</div>
<script>setTimeout(function(){{window.location.replace('{safe}');}}, 800);</script>
</body>
</html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    items = []        # list of (uid, kobo_id)
    base_url = ""
    served = set()
    server_ref = None

    def do_GET(self):
        path = self.path.strip("/").split("?")[0]
        try:
            idx = int(path)
        except ValueError:
            idx = 0

        if idx < len(_Handler.items):
            uid, kobo_id = _Handler.items[idx]
            next_path = (
                f"/api/v2/assets/{uid}/data/{int(kobo_id)}"
                f"/enketo/edit/?return_url=false"
            )
            redirect_url = (
                _Handler.base_url.rstrip("/")
                + "/accounts/login/?next="
                + urllib.parse.quote(next_path, safe="/?=&")
            )
        else:
            redirect_url = _Handler.base_url.rstrip("/") + "/"

        page = _loading_page(redirect_url)
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

        _Handler.served.add(idx)
        if len(_Handler.served) >= len(_Handler.items):
            threading.Thread(target=_Handler.server_ref.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass


def launch(features: list, base_url: str) -> int:
    """Open one browser tab per (uid, kobo_id) pair.

    Each tab shows a loading page then redirects the browser through
    KoboToolbox's login flow so the browser — not Python — obtains the
    Enketo token with full submission-edit permissions.

    Returns the number of tabs opened.
    """
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtGui import QDesktopServices

    if not features:
        return 0

    port = _free_port()

    _Handler.items = features
    _Handler.base_url = base_url
    _Handler.served = set()

    server = socketserver.TCPServer(("localhost", port), _Handler)
    server.allow_reuse_address = True
    _Handler.server_ref = server

    threading.Thread(target=server.serve_forever, daemon=True).start()

    def _watchdog():
        import time
        time.sleep(60)
        server.shutdown()

    threading.Thread(target=_watchdog, daemon=True).start()

    for i in range(len(features)):
        QDesktopServices.openUrl(QUrl(f"http://localhost:{port}/{i}"))

    return len(features)
