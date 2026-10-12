"""Step 3: pack the PS points and time series into the compact files the web map reads.

For every stack (tag) this writes, into <out>/:
  <city>-<pass>.pts.b64.txt     6 x uint16 per point, base64:
        qlon, qlat  position quantised to 16 bits inside index.qb
        int16 LOS velocity x100 (mm/yr), fit RMSE x100 (mm),
        vertical-projected velocity x100 (mm/yr), incidence x100 (deg)
  <city>-<pass>.ts.<c>.b64.txt  int16 displacement x10 (mm), point-major,
        600 points per chunk, master epoch included as 0
  overview.b64.txt              float32 lon, lat, vel, vel_v of a thinned
        descending sample per city, for the national view
  index.json                    metadata per dataset (dates, master, path,
        bounds, stats, baselines, ...)

Points are sorted in Morton (Z-order) so neighbours share a chunk, which keeps
the number of downloads small when a user clicks around one area.

Velocity is the least-squares slope through all epochs including the master;
RMSE is the scatter about that line.

Usage:
  python 03_build_web_data.py --results D:/Deform_paper/Results --out ../web/data [tag ...]
Run 04_ortho_decomposition.py afterwards to add the Ortho datasets.
"""
import argparse, base64, csv, json, math, os, re, datetime as dt
import numpy as np, pandas as pd
from config import CITY, CITY_ORDER, MASTER, PATH, HEADING, BASELINE_SECTIONS, BASELINE_TXT, all_tags

CHUNK = 600            # points per time-series file
MORTON_CELL = 0.004    # deg, grid used for the Z-order sort
OV_TARGET = 5700       # max points per city in the national overview


def b64write(path, arr):
    with open(path, 'w') as f: f.write(base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode())


def morton(ix, iy):
    def spread(x):
        x = x.astype(np.uint64) & np.uint64(0xFFFF)
        for s, m in [(8, 0x00FF00FF), (4, 0x0F0F0F0F), (2, 0x33333333), (1, 0x55555555)]:
            x = (x | (x << np.uint64(s))) & np.uint64(m)
        return x
    return spread(ix) | (spread(iy) << np.uint64(1))


def stats(v):
    return dict(median=float(np.median(v)), p5=float(np.percentile(v, 5)), p95=float(np.percentile(v, 95)),
                min=float(v.min()), max=float(v.max()),
                fast=float((v <= -5).mean()), mod=float(((v > -5) & (v <= -2)).mean()))


def read_baselines(results):
    """Perpendicular baselines (m) per acquisition, keyed by tag."""
    secs, cur = {}, None
    for line in open(os.path.join(results, BASELINE_TXT)).read().splitlines():
        m = re.match(r'\s*\d+\s+(\d\d-\w{3}-\d{4})\s+(-?\d+)\s*m', line)
        if m and cur:
            secs[cur].append([dt.datetime.strptime(m.group(1), '%d-%b-%Y').date().isoformat(), int(m.group(2))])
        else:
            for k, s in BASELINE_SECTIONS.items():
                if line.strip().startswith(s): cur = k; secs[k] = []

    def get(tag):
        if tag in BASELINE_SECTIONS: return MASTER[tag], sorted(secs[tag])
        rows = list(csv.reader(open(os.path.join(results, f'baseline_{tag}.csv'))))[1:]
        m = rows[0][0]
        return m, sorted([[r[1], int(round(float(r[2])))] for r in rows] + [[m, 0]])
    return get


def build(tag, results, out, baselines):
    p, c = tag.split('_'); key = f'{CITY[c]}-{p}'; mst = MASTER[tag]
    los = pd.read_csv(f'{results}/TS_txt/TS_{tag}_ps.txt', sep='\t')
    inc = pd.read_csv(f'{results}/TS_vertical/TS_{tag}_vert.txt', sep='\t', usecols=['inc_deg'])['inc_deg'].values
    dcols = [x for x in los.columns if x[:2] == '20']
    Y = los[dcols].values.astype(np.float64)
    dates = sorted(dcols + [mst]); Y = np.insert(Y, dates.index(mst), 0.0, axis=1)   # master epoch = 0

    t = ((pd.to_datetime(dates) - pd.Timestamp(dates[0])).days / 365.25).values
    A = np.vstack([t, np.ones_like(t)]).T; coef = np.linalg.lstsq(A, Y.T, rcond=None)[0]
    vel = coef[0]; rmse = np.sqrt(((Y - (A @ coef).T) ** 2).mean(axis=1))
    velv = vel / np.cos(np.radians(inc))

    lon, lat = los.lon.values, los.lat.values
    o = np.argsort(morton(((lon - lon.min()) / MORTON_CELL).astype(int), ((lat - lat.min()) / MORTON_CELL).astype(int)), kind='stable')
    lon, lat, vel, rmse, velv, inc, Y = lon[o], lat[o], vel[o], rmse[o], velv[o], inc[o], Y[o]

    # points: positions to 16 bits inside their bounding box (~0.3 m), values to 0.01
    f32 = [x.astype(np.float32) for x in (lon, lat, vel, rmse, velv, inc)]
    lo, la = f32[0], f32[1]
    qb = [float(lo.min()), float(la.min()), float(lo.max()), float(la.max())]
    q = np.zeros((len(lo), 6), np.uint16)
    q[:, 0] = np.round((lo.astype(np.float64) - qb[0]) / (qb[2] - qb[0]) * 65535)
    q[:, 1] = np.round((la.astype(np.float64) - qb[1]) / (qb[3] - qb[1]) * 65535)
    for j, x in enumerate(f32[2:], start=2):
        q[:, j] = np.round(x.astype(np.float64) * 100).astype(np.int16).view(np.uint16)
    b64write(f'{out}/{key}.pts.b64.txt', q)

    # time series: 0.1 mm steps in int16
    ts = np.clip(np.round(Y * 10), -32767, 32767).astype(np.int16)
    nch = math.ceil(len(ts) / CHUNK)
    for ci in range(nch): b64write(f'{out}/{key}.ts.{ci}.b64.txt', ts[ci * CHUNK:(ci + 1) * CHUNK])

    m, pairs = baselines(tag); assert m == mst, (tag, m, mst)
    meta = dict(key=key, tag=tag, city=CITY[c], track=p, n=int(len(ts)), dates=dates, master=mst, path=PATH[tag],
                chunk=CHUNK, nchunks=nch,
                bounds=[round(float(lon.min()), 5), round(float(lat.min()), 5), round(float(lon.max()), 5), round(float(lat.max()), 5)],
                inc=[round(float(inc.min()), 2), round(float(inc.max()), 2)],
                stats=stats(vel), stats_v=stats(velv), baselines=dict(master=mst, pairs=pairs),
                heading=HEADING[p], qb=qb, imin=[int(np.argmin(f32[2])), int(np.argmin(f32[4]))])
    print(f'{key}: n={len(ts)} dates={len(dates)} chunks={nch} LOS median {np.median(vel):+.2f} mm/yr', flush=True)
    return meta, (f32[0], f32[1], f32[2], f32[4])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True, help='folder with TS_txt/, TS_vertical/ and the baseline tables')
    ap.add_argument('--out', required=True, help='web data folder, e.g. ../web/data')
    ap.add_argument('tags', nargs='*')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    getbl = read_baselines(a.results)
    ip = os.path.join(a.out, 'index.json')
    index = json.load(open(ip)) if os.path.exists(ip) else []
    tags = a.tags or all_tags()
    index = [d for d in index if d.get('tag') not in tags]
    sample = {}
    for tag in tags:
        meta, s = build(tag, a.results, a.out, getbl); index.append(meta)
        if meta['track'] == 'dsc': sample[meta['city']] = s

    # national overview: a random, evenly thinned descending sample per city
    # (rebuilt only when every city's descending stack was processed in this run)
    rows, rng, start = [], np.random.default_rng(0), 0
    full = all(c in sample for c in CITY_ORDER)
    for d in index:
        if full: d.pop('ov', None)
    for city in (CITY_ORDER if full else []):
        if city not in sample: continue
        lo, la, v, vv = sample[city]; n = len(lo); k = math.ceil(n / OV_TARGET)
        pick = rng.permutation(np.arange(0, n, k))
        rows.append(np.column_stack([lo[pick], la[pick], v[pick], vv[pick]]).astype(np.float32))
        next(d for d in index if d['city'] == city and d['track'] == 'dsc')['ov'] = [start, int(len(pick))]
        start += len(pick)
    if rows: b64write(os.path.join(a.out, 'overview.b64.txt'), np.vstack(rows))

    tr = {'asc': 0, 'dsc': 1, 'ortho': 2}
    index.sort(key=lambda d: (CITY_ORDER.index(d['city']), tr[d['track']]))
    json.dump(index, open(ip, 'w'), separators=(',', ':'))
