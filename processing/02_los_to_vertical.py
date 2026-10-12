"""Step 2: per-point incidence angle and single-track vertical projection.

The incidence angle of every PS point is estimated from where it falls across
the SLC frame: the frame's near- and far-range long edges come from the
granule footprint (config.FRAMES), the far edge is set to the IW far-range
incidence (46 deg), and incidence is interpolated on a spherical Earth
(radius 6375 km, orbit altitude 693 km).

The LOS series is then divided by cos(incidence) to give the vertical-only
projection d_v = d_LOS / cos(theta). This assumes no horizontal motion; the
two-track Ortho product (step 4) removes that assumption.

Output: <results>/TS_vertical/TS_<tag>_vert.txt
  columns lon, lat, inc_deg, vel_v_mm_yr, [vel_los_stamps_mm_yr], dates...

Usage:  python 02_los_to_vertical.py --results D:/Deform_paper/Results [tag ...]
"""
import argparse, datetime as dt, os
import numpy as np, pandas as pd
from config import FRAMES, FRAME, MASTER, EARTH_R_KM as Re, S1_ALT_KM as H, IW_FAR_INC_DEG as THF, all_tags


def ground_range(th):
    """Ground distance from nadir (km) for incidence th (deg), spherical Earth."""
    th = np.radians(th); look = np.arcsin(Re * np.sin(th) / (Re + H)); return Re * (th - look)


def incidence_of_range(g):
    t = np.linspace(15, 55, 40001); return np.interp(g, ground_range(t), t)


def dist_to_edge(lon, lat, edge):
    """Signed perpendicular distance (km) from points to a frame edge, local equirectangular."""
    (x1, y1), (x2, y2) = sorted(edge, key=lambda p: p[1])          # orient south -> north
    lat0 = np.radians((y1 + y2) / 2); kx = 111.32 * np.cos(lat0); ky = 110.57
    ax, ay = (x2 - x1) * kx, (y2 - y1) * ky; px, py = (lon - x1) * kx, (lat - y1) * ky
    return (ax * py - ay * px) / np.hypot(ax, ay)


def incidence(lon, lat, fr):
    near, far = (fr['W'], fr['E']) if fr['asc'] else (fr['E'], fr['W'])
    dn = dist_to_edge(lon, lat, near); df = dist_to_edge(lon, lat, far)
    width = np.abs(dn - df)
    f = dn / (dn - df)                      # 0 at near edge, 1 at far edge
    g_far = ground_range(THF); g_near = g_far - width
    return incidence_of_range(g_near + f * (g_far - g_near))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True)
    ap.add_argument('--out', help='output folder (default: <results>/TS_vertical)')
    ap.add_argument('tags', nargs='*')
    a = ap.parse_args()
    I = os.path.join(a.results, 'TS_txt'); O = a.out or os.path.join(a.results, 'TS_vertical'); os.makedirs(O, exist_ok=True)
    for tag in (a.tags or all_tags()):
        mst = MASTER[tag]; t0 = dt.datetime.now()
        df = pd.read_csv(f'{I}/TS_{tag}_ps.txt', sep='\t')
        lon, lat = df['lon'].values, df['lat'].values
        th = incidence(lon, lat, FRAMES[FRAME[tag]]); c = np.cos(np.radians(th))
        dcols = [x for x in df.columns if x[:2] == '20']
        vert = df[dcols].values / c[:, None]
        # vertical velocity: least-squares line through all epochs incl. the master (= 0)
        dates = pd.to_datetime(dcols + [mst]); t = ((dates - pd.Timestamp(mst)).days / 365.25).values
        Y = np.hstack([vert, np.zeros((len(df), 1))]); A = np.vstack([t, np.ones_like(t)]).T
        vel = np.linalg.lstsq(A, Y.T, rcond=None)[0][0]
        out = pd.DataFrame({'lon': lon, 'lat': lat, 'inc_deg': np.round(th, 3), 'vel_v_mm_yr': np.round(vel, 3)})
        if 'vel_mm_yr' in df: out['vel_los_stamps_mm_yr'] = df['vel_mm_yr'].values
        out = pd.concat([out, pd.DataFrame(np.round(vert, 3), columns=dcols)], axis=1)
        out.to_csv(f'{O}/TS_{tag}_vert.txt', sep='\t', index=False)
        print(f'{tag}: n={len(df)} inc {th.min():.2f}-{th.max():.2f} | vel_v median {np.median(vel):.2f} '
              f'p5 {np.percentile(vel, 5):.2f} p95 {np.percentile(vel, 95):.2f}  {(dt.datetime.now() - t0).seconds}s', flush=True)
