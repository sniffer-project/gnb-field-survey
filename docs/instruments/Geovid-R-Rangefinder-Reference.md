# Leica Geovid R 10×42 — Rangefinder Reference

**Device:** Leica Geovid R 10×42 rangefinding binoculars
**Order No.:** 40812 · **Type No.:** 4058
**Lab use:** Measuring binocular → antenna distance

---

## Key question: Where is the distance measured FROM?

**The displayed distance is measured from the FRONT of the binoculars (the objective / laser lens end) — NOT from the eyepiece where your eye is.**

The reading = **front objective face → target (antenna)**.

### Why
- The laser pulse exits and returns at the **front**. In the manual's part diagram, **part #12 is the "Laser transmission lens"**, on the front (objective) face.
- A laser rangefinder works by timing a light pulse's round trip (time-of-flight). The emitter/receiver optics sit together at that front aperture, so the measurement's zero point is the **front lens face**.
- The eyepiece end (eyecups #4, eyepiece cap #6, viewing lens #13) is purely optical — your eye position does not affect the measurement.

---

## Practical implication for lab measurements

| Item | Value |
|---|---|
| Front-lens ↔ eyepiece offset | ≈ body length, ~16–17 cm |
| Minimum range | **10 m / 11 yd** (shows `- - -` below this) |
| Max range | ~1800 m highly reflective · ~900 m on game |

### Rangefinder accuracy — the manual gives it as **1σ**, and it depends on mode

Manual p.18 ("Metering range / accuracy") has *two* accuracy columns, both
headed **"Accuracy (1σ)"**:

| Range (m) | Normal operation | **Scan mode** |
|---|---|---|
| < 350 | **±1 m** | **±2 m** |
| 350–700 | ±2 m | ±3 m |
| > 700 | 0.5% | 0.5% |

Two things matter for the lab work:

- These are **1σ**, stated as such — so they drop straight into a least-squares
  weight, no conversion needed.
- **Scan mode doubles the error below 350 m.** Scan mode is press-and-hold
  continuous ranging (p.17), which is the natural way to acquire a small target
  like an antenna. Fitting the 20260716 gNB campaign's own residuals gives
  σ = 1.94 m — matching the scan-mode figure, not normal operation.

---

## Does the Geovid R measure elevation angle?

**Not as a displayed value.** The manual specifies **no angle accuracy
anywhere**, and the Technical Data table (p.20, Order No. 40812 = the 10×42
used here) lists only `Measuring accuracy: ±1 m to 350 m…` and
`Display: LED display with 4 digits`.

The device *does* sense inclination internally — it offers **EHr (Equivalent
Horizontal Range)**, the slant range projected to horizontal, which cannot be
computed without an angle (p.18). But what it shows you is EHr in metres, not
degrees. EHr is only provided between 10 m and 1100 m.

**Open question for the lab:** the 20260716 sheet attributes "Angle to gNB" to
the Geovid R, in whole degrees. Since the Geovid R has no degree readout, those
angles came from somewhere else — a separate inclinometer, or back-computed as
`arccos(EHr / distance)`. Which one it was determines the angle error model,
which is currently estimated from residuals (1.43°) rather than specified.

**The ~16 cm front-vs-eyepiece offset is much smaller than the instrument's own ±1 m uncertainty**, so for antenna distance work it's negligible — just treat the reading as "front of binocular to antenna."

It only matters if:
- You need **sub-meter / cm precision at short range** (near the 10 m minimum) → add ~0.16 m if your reference point is your eye, not the front lens.
- You're **co-locating with a tripod / survey mark** → define the reference as the **front objective face** (the true zero of the measurement).
- Note: you **cannot range closer than 10 m**.

---

## Laser specifications

| Spec | Value |
|---|---|
| Laser class | IEC/EN Class 1 (eye-safe) |
| Wavelength | 900 nm (invisible IR) |
| Pulse duration | 57 ns |
| Output | 1.6 mW |
| Beam divergence | Vertical 0.8 mrad · Horizontal 1.8 mrad |

---

## Source

Official Leica **GEOVID R Instruction Manual** (Geovid R/EN/2022/06/1)
<https://leica-camera.com/sites/default/files/2022-09/EN_Geovid%20RIII.pdf>

— Sections used: Part Designations (p.10–11), Metering Range / Accuracy (p.18), Technical Data (p.20), Technical Data Laser (p.4).
