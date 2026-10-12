"""Step 4: Ortho product - vertical and east-west motion from ascending + descending.

Works on the web data written by step 3, so it can be re-run on the published
files alone.

Method (per city):
  1. Lay a 100 m grid over both stacks and keep the cells that hold points
     from BOTH tracks.
  2. Per cell and track, average the member points' LOS series and incidence.
  3. Reference both tracks to the same ground: remove each track's median LOS
     velocity over the shared cells as a linear trend from its master date,
         d' = d - v_ref (t - t_master)
  4. Interpolate both series onto a common 12-day grid over the period both
     tracks cover, and re-zero at the first epoch.
  5. At every epoch solve the 2 x 2 system (LOS positive towards the satellite,
     alpha = flight azimuth, -11.1 deg ascending, 191.0 deg descending,
     north-south motion neglected):
         d_LOS = d_U cos(theta) - d_E sin(theta) cos(alpha)
  6. Cell velocities are least-squares slopes of the U and E series.

Output: <data>/<city>-ortho.pts.b64.txt (uint16 x 6: qlon, qlat, int16 vU x100,
int16 vE x100, n_asc, n_dsc) and an 'ortho' entry per city in index.json.
The web map rebuilds each cell's series from its member points on click.

Usage:  python 04_ortho_decomposition.py --data ../web/data
"""
import argparse, base64, json, os
import numpy as np
from config import CITY_ORDER

STEP = 100.0   # grid cell (m)
DT = 12        # common epoch spacing (days)
YR = 365.25


def load(data, d):
    q = np.frombuffer(base64.b64decode(open(f"{data}/{d['key']}.pts.b64.txt").read()), np.uint16).reshape(-1, 6)
    s = q.view(np.int16); qb = d['qb']
    lon = qb[0] + q[:, 0] / 65535 * (qb[2] - qb[0]); lat = qb[1] + q[:, 1] / 65535 * (qb[3] - qb[1])
    T = len(d['dates'])
    ts = np.concatenate([np.frombuffer(base64.b64decode(open(f"{data}/{d['key']}.ts.{c}.b64.txt").read()), np.int16)
                         for c in range(d['nchunks'])]).reshape(-1, T) / 10.0
    days = lambda x: float((np.datetime64(x) - np.datetime64('1970-01-01')).astype(int))
    return dict(lon=lon, lat=lat, vel=s[:, 2] / 100, inc=s[:, 5] / 100, ts=ts,
                t=np.array([days(x) for x in d['dates']]), tm=days(d['master']))


def stats(v):
    return dict(median=float(np.median(v)), p5=float(np.percentile(v, 5)), p95=float(np.percentile(v, 95)),
                min=float(v.min()), max=float(v.max()), fast=float((v <= -5).mean()), mod=float(((v > -5) & (v <= -2)).mean()))


def ortho(data, I, city):
    A = load(data, I[city + '-asc']); D = load(data, I[city + '-dsc'])
    lon0 = min(A['lon'].min(), D['lon'].min()); lat0 = min(A['lat'].min(), D['lat'].min())
    cl = np.cos(np.radians((max(A['lat'].max(), D['lat'].max()) + lat0) / 2)); kx = 111320 * cl; ky = 110574.0
    cells = lambda P: (np.floor((P['lon'] - lon0) * kx / STEP).astype(np.int64), np.floor((P['lat'] - lat0) * ky / STEP).astype(np.int64))
    ax, ay = cells(A); dx, dy = cells(D)
    ka = ax * 100000 + ay; kd = dx * 100000 + dy
    common = np.intersect1d(np.unique(ka), np.unique(kd))
    ina = np.isin(ka, common); ind = np.isin(kd, common)
    refA = float(np.median(A['vel'][ina])); refD = float(np.median(D['vel'][ind]))
    t0 = max(A['t'][0], D['t'][0]); t1 = min(A['t'][-1], D['t'][-1]); G = np.arange(t0, t1 + 0.1, DT)

    def cellmean(P, keys, mask, ref):
        k = keys[mask]; order = np.argsort(k, kind='stable'); k = k[order]
        uk, start, cnt = np.unique(k, return_index=True, return_counts=True)
        ts = P['ts'][mask][order]; inc = P['inc'][mask][order]
        ts = ts - ref * (P['t'][None, :] - P['tm']) / YR                      # shared reference
        S = np.add.reduceat(ts, start, axis=0) / cnt[:, None]; th = np.add.reduceat(inc, start) / cnt
        Gi = np.array([np.interp(G, P['t'], row) for row in S]); Gi -= Gi[:, :1]
        return uk, Gi, np.radians(th), cnt

    ukA, SA, thA, nA = cellmean(A, ka, ina, refA); ukD, SD, thD, nD = cellmean(D, kd, ind, refD)
    assert (ukA == ukD).all()
    hA = np.radians(I[city + '-asc']['heading']); hD = np.radians(I[city + '-dsc']['heading'] + 180)
    a11, a12 = np.cos(thA), -np.sin(thA) * np.cos(hA); a21, a22 = np.cos(thD), -np.sin(thD) * np.cos(hD)
    det = a11 * a22 - a12 * a21
    U = (a22[:, None] * SA - a12[:, None] * SD) / det[:, None]; E = (-a21[:, None] * SA + a11[:, None] * SD) / det[:, None]
    tt = (G - G[0]) / YR; X = np.vstack([tt, np.ones_like(tt)]).T
    vU = np.linalg.lstsq(X, U.T, rcond=None)[0][0]; vE = np.linalg.lstsq(X, E.T, rcond=None)[0][0]
    cx = (ukA // 100000 + 0.5) * STEP / kx + lon0; cy = (ukA % 100000 + 0.5) * STEP / ky + lat0
    o = np.lexsort((cx, cy))
    cx, cy, vU, vE, nA, nD, U, E = cx[o], cy[o], vU[o], vE[o], nA[o], nD[o], U[o], E[o]

    qb = [float(cx.min()), float(cy.min()), float(cx.max()), float(cy.max())]
    q = np.zeros((len(cx), 6), np.uint16)
    q[:, 0] = np.round((cx - qb[0]) / (qb[2] - qb[0]) * 65535); q[:, 1] = np.round((cy - qb[1]) / (qb[3] - qb[1]) * 65535)
    q[:, 2] = np.round(vU * 100).astype(np.int16).view(np.uint16); q[:, 3] = np.round(vE * 100).astype(np.int16).view(np.uint16)
    q[:, 4] = np.minimum(nA, 65535); q[:, 5] = np.minimum(nD, 65535)
    key = city + '-ortho'
    with open(f'{data}/{key}.pts.b64.txt', 'w') as f: f.write(base64.b64encode(q.tobytes()).decode())
    dates = [str(np.datetime64('1970-01-01') + np.timedelta64(int(x), 'D')) for x in G]
    i = int(np.argmin(vU))
    print(f"{city}: {len(cx)} cells, {len(G)} epochs {dates[0]}..{dates[-1]}, ref asc {refA:+.2f} dsc {refD:+.2f}, "
          f"vU median {np.median(vU):+.2f}, vE p5/p95 {np.percentile(vE, 5):+.2f}/{np.percentile(vE, 95):+.2f}")
    # 'stats' mirrors 'stats_e' for compatibility with the web map
    return dict(key=key, tag='ortho_' + city[:3], city=city, track='ortho', n=int(len(cx)), dates=dates, qb=qb, bounds=qb,
                grid=dict(lon0=float(lon0), lat0=float(lat0), kx=float(kx), ky=float(ky), step=STEP),
                ref={'asc': refA, 'dsc': refD}, stats=stats(vE), stats_v=stats(vU), stats_e=stats(vE), imin=[i, i],
                check={'i': i, 'u': [round(float(x), 2) for x in U[i][:5]], 'e': [round(float(x), 2) for x in E[i][:5]]})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); a = ap.parse_args()
    ip = os.path.join(a.data, 'index.json'); idx = json.load(open(ip)); I = {d['key']: d for d in idx}
    new = [ortho(a.data, I, c) for c in CITY_ORDER]
    idx = [d for d in idx if d['track'] != 'ortho'] + new
    tr = {'asc': 0, 'dsc': 1, 'ortho': 2}
    idx.sort(key=lambda d: (CITY_ORDER.index(d['city']), tr[d['track']]))
    json.dump(idx, open(ip, 'w'), separators=(',', ':'))
