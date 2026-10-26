"""EPOMAKER RT85 (wired, 3151:5002) screen protocol, read from EPOMAKER Driver v4 3.2.31
(Rongyuan "yc3123_ss_sn001" keyboard class: getTFTLCDDataRGBImg / setTFTLCDDataRGBImg).

Transport: 64-byte feature reports, report id 0, on interface 2 (usage page 0xFFFF, usage 2).
Every packet carries a checksum at byte 7: 0xFF - (sum(bytes 0..6) & 0xFF) ("Bit7").

Upload (GIF of N frames, one header for the whole animation):
  0xA5 header [A5, 0, N, delay, len&FF, (len>>8)&FF, 0, ck, l, t, r, b, l>>8, t>>8, r>>8, b>>8,
               (len>>16)&FF, (len>>24)&FF, gif_layer]   -> reply[1] == 1 means accepted
  0x25 data   [25, frame, N, delay, idx&FF, idx>>8, n<=56, ck, 56 data bytes] per 56-byte chunk,
              chunk index restarting at 0 for every frame, no reply
A single frame goes to still-image slot 0 instead (header/data with frame=slot, N=1, delay=0).

Pixels: RGB565 big-endian, column-major (x outer, y inner), bounding box (l, t, r, b), r/b
exclusive; we always send the full 320x172 box.

The PID 0x5002 is shared by ~100 Rongyuan keyboards, so the firmware id (command 0x8F, reply
bytes 1..4 little-endian) must be 2895 before anything else is sent. Only 0x8F, 0xA5 and 0x25
are ever sent: the same firmware also has bootloader, reset and flash-erase commands.
"""
import struct
import time

import hid

ID = "rt85"
NAME = "EPOMAKER RT85"
VID, PID = 0x3151, 0x5002
IFACE, USAGE_PAGE, USAGE = 2, 0xFFFF, 2
FIRMWARE_ID = 2895
WIDTH, HEIGHT = 320, 172
FRAME_BYTES = WIDTH * HEIGHT * 2
CHUNK = 56
MAX_FRAMES = 51          # the vendor app's limit: 6 MiB flash / 110592 bytes per frame, minus 5 slots
MIN_INTERVAL_MS, MAX_INTERVAL_MS = 1, 255  # frame delay is a single byte
SECONDS_PER_FRAME = 8.0  # ~1966 packets per frame with a 2 ms gap; refine after real uploads
PREVIEW = "rgb565"

CMD_WHO_AM_I, CMD_LCD_HEADER, CMD_LCD_DATA = 0x8F, 0xA5, 0x25
ALLOWED = {CMD_WHO_AM_I, CMD_LCD_HEADER, CMD_LCD_DATA}
PACKET_GAP_S = 0.002     # vendor app: electronUploadPacketDelay default 2 ms


def packet(payload):
    p = bytearray(payload).ljust(64, b"\x00")
    if p[0] not in ALLOWED:
        raise ValueError(f"refusing to send command {p[0]:#04x} to the RT85")
    p[7] = (0xFF - (sum(p[:7]) & 0xFF)) & 0xFF
    return bytes(p)


def find_path():
    for d in hid.enumerate(VID, PID):
        if d["interface_number"] == IFACE and d["usage_page"] == USAGE_PAGE and d["usage"] == USAGE:
            return d["path"]
    return None


class Keyboard:
    def __init__(self, path=None):
        path = path or find_path()
        if path is None:
            raise RuntimeError("RT85 screen interface not found (plugged in by USB cable?)")
        self.dev = hid.device()
        self.dev.open_path(path)

    def close(self):
        self.dev.close()

    def send(self, payload, delay_s=0.010):
        time.sleep(delay_s)
        if self.dev.send_feature_report(b"\x00" + packet(payload)) < 0:
            raise IOError(f"failed to send command {payload[0]:#04x}")

    def read(self, delay_s=0.010):
        time.sleep(delay_s)
        r = bytes(self.dev.get_feature_report(0, 65))
        return r[1:] if len(r) == 65 else r

    def firmware_id(self):
        for _ in range(3):
            self.send(bytes([CMD_WHO_AM_I]))
            r = self.read()
            if len(r) >= 5 and r[0] == CMD_WHO_AM_I:
                return struct.unpack_from("<I", r, 1)[0]
            time.sleep(0.5)
        return None

    def header(self, frame, n_frames, delay, length, box=(0, 0, WIDTH, HEIGHT), gif_layer=0):
        l, t, r, b = box
        p = bytearray(64)
        p[0:4] = bytes([CMD_LCD_HEADER, frame, n_frames, delay])
        p[4], p[5] = length & 0xFF, (length >> 8) & 0xFF
        p[8:12] = bytes([l & 0xFF, t & 0xFF, r & 0xFF, b & 0xFF])
        p[12:16] = bytes([l >> 8, t >> 8, r >> 8, b >> 8])
        p[16], p[17], p[18] = (length >> 16) & 0xFF, (length >> 24) & 0xFF, gif_layer
        for _ in range(11):  # first try + 10 retries, like the vendor app
            self.send(p, 0.010)
            reply = self.read(0.100)
            if len(reply) > 1 and reply[1] == 1:
                time.sleep(0.1)
                return
            time.sleep(0.1)
        raise RuntimeError("the RT85 did not accept the image header")

    def frame(self, frame, n_frames, delay, data, progress=None):
        chunks = (len(data) + CHUNK - 1) // CHUNK
        for i in range(chunks):
            c = data[i * CHUNK:(i + 1) * CHUNK]
            self.send(bytes([CMD_LCD_DATA, frame, n_frames, delay, i & 0xFF, i >> 8, len(c), 0]) + c, PACKET_GAP_S)
            if progress and i % 64 == 0:
                progress(i)


def rgb_to_565_columns(rgb):
    """Raw RGB888 (WIDTH*HEIGHT*3, row-major) -> RGB565 big-endian in column-major order."""
    out = bytearray(FRAME_BYTES)
    o = 0
    for x in range(WIDTH):
        for y in range(HEIGHT):
            i = 3 * (y * WIDTH + x)
            v = ((rgb[i] >> 3) << 11) | ((rgb[i + 1] >> 2) << 5) | (rgb[i + 2] >> 3)
            out[o] = v >> 8
            out[o + 1] = v & 0xFF
            o += 2
    return bytes(out)


# ---------- Model interface ----------
_identity = {}  # device path -> (time checked, is RT85)


def is_connected():
    path = find_path()
    if path is None:
        return False
    checked = _identity.get(path)
    # The id is stable per device; failures are re-checked after a few seconds.
    if checked is None or (not checked[1] and time.time() - checked[0] > 5):
        try:
            kb = Keyboard(path)
            try:
                ok = kb.firmware_id() == FIRMWARE_ID
            finally:
                kb.close()
        except Exception:
            ok = False
        _identity[path] = (time.time(), ok)
    return _identity[path][1]


def upload(frames_rgb, interval_ms, progress=None):
    n = len(frames_rgb)
    if not 1 <= n <= MAX_FRAMES:
        raise ValueError(f"the RT85 takes 1 to {MAX_FRAMES} frames")
    delay = max(MIN_INTERVAL_MS, min(MAX_INTERVAL_MS, interval_ms))
    frames = [rgb_to_565_columns(f) for f in frames_rgb]
    chunks = (FRAME_BYTES + CHUNK - 1) // CHUNK
    total = n * chunks

    kb = Keyboard()
    try:
        if kb.firmware_id() != FIRMWARE_ID:
            raise RuntimeError("this keyboard is not an RT85 (firmware id mismatch); nothing was sent")
        if n == 1:
            # Still image: slot 0, like the vendor app does for single-frame images.
            kb.header(0, 1, 0, FRAME_BYTES)
            kb.frame(0, 1, 0, frames[0], progress and (lambda i: progress(i, total)))
        else:
            kb.header(0, n, delay, FRAME_BYTES)
            for k, data in enumerate(frames):
                kb.frame(k, n, delay, data, progress and (lambda i, k=k: progress(k * chunks + i, total)))
        if progress:
            progress(total, total)
    finally:
        kb.close()
