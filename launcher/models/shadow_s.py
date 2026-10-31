"""Epomaker Shadow-S (USB, 320F:5055) screen protocol, reverse-engineered from Image Custom Tool.

Packet (64 bytes, HID report 0x04 on interface MI_03):
  [0x04][sum16 LE of bytes 3..63][cmd][len][addr24 LE][payload...]

Model interface (see models/__init__.py): ID, NAME, VID, PID, WIDTH, HEIGHT, MAX_FRAMES,
SECONDS_PER_FRAME, PREVIEW, is_connected() and upload(frames_rgb, interval_ms, progress).
"""
import datetime
import time

ID = "shadow-s"
NAME = "EPOMAKER Shadow-S"
VID, PID, IFACE = 0x320F, 0x5055, 3
W, H = 240, 135
WIDTH, HEIGHT = W, H
FRAME_BYTES = W * H * 2
FRAME_STRIDE = 0x10000
CHUNK = 56
MAX_FRAMES = 50
SECONDS_PER_FRAME = 2.4  # ~1171 packets per 64 KB frame at ~2 ms each
PREVIEW = "rgb565"  # how the page should simulate the screen's colors

CMD_BEGIN, CMD_END = 0x01, 0x02
CMD_CFG_READ, CMD_CFG_WRITE = 0x05, 0x06
CMD_DATA, CMD_PREPARE = 0x21, 0x23

CFG_FRAMES, CFG_CLOCK, CFG_INTERVAL = 34, 35, 43


def packet(cmd, length=0, addr=0, payload=b""):
    body = bytes([cmd, length, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF]) + payload
    body = body.ljust(61, b"\x00")
    s = sum(body) & 0xFFFF
    return bytes([0x04, s & 0xFF, s >> 8]) + body


def bcd(n):
    return ((n // 10) << 4) | (n % 10)


def build_config(base, n_frames, interval_ms, now=None):
    now = now or datetime.datetime.now()
    cfg = bytearray(base)
    cfg[CFG_FRAMES] = n_frames
    cfg[CFG_CLOCK : CFG_CLOCK + 7] = bytes(
        [bcd(now.second), bcd(now.minute), bcd(now.hour), now.isoweekday() % 7,
         bcd(now.day), bcd(now.month), bcd(now.year % 100)]
    )
    cfg[CFG_INTERVAL] = interval_ms & 0xFF
    cfg[CFG_INTERVAL + 1] = (interval_ms >> 8) & 0xFF
    return bytes(cfg)


def rgb565_be(img):
    """PIL RGB image 240x135 -> big-endian RGB565 bytes."""
    out = bytearray(FRAME_BYTES)
    for i, (r, g, b) in enumerate(img.getdata()):
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        out[2 * i] = v >> 8
        out[2 * i + 1] = v & 0xFF
    return bytes(out)


def rgb_to_565_be(rgb):
    """Raw RGB888 bytes (W*H*3) -> big-endian RGB565 bytes."""
    out = bytearray(FRAME_BYTES)
    for i in range(W * H):
        r, g, b = rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2]
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        out[2 * i] = v >> 8
        out[2 * i + 1] = v & 0xFF
    return bytes(out)


def image_blob(frames_565):
    blob = bytearray()
    for f in frames_565:
        blob += f.ljust(FRAME_STRIDE, b"\x00")
    return bytes(blob)


def data_packets(blob):
    for addr in range(0, len(blob), CHUNK):
        chunk = blob[addr : addr + CHUNK]
        yield packet(CMD_DATA, len(chunk), addr, chunk)


class Keyboard:
    def __init__(self):
        import hid

        path = next(
            (d["path"] for d in hid.enumerate(VID, PID) if d["interface_number"] == IFACE), None
        )
        if path is None:
            raise RuntimeError("Shadow-S screen interface not found (is it plugged in?)")
        self.dev = hid.device()
        self.dev.open_path(path)

    def close(self):
        self.dev.close()

    def xfer(self, pkt, timeout_ms=3000):
        self.dev.write(pkt)
        reply = bytes(self.dev.read(64, timeout_ms))
        if not reply:
            raise TimeoutError(f"no reply to cmd {pkt[3]:#04x}")
        return reply

    def read_config(self):
        self.xfer(packet(CMD_CFG_READ, 1, 0))
        cfg = bytearray()
        for addr in range(0, 48, 4):
            cfg += self.xfer(packet(CMD_CFG_READ, 4, addr))[4:8]
        return bytes(cfg)

    def set_clock(self):
        """Rewrite the config block with the PC's date/time, keeping frame count and interval.
        The official tool sends this same begin/config/end sequence when only settings change."""
        self.xfer(packet(CMD_BEGIN))
        base = self.read_config()
        self.xfer(packet(CMD_BEGIN))
        cfg = build_config(base, base[CFG_FRAMES], base[CFG_INTERVAL] | (base[CFG_INTERVAL + 1] << 8))
        self.xfer(packet(CMD_CFG_WRITE, len(cfg), 0, cfg))
        self.xfer(packet(CMD_END))

    def upload(self, frames_565, interval_ms, progress=None):
        assert 1 <= len(frames_565) <= MAX_FRAMES
        self.xfer(packet(CMD_BEGIN))
        base = self.read_config()
        self.xfer(packet(CMD_BEGIN))
        cfg = build_config(base, len(frames_565), interval_ms)
        self.xfer(packet(CMD_CFG_WRITE, len(cfg), 0, cfg))
        self.xfer(packet(CMD_END))
        self.xfer(packet(CMD_PREPARE), timeout_ms=60000)
        pkts = list(data_packets(image_blob(frames_565)))
        for i, p in enumerate(pkts):
            reply = self.xfer(p)
            if reply[:8] != p[:8]:
                raise RuntimeError(f"bad ack at packet {i}: {reply[:8].hex()} != {p[:8].hex()}")
            if i == 0:
                time.sleep(0.5)  # official tool pauses here after the first chunk
            if progress and i % 64 == 0:
                progress(i, len(pkts))
        self.xfer(packet(CMD_END))
        if progress:
            progress(len(pkts), len(pkts))


# ---------- Model interface ----------
def is_connected():
    import hid

    return any(d["interface_number"] == IFACE for d in hid.enumerate(VID, PID))


def upload(frames_rgb, interval_ms, progress=None):
    """frames_rgb: list of raw RGB888 frames (WIDTH*HEIGHT*3 bytes each)."""
    kb = Keyboard()
    try:
        kb.upload([rgb_to_565_be(f) for f in frames_rgb], interval_ms, progress)
    finally:
        kb.close()


def set_clock():
    kb = Keyboard()
    try:
        kb.set_clock()
    finally:
        kb.close()
