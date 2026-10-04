#!/usr/bin/env python3
"""Calibrate a per-paper tone curve for the tone-curve CUPS filter.

  tonecal.py chart  out.png --label "Sheet A: Kraft, Plain curve v1"
  tonecal.py measure scan.png
  tonecal.py fit scan.png --current curves/Plain.json --out curves/MyPaper.json [--paper-relative]

Workflow: print out.png through the queue (lp -d QUEUE -o media=Letter -o fit-to-page out.png), let
it dry, scan at 300 dpi colour (Letter, no enhancement, face down), then `measure` / `fit`.
`fit` composes the new curve with --current (the curve that was active when the sheet was printed;
omit it if the queue had no curve) so you can iterate: print, scan, fit, install, repeat.

Chart geometry is fixed. Where it lands on your scan is found automatically from the black block
(it varies by printer margins and scaling). Override with --scale/--ox/--oy and check the sampling
boxes with `measure --overlay check.png`.
"""
import argparse, json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 2550, 3300                       # Letter at 300 dpi
RAMP_N, STRIP_N = 21, 24
RAMP = dict(x0=150, y0=1940, step=110, w=105, h=140)
STRIP = dict(x0=150, y0=350, step=94, w=90, h=150)
BLOCK = (150, 2200, 1250, 2800)
PHOTO_BOX = (150, 560, 2400, 1860)
BLANK = (200, 3000, 2000, 3200)         # unprinted area, in scan pixels, used for paper colour


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/", ""):
        try:
            return ImageFont.truetype(d + name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def synthetic_photo(w, h):
    """Low-key test image with shadows, mids, highlights and saturated colour."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    base = 25 + 200 * (x / w) ** 1.5
    img = np.stack([base, base * 0.95, base * 0.9], axis=-1) * (0.35 + 0.65 * (y / h)[..., None])
    rng = np.random.default_rng(1)
    for _ in range(40):
        cx, cy, r = rng.integers(0, w), rng.integers(0, h), rng.integers(60, 220)
        col = rng.choice(4)
        c = [(230, 40, 30), (30, 160, 70), (40, 80, 220), (240, 200, 40)][col]
        m = ((x - cx) ** 2 + (y - cy) ** 2) < r ** 2
        img[m] = 0.5 * img[m] + 0.5 * np.array(c)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def make_chart(out, label, photo=None):
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((150, 100), label.split("|")[0], font=font(54, True), fill="black")
    d.text((150, 180), "|".join(label.split("|")[1:]) or "", font=font(30), fill="black")
    d.text((150, 310), "Shadow detail (can you see every step?)", font=font(24), fill="black")
    for i in range(STRIP_N):
        v = int(i * 60 / (STRIP_N - 1))
        x = STRIP["x0"] + i * STRIP["step"]
        d.rectangle([x, STRIP["y0"], x + STRIP["w"], STRIP["y0"] + STRIP["h"]], fill=(v, v, v))
    pw, ph = PHOTO_BOX[2] - PHOTO_BOX[0], PHOTO_BOX[3] - PHOTO_BOX[1]
    if photo:
        from PIL import ImageOps
        pic = ImageOps.fit(Image.open(photo).convert("RGB"), (pw, ph))
    else:
        pic = synthetic_photo(pw, ph)
    im.paste(pic, PHOTO_BOX[:2])
    d.text((150, 1900), "Gray 0-100%", font=font(24), fill="black")
    for i in range(RAMP_N):
        v = int(255 - i * 255 / (RAMP_N - 1))
        x = RAMP["x0"] + i * RAMP["step"]
        d.rectangle([x, RAMP["y0"], x + RAMP["w"], RAMP["y0"] + RAMP["h"]], fill=(v, v, v))
    d.rectangle(BLOCK, fill="black")
    d.text((180, 2230), "Small white text on solid black: bleed check 0123456789", font=font(24), fill="white")
    d.text((180, 2290), "The quick brown fox jumps over the lazy dog", font=font(30), fill="white")
    d.text((1350, 2230), "Small black text: bleed check", font=font(24), fill="black")
    d.text((1350, 2290), "The quick brown fox jumps over the lazy dog", font=font(30), fill="black")
    im.save(out, dpi=(300, 300))


def auto_register(im):
    """Find where the chart landed on the scan by locating the black block.
    Returns (scale, ox, oy) for the mapping scan_px = scale * chart_px + offset."""
    g = im.mean(axis=2)
    dark = (g < 60)[2000:3100, 0:1500]
    rows = np.where(dark.mean(axis=1) > 0.5)[0]
    cols = np.where(dark.mean(axis=0) > 0.5)[0]
    if len(rows) < 100 or len(cols) < 100:
        return None
    y0, y1, x0, x1 = rows.min() + 2000, rows.max() + 2000, cols.min(), cols.max()
    kx, ky = (x1 - x0) / (BLOCK[2] - BLOCK[0]), (y1 - y0) / (BLOCK[3] - BLOCK[1])
    k = (kx + ky) / 2
    return k, x0 - k * BLOCK[0], y0 - k * BLOCK[1]


class Scan:
    def __init__(self, path, scale=None, ox=None, oy=None):
        self.im = np.asarray(Image.open(path).convert("RGB")).astype(float)
        if scale is None:
            reg = auto_register(self.im)
            if reg is None:
                print("warning: could not locate the black block; using defaults 0.969/27.6/37", file=sys.stderr)
                reg = (0.969, 27.6, 37.0)
            scale, ox, oy = reg
        self.k, self.ox, self.oy = scale, ox, oy

    def cell(self, x0, y0, w, h, pad=8):
        k, ox, oy = self.k, self.ox, self.oy
        c = self.im[int(k * y0 + oy + pad):int(k * (y0 + h) + oy - pad),
                    int(k * x0 + ox + pad):int(k * (x0 + w) + ox - pad)]
        return c.reshape(-1, 3).mean(0)

    def ramp(self):
        t = np.array([255 - i * 255 / (RAMP_N - 1) for i in range(RAMP_N)])[::-1]      # ascending input
        r = np.array([self.cell(RAMP["x0"] + i * RAMP["step"], RAMP["y0"], RAMP["w"], RAMP["h"])
                      for i in range(RAMP_N)])[::-1]
        return t, r

    def strip(self):
        return np.array([self.cell(STRIP["x0"] + i * STRIP["step"], STRIP["y0"], STRIP["w"], STRIP["h"])
                         for i in range(STRIP_N)])

    def paper(self):
        x0, y0, x1, y1 = BLANK
        return self.im[y0:y1, x0:x1].reshape(-1, 3).mean(0)


def cmd_measure(a):
    s = Scan(a.scan, a.scale, a.ox, a.oy)
    t, r = s.ramp()
    paper = s.paper()
    print("registration: scale %.3f offset %.1f,%.1f" % (s.k, s.ox, s.oy))
    print("paper colour (unprinted area): R%.0f G%.0f B%.0f" % tuple(paper))
    print("input   R    G    B   R-B   %of paper (G)")
    for ti, ri in zip(t[::-1], r[::-1]):
        print("%5.0f %4.0f %4.0f %4.0f %+5.0f   %5.0f%%" % (ti, *ri, ri[0] - ri[2], 100 * ri[1] / paper[1]))
    print("shadow strip (mean):", " ".join("%.0f" % v for v in s.strip().mean(axis=1)))
    if a.overlay:
        im = Image.open(a.scan).convert("RGB"); d = ImageDraw.Draw(im)
        for g, n in ((RAMP, RAMP_N), (STRIP, STRIP_N)):
            for i in range(n):
                x0 = g["x0"] + i * g["step"]
                d.rectangle([s.k * x0 + s.ox, s.k * g["y0"] + s.oy,
                             s.k * (x0 + g["w"]) + s.ox, s.k * (g["y0"] + g["h"]) + s.oy], outline=(255, 0, 0), width=4)
        im.save(a.overlay); print("wrote", a.overlay)


def cmd_fit(a):
    s = Scan(a.scan, a.scale, a.ox, a.oy)
    t, r = s.ramp()
    paper = s.paper()
    x = np.arange(256)
    cur = json.load(open(a.current)) if a.current else {c: list(range(256)) for c in "rgb"}
    f = a.floor
    phi = np.minimum(np.sqrt(x ** 2 + f ** 2) / 255.0, 1.0)         # soft-knee target, literal values
    top = paper if a.paper_relative else np.full(3, 254.0)
    out = {}
    for c, n in enumerate("rgb"):
        want = top[c] * phi
        resp = np.maximum.accumulate(r[:, c]) + np.arange(RAMP_N) * 1e-2    # monotone response of raw input
        resp[-1] = max(resp[-1], top[c])
        tp = np.interp(want, resp, t)
        tp[0] = 0
        tp = np.maximum.accumulate(tp)
        out[n] = np.interp(tp, x, np.array(cur[n], float))
    g = out["g"]
    for n in "rb":                                                  # keep channels from diverging wildly
        out[n] = np.clip(out[n], g - a.clamp, g + a.clamp)
    for n in "rgb":
        v = np.convolve(np.pad(out[n], 3, mode="edge"), np.ones(7) / 7, mode="valid")
        v[0], v[255] = 0, 255
        out[n] = [int(round(q)) for q in np.clip(np.maximum.accumulate(v), 0, 255)]
    out["comment"] = a.comment or "fit from %s" % a.scan
    json.dump({"comment": out.pop("comment"), **out}, open(a.out, "w"))
    print("wrote", a.out)
    for i in (0, 3, 10, 25, 60, 100, 128, 160, 200, 230, 255):
        print("  in %3d -> R%3d G%3d B%3d" % (i, out["r"][i], out["g"][i], out["b"][i]))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("chart"); c.add_argument("out"); c.add_argument("--label", default="Test sheet | settings")
    c.add_argument("--photo", help="optional photo for the photo area (default: synthetic)")
    for name in ("measure", "fit"):
        m = sub.add_parser(name); m.add_argument("scan")
        m.add_argument("--scale", type=float, help="override auto-registration")
        m.add_argument("--ox", type=float); m.add_argument("--oy", type=float)
        if name == "measure":
            m.add_argument("--overlay", help="write an image showing where cells are sampled")
        else:
            m.add_argument("--current", help="curve JSON that was active when the sheet was printed")
            m.add_argument("--out", required=True)
            m.add_argument("--floor", type=float, default=13.0, help="soft-knee floor (the paper's black level)")
            m.add_argument("--paper-relative", action="store_true", help="aim for fractions of the paper colour (kraft, tinted stock)")
            m.add_argument("--clamp", type=float, default=14.0, help="max R/B deviation from G in curve (levels)")
            m.add_argument("--comment")
    a = p.parse_args()
    {"chart": lambda: make_chart(a.out, a.label, a.photo), "measure": lambda: cmd_measure(a), "fit": lambda: cmd_fit(a)}[a.cmd]()


if __name__ == "__main__":
    main()
