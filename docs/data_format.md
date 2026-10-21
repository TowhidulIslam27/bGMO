# Web data format

All files live in `web/data/`. I stored the binary arrays as little-endian values in
base64 text (`*.b64.txt`) so that any static host can serve them. To read them back I
use:

```python
import base64, numpy as np
raw = base64.b64decode(open('web/data/khulna-dsc.pts.b64.txt').read())
```

## index.json

A list with one object per dataset (`<city>-asc`, `<city>-dsc`, `<city>-ortho`).

| Field | Meaning |
|---|---|
| `key`, `tag`, `city`, `track` | identifiers; `track` is `asc`, `dsc` or `ortho` |
| `n` | number of points (or Ortho cells) |
| `dates` | acquisition dates (ISO), master included; Ortho: the 12-day grid |
| `master` | master date; displacement is 0 there |
| `path` | Sentinel-1 relative orbit |
| `chunk`, `nchunks` | points per time-series file and number of files |
| `bounds` | lon/lat bounding box `[W, S, E, N]` |
| `qb` | box used to quantise positions (see below) |
| `inc` | min/max incidence angle (deg) |
| `heading` | track heading (deg); descending flight azimuth = heading + 180 |
| `stats`, `stats_v` | LOS and vertical-projected velocity statistics (mm/yr); Ortho: `stats_v` vertical, `stats_e` east–west |
| `baselines` | `{master, pairs: [[date, B_perp_m], ...]}` |
| `ov` | descending only: `[start, count]` of this city's rows in `overview.b64.txt` |
| `imin` | index of the fastest-sinking point (opened by default) |
| `grid`, `ref`, `check` | Ortho only: grid origin/scale, removed reference velocities, a test vector |

## `<city>-<asc|dsc>.pts.b64.txt`

`n × 6` unsigned 16-bit integers, one row per point, points in Morton (Z-order):

| Column | Type | Decoding |
|---|---|---|
| 0 | uint16 | lon = qb[0] + v / 65535 × (qb[2] − qb[0]) |
| 1 | uint16 | lat = qb[1] + v / 65535 × (qb[3] − qb[1]) |
| 2 | int16 | LOS velocity = v / 100 (mm/yr) |
| 3 | int16 | fit RMSE = v / 100 (mm) |
| 4 | int16 | LOS velocity / cos θ = v / 100 (mm/yr) |
| 5 | int16 | incidence θ = v / 100 (deg) |

## `<city>-<asc|dsc>.ts.<c>.b64.txt`

int16, point-major, `len(dates)` values per point, 600 points per file (file `c` holds
points `600c … 600c+599`). Displacement along LOS = v / 10 mm, relative to the master.

## `<city>-ortho.pts.b64.txt`

`n × 6` uint16 per 100 m cell: qlon, qlat (as above, cell centres), int16 vertical
velocity ×100, int16 east–west velocity ×100 (mm/yr, east positive), number of
ascending points, number of descending points. Cell series are not stored; the web
map rebuilds them from the member points using the method in
[methodology.md](methodology.md).

## `overview.b64.txt`

float32 rows of `lon, lat, LOS velocity, vertical-projected velocity`, a thinned
descending sample for each city, used for the national view.

## `catalog.json`, `boundaries.geojson`

The country/city list shown in the side panel, and the country outline and city
extents (geoBoundaries, CC BY 4.0).
