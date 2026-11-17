#!/usr/bin/env python3
"""番組の絵 cover.jpg（1400×1400、Podcast アプリに出る）を作る。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
S = 1400
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

img = Image.new("RGB", (S, S), "#17543f")
d = ImageDraw.Draw(img)
# 右下から広がる電波
cx, cy = 1160, 1160
for r in range(170, 620, 130):
    d.arc((cx - r, cy - r, cx + r, cy + r), 180, 270, fill="#3f8a6c", width=46)
d.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), fill="#f2c14e")

big = ImageFont.truetype(FONT, 210)
d.text((120, 190), "English", font=big, fill="white")
d.text((120, 420), "Radio", font=big, fill="#f2c14e")
img.save(ROOT / "cover.jpg", quality=90)
print("cover.jpg")
