"""Turn a raw receiver capture (server/kiwi.py --out *.npz) into a committed real-signal recording.

    python server/make_recording.py capture.npz --id wwv-10mhz-montana --station WWV --out-rate 3000

The IQ is shifted so the tuned station sits at 0 Hz, low-pass filtered and decimated (linear phase, delay
compensated, so the GPS start time stays valid), and written as an int16 stereo I/Q .wav plus a JSON
sidecar. The sidecar keeps the exact sample rate (the WAV header can only hold an integer).
"""

import argparse
import datetime as dt
import json
import os
import sys
import wave

import numpy as np
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from stations import STATIONS          # noqa: E402

OUT_DIR = os.path.join(ROOT, 'recordings', 'real')


def write_wav(path, iq, fs):
    scale = 32000.0 / max(float(np.max(np.abs(iq.real))), float(np.max(np.abs(iq.imag))), 1e-12)
    stereo = np.empty(2 * len(iq), dtype=np.int16)
    stereo[0::2] = np.clip(iq.real * scale, -32768, 32767).astype(np.int16)
    stereo[1::2] = np.clip(iq.imag * scale, -32768, 32767).astype(np.int16)
    with wave.open(path, 'w') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(int(round(fs)))
        w.writeframes(stereo.tobytes())


def load_recording(rec_id, directory=OUT_DIR):
    """(iq, meta) for a committed recording, using the exact sample rate from the sidecar."""
    meta = json.load(open(os.path.join(directory, rec_id + '.json'), encoding='utf-8'))
    with wave.open(os.path.join(directory, rec_id + '.wav')) as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return (raw[0::2] + 1j * raw[1::2]).astype(np.complex64), meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz')
    ap.add_argument('--id', required=True)
    ap.add_argument('--station', required=True, help='key in server/stations.py')
    ap.add_argument('--out-rate', type=float, default=3000.0, help='approximate output sample rate (Hz)')
    ap.add_argument('--note', default='')
    a = ap.parse_args()
    st = STATIONS[a.station]
    d = np.load(a.npz)
    cap = json.loads(str(d['meta']))
    iq = d['iq'].astype(np.complex128)
    fs = float(cap['fs'])
    shift = float(cap.get('tuning_offset_hz', st['tuning_offset_hz']))
    iq = iq * np.exp(-2j * np.pi * shift * np.arange(len(iq)) / fs)
    down = max(1, int(round(fs / a.out_rate)))
    out = resample_poly(iq, 1, down, window=('kaiser', 8.0)) if down > 1 else iq
    fs_out = fs / down
    os.makedirs(OUT_DIR, exist_ok=True)
    write_wav(os.path.join(OUT_DIR, a.id + '.wav'), out, fs_out)
    rx = cap['receiver']
    t0 = cap['t0_unix']
    meta = {
        'id': a.id, 'station_key': a.station, 'station': {k: st[k] for k in ('name', 'operator', 'country', 'frequency_khz',
                                                                              'service', 'site', 'references')},
        'receiver': {'url': rx.get('url'), 'name': rx.get('rx_name') or rx.get('name'), 'location': rx.get('loc'),
                     'gps': rx.get('gps'), 'distance_km': rx.get('distance_km'), 'gps_timed': rx.get('gps_timed'),
                     'software': f"KiwiSDR v{rx.get('version_maj', '?')}.{rx.get('version_min', '?')}"},
        'capture': {'t0_unix': t0, 't0_utc': dt.datetime.fromtimestamp(t0, dt.timezone.utc).isoformat(timespec='milliseconds'),
                    'timing': cap['timing'], 'gps_stamp_spread_s': cap.get('gps_stamp_spread_s'),
                    'tuned_khz': cap['freq_khz'], 'receiver_fs_hz': fs, 'baseband_shift_hz': shift,
                    'decimation': down, 'fs_hz': fs_out, 'wav_header_fs_hz': int(round(fs_out)),
                    'duration_s': round(len(out) / fs_out, 3), 'rssi_dbm': round(cap.get('rssi_dbm', 0.0), 1),
                    'adc_overflow_blocks': cap.get('adc_overflow_blocks')},
        'note': a.note,
    }
    json.dump(meta, open(os.path.join(OUT_DIR, a.id + '.json'), 'w', encoding='utf-8'), indent=1)
    print(a.id, len(out), 'samples at', round(fs_out, 3), 'Hz', os.path.getsize(os.path.join(OUT_DIR, a.id + '.wav')) // 1024, 'KiB')


if __name__ == '__main__':
    main()
