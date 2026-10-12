"""Shared settings for the bGMO processing chain.

Each dataset is identified by a tag '<pass>_<city>', e.g. 'dsc_dha' for the
descending stack over Dhaka.
"""

# city codes used in file names -> city ids used by the web map
CITY = {'dha': 'dhaka', 'ctg': 'chattogram', 'khu': 'khulna',
        'bar': 'barishal', 'syl': 'sylhet', 'com': 'cumilla'}
CITY_ORDER = ['dhaka', 'chattogram', 'khulna', 'barishal', 'sylhet', 'cumilla']

# StaMPS CSV exports -> (pass, city code)
EXPORTS = [('TS_asc_dha_ps.csv', 'asc', 'dha'), ('TS_dsc_dha_ps.csv', 'dsc', 'dha'),
           ('TS_asc_ctg_ps.csv', 'asc', 'ctg'), ('TS_dsc_ctg_ps.csv', 'dsc', 'ctg'),
           ('TS_asc_khu_ps.csv', 'asc', 'khu'), ('TS_dsc_khu_ps.csv', 'dsc', 'khu'),
           ('syl_Asc .csv', 'asc', 'syl'), ('syl_Dsc.csv', 'dsc', 'syl'),
           ('Bar_Asc.csv', 'asc', 'bar'), ('Bar_Dsc.csv', 'dsc', 'bar'),
           ('Com_Asc.csv', 'asc', 'com'), ('Com_Dsc.csv', 'dsc', 'com')]

# master (reference) acquisition of each stack; displacement is 0 there by definition
MASTER = {'asc_dha': '2020-12-16', 'asc_khu': '2020-12-16', 'asc_bar': '2020-12-16', 'asc_com': '2020-12-16',
          'asc_ctg': '2020-08-06', 'asc_syl': '2020-06-26',
          'dsc_dha': '2020-10-19', 'dsc_khu': '2020-10-19', 'dsc_bar': '2020-10-19',
          'dsc_ctg': '2021-11-14', 'dsc_syl': '2022-01-01', 'dsc_com': '2022-01-01'}

# Sentinel-1 relative orbit (path) of each stack
PATH = {'asc_dha': 114, 'asc_khu': 114, 'asc_bar': 114, 'asc_com': 114, 'asc_ctg': 114, 'asc_syl': 41,
        'dsc_dha': 150, 'dsc_khu': 150, 'dsc_bar': 150, 'dsc_ctg': 77, 'dsc_syl': 77, 'dsc_com': 77}

# SLC frame used for each stack (footprints in FRAMES below)
FRAME = {'asc_dha': 'p114', 'asc_khu': 'p114', 'asc_bar': 'p114', 'asc_com': 'p114',
         'asc_ctg': 'p114s', 'asc_syl': 'p41',
         'dsc_dha': 'p150', 'dsc_khu': 'p150s', 'dsc_bar': 'p150s',
         'dsc_ctg': 'p77s', 'dsc_syl': 'p77n', 'dsc_com': 'p77m'}

# SLC frame footprint edges (lon, lat) from the NASA CMR / ASF granule metadata.
# W/E are the western and eastern long edges. Sentinel-1 looks right, so the
# near-range edge is W on ascending passes and E on descending passes.
FRAMES = {
    'p114':  dict(W=[(89.097237, 23.81686), (89.443008, 22.189425)], E=[(91.885185, 22.614655), (91.570801, 24.23884)], asc=True),
    'p114s': dict(W=[(89.415573, 22.317778), (89.770828, 20.632208)], E=[(92.185944, 21.060772), (91.860458, 22.742825)], asc=True),
    'p41':   dict(W=[(90.869606, 25.162235), (91.230408, 23.476929)], E=[(93.694572, 23.899137), (93.36866, 25.581211)], asc=True),
    'p150':  dict(E=[(91.127937, 23.428671), (91.477821, 25.063679)], W=[(88.988754, 25.481558), (88.672462, 23.849678)], asc=False),
    'p150s': dict(E=[(90.810524, 21.929443), (91.157402, 23.56461)], W=[(88.699036, 23.985392), (88.383087, 22.3535)], asc=False),
    'p77s':  dict(E=[(92.596016, 20.640978), (92.940613, 22.27607)], W=[(90.509193, 22.699039), (90.193291, 21.067337)], asc=False),
    'p77n':  dict(E=[(93.22937, 23.640032), (93.590828, 25.326694)], W=[(91.098618, 25.743635), (90.77224, 24.060169)], asc=False),
    'p77m':  dict(E=[(92.911751, 22.141489), (93.258896, 23.776087)], W=[(90.798843, 24.196003), (90.482956, 22.564653)], asc=False),
}

# geometry constants
EARTH_R_KM = 6375.0      # local Earth radius at ~23 deg N
S1_ALT_KM = 693.0        # Sentinel-1 orbit altitude
IW_FAR_INC_DEG = 46.0    # IW swath far-edge incidence angle

# track heading (deg from north) shown in the web map; the descending
# flight azimuth used for decomposition is heading + 180 (about 191 deg)
HEADING = {'asc': -11.1, 'dsc': 11.0}

# baseline tables: Dhaka, Chattogram and Khulna come as baseline_<tag>.csv,
# the other three cities as sections of one text file
BASELINE_SECTIONS = {'dsc_bar': 'Barishal_Descending', 'asc_bar': 'Barishal Ascending',
                     'asc_syl': 'Sylhet Ascending', 'dsc_syl': 'Sylhet Descending',
                     'dsc_com': 'Comilla Descending', 'asc_com': 'Comilla Ascending'}
BASELINE_TXT = 'Baseline_Syl_Com_Bar.txt'


def all_tags():
    return [f'{p}_{c}' for _, p, c in EXPORTS]
