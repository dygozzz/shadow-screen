"""First hardware test: upload 3 new solid colors + a 'OK' frame at 300 ms."""
import os
import sys
import time

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "launcher"))
import shadow  # noqa: E402

frames = []
for c in [(255, 0, 255), (0, 255, 255), (255, 255, 0)]:
    frames.append(Image.new("RGB", (shadow.W, shadow.H), c))
f = Image.new("RGB", (shadow.W, shadow.H), (0, 0, 0))
d = ImageDraw.Draw(f)
for y in range(0, shadow.H, 15):
    for x in range(0, shadow.W, 15):
        if (x // 15 + y // 15) % 2 == 0:
            d.rectangle([x, y, x + 14, y + 14], fill=(255, 128, 0))
frames.append(f)

kb = shadow.Keyboard()
print("config before:", kb.read_config().hex())
t = time.time()
kb.upload([shadow.rgb565_be(x) for x in frames], 300,
          progress=lambda i, n: print(f"  {i}/{n}", flush=True) if i % 1024 == 0 or i == n else None)
print(f"done in {time.time() - t:.1f}s")
print("config after: ", kb.read_config().hex())
kb.close()
