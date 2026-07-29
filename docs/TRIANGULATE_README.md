# gNB Trilateration

Computes the 3-D position of a gNB from rangefinder survey points using
weighted least-squares over slant distance and elevation angle.

The calculation uses **trilateration**: it uses distances and elevation angles,
but no compass bearing or azimuth.

## Quick start

From a clone of this repository:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
python survey.py
```

The last command opens an interactive picker listing every survey found under
`data/raw/`; pressing Enter runs the selected survey. To skip the prompt:

```bash
python survey.py 20260716 solve
python survey.py --list
python survey.py solve "/path/to/SURVEY.csv" "/path/to/BINOC.xlsx"
```

No survey is built into the program. `--data-root PATH` scans somewhere else.

## What the program needs

Two files, recorded by two different instruments at the same ground marks.

**1. A MapPro survey-point CSV** — the raw export straight off the GNSS
receiver, no pre-processing. Choose *Survey point data format (csv)* with
**Distance Unit = Meter**; any of the nine Lat/Lon formats works, because the
program detects the format and verifies it against the file's own
`Northing`/`Easting`. Required columns:

| CSV column | Meaning |
|---|---|
| `Point Name` | Label used to match the binocular sightings (e.g. `Pt1`) |
| `Latitude`, `Longitude` | Any of the nine exported formats |
| `Altitude` | The **ground mark**, with pole and antenna already reduced out |
| `Northing`, `Easting` | Projected metres; used to verify the Lat/Lon format |
| `Original Altitude`, `Antenna Height` | Optional; used to re-check the reduction |

**2. A binocular sightings workbook** (`.xlsx`, first worksheet, one header row):

| Column contains | Meaning |
|---|---|
| `point name` | Must match a `Point Name` in the CSV (case-insensitive) |
| `distance` | Slant/line-of-sight distance to the gNB, metres |
| `angle` | Elevation angle above horizontal, degrees |
| `height` | Height the binoculars were held at, metres above the ground mark |

Column headers are matched on those keywords, so wording and typos do not
matter. Each point may appear **once**; a duplicate is an error, not a silent
overwrite.

Collect observations from at least three points — four to six well-separated
ones are preferable. All points in one survey must observe the same physical
gNB antenna or sector. The solver does not currently accept compass bearing or
azimuth.

### Why the height comes from the binoculars, not the survey

The GNSS antenna sits on a 2 m pole (`Antenna Height` 2.066 m in the 20260716
data); the binoculars are handheld and varied between 1.89 m and 2.08 m across
the same points. The distance and angle were read from the binoculars, so each
point's altitude is `Altitude` (the ground mark) **plus that point's binocular
height** — never the GNSS antenna's. Using `Original Altitude` instead would
put the observer on the pole and shift the reported gNB altitude by ~2 m.

## Complete user guide

### Step 1: Plan the survey

1. Identify the gNB antenna or sector that will be measured. Record supporting
   identifiers such as site name, operator, PCI, band, or frequency so that
   every observation can be checked against the same target.
2. Choose at least three locations with clear line of sight to the antenna.
   Four to six locations provide useful redundancy.
3. Spread the locations over the widest practical baseline. Points that are
   close together or nearly collinear produce an elongated error ellipse and
   poor cross-range accuracy.
4. Keep the gNB within the rangefinder's usable distance and angle limits.
5. Use the same position source, altitude datum, and measurement procedure at
   every point.

Good survey geometry matters as much as instrument accuracy. Moving one point
sideways, away from the line formed by the other points, is often more useful
than adding several measurements to the same cluster.

### Step 2: Collect each observation

At every survey point:

1. Place the position receiver and rangefinder at the recorded location.
2. Record latitude and longitude as WGS84 **decimal degrees**, not
   degrees-minutes-seconds text.
3. Let the GNSS receiver record the ground mark; separately note the height you
   are holding the binoculars at, in metres. The program adds the two. Do not
   pre-add it yourself, and do not use the pole/antenna height.
4. Aim at the same reference point on the gNB antenna.
5. Record the elevation angle. Positive values mean above horizontal; negative
   values mean below horizontal.
6. Record the slant distance shown by the rangefinder. Do not substitute a
   horizontal map distance.
7. Repeat or sanity-check unstable readings before moving to the next point.

Keep all altitude values in one consistent vertical datum. Mixing ellipsoid,
mean-sea-level, and ground-relative heights can bias the estimated antenna
altitude.

### Step 3: Prepare the inputs

Export the survey from MapPro (*Export data* → *Survey point data format
(csv)*, **Distance Unit = Meter**) and keep the file exactly as written. There
is no normalisation step: the program reads the raw export.

Record the binocular sightings in a workbook whose first worksheet looks like
this:

| Point Name | distance from binoc viewfinder to gnb | angle from binoc viewfinder to gnb | height of binoc from ground (in meters) |
|---|---:|---:|---:|
| pt1 | 49.4 | 51 | 2.06 |
| pt2 | 54.0 | 46 | 2.08 |
| pt3 | 54.6 | 46 | 2.08 |

Rules the program enforces, loudly:

- Every sighted point name must exist in the survey CSV. A name that does not
  match is an error naming the point — that is what a mislabelled sighting
  looks like.
- A point may be sighted at most once. Duplicates are rejected.
- Distance must be positive, angle within 0–90°, binocular height within 0–3 m.
- Surveyed points with no sighting are simply unused; that is not an error.
- The CSV's `Latitude`/`Longitude` must agree with its own `Northing`/`Easting`,
  otherwise the file is refused rather than solved with wrong coordinates.

Nothing is silently dropped. If a point is missing from the report, the program
told you why and exited non-zero.

### Plotting the same survey in Google My Maps

Conversion is `python survey.py <name> convert`, in this repository. It converts
the raw MapPro CSV into a My Maps-importable file with decimal-degree coordinates.
It is an independent branch of the pipeline — solving does not read its output.

### Step 4: Install the software

Requirements:

- Python 3.10+
- NumPy
- SciPy
- openpyxl
- pyproj for optional SVY21 output
- pytest for the test suite

Create an isolated Python environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### Step 5: Run the solver

```bash
python survey.py                            # interactive picker
python survey.py 20260716                   # pick a verb for one survey
python survey.py 20260716 solve             # solve, no prompts
python survey.py --list                     # what each survey can do
python survey.py solve "/path/to/SURVEY.csv" "/path/to/BINOC.xlsx"
```

If a path contains spaces, keep the quotation marks.

Input precedence is: two explicit paths, then a bare survey name, then the
interactive picker. The picker only appears when stdin is a terminal — in a pipe, a cron
job or CI it errors instead, so automation never blocks on a prompt. Add
`--no-input` to enforce that explicitly.

Every run also writes the gNB and a 36-point ring tracing its **95% confidence
ellipse** into `data/output/<survey>_gnb.csv`, ready to import into Google My Maps
(choose Latitude and Longitude when it asks which columns position the points).
Use `--csv PATH` to write elsewhere, or `--no-csv` to skip it.

The ring is deliberately *not* the "1σ" ellipse quoted in the console. In two
dimensions a 1σ ellipse contains only 39% of the probability, not the 68% most
readers assume — `1 − exp(−½)`. The 95% contour sits at 2.45σ. For the
20260716 survey that is semi-axes of 7.72 × 1.67 m, spanning 15.4 m by
3.3 m, with the long axis bearing 099°. That long thin shape is the honest
picture of a fix whose cross-range direction is weakly constrained.

`Northing` and `Easting` are left blank: My Maps positions purely by
latitude/longitude. The columns are kept so the file concatenates with survey
exports.

### Step 6: Interpret the report

The 20260716 Cetran survey produces:

```text
=== Cetran gNB ===
  Position : 1.3555437, 103.6937797   alt 74.7 m
  SVY21    : E 12470.9  N 37515.1  (EPSG:3414)
  Uncertainty (1σ): horiz ±3.2 m (ellipse 3.2×0.7 m), vert ±0.7 m
  Geometry : OK (cond 34)   seed: srls
  Residuals:
    Pt1                    dist  +1.8 m   elev +0.4°
    Pt2                    dist  -1.0 m   elev +1.3°
    Pt3                    dist  -1.4 m   elev -0.4°
    Pt4                    dist  +1.4 m   elev -1.5°
    Pt8                    dist  -2.7 m   elev +1.6°   <-- largest
    Pt7                    dist  +1.3 m   elev -1.4°
```

All nine MapPro Lat/Lon export formats of the same survey produce this
identical result; that equivalence is asserted by the test suite.

The `Model check` line compares the sigmas the solve assumed against what this
survey's own residuals imply. They should agree; `<-- CHECK` means the
assumed measurement model does not describe this data, and the reported
uncertainty should not be trusted until you know why.

Each report field means:

- **Position** — estimated WGS84 latitude, longitude, and altitude.
- **SVY21** — EPSG:3414 easting and northing for Singapore mapping systems.
  This line is omitted if `pyproj` is unavailable.
- **Horizontal and vertical 1σ uncertainty** — model-based standard
  uncertainty. Under the measurement model, approximately 68% of repeated
  estimates would fall within a one-standard-deviation region.
- **Ellipse major × minor** — the two semi-axes of the horizontal 1σ error
  ellipse. The major axis is the weak direction and is often the most useful
  accuracy warning.
- **Geometry** — `OK`, `WEAK`, or `UNDER-CONSTRAINED`. Weak geometry usually
  means the survey points are too clustered or too nearly collinear.
- **Condition number** — a numerical geometry-quality indicator; higher is
  worse. The report flags values at or above `10000` as weak.
- **Seed** — `srls` is the normal globally optimized squared-range
  initializer. `azimuth-multistart` is the fallback used for degenerate seed
  geometry; despite its name, it does not consume measured azimuth.
- **Residuals** — predicted minus measured distance and elevation for every
  included point. Positive distance residual means the fitted gNB is farther
  from that point than the measurement indicated.
- **Largest** — the point with the greatest absolute distance residual, which
  is the first observation to recheck.

The model assumes a distance uncertainty of `2.0 m` and an elevation-angle
uncertainty of `1.4°` — see [Advanced settings and
tests](#advanced-settings-and-tests) for where those come from. Residuals
appreciably larger than that deserve investigation, especially when one point
disagrees with all the others.

### Step 7: Check whether the answer is trustworthy

Before using a result:

- Confirm that at least three complete points appear in the residual list.
- Prefer `Geometry: OK`.
- Look at the major error-ellipse axis, not only the rounded coordinates.
- Check whether one point has a much larger residual than the others.
- Confirm the estimated altitude is physically plausible for the antenna.
- Plot the WGS84 or SVY21 position on a map and compare it with the visible
  site.
- Treat 1σ values as uncertainty estimates, not guaranteed maximum errors.

A result can have small residuals but still have a long error ellipse. That
means the observations agree with one another while the point layout remains
weak in one direction.

## Troubleshooting

| Symptom | Likely cause and action |
|---|---|
| `error: survey CSV not found` / `binocular workbook not found` | Check the filename, path, and quotation marks. |
| `no surveys found under ...` | The data root has no `surveys/<NAME>/mappro/*.csv`. `--list` shows what was found and why anything was skipped. |
| `no input given and not running interactively` | You piped input or ran under CI. Pass a survey name or the two paths. |
| A survey is listed with blocked capabilities | Its survey folder has no CSV, or no `<NAME>*.xlsx` workbook exists. Excel `~$` lock files are ignored by design. |
| `'ptN' appears twice` | The binocular workbook sights one point on two rows. Fix the label at the named row. |
| `sighted but never surveyed: ptN` | A point name in the workbook has no matching `Point Name` in the CSV. The error lists the surveyed names. |
| `no format reproduces the surveyed Northing/Easting` | The CSV's Lat/Lon and Northing/Easting disagree — usually a hand-edited or partially converted file. Re-export from MapPro. |
| `Latitude/Longitude are bare numbers and Northing/Easting is missing` | Re-export including the `Northing`/`Easting` columns so the format can be verified. |
| `Original Altitude ... Antenna Height ... inconsistent` | The CSV's altitude columns do not reduce cleanly. Re-export rather than guessing the datum. |
| `only N sighting(s); at least 3 are needed` | Collect at least three complete observations. |
| `UNDER-CONSTRAINED` | Collect at least three complete observations. |
| `WEAK` or a very long ellipse | Increase the baseline and add points away from the existing line or cluster. |
| One large residual | Recheck transcription, target identity, line of sight, distance, elevation, and position. |
| No `SVY21` line | Install `pyproj`. The WGS84 solution is still computed normally. |
| Implausible altitude | Check the binocular heights in the workbook, and that the CSV's `Altitude` is the ground mark rather than the antenna. |
| Mirrored or sideways-uncertain position | Collect points with wider cross-range separation; an independent azimuth measurement can help validate the side, although this solver does not ingest azimuth. |
| Spreadsheet formulas are ignored | Replace them with numeric values or ensure the workbook was recalculated and saved with cached numeric results. |

No input row is ever skipped silently: every rejection names the file, the
point, and what to fix, and exits non-zero. If a point is missing from the
residual list, it was not in the binocular workbook.

## Improving future surveys

- Collect four to six observations instead of relying on the minimum of three.
- Maximize the lateral spread of the points around the target.
- Avoid collecting all observations along one road, corridor, or building
  edge.
- Use clear line of sight and repeat readings that fluctuate.
- Record angles with the instrument's available precision rather than rounding
  unnecessarily.
- Keep the same coordinate and altitude source throughout a survey.
- Record target-identifying metadata so measurements from different antennas
  are not combined accidentally.
- If possible, record an independent compass bearing for validation. One
  bearing can greatly reduce left/right ambiguity and cross-range uncertainty,
  but adding bearing as a solver input would require a code change.

## Advanced settings and tests

The assumed instrument errors are defined near the top of
`gnb_survey/triangulate/solver.py`:

```python
SIGMA_DISTANCE_M = 2.0
SIGMA_ELEVATION_DEG = 1.4
```

**Only the ratio of these two matters.** The covariance is rescaled by the a
posteriori variance factor (`rss/dof`), so multiplying both by any constant
leaves the solution and its uncertainty bit-for-bit unchanged. Set them as
realistic *relative* weights; the absolute scale calibrates itself.

Where the values come from:

| Constant | Provenance |
|---|---|
| `SIGMA_DISTANCE_M = 2.0` | Geovid R manual (Geovid R/EN/2022/06/1, p.18) states accuracy as an explicit **1σ** below 350 m: ±1 m normal operation, **±2 m scan mode**. A variance-component fit of the 20260716 residuals gives 1.94 m, matching the scan-mode figure. |
| `SIGMA_ELEVATION_DEG = 1.4` | **The manual specifies no angle accuracy**, and documents no angle readout — the Geovid R displays distance and Equivalent Horizontal Range (p.18). Estimated from the data instead: the same fit gives 1.43°, consistent with angles recorded as whole degrees (±0.5° from rounding alone, before pointing error). |

Both estimates carry roughly 33% uncertainty on six points (~4.5 dof per
group). These are defaults, not instrument constants. Override them per run
with `--sigma-distance` and `--sigma-elevation` rather than editing the file,
and remember that only their ratio affects the result.

There is no instrument-height constant: the height is applied per point from
the binocular workbook, because it varies between points.

Run the automated tests:

```bash
pytest
```

The suite covers coordinate-format decoding and detection, the two readers and
their validation, the survey join, WGS84/ENU conversion, the global
initializer, and synthetic solver cases.

## Method

Each survey point has a known position (latitude, longitude, altitude) and two
readings toward the gNB from a Leica Geovid R: a slant **distance** and an
**elevation angle**. There is no compass bearing, so this is trilateration, not
classic ray triangulation.

The solver works in a local East-North-Up metric frame and finds the gNB
position `(X, Y, Z)` that minimizes, over all points, the weighted residuals:

```text
slant residual     = (‖gNB − point‖ − measured_distance) / σ_distance
elevation residual = (atan2(ΔZ, horizontal) − measured_elevation) / σ_elevation
```

with `σ_distance = 2.0 m` and `σ_elevation = 1.4°`. The Jacobian at the
solution yields a covariance matrix and the reported 1σ error ellipse and
vertical error.

### Global initialization (SR-LS)

Because no azimuth is measured, the range cost is non-convex and has multiple
basins: the gNB could sit on either side of the point cluster. Rather than rely
on a local solver landing in the correct basin, the program computes a
globally optimal seed in closed form using **Squared-Range Least Squares**
(`srls.py`). The squared-range problem is a Generalized Trust Region Subproblem
solved by one-dimensional bisection, so it requires no initial guess. The
elevation angles then fix the vertical component, and one
Levenberg-Marquardt pass refines the true distance-plus-elevation residuals. A
24-direction multi-start remains as a fallback for degenerate geometry.

See `RESEARCH.md` for the supporting literature.

### Coordinate systems (SVY21 / EPSG:3414)

The solve runs in a true-distance local ENU frame, not SVY21, because a
Transverse Mercator grid carries a scale factor and grid distances are not
identical to ground distances. SVY21 easting/northing is reported only as an
extra output for overlaying on Singapore official data, OneMap, or QGIS. It is
never fed into the solver.

If `pyproj` is not installed, the SVY21 line is omitted.

## Results on the 20260716 survey

| Site | gNB latitude | gNB longitude | Altitude | SVY21 E,N | Horizontal 1σ | Vertical 1σ |
|---|---:|---:|---:|---:|---:|---:|
| Cetran | 1.3555437 | 103.6937797 | 74.7 m | 12470.9, 37515.1 | ±3.2 m | ±0.7 m |

Six sightings, converging from the SR-LS global seed. Residuals reach −2.7 m in
distance and +1.6° in elevation, both consistent with the calibrated
measurement model.

## Honest limitations

- **Cross-range uncertainty dominates.** The error ellipses can be very
  elongated, such as `11.3 × 0.8 m` for S2 and S1. The range direction may be
  pinned to sub-metre precision while the perpendicular direction is weak
  because the survey points are clustered relative to the gNB distance. Treat
  the major axis as the practical uncertainty warning.
- **The current solver does not ingest azimuth.** One bearing measurement would
  greatly reduce cross-range ambiguity, but it can presently be used only as
  an independent validation measurement.
- **The elevation-angle uncertainty is calibrated from the data, not specified.**
  The Geovid R manual gives no angle accuracy and documents no angle readout at
  all — it displays distance and Equivalent Horizontal Range. `SIGMA_ELEVATION_DEG`
  is therefore an estimate from six points, good to roughly 33%. Worse, the
  provenance of the recorded angles is unconfirmed: if they were read off a
  different instrument, or derived from EHR, the error model would differ.
- **The distance residuals are nearer scan-mode than normal-operation accuracy.**
  The fitted 1.94 m matches the manual's ±2 m scan-mode figure rather than the
  ±1 m normal-operation one. Part of that excess may not be the instrument at
  all, but which part of the antenna panel was ranged from each point.
- **Uncertainty depends on the measurement model.** The reported covariance
  assumes independent errors consistent with the configured distance and
  angle standard deviations. Systematic errors, mixed datums, incorrect
  targets, and obstructions are not captured fully by the reported 1σ values.

## Project layout

```text
gnb_survey/
  convert/     MapPro export converter (stdlib-only)
  triangulate/
    models.py    frozen data models for stations, sightings, surveys, solutions
    errors.py    SurveyDataError, raised for any unusable input
    coords.py    decodes MapPro's nine Lat/Lon formats; detects which one
    discovery.py find surveys under a data root
    prompt.py    interactive selection through injected streams
    mymaps.py    gNB + 95% confidence ring as a My Maps CSV
    mappro.py    reads a raw MapPro survey CSV into Stations
    binoc.py     reads the binocular sightings workbook
    assemble.py  joins the two, validating that they agree
    geo.py       WGS84/local ENU conversion and optional SVY21 output
    srls.py      squared-range least-squares global seed
    solver.py    weighted 3-D least-squares and covariance
    report.py    console report formatting
  animate/     ManimGL scene data builder & runner
  cli/         CLI dispatch, capability checks & menu
survey.py      command-line entry point
tests/         convert, triangulate, animate, and cli test suite
```
