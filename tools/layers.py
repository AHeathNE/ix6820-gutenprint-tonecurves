#!/usr/bin/env python3
"""Prepare any number of overprint passes ("layers") for one sheet or roll page.

  layers.py spec.json                  # writes <prefix>.layerN.pdf, a stacked preview, and prints the lp commands
  layers.py --example > spec.json      # a starter spec (the four-pass Letter sheet)
  layers.py spec.json --print-layer 2  # actually send layer 2 (nothing is ever sent without this flag)

Print the layers one after another on the SAME sheet: lightest first, let it dry, put the sheet back in the
cassette the way it went in the first time, then the next layer. On the Canon TC-20M the cassette re-feed lands
within about 0.05 mm, so layers register almost perfectly; use "offset" to add misregistration on purpose.
(The TC-20M roll cannot be pulled back to re-register, so multi-pass is for cut sheets, up to 11x17.)

Spec (JSON, paths relative to the spec file):
{
  "page":  {"size": "letter"},            # or {"width": 8.5, "height": 11}; "a4", "a3", "11x17", or roll {"width": 24, "height": 16}
  "dpi": 300, "margin": 1.0, "marks": true,
  "printer": {"queue": "TC-20M", "quality": "High", "media_type": "Stationery"},
  "layers": [
    {"image": "bg.jpg", "box": [1, 1, 6.5, 9], "fit": "cover", "ink": 0.5, "mark": "cyan"},
    {"image": "type.png", "box": [1, 1, 6.5, 9], "mode": "black", "contrast": 1.4, "offset": [0.03, -0.02]},
    {"image": "bg.jpg", "crop": [1700, 0, 4300, 1300], "box": [2, 6.9, 5, 2.5], "ink": 0.5, "feather": 0.2}
  ]
}
Layer keys: image, box [x,y,w,h inches from the top-left of the page] (default: inside the margin), fit cover|contain,
crop [x0,y0,x1,y1] source pixels (or 0-1 fractions), mode color|black, ink 0-1 (fade toward white), contrast (black
mode), offset [dx,dy] inches, feather inches (soft edges), mark (cross colour: name or [r,g,b]).
"""
import argparse, json, os, shlex, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageOps

Image.MAX_IMAGE_PIXELS = None
SIZES = {"letter": (8.5, 11.0), "a4": (8.27, 11.69), "a3": (11.69, 16.54), "11x17": (11.0, 17.0), "tabloid": (11.0, 17.0)}
COLORS = {"cyan": (0, 170, 220), "black": (0, 0, 0), "magenta": (230, 0, 126), "green": (0, 170, 70),
          "orange": (255, 140, 0), "blue": (30, 60, 220), "red": (220, 30, 30), "yellow": (230, 200, 0)}
CYCLE = ["cyan", "black", "magenta", "green", "orange", "blue", "red", "yellow"]

EXAMPLE = {
    "page": {"size": "letter"}, "dpi": 300, "margin": 1.0, "marks": True,
    "printer": {"queue": "TC-20M", "quality": "High", "media_type": "Stationery"},
    "layers": [
        {"image": "photo.jpg", "box": [1, 1, 6.5, 9], "fit": "cover", "ink": 0.5, "mark": "cyan"},
        {"image": "type.png", "box": [1, 1, 6.5, 9], "mode": "black", "mark": "black"},
        {"image": "photo.jpg", "crop": [1700, 0, 4300, 1300], "box": [2.0, 6.9, 5.0, 2.5], "ink": 0.5, "feather": 0.2, "mark": "magenta"},
        {"image": "photo.jpg", "crop": [2900, 350, 4300, 1750], "box": [4.5, 1.1, 3.0, 3.0], "ink": 1.0, "mark": "green"},
    ],
}


def page_size(spec):
    p = spec.get("page", {"size": "letter"})
    if "size" in p:
        return SIZES[p["size"].lower()]
    return float(p["width"]), float(p["height"])


def check_limits(w_in, h_in):
    w, h = round(w_in * 72), round(h_in * 72)
    if w >= 842:                       # wider than A3: roll
        if not (w <= 1728 and 576 <= h <= 11338):
            sys.exit("Roll page %dx%d pt is outside the TC-20M range (842-1728 wide, 576-11338 tall)." % (w, h))
        return True
    if not (595 <= w <= 842 and h <= 1225):
        sys.exit("Sheet %dx%d pt is outside the cassette range (8.27-11.69 in wide, up to 17.01 in long)." % (w, h))
    return False


def color_of(v, idx):
    if v is None:
        v = CYCLE[idx % len(CYCLE)]
    return tuple(v) if isinstance(v, (list, tuple)) else COLORS[v.lower()]


def feather_mask(w, h, f):
    if f <= 0:
        return None
    y = np.minimum(np.arange(h), np.arange(h)[::-1])[:, None]
    x = np.minimum(np.arange(w), np.arange(w)[::-1])[None, :]
    t = np.clip(np.minimum(x, y) / float(f), 0, 1)
    t = t * t * (3 - 2 * t)             # smoothstep
    return Image.fromarray((t * 255).astype(np.uint8))


def render_layer(L, base, dpi, margin, page_px, idx, marks):
    W, H = page_px
    src = Image.open(os.path.join(base, L["image"])).convert("RGB")
    if "crop" in L:
        c = L["crop"]
        if all(0 <= v <= 1 for v in c):
            c = [c[0] * src.width, c[1] * src.height, c[2] * src.width, c[3] * src.height]
        src = src.crop(tuple(int(v) for v in c))
    bx, by, bw, bh = L.get("box", [margin, margin, W / dpi - 2 * margin, H / dpi - 2 * margin])
    bw_px, bh_px = int(round(bw * dpi)), int(round(bh * dpi))
    if L.get("fit", "cover") == "cover":
        art = ImageOps.fit(src, (bw_px, bh_px), Image.LANCZOS)
    else:
        art = src.copy(); art.thumbnail((bw_px, bh_px), Image.LANCZOS)
    if L.get("mode", "color") == "black":
        g = art.convert("L"); k = float(L.get("contrast", 1.0))
        if k != 1.0:
            g = g.point(lambda v: max(0, min(255, int(128 + (v - 128) * k))))
        art = Image.merge("RGB", (g, g, g))
    ink = max(0.0, min(1.0, float(L.get("ink", 1.0))))
    if ink < 1.0:
        art = Image.blend(Image.new("RGB", art.size, "white"), art, ink)
    mask = feather_mask(art.width, art.height, int(float(L.get("feather", 0)) * dpi))
    dx, dy = L.get("offset", [0, 0])
    px = int(round(bx * dpi + (bw_px - art.width) / 2 + dx * dpi)); py = int(round(by * dpi + (bh_px - art.height) / 2 + dy * dpi))
    page = Image.new("RGB", (W, H), "white")
    page.paste(art, (px, py), mask)
    if marks:
        col = color_of(L.get("mark"), idx); arm = int(0.18 * dpi); wd = max(2, dpi // 100); m = int(round(margin * dpi / 2))
        d = ImageDraw.Draw(page)
        for x, y in [(m, m), (W - m, m), (m, H - m), (W - m, H - m), (W // 2, m), (W // 2, H - m)]:
            d.line([x - arm, y, x + arm, y], fill=col, width=wd); d.line([x, y - arm, x, y + arm], fill=col, width=wd)
            d.ellipse([x - arm // 2, y - arm // 2, x + arm // 2, y + arm // 2], outline=col, width=wd)
    return page


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("spec", nargs="?")
    p.add_argument("--example", action="store_true", help="print an example spec and exit")
    p.add_argument("--out-prefix", help="default: the spec path without .json")
    p.add_argument("--print-layer", type=int, metavar="N", help="send layer N (1-based) to the printer")
    a = p.parse_args()
    if a.example:
        print(json.dumps(EXAMPLE, indent=2)); return
    if not a.spec:
        p.error("give a spec file, or --example")
    spec = json.load(open(a.spec)); base = os.path.dirname(os.path.abspath(a.spec))
    prefix = a.out_prefix or os.path.splitext(os.path.abspath(a.spec))[0]
    w_in, h_in = page_size(spec); dpi = int(spec.get("dpi", 300)); margin = float(spec.get("margin", 1.0))
    roll = check_limits(w_in, h_in) if spec.get("check", True) else w_in * 72 >= 842
    W, H = int(round(w_in * dpi)), int(round(h_in * dpi)); w_pt, h_pt = round(w_in * 72), round(h_in * 72)
    layers = spec["layers"]
    print("page %.2f x %.2f in (%d x %d pt), %d dpi, %s, %d layers" % (w_in, h_in, w_pt, h_pt, dpi, "ROLL" if roll else "cut sheet", len(layers)))
    pages, files = [], []
    for i, L in enumerate(layers):
        pg = render_layer(L, base, dpi, margin, (W, H), i, spec.get("marks", True))
        f = "%s.layer%d.pdf" % (prefix, i + 1); pg.save(f, resolution=dpi); pages.append(pg); files.append(f)
        print("  layer %d: %s  ink %.0f%%  %s" % (i + 1, os.path.basename(L["image"]), 100 * float(L.get("ink", 1.0)), L.get("mode", "color")))
    comp = np.ones((H // 4, W // 4, 3))                   # stacked preview: multiply, like ink on paper
    for pg in pages:
        comp *= np.asarray(pg.resize((W // 4, H // 4), Image.BILINEAR)).astype(float) / 255.0
    Image.fromarray((comp * 255).astype(np.uint8)).save(prefix + ".preview.png")
    print("preview (all layers stacked):", prefix + ".preview.png")
    pr = spec.get("printer", {})
    size = "Letter" if (w_pt, h_pt) == (612, 792) else "Custom.%dx%d" % (w_pt, h_pt)
    base_cmd = ["lp", "-d", pr.get("queue", "TC-20M"), "-o", "PageSize=" + size, "-o", "InputSlot=" + ("Auto" if roll else "Main"),
                "-o", "MediaType=" + pr.get("media_type", "Stationery"), "-o", "cupsPrintQuality=" + pr.get("quality", "High"),
                "-o", "ColorModel=RGB", "-o", "print-scaling=none", "-o", "CutMedia=" + ("Auto" if roll else "None")]
    cmds = [base_cmd + ["-t", "layer %d" % (i + 1), f] for i, f in enumerate(files)]
    for i, c in enumerate(cmds):
        print("layer %d: %s" % (i + 1, " ".join(shlex.quote(x) for x in c)))
    if roll and len(layers) > 1:
        print("WARNING: roll pages cannot be re-registered on the TC-20M (the roll is cut); multi-pass needs cut sheets.")
    if a.print_layer:
        sys.exit(subprocess.call(cmds[a.print_layer - 1]))


if __name__ == "__main__":
    main()
