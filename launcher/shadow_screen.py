"""Shadow Screen launcher: serves index.html on localhost in the background and opens it
as a standalone app window (Chrome/Edge --app). Closing the window stops the server."""
import functools
import http.server
import os
import subprocess
import sys
import threading

PORT = 8765  # fixed: WebHID permissions are remembered per origin
URL = f"http://localhost:{PORT}/"
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILE = os.path.join(os.environ.get("LOCALAPPDATA", BASE), "ShadowScreen", "browser")

BROWSERS = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass  # windowed exe has no stderr

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def find_browser():
    for p in BROWSERS:
        p = os.path.expandvars(p)
        if os.path.isfile(p):
            return p
    return None


def open_window(browser):
    return subprocess.Popen([
        browser, f"--app={URL}", f"--user-data-dir={PROFILE}",
        "--window-size=1320,900", "--no-first-run", "--no-default-browser-check",
    ])


def main():
    browser = find_browser()
    if not browser:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, "Instale o Google Chrome ou o Microsoft Edge.", "Shadow Screen", 0x10)
        return

    handler = functools.partial(QuietHandler, directory=BASE)
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    except OSError:
        # Another instance already serves the page: just bring up a window.
        open_window(browser)
        return

    threading.Thread(target=server.serve_forever, daemon=True).start()
    open_window(browser).wait()
    server.shutdown()


if __name__ == "__main__":
    main()
