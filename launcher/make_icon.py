"""Draws the app icon (a tiny keyboard screen showing pixel art) as a multi-size .ico."""
import sys

from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Bezel
d.rounded_rectangle([8, 36, S - 8, S - 36], radius=44, fill=(18, 20, 26, 255), outline=(48, 52, 66, 255), width=6)
# Screen with a violet gradient
x0, y0, x1, y1 = 34, 62, S - 34, S - 62
for y in range(y0, y1):
    t = (y - y0) / (y1 - y0)
    c = (int(139 + (179 - 139) * t), int(123 + (168 - 123) * t), 255, 255)
    d.line([(x0, y), (x1, y)], fill=c)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([x0, y0, x1, y1], radius=14, fill=255)
screen = img.copy()
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([8, 36, S - 8, S - 36], radius=44, fill=(18, 20, 26, 255), outline=(48, 52, 66, 255), width=6)
img.paste(screen, (0, 0), mask)

# Pixel-art "play" glyph on the screen
d = ImageDraw.Draw(img)
p = 14
cx, cy = S // 2 - p, S // 2 - 3 * p // 2
for row, cols in enumerate([1, 2, 3, 2, 1]):
    for col in range(cols):
        x, y = cx + col * p, cy + (row - 1) * p + p // 2
        d.rectangle([x, y, x + p - 2, y + p - 2], fill=(11, 8, 32, 255))

img.save(sys.argv[1], sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", sys.argv[1])
