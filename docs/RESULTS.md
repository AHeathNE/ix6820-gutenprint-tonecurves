# Measured results

Method: print a chart (21-step gray ramp, 24-step shadow strip, black block, photo) through each queue,
scan on a flatbed at 300 dpi, read the mean RGB of each patch. Numbers are scanner values (0-255).
"Target" is the soft-knee target the curves aim for: roughly the input value, rounded off at the paper's black floor.

## Plain paper (Gutenprint defaults, no curve -> final curve)

| Input | 229 | 178 | 127 | 102 | 76 | 51 | 25 | 0 |
|---|---|---|---|---|---|---|---|---|
| Gutenprint, Density 60 Gamma 1.8 Black 70, no curve | 237 | 171 | 91 | 51 | 30 | 20 | 14 | 16 |
| With curve v2 | 231 | 180 | 133 | 106 | 82 | 56 | 31 | 19 |
| Target | 230 | 179 | 129 | 104 | 78 | 55 | 32 | 20 |

Without the curve the shadow strip's 24 steps spanned about 14-30. With it they span 14-70 and are all distinct.

## Cardstock (Hammermill Premium 110 lb)

| Input | 229 | 178 | 127 | 76 | 51 | 25 | 0 |
|---|---|---|---|---|---|---|---|
| Plain curve applied (sheet C1) | 233 | 182 | 132 | 83 | 60 | 39 | 27 |
| Refit curve (sheet C2) | 230 | 176 | 124 | 75 | 55 | 34 | 23 |

The Plain curve overcorrected red in the deep shadows, which gave a blue cast. The refit removed it (red-minus-blue within 0-4 across the strip).

## Glossy vinyl sticker paper (Koala)

| Input | 242 | 204 | 153 | 127 | 102 | 76 | 51 | 25 |
|---|---|---|---|---|---|---|---|---|
| No curve (S1) | 254 | 223 | 180 | 155 | 115 | 53 | 12 | 12 |
| With curve (S2) | 241 | 201 | 147 | 122 | 94 | 67 | 42 | 12 |
| Clear vinyl, same curve, white backing | 232 | 194 | 139 | 115 | 90 | 62 | 41 | 18 |

Without a curve everything below 51 was crushed to the 11-12 floor and the midtones had a +15-19 warm cast; with it the cast is +4-8. Vinyl keeps darkening for hours after printing, so S1 (scanned at ~25 min) and S2 (~3 h) disagree below about 25; trust the upper range most. The clear stock behaved like the white within 3-9 points, so both share one queue.

## Kraft sticker paper (Naturalabel)

Paper colour scans at about R195 G161 B118. Tones as % of that colour, G channel:

| Input | 204 | 153 | 127 | 89 | 51 | 25 |
|---|---|---|---|---|---|---|
| Target | 80 | 60 | 50 | 35 | 20 | 10 |
| Plain curve (KR1) | 81 | 57 | 47 | 31 | 19 | 8 |
| Per-channel refit (KR2) | 80 | 59 | 49 | 34 | 19 | 9 |

The R-minus-G/B spread in the midtones fell from about 12 to 5-7 points, so the dark grays moved from maroon-brown to neutral graphite with a kraft tint.

## Canon imagePROGRAF TC-20M (driverless, plain copy paper, High quality)

First measurement was misleading: with the cyan and magenta heads not firing, the printer fell back to
black only and every input above ~140 printed as bare paper. After the heads were fixed (the nozzle check
printed all colours) the real response was just too dark:

| Input | 230 | 178 | 140 | 128 | 102 | 76 | 51 | 25 |
|---|---|---|---|---|---|---|---|---|
| Target | 230 | 179 | 140 | 128 | 102 | 77 | 51 | 26 |
| No curve (TC5) | 237 | 178 | 128 | 103 | 52 | 15 | 3 | 1 |
| With `TC-20M.High.json` (TC6) | 229 | 176 | 135 | 119 | 96 | 70 | 54 | 27 |

The 24-step shadow strip went from 2-12 (one black bar) to 2-66, all steps distinct, and the
blue lean in the dark grays (-3 to -9) fell to within +/-5. Normal quality showed fine horizontal
banding that High did not; High was used as the baseline.

### TC-20M roll (20 lb bright copy paper), High quality

The cassette curve was applied during the first roll measurement (R4); the roll curve was fit on top of it (R5).

| Input | 242 | 204 | 153 | 128 | 102 | 76 | 51 | 38 | 26 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|
| Target | 243 | 204 | 154 | 128 | 103 | 78 | 53 | 41 | 29 | 19 |
| Cassette curve on roll (R4) | 235 | 203 | 152 | 132 | 110 | 84 | 66 | 55 | 45 | 38 |
| `TC-20M.roll.High.json` (R5) | 240 | 203 | 154 | 127 | 102 | 78 | 49 | 40 | 33 | 25 |

The shadow strip went from 9-80 (too light and flat) to 7-69 with an even climb.
