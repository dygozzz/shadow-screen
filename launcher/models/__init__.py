"""Supported keyboards.

Each model is a module exposing:
  ID, NAME            short id and display name
  VID, PID            USB ids of the keyboard (used for detection)
  WIDTH, HEIGHT       screen resolution in pixels
  MAX_FRAMES          how many frames the keyboard can store
  SECONDS_PER_FRAME   rough upload time per frame (for the ETA)
  PREVIEW             "rgb565" or "rgb888": how the page simulates the screen's colors
  is_connected()      True when the keyboard's screen interface is present
  upload(frames_rgb, interval_ms, progress)
                      frames_rgb is a list of raw RGB888 frames (WIDTH*HEIGHT*3 bytes),
                      progress(done, total) may be called while sending

To add a keyboard, create a module next to shadow_s.py and list it in MODELS below.
See docs/ADICIONAR-TECLADO.md.
"""
from . import shadow_s

MODELS = [shadow_s]


def find_connected():
    for m in MODELS:
        if m.is_connected():
            return m
    return None


def is_supported(vid, pid):
    return any((m.VID, m.PID) == (vid, pid) for m in MODELS)


def info(m):
    return {
        "id": m.ID, "name": m.NAME, "width": m.WIDTH, "height": m.HEIGHT,
        "maxFrames": m.MAX_FRAMES, "secondsPerFrame": m.SECONDS_PER_FRAME, "preview": m.PREVIEW,
    }
