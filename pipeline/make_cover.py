#!/usr/bin/env python3
"""生成播客封面 3000x3000 (需 pillow): ~/projects/tech-daily-podcast/.venv/bin/python pipeline/make_cover.py
设计: 深色底 + 光晕; 书法"乐"字 logo(项目根 logo.png, 青→紫渐变) + 节目名「乐见未来」+ 声波条。"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 3000
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
CYAN = (32, 190, 220)
VIOLET = (140, 110, 245)


def vgradient(size, top, bottom):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=c)
    return img


def tint_logo(logo, h_target, c0, c1):
    """logo(黑墨+alpha) 染成竖直渐变 c0→c1, 高缩放到 h_target"""
    w = round(logo.width * h_target / logo.height)
    lg = logo.resize((w, h_target), Image.LANCZOS)
    grad = Image.new("RGB", (w, h_target))
    gd = ImageDraw.Draw(grad)
    for y in range(h_target):
        t = y / max(1, h_target - 1)
        col = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
        gd.line([(0, y), (w, y)], fill=col)
    out = Image.new("RGBA", (w, h_target), (0, 0, 0, 0))
    out.paste(grad, (0, 0), lg.getchannel("A"))
    return out


def main():
    img = vgradient(SIZE, (10, 16, 34), (16, 30, 60))

    # 光晕
    glow = Image.new("L", (SIZE, SIZE), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([400, 200, 2600, 2400], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(500))
    img = Image.composite(Image.new("RGB", (SIZE, SIZE), CYAN), img, glow)
    d = ImageDraw.Draw(img)

    bold = lambda s: ImageFont.truetype(FONT, s, index=1)
    reg = lambda s: ImageFont.truetype(FONT, s, index=0)

    # logo「乐」— 左上, 青→紫渐变
    logo = Image.open(os.path.join(ROOT, "logo.png"))
    tinted = tint_logo(logo, 640, CYAN, VIOLET)
    img.paste(tinted, (345, 330), tinted)
    d = ImageDraw.Draw(img)

    # 节目名
    d.text((330, 1080), "乐见未来", font=bold(500), fill=(248, 250, 255))

    # 副标题
    d.text((345, 1730), "每日 5 分钟 · Adam 的科技 AI 早间谈话", font=reg(108), fill=(165, 180, 205))

    # 声波 bars
    x0, y_base, bw, gap = 345, 2420, 68, 24
    n = 26
    for i in range(n):
        h = 110 + int(170 * abs(math.sin(i * 0.9 + 1.3))) + (280 if i in (9, 10, 11, 14, 15) else 0)
        t = i / (n - 1)
        col = tuple(int(CYAN[k] + (VIOLET[k] - CYAN[k]) * t) for k in range(3))
        x = x0 + i * (bw + gap)
        d.rounded_rectangle([x, y_base - h, x + bw, y_base], radius=34, fill=col)

    # 底部信息
    d.text((345, 2560), "主播 Adam    |    每天早上 7 点更新",
           font=reg(84), fill=(120, 138, 168))

    out = os.path.join(ROOT, "cover.png")
    img.save(out, optimize=True)
    print("OK", out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main()
