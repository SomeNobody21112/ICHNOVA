"""Real-signal receivers: synthetic round trips, null behaviour, and regression on recordings of real
government transmissions (recordings/real, GPS-timestamped by the receiving KiwiSDR)."""

import datetime as dt
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import broadcast                                   # noqa: E402
import fsk                                         # noqa: E402
import realsig                                     # noqa: E402
import timecodes as tc                             # noqa: E402
from make_recording import load_recording          # noqa: E402

START = dt.datetime(2026, 9, 17, 2, 57, 23, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize('protocol', ['WWV', 'WWVB', 'DCF77', 'MSF', 'JJY'])
def test_timecode_round_trip(protocol):
    fs = 3000.0
    lead = 0.412
    iq = tc.synthesize(protocol, START, 190, fs=fs, snr_db=12, lead_s=lead, rng=np.random.default_rng(7),
                       flags={'dst1': 1, 'dst2': 1} if protocol == 'WWV' else None)
    r = tc.receive(iq, fs, t0_unix=START.timestamp() - lead, timing='gps', protocols=[protocol], carrier_hz=-1000.0)
    res = r['results'][0]
    assert r['status'] == 'DECODED', res.get('unresolved_digits')
    # The first complete frame starts at the first whole minute after the receiver settles.
    assert r['utc'] == '2026-09-17T02:58:00+00:00'
    assert abs(res['verification']['arrival_minus_decoded_ms']) < 15
    assert res['complete_frames'] >= 2 and res['time_established']


def test_timecode_catalogue_accepts_only_the_transmitted_protocol():
    iq = tc.synthesize('DCF77', START, 190, fs=3000.0, snr_db=15, rng=np.random.default_rng(3))
    r = tc.receive(iq, 3000.0, carrier_hz=-1000.0)
    assert r['protocol'] == 'DCF77' and r['status'] == 'DECODED'
    assert [x['protocol'] for x in r['results'] if x['accepted']] == ['DCF77']


def test_timecode_noise_is_unknown():
    rng = np.random.default_rng(11)
    n = int(190 * 3000)
    iq = np.exp(-2j * np.pi * 1000 * np.arange(n) / 3000) + 0.3 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    r = tc.receive(iq, 3000.0, carrier_hz=-1000.0)
    assert r['status'] == 'UNKNOWN'
    assert not any(x['detected'] for x in r['results'])


def test_timecode_encode_decode_fields_are_inverse():
    t = dt.datetime(2031, 2, 28, 23, 59, tzinfo=dt.timezone.utc)
    for p in tc.PROTOCOLS:
        values = tc.fields_for(p, t, {'cest': 0} if p == 'DCF77' else ({'bst': 0} if p == 'MSF' else None))
        assert tc.frame_time(p, values) == t, p


def test_fsk_ita2_blind_parameters_and_text():
    msg = 'ZCZC SEA WEATHER REPORT GERMAN BIGHT WEST 5 NNNN '
    iq = fsk.synthesize_async(fsk.ita2_encode(msg) * 4, 8000, 45.45, -1085.0, -915.0, data_bits=5, stop_bits=1.5,
                              snr_db=8, rng=np.random.default_rng(5))
    r = fsk.analyze_fsk(iq, 8000)
    assert r['status'] == 'DECODED'
    assert r['baud'] == 45.45
    assert abs(r['measured_shift_hz'] - 170) < 15
    assert msg.strip() in r['text']


def test_fsk_noise_is_not_decoded():
    rng = np.random.default_rng(2)
    iq = rng.standard_normal(8000 * 30) + 1j * rng.standard_normal(8000 * 30)
    assert fsk.analyze_fsk(iq, 8000)['status'] != 'DECODED'


def test_chu_packet_redundancy_and_time():
    t = dt.datetime(2026, 9, 17, 3, 20, 35, tzinfo=dt.timezone.utc)
    iq, t0 = fsk.chu_synthesize(t, snr_db=15, rng=np.random.default_rng(1))
    r = fsk.chu_packets(iq, 12000.0, t0, 'gps', carrier_hz=-1500.0)
    pk = [p for p in r['packets'] if p['redundancy_ok']]
    assert r['status'] == 'DECODED' and pk[0]['utc'] == t.isoformat()
    assert abs(pk[0]['verification']['arrival_minus_decoded_ms']) < 5


def test_am_characterisation():
    fs, n = 12000.0, 12000 * 20
    t = np.arange(n) / fs
    audio = 0.5 * np.sin(2 * np.pi * 1000 * t)
    rng = np.random.default_rng(4)
    iq = (1 + audio) * np.exp(2j * np.pi * 12.3 * t) + 0.01 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    r = broadcast.analyze_am(iq, fs)
    assert abs(r['carrier_offset_hz'] - 12.3) < 0.01
    assert abs(r['modulation_depth_rms'] - 0.5 / math.sqrt(2)) < 0.03
    assert r['receiver_passband'] == 'both sidebands' and r['modulation'].startswith('AM (double')


REAL = os.path.join(ROOT, 'recordings', 'real')


def _real(rec_id):
    if not os.path.exists(os.path.join(REAL, rec_id + '.wav')):
        pytest.skip('recording not present')
    iq, meta = load_recording(rec_id)
    c = meta['capture']
    out, _ = realsig.analyze_capture(iq, c['fs_hz'], c['t0_unix'], c['timing'], 0.0)
    return out, meta


@pytest.mark.parametrize('rec_id,protocol', [
    ('jjy40-japan-2026-09-17', 'JJY'), ('dcf77-france-2026-09-17', 'DCF77'),
    ('msf-uk-2026-09-17', 'MSF'), ('wwv-10mhz-montana-2026-09-17', 'WWV'),
])
def test_real_government_time_signal_decodes_to_gps_time(rec_id, protocol):
    out, meta = _real(rec_id)
    a = out['answer']
    assert a['status'] == 'DECODED' and a['protocol'] == protocol
    # Independent check: the decoded minute is where the GPS-stamped capture says the frame arrived.
    assert a['verification']['timing'] == 'gps'
    assert abs(a['verification']['arrival_minus_decoded_ms']) < 60


def test_real_weak_wwvb_is_refused_not_guessed():
    out, _ = _real('wwvb-montana-2026-09-17')
    assert out['answer']['status'] == 'SIGNAL_NO_CODE'
    assert out['runs']['timecode']['protocol'] == 'WWVB'


def test_real_dwd_rtty_text():
    out, _ = _real('ddh47-denmark-2026-09-17')
    fk = out['runs']['fsk']
    assert fk['status'] == 'DECODED' and fk['baud'] == 50.0 and fk['code'] == 'ITA2'
    assert 'DE DDH47' in fk['text'] and '147.3 KHZ' in fk['text']
    assert abs(fk['measured_shift_hz'] - 85) < 6


def test_real_air_medium_wave_carrier():
    out, _ = _real('air-chennai-720-bangalore-2026-09-17')
    am = out['runs']['am']
    assert am['carrier_to_noise_db'] > 40 and abs(am['carrier_offset_hz']) < 5


def test_live_processor_replay_establishes_time_like_a_live_session():
    import live
    iq, meta = load_recording('jjy40-japan-2026-09-17')
    c = meta['capture']
    events = []
    proc = live.LiveProcessor('JJY', c['fs_hz'], c['t0_unix'], c['timing'], 0.0,
                              lambda type_, t=None, **p: events.append({'type': type_, **p}))
    block = int(c['fs_hz'] * 0.05)
    for i in range(0, len(iq), block):
        proc.feed(iq[i:i + block])
    kinds = {e['type'] for e in events}
    assert {'spectrum', 'symbol', 'decode', 'status'} <= kinds
    last = [e for e in events if e['type'] == 'decode'][-1]
    assert last['established'] and last['utc'] == '2026-09-17T03:17:00+00:00'


def test_air_band_census_matches_official_list():
    import live
    path = os.path.join(REAL, 'air-mw-band-bangalore-2026-09-17.npz')
    if not os.path.exists(path):
        pytest.skip('recording not present')
    import json
    z = np.load(path)
    meta = json.load(open(path[:-4] + '.json', encoding='utf-8'))
    rows = z['rows'].astype(float) - 255.0 + meta['capture']['wf_cal_db']
    census = live.spectrum_census(rows, z['freqs_khz'])
    names = {s['station'] for ch in census['channels'] for s in ch['stations']}
    assert 612.0 in [ch['khz'] for ch in census['channels']] and 'Bangalore' in names
    assert all(ch['stations'] for ch in census['channels'])
