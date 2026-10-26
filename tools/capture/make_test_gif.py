"""Build a 240x135 GIF with known colors to decode the pixel format from a capture."""
import sys

from PIL import Image, ImageDraw

W, H = 240, 135
frames = []
for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
    frames.append(Image.new("RGB", (W, H), color))

# Frame 4: left half white / right half black, plus a red top-left 8x8 marker
# to reveal pixel order and orientation.
f = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(f)
d.rectangle([0, 0, W // 2 - 1, H - 1], fill=(255, 255, 255))
d.rectangle([0, 0, 7, 7], fill=(255, 0, 0))
frames.append(f)

frames[0].save(sys.argv[1], save_all=True, append_images=frames[1:], duration=500, loop=0)
print("wrote", sys.argv[1])
