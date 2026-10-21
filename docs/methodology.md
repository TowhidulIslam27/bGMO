# Method

This is the method behind bGMO Release 1.0. A shorter version is in the Methodology
section of the [map](https://bgmo.sarsense.com).

## Images

We used Sentinel-1A radar images taken in Interferometric Wide swath (IW) mode and
delivered as single look complex (SLC) products. We processed each city twice, once from
each viewing direction. The ascending images were taken at about six in the evening
local time, with the satellite looking east. The descending images were taken a little
before six in the morning, looking west.

| City | Ascending path | Descending path | Scenes (asc / dsc) |
|---|---|---|---|
| Dhaka | 114 | 150 | 217 / 183 |
| Chattogram | 114 | 77 | 179 / 176 |
| Khulna | 114 | 150 | 217 / 186 |
| Barishal | 114 | 150 | 216 / 185 |
| Sylhet | 41 | 77 | 218 / 151 |
| Cumilla | 114 | 77 | 199 / 159 |

Depending on the city, the stacks start between 2016 and 2018 and run to 2023 or 2024.

## Finding stable points

For every stack we picked one master image from the middle years and formed an
interferogram between it and each of the other dates (single-master network; the
perpendicular baselines are plotted in the web map under *About the data*). We then
selected persistent scatterers with StaMPS. These are points whose radar return stays
steady over the whole period, mostly rooftops, walls and paved ground, which is why the
points crowd the built-up core of each city and thin out over fields, rivers and trees.

The StaMPS exports come in two layouts. We checked their dates against `ps_info` and
found that the MATLAB datenums in the `export_res_*` files are one day early, so we
shifted them by +1 day (`processing/01_stamps_csv_to_txt.py`). We also inserted the
master epoch, which is zero by definition, into every series.

## What the radar sees

The satellite measures how the distance between itself and the ground changes. That
distance runs along its line of sight (LOS), tilted between roughly 31° and 46° from
the vertical depending on where the city falls across the 250 km swath. A negative
LOS velocity means the point moved away from the satellite, which usually indicates
subsidence.

## Incidence angle

We estimated the incidence angle θ of every point from the footprint of the Sentinel-1
SLC frame it falls in (granule metadata from NASA CMR / ASF, listed in
`processing/config.py`):

1. We took the perpendicular distances from the point to the frame's near-range and
   far-range long edges to get its fractional position across the frame.
2. We set the far edge to the IW far-range incidence of 46°. On a spherical Earth
   (radius 6375 km, orbit altitude 693 km) the ground range from nadir is g(θ) = R (θ −
   asin(R sin θ / (R + H))).
3. We interpolated the point's ground range between the near and far edges and found θ
   by inverting g(θ).

We expect the result to be correct to about one degree, which shifts derived vertical
and east–west values by one or two percent (`processing/02_los_to_vertical.py`).

As a first check we divided each track's LOS rate by cos θ, as if all motion were
vertical, and compared the two tracks where they overlap. In Dhaka, Khulna, Sylhet and
Barishal they agreed to within about 0.3 mm/yr. In Chattogram the ascending track read
1.8 mm/yr higher, and in Cumilla 4.3 mm/yr lower, than the descending track. Differences
like these are why we only offer vertical and east–west motion through the Ortho
product, where both tracks are tied to the same ground and solved together.

## Rates and time series

We take every rate as the slope of a least-squares straight line through the full time
series, with the master date fixed at zero. RMSE is the scatter of the measurements
around that line. We store displacements to 0.1 mm and velocities to 0.01 mm/yr
(`processing/03_build_web_data.py`).

## Combining the two tracks (Ortho)

Each track sees the ground from one side, so a single track cannot separate sinking from
sideways movement. With both tracks we can separate the two. The code for this part is
`processing/04_ortho_decomposition.py`.

We laid a 100 m grid over each city and kept only the cells that hold points from both
tracks. In each cell we averaged the points of each track, together with their incidence
angles.

Each stack was processed with its own reference area, so before combining we removed
each track's median velocity v_ref over the shared cells, counted from that track's
master date t_m:

```math
d'(t) = d(t) - v_\mathrm{ref}\,(t - t_m)
```

This makes the typical ground of each city our common zero. In Cumilla the two stacks
differed by more than 3 mm/yr before this step.

| City | v_ref ascending | v_ref descending (mm/yr LOS) |
|---|---:|---:|
| Dhaka | −0.38 | −0.08 |
| Chattogram | +1.85 | +0.65 |
| Khulna | +0.41 | +0.29 |
| Barishal | +0.04 | −0.19 |
| Sylhet | −0.09 | −0.09 |
| Cumilla | −3.39 | −0.15 |

We then interpolated both cell series linearly onto a shared 12-day timeline over the
period that both tracks cover, and re-zeroed them at the first epoch.

If a point moves up by d_U, east by d_E and north by d_N, the change
along the line of sight (positive towards the satellite) is

```math
d_\mathrm{LOS} = d_U\cos\theta - \sin\theta\,(d_E\cos\alpha - d_N\sin\alpha)
```

where θ is the incidence angle and α the flight azimuth, clockwise from north.
Sentinel-1 flies close to north–south, at about −11.1° ascending and 191.0° descending,
so sin α is small and we neglected the north–south term. That leaves two unknowns and
one equation per track:

```math
d_\mathrm{asc} = d_U\cos\theta_a - d_E\sin\theta_a\cos\alpha_a
```
```math
d_\mathrm{dsc} = d_U\cos\theta_d - d_E\sin\theta_d\cos\alpha_d
```

On the ascending track cos α ≈ +1 and on the descending track cos α ≈ −1, so eastward
motion lowers the ascending reading and raises the descending one, while sinking lowers
both. Solving the pair, we get:

```math
D = \sin\theta_a\cos\theta_d\cos\alpha_a - \cos\theta_a\sin\theta_d\cos\alpha_d
```

```math
d_E = \frac{\cos\theta_a\,d_\mathrm{dsc} - \cos\theta_d\,d_\mathrm{asc}}{D} \qquad d_U = \frac{\sin\theta_a\cos\alpha_a\,d_\mathrm{dsc} - \sin\theta_d\cos\alpha_d\,d_\mathrm{asc}}{D}
```

We solved this for every cell on every 12-day date, using the mean incidence angle of
each track's points in that cell. East–west is positive towards the east. We took the
vertical and east–west rates from the slopes of straight lines fitted through the two
resulting series.

For example, in central Dhaka θ_a ≈ 39° and θ_d ≈ 36°, so D ≈ 0.95 and
d_E ≈ 0.82 d_dsc − 0.85 d_asc. A cell where the descending track reads 2 mm/yr more
than the ascending track is moving roughly 1.6 mm/yr to the east.

The web map rebuilds each cell's series from its member points when a cell is clicked;
it matches the Python reference to 0.1 mm. Cells built from one or two points per track
are noisier than cells with many, so we record how many ascending and descending points
each cell holds.

## Resolution cell

When zoomed in, each point is drawn at the size of its Sentinel-1 IW resolution cell:
the slant-range resolution of its sub-swath divided by sin θ in ground range (about
5 m), by about 22.5 m in azimuth. Ortho cells are drawn as 100 m squares.

## Things to keep in mind

- All rates are relative to the reference area of their own stack and have not been
  calibrated against GNSS. They describe motion compared with the surrounding ground;
  absolute rates and fair city-to-city comparison need GNSS ties (planned: bGMO
  Calibrated).
- We did not measure north–south motion and assumed it is small.
- Persistent scatterers favour built-up areas; fields, water and vegetation have few or
  no points.
- The vertical-only projection d_LOS / cos θ of a single track assumes no horizontal
  motion. We keep it in `TS_vertical/` for reference, but we don't show it on the map.