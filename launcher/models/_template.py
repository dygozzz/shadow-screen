"""TEMPLATE for a new keyboard. Copy to e.g. rt85.py, fill in, and add it to MODELS in
__init__.py. See docs/ADICIONAR-TECLADO.md and shadow_s.py for a complete example.
"""
import hid

ID = "rt85"                      # short id, no spaces
NAME = "EPOMAKER RT85"           # shown in the app
VID, PID = 0x0000, 0x0000        # from tools/list_devices.py
USAGE_PAGE = 0xFF00              # the vendor-defined interface the official tool talks to
WIDTH, HEIGHT = 0, 0             # screen resolution
MAX_FRAMES = 1                   # how many frames the keyboard stores (be conservative)
SECONDS_PER_FRAME = 1.0          # measure after the first successful upload
PREVIEW = "rgb565"               # "rgb565" if the screen uses 16-bit color, else "rgb888"


def is_connected():
    return any(d["usage_page"] == USAGE_PAGE for d in hid.enumerate(VID, PID))


def upload(frames_rgb, interval_ms, progress=None):
    """frames_rgb: list of raw RGB888 frames (WIDTH*HEIGHT*3 bytes each), already framed by the app.

    Encode each frame the way the keyboard expects and send the same packets the official tool
    sends (same order, sizes and pauses). Raise an exception on any unexpected reply, since the
    app shows its message to the user. Call progress(done, total) now and then.
    """
    raise NotImplementedError("protocol not implemented yet")
