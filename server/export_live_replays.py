"""Replay timelines for the Live Monitor, produced by running the live processor over committed recordings.

    python server/export_live_replays.py

Writes frontend/public/live/index.json and one <id>.json per recording (plus <id>.wav programme audio for
AM recordings). The browser plays these event streams with their own timestamps, so an offline demo shows
exactly the evidence a live session produced.
"""

import base64
import glob
import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))

import live                                 # noqa: E402
from make_recording import load_recording   # noqa: E402
from stations import STATIONS               # noqa: E402

REC = os.path.join(ROOT, 'recordings', 'real')
PUB = os.path.join(ROOT, 'frontend', 'public', 'live')


def replay_iq(rec_id):
    iq, meta = load_recording(rec_id)
    c = meta['capture']
    events = []

    def emit(type_, t=None, **payload):
        if type_ == 'spectrum' and events and events[-1]['type'] == 'spectrum' and t - events[-1]['t'] < 0.16:
            return                                          # ~6 rows/s is plenty for a replay
        events.append({'type': type_, 't': round(float(t if t is not None else proc.seconds), 3), **live._clean(payload)})

    st = STATIONS[meta['station_key']]
    events.append({'type': 'status', 't': 0.0, 'phase': 'directory', 'message': 'receiver selected from the public KiwiSDR directory'})
    events.append({'type': 'receiver', 't': 0.0, **live._clean(meta['receiver']), 'rssi_dbm': c.get('rssi_dbm'),
                   'fs_hz': c['fs_hz'], 'tuned_khz': c['tuned_khz'], 'timing': c['timing'], 't0_utc': c['t0_utc']})
    proc = live.LiveProcessor(meta['station_key'], c['fs_hz'], c['t0_unix'], c['timing'], 0.0, emit)
    block = int(c['fs_hz'] * 0.05)
    for i in range(0, len(iq), block):
        proc.feed(iq[i:i + block])
    out, audio = proc.finish()
    has_audio = audio is not None and STATIONS[meta['station_key']]['analysis'] == 'am'
    if has_audio:
        with wave.open(os.path.join(PUB, rec_id + '.wav'), 'w') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(round(out['runs']['am']['audio_rate_hz'])))
            w.writeframes(audio.tobytes())
    events.append({'type': 'status', 't': round(proc.seconds, 3), 'phase': 'analysing',
                   'message': f'blind analysis of {proc.seconds:.0f} s over every receiver'})
    events.append({'type': 'result', 't': round(proc.seconds + 0.5, 3), 'answer': out['answer'], 'runs': out['runs'],
                   'recording_id': rec_id, 'has_audio': has_audio})
    return meta, events, out


def replay_band(rec_id):
    d = np.load(os.path.join(REC, rec_id + '.npz'))
    meta = json.load(open(os.path.join(REC, rec_id + '.json'), encoding='utf-8'))
    rows = d['rows'].astype(np.float32) - 255.0 + meta['capture']['wf_cal_db']
    times, f = d['times'], d['freqs_khz']
    lo, hi = STATIONS['AIR-MW']['band_khz']
    sel = (f >= lo - 20) & (f <= hi + 20)
    events = [{'type': 'status', 't': 0.0, 'phase': 'directory', 'message': 'waterfall receiver selected'},
              {'type': 'receiver', 't': 0.0, **meta['receiver'], 'span_khz': [float(f[0]), float(f[-1])]}]
    last_census = 0.0
    for i, (row, t) in enumerate(zip(rows, times)):
        if i % 2 == 0:
            q = np.clip((row[sel] + 125.0) / 90.0 * 255, 0, 255).astype(np.uint8)
            events.append({'type': 'spectrum', 't': round(float(t), 3), 'row': base64.b64encode(q.tobytes()).decode(),
                           'f0_hz': float(f[sel][0] * 1e3), 'f1_hz': float(f[sel][-1] * 1e3), 'db_min': -125.0, 'db_max': -35.0})
        if t - last_census > 3 and i >= 10:
            last_census = t
            events.append({'type': 'census', 't': round(float(t), 3), **live.spectrum_census(rows[max(0, i - 40):i + 1], f)})
    census = live.spectrum_census(rows, f)
    matched = sum(1 for c in census['channels'] if c['stations'])
    answer = {'status': 'SIGNAL_NO_CODE', 'receiver': 'census', 'protocol': 'AM broadcast census',
              'summary': f"{len(census['channels'])} medium-wave carriers; {matched} match transmitters in the official AIR list"}
    events.append({'type': 'result', 't': round(float(times[-1]) + 0.5, 3), 'answer': answer, 'census': census,
                   'recording_id': rec_id})
    return meta, events, {'answer': answer, 'census': census}


def main():
    os.makedirs(PUB, exist_ok=True)
    index = []
    for path in sorted(glob.glob(os.path.join(REC, '*.json'))):
        rec_id = os.path.basename(path)[:-5]
        meta = json.load(open(path, encoding='utf-8'))
        if meta.get('kind') == 'waterfall':
            meta, events, out = replay_band(rec_id)
            station_key = 'AIR-MW'
            mode = 'band'
        else:
            meta, events, out = replay_iq(rec_id)
            station_key = meta['station_key']
            mode = 'iq'
        st = STATIONS[station_key]
        doc = {'id': rec_id, 'mode': mode, 'station_key': station_key,
               'station': {k: st[k] for k in ('name', 'operator', 'country', 'frequency_khz', 'service', 'site', 'references')},
               'recording': live._clean(meta), 'events': events}
        json.dump(doc, open(os.path.join(PUB, rec_id + '.json'), 'w', encoding='utf-8'), separators=(',', ':'))
        index.append({'id': rec_id, 'mode': mode, 'station_key': station_key, 'station': doc['station']['name'],
                      'operator': st['operator'], 'country': st['country'], 'frequency_khz': st['frequency_khz'],
                      't0_utc': meta['capture']['t0_utc'], 'duration_s': meta['capture'].get('duration_s'),
                      'receiver': meta['receiver'].get('location') or meta['receiver'].get('name'),
                      'answer': live._clean(out['answer'])})
        print(rec_id, len(events), 'events', out['answer']['status'], (out['answer'].get('summary') or '')[:80].replace('\n', ' '))
    json.dump(index, open(os.path.join(PUB, 'index.json'), 'w', encoding='utf-8'), indent=1)
    import timecodes as tc
    layouts = {}
    for proto, spec in tc.PROTOCOLS.items():
        lay = spec['layout'][0] if proto == 'MSF' else spec['layout']
        layouts[proto] = {'operator': spec['operator'], 'zone': spec['zone'], 'refers_to': spec['refers_to'],
                          'positions': [{'kind': e[0], 'field': e[1] if len(e) > 1 else None} for e in lay]}
    keys = ('name', 'operator', 'country', 'service', 'frequency_khz', 'site', 'analysis', 'capture_s', 'references')
    stations = {k: {**{kk: v[kk] for kk in keys}, 'protocol': v.get('protocol')} for k, v in STATIONS.items()}
    json.dump({'stations': stations, 'layouts': layouts}, open(os.path.join(PUB, 'stations.json'), 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    main()
