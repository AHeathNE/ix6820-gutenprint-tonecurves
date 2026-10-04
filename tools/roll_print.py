#!/usr/bin/env python3
"""Print an image (poster/photo) on the Canon TC-20M roll at its true size.

  roll_print.py poster.jpg                      # builds poster.roll.pdf and prints the lp command
  roll_print.py poster.jpg --print              # ...and sends it
  roll_print.py poster.jpg --width 24 --margin 0.5 --dpi 200 --print

Why this exists: the TC-20M picks its paper source from the page size and ignores InputSlot and
media-source from CUPS, and CUPS rescales raster images unpredictably (a 300 dpi PNG came out ~1.44x
too big). A PDF whose page is exactly the roll width and printed with --print-scaling=none avoids both.
The page is wider than A3, so the filter also selects the `<queue>.roll.<quality>` curve.
"""
import argparse, os, shlex, subprocess, sys
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image")
    p.add_argument("--queue", default="TC-20M")
    p.add_argument("--width", type=float, default=24.0, help="roll width in inches (24 for the TC-20M)")
    p.add_argument("--margin", type=float, default=0.25, help="white margin in inches (printer minimum is ~0.2)")
    p.add_argument("--dpi", type=int, default=300, help="render resolution; 200 halves the file size")
    p.add_argument("--quality", default="High", choices=["Draft", "Normal", "High"])
    p.add_argument("--media-type", default="Stationery")
    p.add_argument("--cut", action="store_true", default=True, help="cut after the page (default)")
    p.add_argument("--no-cut", dest="cut", action="store_false")
    p.add_argument("--out", help="PDF path (default: next to the image)")
    p.add_argument("--print", action="store_true", help="send it to the printer")
    a = p.parse_args()

    img = Image.open(a.image).convert("RGB")
    usable_w = a.width - 2 * a.margin
    px_w = int(round(usable_w * a.dpi))
    px_h = int(round(img.height * px_w / img.width))
    img = img.resize((px_w, px_h), Image.LANCZOS)
    page_h_in = px_h / a.dpi + 2 * a.margin
    w_pt, h_pt = round(a.width * 72), round(page_h_in * 72)
    # limits from the TC-20M PPD: width 842-1728 pt, height 576-11338 pt
    if not (842 <= w_pt <= 1728 and 576 <= h_pt <= 11338):
        sys.exit("Page %dx%d pt is outside the printer's range (842-1728 wide, 576-11338 tall)." % (w_pt, h_pt))
    page = Image.new("RGB", (int(round(a.width * a.dpi)), int(round(page_h_in * a.dpi))), "white")
    page.paste(img, (int(round(a.margin * a.dpi)), int(round(a.margin * a.dpi))))
    out = a.out or os.path.splitext(a.image)[0] + ".roll.pdf"
    page.save(out, resolution=a.dpi)
    cmd = ["lp", "-d", a.queue, "-o", "PageSize=Custom.%dx%d" % (w_pt, h_pt), "-o", "InputSlot=Auto",
           "-o", "MediaType=" + a.media_type, "-o", "cupsPrintQuality=" + a.quality, "-o", "ColorModel=RGB",
           "-o", "CutMedia=" + ("Auto" if a.cut else "None"), "-o", "print-scaling=none", "-t", os.path.basename(a.image), out]
    print("page: %.2f x %.2f in (%d x %d pt), image %.2f in wide; wrote %s" % (a.width, page_h_in, w_pt, h_pt, usable_w, out))
    print("roll used: about %.1f in (%.2f ft)" % (page_h_in, page_h_in / 12))
    print(" ".join(shlex.quote(c) for c in cmd))
    if a.print:
        sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
