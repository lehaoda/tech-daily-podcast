#!/usr/bin/env python3
"""生成播客封面 3000x3000 (需 pillow): ~/projects/tech-daily-podcast/.venv/bin/python pipeline/make_cover.py"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 3000
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def vgradient(size, top, bottom):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=c)
    return img


def main():
    img = vgradient(SIZE, (10, 16, 34), (16, 30, 60))
    d = ImageDraw.Draw(img)

    # 光晕
    glow = Image.new("L", (SIZE, SIZE), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([400, 300, 2600, 2500], fill=90)
    glow = glow.filter(__import__("PIL.ImageFilter", fromlist=["ImageFilter"]).GaussianBlur(500))
    cyan = Image.new("RGB", (SIZE, SIZE), (32, 190, 220))
    img = Image.composite(cyan, img, glow)
    d = ImageDraw.Draw(img)

    bold = lambda s: ImageFont.truetype(FONT, s, index=1)
    reg = lambda s: ImageFont.truetype(FONT, s, index=0)

    # 顶部标签
    tag = "TECH DAILY PODCAST"
    d.text((340, 520), tag, font=reg(92), fill=(94, 215, 235))
    d.rectangle([340, 660, 1160, 672], fill=(94, 215, 235))

    # 主标题
    d.text((330, 880), "科技早报", font=bold(640), fill=(248, 250, 255))

    # 副标题
    d.text((345, 1720), "每日 5 分钟 · Adam 的科技 AI 早间谈话", font=reg(118), fill=(165, 180, 205))

    # 声波 bars
    import random
    random.seed(7)
    import math
    x0, y_base, w, gap = 345, 2520, 68, 24
    n = 26
    colors = [(32, 190, 220), (140, 110, 245)]
    for i in range(n):
        h = 120 + int(200 * abs(math.sin(i * 0.9 + 1.3))) + (300 if i in (9, 10, 11, 14, 15) else 0)
        t = i / (n - 1)
        col = tuple(int(colors[0][k] + (colors[1][k] - colors[0][k]) * t) for k in range(3))
        x = x0 + i * (w + gap)
        d.rounded_rectangle([x, y_base - h, x + w, y_base], radius=40, fill=col)

    # 底部信息
    d.text((345, 2620), "主播 Adam    |    每天早上 7 点更新",
           font=reg(84), fill=(120, 138, 168))

    out = os.path.join(ROOT, "cover.png")
    img.save(out, optimize=True)
    print("OK", out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main()
