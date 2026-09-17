"""One entry point for real narrowband captures (LF/MF/HF, a few kHz wide).

Runs every receiver that could apply and reports each one's own decision; nothing is chosen by hint alone.
  - time codes (timecodes.receive): WWV, WWVB, DCF77, MSF, JJY
  - start-stop FSK text (fsk.analyze_fsk): baud, shift, framing, ITA2/ASCII
  - CHU FSK time code (fsk.chu_packets)
  - AM broadcast characterisation (broadcast.analyze_am)
The overall answer is the most specific DECODED result; otherwise the strongest detection.
"""

import time

import numpy as np

import broadcast
import fsk
import timecodes


def analyze_capture(iq, fs, t0_unix=None, timing=None, tuning_offset_hz=None, receivers=None):
    iq = np.asarray(iq, dtype=complex)
    wanted = set(receivers or ('timecode', 'fsk', 'chu', 'am'))
    out = {'samples': len(iq), 'fs_hz': fs, 'duration_s': round(len(iq) / fs, 3), 'timing': timing,
           't0_unix': t0_unix, 'runs': {}}
    search = (tuning_offset_hz, 80.0) if tuning_offset_hz is not None else None
    timers = {}

    def run(name, fn):
        t = time.time()
        try:
            out['runs'][name] = fn()
        except Exception as e:                        # a receiver failing must not hide the others
            out['runs'][name] = {'status': 'ERROR', 'error': f'{type(e).__name__}: {e}'}
        timers[name] = round(time.time() - t, 3)

    if 'timecode' in wanted and len(iq) / fs >= 62:
        run('timecode', lambda: timecodes.receive(iq, fs, t0_unix, timing, carrier_search=search))
    if 'fsk' in wanted:
        run('fsk', lambda: fsk.analyze_fsk(iq, fs))
    if 'chu' in wanted and len(iq) / fs >= 2 and fs >= 5000:
        run('chu', lambda: fsk.chu_packets(iq, fs, t0_unix, timing,
                                           carrier_hz=(tuning_offset_hz if tuning_offset_hz is not None else None)))
    if 'am' in wanted:
        run('am', lambda: broadcast.analyze_am(iq, fs, search_hz=abs(tuning_offset_hz or 0) + 600))
    out['timers_s'] = timers
    audio = out['runs'].get('am', {}).pop('_audio_pcm', None)
    answer = None
    tc = out['runs'].get('timecode', {})
    fk = out['runs'].get('fsk', {})
    ch = out['runs'].get('chu', {})
    if tc.get('status') == 'DECODED':
        best = next(r for r in tc['results'] if r['accepted'] and r['protocol'] == tc['protocol'])
        answer = {'status': 'DECODED', 'receiver': 'timecode', 'protocol': tc['protocol'],
                  'operator': best['operator'], 'summary': f"{tc['protocol']} time code: {tc['utc']} UTC",
                  'log10_p': best['log10_p'], 'verification': best.get('verification')}
    elif ch.get('status') == 'DECODED':
        pk = next(p for p in ch['packets'] if p['redundancy_ok'])
        answer = {'status': 'DECODED', 'receiver': 'chu', 'protocol': 'CHU', 'operator': 'NRC (Canada)',
                  'summary': f"CHU time code {pk.get('utc', '')}", 'log10_p': pk['log10_p'],
                  'verification': pk.get('verification')}
    elif fk.get('status') == 'DECODED' and fk.get('printable_fraction', 0) > 0.8:
        answer = {'status': 'DECODED', 'receiver': 'fsk', 'protocol': f"{fk['code']} {fk['baud']:g} Bd FSK",
                  'summary': fk['text'][:160], 'log10_p': fk['framing']['log10_p']}
    elif tc.get('status') == 'SIGNAL_NO_CODE':
        answer = {'status': 'SIGNAL_NO_CODE', 'receiver': 'timecode', 'protocol': tc['protocol'], 'summary': tc['reason']}
    elif out['runs'].get('am', {}).get('status') == 'SIGNAL_NO_CODE':
        am = out['runs']['am']
        answer = {'status': 'SIGNAL_NO_CODE', 'receiver': 'am', 'protocol': 'AM broadcast',
                  'summary': f"{am['modulation']}, carrier {am['carrier_to_noise_db']} dB above noise"}
    out['answer'] = answer or {'status': 'UNKNOWN', 'summary': 'no receiver established a signal'}
    return out, audio
