"""Shadow Screen launcher.

Serves index.html on localhost in the background, talks to the keyboard itself over HID
(/api/status, /api/upload) and opens the page in a frameless pywebview window with the app's
own title bar. Falls back to a Chrome/Edge --app window when pywebview isn't installed, and
the page falls back to WebHID when hidapi isn't installed.
"""
import functools
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models  # noqa: E402

try:
    import hid  # noqa: F401
    HAS_HID = True
except ImportError:
    HAS_HID = False

PORT = 8765  # fixed: WebHID permissions (browser fallback) are remembered per origin
URL = f"http://localhost:{PORT}/"
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILE = os.path.join(os.environ.get("LOCALAPPDATA", BASE), "ShadowScreen", "browser")
CONFLICTS = {"via.exe": "VIA", "image custom tool.exe": "Image Custom Tool", "epomaker driver v4.exe": "EPOMAKER Driver"}

BROWSERS = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
]

# ---------- Keyboard side ----------
job = {"phase": "idle", "done": 0, "total": 0, "error": None}
upload_lock = threading.Lock()
_conflicts = {"t": 0.0, "names": []}


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.05):
            return True
    except OSError:
        return False


def running_conflicts():
    """Apps that share the keyboard's HID interface (cached for 2 s; tasklist is slowish)."""
    if time.time() - _conflicts["t"] > 2:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
        names = {line.split('","')[0].strip('"').lower() for line in out.splitlines() if line}
        found = {v for k, v in CONFLICTS.items() if k in names}
        if port_open(3838):  # EPOMAKER Driver v4's HID service (Rongyuan), which can lock the device
            found.add("EPOMAKER Driver")
        _conflicts.update(t=time.time(), names=sorted(found))
    return _conflicts["names"]


_others = {"t": 0.0, "names": []}


def unsupported_devices():
    """Other EPOMAKER devices that are plugged in (e.g. models we don't support yet).

    Matched by name, not vendor id: chip vendors like Evision (320F) also make mice etc."""
    if time.time() - _others["t"] > 2:
        names = set()
        for d in hid.enumerate():
            if models.is_supported(d["vendor_id"], d["product_id"]):
                continue
            name = (d.get("product_string") or "").strip()
            maker = (d.get("manufacturer_string") or "").strip()
            if "epomaker" in (name + " " + maker).lower():
                names.add(name or f"{d['vendor_id']:04X}:{d['product_id']:04X}")
        _others.update(t=time.time(), names=sorted(names))
    return _others["names"]


def run_upload(model, blob, n, interval):
    try:
        size = model.WIDTH * model.HEIGHT * 3
        frames = [blob[k * size:(k + 1) * size] for k in range(n)]
        model.upload(frames, interval, progress=lambda i, total: job.update(done=i, total=total))
        job.update(phase="done")
    except Exception as e:  # reported to the page
        job.update(phase="error", error=str(e))
    finally:
        upload_lock.release()


# ---------- HTTP ----------
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass  # windowed app has no stderr

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/"):
            if not HAS_HID:
                return self.send_error(404)
            if self.path.startswith("/api/status"):
                model = models.find_connected()
                return self.send_json({
                    "connected": model is not None, "model": models.info(model) if model else None,
                    "conflicts": running_conflicts(), "job": job,
                    "unsupported": [] if model else unsupported_devices(),
                })
            return self.send_error(404)
        super().do_GET()

    def do_POST(self):
        if not (HAS_HID and self.path.startswith("/api/upload")):
            return self.send_error(404)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            n, interval, model_id = int(q["frames"][0]), int(q["interval"][0]), q["model"][0]
            length = int(self.headers["Content-Length"])
        except (KeyError, ValueError):
            return self.send_json({"error": "invalid parameters"}, 400)
        model = models.find_connected()
        if model is None or model.ID != model_id:
            return self.send_json({"error": "keyboard not connected"}, 409)
        frame_size = model.WIDTH * model.HEIGHT * 3
        lo, hi = getattr(model, "MIN_INTERVAL_MS", 10), getattr(model, "MAX_INTERVAL_MS", 60000)
        if not (1 <= n <= model.MAX_FRAMES and lo <= interval <= hi and length == n * frame_size):
            return self.send_json({"error": "invalid parameters"}, 400)
        blob = self.rfile.read(length)
        if not upload_lock.acquire(blocking=False):
            return self.send_json({"error": "an upload is already running"}, 409)
        job.update(phase="sending", done=0, total=0, error=None)
        threading.Thread(target=run_upload, args=(model, blob, n, interval), daemon=True).start()
        self.send_json({"ok": True}, 202)


# ---------- Window ----------
class WindowApi:
    """Called from the page's custom title bar (window.pywebview.api)."""

    def __init__(self):
        self.window = None
        self.maximized = False

    def minimize(self):
        self.window.minimize()

    def toggle_maximize(self):
        if self.maximized:
            self.window.restore()
        else:
            self.window.maximize()
        self.maximized = not self.maximized
        return self.maximized

    def close(self):
        self.window.destroy()


def find_browser():
    for p in BROWSERS:
        p = os.path.expandvars(p)
        if os.path.isfile(p):
            return p
    return None


def open_browser_window():
    browser = find_browser()
    if not browser:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, "Instale o Google Chrome ou o Microsoft Edge.", "Shadow Screen", 0x10)
        return None
    return subprocess.Popen([
        browser, f"--app={URL}", f"--user-data-dir={PROFILE}",
        "--window-size=1320,900", "--no-first-run", "--no-default-browser-check",
    ])


def open_app_window():
    """Frameless pywebview window; returns False if pywebview isn't available."""
    try:
        import webview
    except ImportError:
        return False
    api = WindowApi()
    api.window = webview.create_window(
        "Shadow Screen", URL, js_api=api, width=1320, height=900, min_size=(900, 640),
        frameless=True, easy_drag=False, background_color="#0a0b0e",
    )
    webview.start(private_mode=False, storage_path=os.path.join(PROFILE, "..", "webview"))
    return True


def main():
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Handler, directory=BASE))
    except OSError:
        server = None  # another instance already serves the page; just open a window

    if server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    if not open_app_window():
        proc = open_browser_window()
        if proc and server:
            proc.wait()
    if server:
        server.shutdown()


if __name__ == "__main__":
    main()
