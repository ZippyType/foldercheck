#!/usr/bin/env python3
"""Generate the FolderCheck app icon in .icns, .ico, and .png form.

Draws two overlapping folder shapes with a check mark on a rounded gradient
tile. Uses only Pillow (plus macOS `iconutil` for the .icns).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


HERE = Path(__file__).resolve().parent
OUT = HERE / "icon"
OUT.mkdir(exist_ok=True)


# ---- palette ----
BG_TOP = (46, 128, 237)      # blue
BG_BOT = (28, 78, 173)
FOLDER_BACK = (255, 202, 92)   # amber
FOLDER_BACK_EDGE = (198, 148, 40)
FOLDER_FRONT = (255, 236, 179)  # cream
FOLDER_FRONT_EDGE = (198, 168, 80)
CHECK = (58, 176, 92)
CHECK_EDGE = (33, 120, 60)
SHADOW = (0, 0, 0, 90)


def rounded_gradient(size: int, radius_frac: float = 0.22) -> Image.Image:
    """Rounded-corner vertical gradient tile."""
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        r = round(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        grad.putpixel((0, y), (r, g, b))
    grad = grad.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    r = int(size * radius_frac)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=255)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def folder_polygon(size: int, x: int, y: int, w: int, h: int,
                   tab_w: int, tab_h: int, tab_off: int = 0) -> list[tuple[int, int]]:
    """Folder outline with a tab on top."""
    return [
        (x + tab_off, y + tab_h),
        (x + tab_off + int(tab_w * 0.15), y),
        (x + tab_off + tab_w, y),
        (x + tab_off + tab_w + int(tab_w * 0.10), y + tab_h),
        (x + w, y + tab_h),
        (x + w, y + h),
        (x, y + h),
        (x, y + tab_h),
    ]


def draw_shadow(layer: Image.Image, poly, blur: int = 8, offset=(0, 6)) -> None:
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.polygon([(x + offset[0], y + offset[1]) for x, y in poly], fill=SHADOW)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    layer.alpha_composite(shadow)


def render(size: int) -> Image.Image:
    S = size
    img = rounded_gradient(S)

    # subtle highlight bar near the top
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hd.rounded_rectangle((int(S * 0.08), int(S * 0.08),
                          int(S * 0.92), int(S * 0.32)),
                         radius=int(S * 0.14), fill=(255, 255, 255, 22))
    img.alpha_composite(hl)

    d = ImageDraw.Draw(img)

    # ---- back folder (amber) ----
    bw, bh = int(S * 0.62), int(S * 0.50)
    bx, by = int(S * 0.10), int(S * 0.28)
    tab_w, tab_h = int(bw * 0.42), int(S * 0.06)
    back = folder_polygon(S, bx, by, bw, bh, tab_w, tab_h, tab_off=int(bw * 0.06))
    draw_shadow(img, back, blur=int(S * 0.03), offset=(0, int(S * 0.02)))
    d.polygon(back, fill=FOLDER_BACK, outline=FOLDER_BACK_EDGE, width=max(2, S // 128))

    # ---- front folder (cream), overlapping bottom-right ----
    fw, fh = int(S * 0.62), int(S * 0.46)
    fx, fy = int(S * 0.30), int(S * 0.42)
    ftab_w, ftab_h = int(fw * 0.38), int(S * 0.055)
    front = folder_polygon(S, fx, fy, fw, fh, ftab_w, ftab_h, tab_off=int(fw * 0.08))
    draw_shadow(img, front, blur=int(S * 0.035), offset=(0, int(S * 0.025)))
    d.polygon(front, fill=FOLDER_FRONT, outline=FOLDER_FRONT_EDGE, width=max(2, S // 128))

    # thin lip on front folder
    lip_y = fy + ftab_h + int(S * 0.04)
    d.line([(fx + int(S * 0.03), lip_y), (fx + fw - int(S * 0.03), lip_y)],
           fill=FOLDER_FRONT_EDGE, width=max(1, S // 256))

    # ---- check mark badge in bottom-right ----
    cx, cy = int(S * 0.72), int(S * 0.72)
    cr = int(S * 0.18)
    d.ellipse((cx - cr, cy - cr, cx + cr, cy + cr),
              fill=CHECK, outline=CHECK_EDGE, width=max(2, S // 96))
    # the check itself
    stroke = max(3, S // 32)
    p1 = (cx - int(cr * 0.55), cy + int(cr * 0.05))
    p2 = (cx - int(cr * 0.10), cy + int(cr * 0.45))
    p3 = (cx + int(cr * 0.55), cy - int(cr * 0.35))
    d.line([p1, p2], fill=(255, 255, 255), width=stroke)
    d.line([p2, p3], fill=(255, 255, 255), width=stroke)

    return img


def write_png(size: int) -> Path:
    p = OUT / f"icon_{size}.png"
    render(size).save(p, "PNG")
    return p


def build_icns() -> Path:
    """Create icon.icns on macOS via iconutil."""
    iconset = OUT / "FolderCheck.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()

    # Apple's required sizes.
    plan = [
        (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
    ]
    for size, name in plan:
        render(size).save(iconset / name, "PNG")

    out = OUT / "FolderCheck.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    shutil.rmtree(iconset)
    return out


def build_ico() -> Path:
    """Multi-size Windows .ico."""
    p = OUT / "FolderCheck.ico"
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = render(256)
    base.save(p, format="ICO", sizes=[(s, s) for s in sizes])
    return p


def build_master_png() -> Path:
    """1024-px PNG for Linux / generic use."""
    p = OUT / "FolderCheck.png"
    render(1024).save(p, "PNG")
    return p


def main() -> None:
    icns = None
    if sys.platform == "darwin" and shutil.which("iconutil"):
        icns = build_icns()
    ico = build_ico()
    png = build_master_png()
    print("Wrote:")
    if icns:
        print(f"  {icns}")
    print(f"  {ico}")
    print(f"  {png}")


if __name__ == "__main__":
    main()
