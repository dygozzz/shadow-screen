"""Builds a GIF with known colors to decode a screen's pixel format from a capture.

Usage: python make_test_gif.py out.gif [WIDTH HEIGHT]   (default 240 135)

Frames: solid red, solid green, solid blue, then left half white / right half black with a
red 8x8 square in the top-left corner (reveals pixel order and orientation).
"""
import sys

from PIL import Image, ImageDraw

out = sys.argv[1]
W, H = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) >= 4 else (240, 135)

frames = [Image.new("RGB", (W, H), c) for c in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]]
f = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(f)
d.rectangle([0, 0, W // 2 - 1, H - 1], fill=(255, 255, 255))
d.rectangle([0, 0, 7, 7], fill=(255, 0, 0))
frames.append(f)

frames[0].save(out, save_all=True, append_images=frames[1:], duration=500, loop=0)
print(f"wrote {out} ({W}x{H}, 4 frames, 500 ms)")
