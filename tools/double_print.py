#!/usr/bin/env python3
"""Prepare a two-pass ("double print") job for the Canon TC-20M roll or any cut sheet.

  double_print.py --first background.jpg --second black_art.png --out-prefix poster
  double_print.py --first bg.jpg --second fg.png --first-ink 0.45 --offset-x 0.04 --offset-y -0.03

Writes <prefix>.layer1.pdf (colour, faded toward white) and <prefix>.layer2.pdf (black, full strength).
Both pages are the SAME size, with the artwork placed identically and registration crosses at the same
spots, so the crosses of pass 2 land on those of pass 1 only if the paper is re-registered exactly. The
distance between the two crosses is your misregistration; scan it with `tonecal.py`-style tools or just look.

This script only prepares files. It sends nothing to a printer (use --print-cmd to see the lp lines).
Retracting/re-feeding the paper between the passes is a manual procedure on the TC-20M; see README.
"""
import argparse, os, shlex, sys
from PIL import Image, ImageDraw, ImageOps

Image.MAX_IMAGE_PIXELS = None


def fit(img, box_w, box_h, mode):
    if mode == "cover":
        return ImageOps.fit(img, (box_w, box_h), Image.LANCZOS)
    img = img.copy(); img.thumbnail((box_w, box_h), Image.LANCZOS)
    return img


def cross(d, x, y, arm, width, color):
    d.line([x - arm, y, x + arm, y], fill=color, width=width)
    d.line([x, y - arm, x, y + arm], fill=color, width=width)
    d.ellipse([x - arm // 2, y - arm // 2, x + arm // 2, y + arm // 2], outline=color, width=width)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--first", required=True, help="background / first-pass image (colour)")
    p.add_argument("--second", required=True, help="foreground / second-pass image (printed in black)")
    p.add_argument("--width", type=float, default=24.0, help="page width in inches (24 = roll width)")
    p.add_argument("--height", type=float, help="page height in inches (default: from the first image's aspect)")
    p.add_argument("--margin", type=float, default=1.0, help="white margin around the artwork, inches (marks sit inside it)")
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--fit", choices=["cover", "contain"], default="cover")
    p.add_argument("--first-ink", type=float, default=0.5, help="0-1; fades the first pass toward white (lighter ink)")
    p.add_argument("--second-contrast", type=float, default=1.0, help=">1 pushes the second pass toward solid black")
    p.add_argument("--offset-x", type=float, default=0.0, help="deliberate shift of pass 2 art, inches (+ = right)")
    p.add_argument("--offset-y", type=float, default=0.0, help="deliberate shift of pass 2 art, inches (+ = down)")
    p.add_argument("--no-marks", action="store_true")
    p.add_argument("--out-prefix", default="double")
    p.add_argument("--print-cmd", action="store_true", help="show the lp commands (nothing is sent)")
    p.add_argument("--queue", default="TC-20M")
    a = p.parse_args()

    dpi = a.dpi
    first = Image.open(a.first).convert("RGB")
    box_w = int(round((a.width - 2 * a.margin) * dpi))
    height_in = a.height if a.height else (a.width - 2 * a.margin) * first.height / first.width + 2 * a.margin
    box_h = int(round((height_in - 2 * a.margin) * dpi))
    W, H = int(round(a.width * dpi)), int(round(height_in * dpi))
    w_pt, h_pt = round(a.width * 72), round(height_in * 72)
    roll = w_pt >= 842                       # wider than A3 can only come from the roll
    if roll and not (576 <= h_pt <= 11338 and w_pt <= 1728):
        sys.exit("Roll page %dx%d pt is outside the TC-20M's range (842-1728 wide, 576-11338 tall)." % (w_pt, h_pt))
    if not roll and not (595 <= w_pt <= 842 and h_pt <= 1225):
        sys.exit("Sheet %dx%d pt is outside the cassette's range (8.27-11.69 in wide, up to 17.01 in long)." % (w_pt, h_pt))
    ox, oy = int(round(a.margin * dpi)), int(round(a.margin * dpi))

    # pass 1: colour, faded toward white (lighter ink)
    l1 = Image.new("RGB", (W, H), "white")
    art1 = fit(first, box_w, box_h, a.fit)
    art1 = Image.blend(Image.new("RGB", art1.size, "white"), art1, max(0.0, min(1.0, a.first_ink)))
    l1.paste(art1, (ox + (box_w - art1.width) // 2, oy + (box_h - art1.height) // 2))

    # pass 2: black art on white; optional contrast push and deliberate offset
    l2 = Image.new("RGB", (W, H), "white")
    art2 = fit(Image.open(a.second).convert("L"), box_w, box_h, a.fit)
    if a.second_contrast != 1.0:
        art2 = art2.point(lambda v: max(0, min(255, int(128 + (v - 128) * a.second_contrast))))
    dx, dy = int(round(a.offset_x * dpi)), int(round(a.offset_y * dpi))
    l2.paste(Image.merge("RGB", (art2,) * 3), (ox + (box_w - art2.width) // 2 + dx, oy + (box_h - art2.height) // 2 + dy))

    if not a.no_marks:
        arm, wd = int(0.18 * dpi), max(2, dpi // 100)
        m = int(round(a.margin * dpi / 2))
        pts = [(m, m), (W - m, m), (m, H - m), (W - m, H - m), (W // 2, m), (W // 2, H - m)]
        d1, d2 = ImageDraw.Draw(l1), ImageDraw.Draw(l2)
        for x, y in pts:
            cross(d1, x, y, arm, wd, (0, 170, 220))     # pass 1 marks: cyan
            cross(d2, x, y, arm, wd, (0, 0, 0))         # pass 2 marks: black, same spots
    out1, out2 = a.out_prefix + ".layer1.pdf", a.out_prefix + ".layer2.pdf"
    l1.save(out1, resolution=dpi); l2.save(out2, resolution=dpi)
    print("page %.2f x %.2f in (%d x %d pt) at %d dpi" % (a.width, height_in, w_pt, h_pt, dpi))
    print("pass 1: %s  (ink %.0f%%)   pass 2: %s" % (out1, a.first_ink * 100, out2))
    if a.print_cmd:
        size = "Letter" if (w_pt, h_pt) == (612, 792) else "Custom.%dx%d" % (w_pt, h_pt)
        base = ["lp", "-d", a.queue, "-o", "PageSize=" + size, "-o", "InputSlot=" + ("Auto" if roll else "Main"),
                "-o", "MediaType=Stationery", "-o", "cupsPrintQuality=High", "-o", "ColorModel=RGB",
                "-o", "print-scaling=none"]
        print("pass 1:", " ".join(shlex.quote(c) for c in base + ["-o", "CutMedia=None", out1]))
        print("pass 2:", " ".join(shlex.quote(c) for c in base + ["-o", "CutMedia=Auto", out2]))


if __name__ == "__main__":
    main()
