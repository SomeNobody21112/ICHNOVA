"""Record a KiwiSDR waterfall (e.g. the Indian medium-wave band) for offline census replay.

    python server/record_band.py --url http://vu2cpl.ddns.net:8073 --cf 1066.5 --zoom 4 --seconds 60 --id air-mw-band-bangalore
"""

import argparse
import datetime as dt
import json
import os
import time

import numpy as np

import kiwi

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'recordings', 'real')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--cf', type=float, required=True)
    ap.add_argument('--zoom', type=int, default=4)
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--id', required=True)
    ap.add_argument('--location', default='')
    a = ap.parse_args()
    rows, times = [], []
    t0 = time.time()
    with kiwi.KiwiWaterfall(a.url, a.cf, a.zoom) as wf:
        for row, info in wf.rows():
            rows.append(np.clip(np.round(row + 255.0), 0, 255).astype(np.uint8))
            times.append(info['received_unix'] - t0)
            if time.time() - t0 >= a.seconds:
                break
        freqs = wf.freqs_khz()
        name = wf.meta.get('rx_name')
        wf_cal = wf.wf_cal
    os.makedirs(OUT, exist_ok=True)
    np.savez_compressed(os.path.join(OUT, a.id + '.npz'), rows=np.array(rows), times=np.array(times), freqs_khz=freqs)
    meta = {'id': a.id, 'kind': 'waterfall', 'receiver': {'url': a.url, 'name': name, 'location': a.location},
            'capture': {'t0_unix': t0, 't0_utc': dt.datetime.fromtimestamp(t0, dt.timezone.utc).isoformat(timespec='seconds'),
                        'timing': 'arrival', 'cf_khz': a.cf, 'zoom': a.zoom, 'rows': len(rows), 'duration_s': round(times[-1], 2),
                        'row_units': 'dBm = value - 255 + wf_cal', 'wf_cal_db': wf_cal},
            'station_key': 'AIR-MW'}
    json.dump(meta, open(os.path.join(OUT, a.id + '.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows), 'rows', freqs[0], freqs[-1])
