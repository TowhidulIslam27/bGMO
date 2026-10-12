"""Step 1: convert the StaMPS PS time-series CSV exports to tidy tab-separated text.

Two export layouts occur in the raw results:
  * dated header  : x, y, MM/DD/YYYY, ...          (Dhaka, Chattogram, Khulna)
  * export_res_*  : lon, lat, vel, <datenums...>   with a second row of MATLAB
                    datenums (Barishal, Sylhet, Cumilla). These datenums come out
                    one day early relative to ps_info, so +1 day is applied.

Output: <results>/TS_txt/TS_<pass>_<city>_ps.txt
  columns lon, lat, [vel_mm_yr], then one column per acquisition date (ISO),
  values are LOS displacement in mm relative to the master date.

Usage:  python 01_stamps_csv_to_txt.py --results D:/Deform_paper/Results [tag ...]
"""
import argparse, csv, datetime as dt, os
from config import EXPORTS


def matlab_datenum(n):
    return dt.date.fromordinal(int(float(n)) - 366) + dt.timedelta(1)


def convert(src, out):
    n = bad = 0
    with open(src, newline='') as fi, open(out, 'w', newline='') as fo:
        r = csv.reader(fi); w = csv.writer(fo, delimiter='\t', lineterminator='\n')
        h = next(r)
        if h[0] == 'x':                                   # dated header
            keep = [i for i, x in enumerate(h) if x != '']
            dates = [dt.datetime.strptime(h[i], '%m/%d/%Y').date().isoformat() for i in keep[2:]]
            hdr = ['lon', 'lat'] + dates
        else:                                             # export_res_* layout
            d = next(r); keep = list(range(len(h)))
            dates = [matlab_datenum(x).isoformat() for x in d[3:]]
            hdr = ['lon', 'lat', 'vel_mm_yr'] + dates
        w.writerow(hdr)
        for row in r:
            v = [row[i] for i in keep]
            if len(v) != len(hdr) or any(x == '' for x in v): bad += 1
            w.writerow(v); n += 1
    return n, dates, bad


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True, help='folder holding the StaMPS CSV exports')
    ap.add_argument('--out', help='output folder (default: <results>/TS_txt)')
    ap.add_argument('tags', nargs='*', help='e.g. dsc_dha (default: all)')
    a = ap.parse_args()
    O = a.out or os.path.join(a.results, 'TS_txt'); os.makedirs(O, exist_ok=True)
    for src, p, c in EXPORTS:
        tag = f'{p}_{c}'
        if a.tags and tag not in a.tags: continue
        n, dates, bad = convert(os.path.join(a.results, src), os.path.join(O, f'TS_{tag}_ps.txt'))
        print(f'{src} -> TS_{tag}_ps.txt  points={n} dates={len(dates)} {dates[0]}..{dates[-1]} bad_rows={bad}', flush=True)
