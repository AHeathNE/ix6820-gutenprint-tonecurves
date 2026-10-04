# Canon PIXMA iX6820 (and imagePROGRAF TC-20M) on Linux: tone curves for CUPS

Photos printing **far too dark** on a Canon PIXMA iX6820 (iX6800 series) under Linux, with shadow detail
lost? This repo is a small CUPS filter plus measured tone curves that fix it, and a calibration tool
so you can make curves for your own paper. It also works on the **driverless (IPP Everywhere) Canon
imagePROGRAF TC-20M**, which showed the same crushed shadows (see below).

## The problem

The iX6820 works on Linux through [Gutenprint](https://gutenprint.sourceforge.io/) (`iX6800-series`). Canon's
own Linux driver does not cover it. Gutenprint's tone response on this printer is steeply S-shaped,
and none of its built-in controls (density, gamma, ink limit, image type, colour correction) can
straighten it. Measured with a flatbed scanner, on plain paper at the defaults:

* every input below ~25% brightness prints at the same near-black, so shadows are lost;
* the top ~5% clips into paper white;
* the midtones carry a warm cast.

Gamma and density only slide the middle of the curve, so no combination of them fixes both ends.

## The fix

`rastertogutenprint-curve` is a CUPS filter that sits in front of Gutenprint's raster filter. It applies a
256-entry lookup table per R/G/B channel to the page raster, then hands the result to the stock
`rastertogutenprint.*`. The curves are the inverse of the measured response, so the printed tones
follow the input. Everything stays driver-side, so it works from the browser, GIMP, LibreOffice,
whatever prints.

One curve per CUPS queue, so each paper gets its own queue (and its own ink settings):

| Curve file | Paper | Notes |
|---|---|---|
| `Plain.json` | plain paper | baseline Density 600, Gamma 1800, Black 700, Photo |
| `iX6820-Cardstock.json` | Hammermill Premium 110 lb cardstock | same ink settings as plain |
| `iX6820-Sticker.json` | Koala inkjet vinyl sticker paper, glossy (white, and the clear one) | MediaType GlossyPaperStandard, Density 500, Gamma 1800, Black 600 |
| `iX6820-Kraft.json` | Naturalabel kraft sticker paper | targets fractions of the paper's own colour |
| `TC-20M.High.json` | imagePROGRAF TC-20M, plain copy paper from the cassette, High quality | driverless queue, see below |
| `TC-20M.roll.High.json` | imagePROGRAF TC-20M, 20 lb bright copy paper on the roll, High quality | used automatically for pages wider than A3 |

See [docs/RESULTS.md](docs/RESULTS.md) for before/after measurements. **These curves are for the author's
printer, ink and paper batches.** They should be a good starting point for the same papers, but
for anything else use the calibration tool below.

## Install

Requirements: CUPS 2.4, `printer-driver-gutenprint` (the iX6800 model), Python 3 with NumPy and Pillow.

```bash
sudo ./install.sh                     # filter + curves; changes no queue
sudo ./add-queue.sh iX6820-Plain "iX6820 plain" Plain 600 1800 700
sudo ./add-queue.sh iX6820-Sticker "iX6820 sticker" GlossyPaperStandard 500 1800 600
```

`add-queue.sh <queue> "<description>" <MediaType> <Density> <Gamma> <Black> [InkLimit]` creates a
Gutenprint queue on the first iX68xx it finds on USB (override with `URI=usb://...`), points its PPD
at the filter, and sets the defaults. The curve used is `curves/<queue>.json`, else
`curves/<MediaType>.json`, else none (pass-through). Pick the queue that matches the paper in the tray.

Uninstall with `sudo ./uninstall.sh` and `lpadmin -x <queue>`.

## Driverless printers (Canon TC-20M)

Printers that take URF/PWG raster over IPP Everywhere have no Gutenprint step, so the same file is
installed as `rastertopwg-curve` and wraps CUPS's raster-to-URF filter instead.

```bash
sudo ./install.sh
sudo ./patch-ipp-queue.sh TC-20M High      # an existing driverless queue; sets the default quality
```

`patch-ipp-queue.sh` adds one `*cupsFilter2` line to the queue's PPD and removes the printer's JPEG
pass-through (which would otherwise skip the curve). Curves are looked up as `<queue>.<quality>.json`
(for example `TC-20M.High.json`), then `<queue>.json`, then `<MediaType>.json`. Quality modes behave
very differently on this printer, so each gets its own curve; Normal has none and passes through.

### Printing on the TC-20M roll

The TC-20M chooses its paper source from the **page size** and ignores `InputSlot` and `media-source` from
CUPS: a Letter job came out of the cassette even with the roll selected. And CUPS renders raster images
(a 300 dpi PNG with `scaling=100`) at an unpredictable size (about 1.44x too big here). The reliable way is a
PDF whose page is exactly the roll width, printed with `print-scaling=none`:

```bash
python3 tools/roll_print.py poster.jpg --print            # fits the image to the 24 in roll and prints
python3 tools/roll_print.py poster.jpg --dpi 200          # just build the PDF and show the lp command
```

Pages whose shorter side is wider than A3 can only come from the roll, so the filter then uses
`<queue>.roll.<quality>.json` (falling back to the cassette curve). The roll paper took ink less darkly than the
cassette paper: the cassette curve left roll shadows 15-25 levels too light, so it has its own curve.

### USB printers stop answering after suspend

A suspend/resume resets the USB bus and `ipp-usb` keeps stale handles, so USB IPP printers and scanners
(Canon TC-20M, Brother MFC) stop answering until it is restarted. `contrib/ipp-usb-resume-restart` is a
systemd-sleep hook that restarts it on resume:

```bash
sudo install -m 755 contrib/ipp-usb-resume-restart /usr/lib/systemd/system-sleep/ipp-usb-resume-restart
```

(`sudo systemctl restart ipp-usb` fixes it by hand. Connecting the printer over the network avoids it entirely.)

## Calibrate your own paper

```bash
python3 tools/tonecal.py chart sheetA.png --label "SHEET A|MyPaper, no curve"
lp -d MyQueue -o media=Letter -o fit-to-page sheetA.png
# let it dry, scan: 300 dpi, colour, Letter, no auto-enhance, face down
python3 tools/tonecal.py measure scanA.png --overlay check.png   # confirm the red boxes sit on the patches
python3 tools/tonecal.py fit scanA.png --out curves/MyQueue.json # add --current <curve> when iterating
sudo ./install.sh                                                  # then reprint, rescan, refit once more
```

Use `--paper-relative` for tinted stock (kraft) and `--floor` for the paper's black level. Measure
vinyl only after it has fully dried, because it keeps darkening for hours. The chart's geometry is fixed. The
default scan registration (scale 0.969, offset 27.6/37 px) is what a CUPS fit-to-page Letter print
gives on the author's scanner. If your boxes are off, adjust `--scale/--ox/--oy`.

## Caveats

* Tested on one machine: Linux Mint, CUPS 2.4.7, Gutenprint 5.3.4, iX6820 and TC-20M over USB. Not tested elsewhere.
* Check the printer first. A TC-20M with dead colour heads printed monochrome with blown highlights, which looked
  like a tone problem and was not. Run the printer's own nozzle check before calibrating anything.
* Scanner response is assumed neutral. Absolute numbers are scanner values, not colorimetric.
* Sheet-to-sheet variation on plain paper was about 5-10 levels in the midtones.
* Queues built from PPDs depend on CUPS "printer drivers", which CUPS has said it will drop in a future
  release. The filter itself works on the raster stream and does not care.
* Nothing here changes saturation. Saturated reds print duller than on screen; that is a gamut limit.
* SELinux/AppArmor may block a Python filter on some distributions. Check the CUPS error log first.

## License

MIT. Gutenprint is GPL and is not included.
