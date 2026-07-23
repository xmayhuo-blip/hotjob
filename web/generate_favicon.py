#!/usr/bin/env python3
"""
Generate monkey favicon for OfferBoast.
Outputs: favicon.ico (multi-size), favicon-16x16.png, favicon-32x32.png,
         favicon-48x48.png, apple-touch-icon-180x180.png, favicon-512x512.png
"""

from PIL import Image, ImageDraw, ImageFilter
import math
import os

# ── Color palette ──
BROWN       = (155, 110, 65)   # #9B6E41 outer face & ears
BROWN_DARK  = (125,  88, 52)   # ear inner
BEIGE       = (232, 213, 183)  # #E8D5B7 muzzle
BEIGE_LIGHT = (245, 232, 210)  # highlight
EYE_BLACK   = ( 26,  26,  26)  # #1A1A1A
EYE_WHITE   = (255, 255, 255)
NOSE        = ( 92,  64,  51)  # #5C4033
MOUTH       = ( 92,  64,  51)
BLUSH       = (240, 170, 150)  # pink cheeks (subtle)

def draw_monkey(size: int) -> Image.Image:
    """Draw a monkey face icon at the given pixel size (square)."""
    # Render at 4x for anti-aliasing, then downscale
    scale = 4
    S = size * scale
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx, cy = S / 2, S / 2
    r = S * 0.38  # face radius

    # ── Ears ──
    ear_r = S * 0.16
    ear_offset = r * 0.95
    ear_y = cy - S * 0.02

    # Left ear outer
    lx, ly = cx - ear_offset, ear_y
    d.ellipse([lx - ear_r, ly - ear_r, lx + ear_r, ly + ear_r], fill=BROWN)
    # Left ear inner
    d.ellipse([lx - ear_r*0.55, ly - ear_r*0.55, lx + ear_r*0.55, ly + ear_r*0.55], fill=BROWN_DARK)

    # Right ear outer
    rx, ry = cx + ear_offset, ear_y
    d.ellipse([rx - ear_r, ry - ear_r, rx + ear_r, ry + ear_r], fill=BROWN)
    # Right ear inner
    d.ellipse([rx - ear_r*0.55, ry - ear_r*0.55, rx + ear_r*0.55, ry + ear_r*0.55], fill=BROWN_DARK)

    # ── Face (head circle) ──
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BROWN)

    # ── Muzzle (lighter lower face) ──
    muzzle_r = r * 0.72
    muzzle_cy = cy + S * 0.06
    d.ellipse(
        [cx - muzzle_r, muzzle_cy - muzzle_r * 0.85,
         cx + muzzle_r, muzzle_cy + muzzle_r * 0.85],
        fill=BEIGE
    )

    # ── Eyes ──
    eye_r = S * 0.045
    eye_offset_x = S * 0.11
    eye_y = cy - S * 0.04

    # Eye whites (subtle, only for larger sizes)
    if size >= 32:
        d.ellipse([cx - eye_offset_x - eye_r*1.3, eye_y - eye_r*1.3,
                    cx - eye_offset_x + eye_r*1.3, eye_y + eye_r*1.3], fill=EYE_WHITE)
        d.ellipse([cx + eye_offset_x - eye_r*1.3, eye_y - eye_r*1.3,
                    cx + eye_offset_x + eye_r*1.3, eye_y + eye_r*1.3], fill=EYE_WHITE)

    # Eye pupils
    d.ellipse([cx - eye_offset_x - eye_r, eye_y - eye_r,
               cx - eye_offset_x + eye_r, eye_y + eye_r], fill=EYE_BLACK)
    d.ellipse([cx + eye_offset_x - eye_r, eye_y - eye_r,
               cx + eye_offset_x + eye_r, eye_y + eye_r], fill=EYE_BLACK)

    # Eye highlights (for larger sizes)
    if size >= 48:
        hr = eye_r * 0.35
        d.ellipse([cx - eye_offset_x + eye_r*0.3 - hr, eye_y - eye_r*0.3 - hr,
                   cx - eye_offset_x + eye_r*0.3 + hr, eye_y - eye_r*0.3 + hr], fill=EYE_WHITE)
        d.ellipse([cx + eye_offset_x + eye_r*0.3 - hr, eye_y - eye_r*0.3 - hr,
                   cx + eye_offset_x + eye_r*0.3 + hr, eye_y - eye_r*0.3 + hr], fill=EYE_WHITE)

    # ── Nose ──
    nose_w = S * 0.05
    nose_h = S * 0.035
    nose_y = cy + S * 0.05
    d.ellipse([cx - nose_w, nose_y - nose_h, cx + nose_w, nose_y + nose_h], fill=NOSE)

    # ── Mouth (smile arc) ──
    mouth_y = cy + S * 0.11
    mouth_w = S * 0.09
    if size >= 32:
        # Draw smile as two nostrils + arc
        d.arc([cx - mouth_w, mouth_y - mouth_w * 0.5,
               cx + mouth_w, mouth_y + mouth_w * 0.8],
              start=20, end=160, fill=MOUTH, width=max(1, int(S * 0.012)))
    else:
        # Simple line for tiny sizes
        d.line([cx - mouth_w * 0.7, mouth_y, cx + mouth_w * 0.7, mouth_y],
               fill=MOUTH, width=max(1, int(S * 0.02)))

    # ── Cheeks (blush, only for larger sizes) ──
    if size >= 64:
        blush_r = S * 0.05
        blush_alpha = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        bd = ImageDraw.Draw(blush_alpha)
        bd.ellipse([cx - S*0.22 - blush_r, cy + S*0.02 - blush_r,
                    cx - S*0.22 + blush_r, cy + S*0.02 + blush_r],
                   fill=(*BLUSH, 80))
        bd.ellipse([cx + S*0.22 - blush_r, cy + S*0.02 - blush_r,
                    cx + S*0.22 + blush_r, cy + S*0.02 + blush_r],
                   fill=(*BLUSH, 80))
        img = Image.alpha_composite(img, blush_alpha)

    # Downscale with anti-aliasing
    img = img.resize((size, size), Image.LANCZOS)
    return img


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    sizes = [16, 32, 48, 180, 512]
    images = {}

    for s in sizes:
        img = draw_monkey(s)
        img.save(os.path.join(out_dir, f"favicon-{s}x{s}.png"))
        images[s] = img
        print(f"  ✓ favicon-{s}x{s}.png")

    # Apple touch icon (180x180 with white background)
    apple = Image.new("RGBA", (180, 180), (255, 255, 255, 255))
    apple.paste(draw_monkey(180), (0, 0), draw_monkey(180))
    apple.save(os.path.join(out_dir, "apple-touch-icon.png"))
    print("  ✓ apple-touch-icon.png")

    # favicon.ico (multi-resolution: 16, 32, 48)
    ico_images = [images[16], images[32], images[48]]
    images[16].save(
        os.path.join(out_dir, "favicon.ico"),
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=[images[32], images[48]]
    )
    print("  ✓ favicon.ico (16+32+48)")

    # Also save a large preview
    preview = draw_monkey(256)
    preview.save(os.path.join(out_dir, "favicon-preview.png"))
    print("  ✓ favicon-preview.png (256x256)")

    print(f"\nAll files saved to: {out_dir}")


if __name__ == "__main__":
    main()
