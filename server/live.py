"""Live reception sessions: real receiver -> incremental evidence -> final blind analysis -> recording.

A session is a thread that feeds IQ blocks into a LiveProcessor. The processor is source-agnostic: the same
code turns a committed recording into a replay timeline (server/export_live_replays.py), so what the
browser replays offline is exactly what it would have shown live.

Events (dicts with 'type' and 't' = seconds since capture start):
  status     {phase, message}
  receiver   {url, name, location, gps, distance_km, gps_timed, rssi_dbm}
  spectrum   {row: base64 uint8[bins], f0_hz, f1_hz, db_min, db_max}
  symbol     {k, symbol, confidence, utc_second}                 time codes, one per received second
  decode     {protocol, frames, utc, digits, established, log10_p, mismatches, observed}
  fsk        {baud, shift_hz, framing, text, log10_p}
  am         {carrier_offset_hz, carrier_to_noise_db, modulation_depth_rms, audio_bandwidth_99_hz, ...}
  census     {channels: [{khz, level_db, stations: [...]}]}      band sessions
  result     {answer, runs, recording_id}
  error      {message}
"""

import base64
import datetime as dt
import json
import math
import os
import queue
import sys
import threading
import time
import uuid

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))

import broadcast                          # noqa: E402
import fsk                                # noqa: E402
import kiwi                               # noqa: E402
import realsig                            # noqa: E402
import timecodes as tc                    # noqa: E402
from make_recording import write_wav      # noqa: E402
from stations import STATIONS             # noqa: E402

LIVE_DIR = os.path.join(ROOT, 'results', 'live')
AIR_REFERENCE = os.path.join(ROOT, 'recordings', 'reference', 'air_mw_transmitters.json')
MAX_SESSIONS = 3
SPECTRUM_ROWS_PER_S = 8
SPECTRUM_BINS = 256
DISPLAY_SPAN_HZ = {'timecode': 160.0, 'fsk': 320.0, 'chu': 3200.0, 'am': 5000.0}
DISPLAY_WINDOW_S = {'timecode': 0.25, 'fsk': 0.08, 'chu': 0.03, 'am': 0.06}   # short enough to show keying


def _b64(arr):
    return base64.b64encode(np.asarray(arr, dtype=np.uint8).tobytes()).decode()


def _clean(o):
    """JSON-safe copy (numpy scalars/arrays -> Python)."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items() if not str(k).startswith('_')}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


class LiveProcessor:
    """Incremental analysis of one station's IQ stream."""

    def __init__(self, station_key, fs, t0_unix, timing, tuning_offset_hz, emit):
        self.key = station_key
        self.st = STATIONS[station_key]
        self.kind = self.st['analysis']
        self.fs = fs
        self.t0 = t0_unix
        self.timing = timing
        self.offset = tuning_offset_hz
        self.emit = emit
        self.buf = np.zeros(1 << 16, dtype=np.complex64)
        self.n = 0
        self.last_row_n = 0
        self.next_work_s = 10.0 if self.kind in ('timecode', 'fsk') else 3.0
        self.carrier = None
        self.epoch = None
        self.epoch_fixed = False
        self.symbols = {}
        self.frames_reported = 0
        self.last_decode_emit_s = 0.0
        self.fsk_chars = 0
        self.chu_seen = set()
        span = DISPLAY_SPAN_HZ[self.kind]
        self.span = span
        self.nfft = 1 << int(round(math.log2(max(self.fs * DISPLAY_WINDOW_S[self.kind], 32))))

    # ------------------------------------------------------------------ buffers
    @property
    def seconds(self):
        return self.n / self.fs

    def iq(self, last_s=None):
        """View of the capture so far (or its last `last_s` seconds)."""
        if last_s is None:
            return self.buf[:self.n]
        return self.buf[max(0, self.n - int(last_s * self.fs)):self.n]

    def feed(self, block):
        block = np.asarray(block, dtype=np.complex64)
        if self.n + len(block) > len(self.buf):                   # amortised doubling, no per-row copies
            grown = np.zeros(max(2 * len(self.buf), self.n + len(block)), dtype=np.complex64)
            grown[:self.n] = self.buf[:self.n]
            self.buf = grown
        self.buf[self.n:self.n + len(block)] = block
        self.n += len(block)
        self._spectrum_rows()
        if self.seconds >= self.next_work_s:
            step = {'timecode': 1.0, 'fsk': 5.0, 'chu': 2.0, 'am': 3.0}[self.kind]
            self.next_work_s = self.seconds + step
            try:
                getattr(self, '_work_' + self.kind)()
            except Exception as e:                      # keep streaming; the final analysis decides
                self.emit('status', phase='warning', message=f'incremental {self.kind} step failed: {e}')

    # ------------------------------------------------------------------ spectrum
    def _spectrum_rows(self):
        hop = int(self.fs / SPECTRUM_ROWS_PER_S)
        while self.n - self.last_row_n >= hop and self.n >= self.nfft:
            self.last_row_n += hop
            x = self.buf[self.last_row_n - self.nfft:self.last_row_n] if self.last_row_n >= self.nfft else self.buf[:self.nfft]
            spec = np.fft.fftshift(np.abs(np.fft.fft(x * np.hanning(len(x)))) ** 2)
            f = np.fft.fftshift(np.fft.fftfreq(len(x), 1 / self.fs))
            centre = self.offset
            grid = np.linspace(centre - self.span, centre + self.span, SPECTRUM_BINS)
            db = 10 * np.log10(np.interp(grid, f, spec) + 1e-20)
            lo = float(np.percentile(db, 10)) - 6
            hi = max(lo + 40.0, float(np.max(db)) + 3)          # keep strong carriers inside the colour range
            q = np.clip((db - lo) / (hi - lo) * 255, 0, 255)
            self.emit('spectrum', row=_b64(q), f0_hz=float(grid[0] - centre), f1_hz=float(grid[-1] - centre),
                      db_min=round(lo, 1), db_max=round(hi, 1), t=self.last_row_n / self.fs)

    # ------------------------------------------------------------------ time codes
    def _work_timecode(self):
        proto = self.st['protocol']
        demod = tc.PROTOCOLS[proto]['demod']
        if self.carrier is None or int(self.seconds) % 20 == 0:
            recent = self.iq(10.0)
            shifted = recent * np.exp(-2j * np.pi * self.offset * np.arange(len(recent)) / self.fs)
            fc, db = tc.find_carrier(shifted, self.fs, 80.0)
            self.carrier = fc + self.offset
            self.emit('status', phase='carrier', message=f'carrier {db:.0f} dB above noise at {self.carrier - self.offset:+.2f} Hz from tuning',
                      carrier_db=round(db, 1))
        if not self.epoch_fixed and (self.epoch is None or int(self.seconds) % 5 == 0):
            data = self.iq()
            env = tc.envelopes(data, self.fs, self.carrier)
            series = env['subcarrier'] if demod == 'subcarrier' else env['carrier']
            tick = env['tick'] if demod == 'subcarrier' else None
            self.epoch, contrast = tc.estimate_epoch(series, env['rate'], proto, tick)
            self.epoch_fixed = self.seconds >= 40
            self.emit('status', phase='epoch', message=f'second epoch at {self.epoch * 1e3:.1f} ms (fold contrast {contrast:.1f})',
                      epoch_ms=round(self.epoch * 1e3, 1), fixed=self.epoch_fixed)
        chunk_s = min(self.seconds, 8.0)
        chunk = self.iq(chunk_s)
        start_s = self.seconds - len(chunk) / self.fs
        env = tc.envelopes(chunk, self.fs, self.carrier)
        series = env['subcarrier'] if demod == 'subcarrier' else env['carrier']
        rel_epoch = (self.epoch - start_s) % 1.0
        starts, res, amp, names = tc._fit_seconds(series, env['rate'], rel_epoch, proto)
        if not starts:
            return
        depth = amp.max(axis=1)
        typical = float(np.median(depth))
        new = False
        for i, s_rel in enumerate(starts):
            s_abs = start_s + s_rel
            if s_rel < 0.3 or s_rel + 1.3 > len(chunk) / self.fs:
                continue
            k = int(round(s_abs - self.epoch))
            if k in self.symbols or s_abs < tc.SETTLE_S:
                continue
            order = np.argsort(res[i])
            sym = names[order[0]]
            conf = float((res[i, order[1]] - res[i, order[0]]) / (res[i, order[1]] + 1e-12))
            flat = (proto == 'DCF77' and sym == 'M') or (proto == 'WWV' and sym == 'H')
            if not flat and depth[i] < 0.3 * max(typical, 1e-12):
                sym, conf = None, 0.0
            self.symbols[k] = {'start_s': s_abs, 'symbol': sym, 'confidence': round(max(conf, 0.0), 3)}
            arrival = self.t0 + s_abs if self.t0 else None
            self.emit('symbol', k=k, symbol=sym, confidence=round(max(conf, 0.0), 3),
                      utc_second=None if arrival is None else int(math.floor(arrival + 0.5)), t=s_abs)
            new = True
        if new and len(self.symbols) >= 60:
            self._emit_decode(proto)

    def _symbol_list(self):
        ks = sorted(self.symbols)
        out = []
        for k in range(ks[0], ks[-1] + 1):
            s = self.symbols.get(k)
            out.append(s if s else {'start_s': self.epoch + k, 'symbol': None, 'confidence': 0.0})
        return out

    def _emit_decode(self, proto):
        syms = self._symbol_list()
        r = tc.decode(syms, proto, self.t0, self.timing)
        frames = r.get('complete_frames', 0)
        if frames == self.frames_reported and self.seconds - self.last_decode_emit_s < 15:
            return
        self.frames_reported = frames
        self.last_decode_emit_s = self.seconds
        detected = r.get('decoded') and r.get('log10_p', 0) <= math.log10(tc.ALPHA / len(tc.PROTOCOLS))
        self.emit('decode', protocol=proto, frames=frames, utc=r.get('utc_first_frame'), digits=r.get('digits'),
                  established=bool(detected and r.get('time_established')), detected=bool(detected),
                  log10_p=r.get('log10_p'), mismatches=r.get('mismatches'), observed=r.get('observed_symbols'),
                  flags=r.get('flags'), verification=r.get('verification'), frame_offset=r.get('frame_offset'))

    # ------------------------------------------------------------------ FSK text
    def _work_fsk(self):
        r = fsk.analyze_fsk(self.iq(), self.fs, search=(self.offset, 600.0))
        if r.get('status') != 'DECODED':
            self.emit('fsk', status=r.get('status'), reason=r.get('reason'), baud=r.get('baud'))
            return
        self.emit('fsk', status='DECODED', baud=r['baud'], baud_estimate=r.get('baud_estimate'),
                  shift_hz=r.get('measured_shift_hz'), center_offset_hz=round(r['center_hz'] - self.offset, 2),
                  framing=_clean(r['framing']), code=r['code'], text=r['text'], log10_p=r['framing']['log10_p'])

    # ------------------------------------------------------------------ CHU
    def _work_chu(self):
        r = fsk.chu_packets(self.iq(15.0), self.fs, None, self.timing, carrier_hz=self.offset)
        for p in r['packets']:
            key = (p.get('hour'), p.get('minute'), p.get('second'), p['format'])
            if p['redundancy_ok'] and key not in self.chu_seen:
                self.chu_seen.add(key)
                self.emit('chu', **_clean(p))

    # ------------------------------------------------------------------ AM
    def _work_am(self):
        r = broadcast.analyze_am(self.iq(10.0), self.fs, search_hz=abs(self.offset) + 600)
        self.emit('am', **_clean({k: v for k, v in r.items() if not k.startswith('_')}))

    # ------------------------------------------------------------------ final
    def finish(self):
        data = self.iq()
        out, audio = realsig.analyze_capture(data, self.fs, self.t0, self.timing, self.offset)
        return _clean(out), audio


def spectrum_census(rows_dbm, freqs_khz, band=(526.5, 1606.5), raster=9.0, min_prominence_db=6.0):
    """Carrier census of a medium-wave waterfall, matched to the official AIR transmitter list.

    A channel counts only if it is a local maximum that stands out from its own +-1.5-channel neighbourhood
    (topographic prominence), so the skirts and splatter of a strong local transmitter are not reported as
    separate stations."""
    ref = json.load(open(AIR_REFERENCE, encoding='utf-8'))
    m = np.mean(rows_dbm, axis=0)
    sel = (freqs_khz >= band[0]) & (freqs_khz <= band[1])
    f, p = freqs_khz[sel], m[sel]
    df = float(f[1] - f[0])
    half = max(2, int(round(1.5 * raster / df)))
    floor = float(np.median(p))
    cand = []
    for i in range(1, len(p) - 1):
        if p[i] < p[i - 1] or p[i] < p[i + 1]:
            continue
        left = p[max(0, i - half):i]
        right = p[i + 1:i + 1 + half]
        if len(left) == 0 or len(right) == 0:
            continue
        prominence = p[i] - max(float(left.min()), float(right.min()))
        if prominence >= min_prominence_db:
            cand.append((i, prominence))
    peaks = []
    for i, prom in sorted(cand, key=lambda c: -p[c[0]]):
        if all(abs(f[i] - f[j]) > 0.6 * raster for j, _ in peaks):
            peaks.append((i, prom))
    obs = np.array([f[i] for i, _ in peaks])
    coef = (1.0, 0.0)
    corrected = obs
    if len(obs) >= 4:
        nominal = np.round((obs - 531.0) / raster) * raster + 531.0
        A = np.vstack([nominal, np.ones_like(nominal)]).T
        fit, *_ = np.linalg.lstsq(A, obs, rcond=None)
        resid = obs - A @ fit
        if abs(fit[0] - 1) < 0.01 and np.max(np.abs(resid)) < raster / 3:
            coef, corrected = (float(fit[0]), float(fit[1])), (obs - fit[1]) / fit[0]
    channels = {}
    for (i, prom), fc in zip(peaks, corrected):
        khz = round((fc - 531.0) / raster) * raster + 531.0
        if khz in channels and channels[khz]['level_db'] >= p[i] - floor:
            continue                                   # one entry per channel: keep its strongest peak
        stations = [t for t in ref['transmitters'] if abs(t['frequency_khz'] - khz) < 0.5]
        channels[khz] = {'khz': khz, 'measured_khz': round(float(fc), 2), 'level_db': round(float(p[i] - floor), 1),
                         'prominence_db': round(float(prom), 1), 'stations': stations}
    channels = sorted(channels.values(), key=lambda c: c['khz'])
    return {'channels': channels, 'axis_fit': {'scale': round(coef[0], 6), 'offset_khz': round(coef[1], 3)},
            'bin_khz': round(df, 3), 'reference': ref['source']}


# ---------------------------------------------------------------------------- sessions

class Session:
    def __init__(self, station_key, mode='iq', seconds=None, receiver=None):
        self.id = 'LIVE-' + uuid.uuid4().hex[:8].upper()
        self.station_key = station_key
        self.st = STATIONS[station_key]
        self.mode = mode
        self.seconds = float(seconds or (60 if mode == 'band' else self.st['capture_s']))
        self.receiver = receiver
        self.created = time.time()
        self.state = 'starting'
        self.history = []
        self.subscribers = []
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.result = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def summary(self):
        return {'id': self.id, 'station': self.station_key, 'mode': self.mode, 'state': self.state,
                'created': self.created, 'seconds': self.seconds}

    def emit(self, type_, t=None, **payload):
        ev = {'type': type_, 't': round(t if t is not None else time.time() - self.created, 3), **_clean(payload)}
        with self.lock:
            if type_ != 'spectrum':
                self.history.append(ev)
            else:
                self._last_rows = (getattr(self, '_last_rows', []) + [ev])[-120:]
            for q in list(self.subscribers):
                try:
                    q.put_nowait(ev)
                except queue.Full:
                    pass

    def subscribe(self):
        q = queue.Queue(maxsize=4000)
        with self.lock:
            for ev in self.history + getattr(self, '_last_rows', []):
                q.put_nowait(ev)
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def _receivers(self):
        rc = self.st['receivers']
        directory = directory_cached()
        freq = self.st['frequency_khz']
        site = (self.st['site']['lat'], self.st['site']['lon'])
        seen, out = set(), []
        for r in kiwi.rank_receivers(directory, freq, site, rc.get('min_km', 0), rc.get('max_km', 2500)):
            if r['url'] not in seen:
                seen.add(r['url'])
                out.append(r)
        # An operator may say which public receiver to use, but only one the public directory
        # actually lists. Without this check the `receiver` query parameter chooses an arbitrary host
        # and port for this server to open a TCP connection to, and the per-receiver failure is
        # reported straight back over the event stream: a server-side request forgery with an oracle
        # attached, usable to map hosts and ports the client cannot reach itself. The station's own
        # `preferred` list is configuration, not input, and stays trusted.
        if self.receiver and self.receiver not in {r.get('url') for r in directory}:
            raise kiwi.KiwiError(
                f'{self.receiver} is not in the public receiver directory. Name a listed receiver, '
                f'or leave the choice to the server.')
        pref = ([self.receiver] if self.receiver else []) + rc.get('preferred', [])
        front = [r for p in pref for r in out if r['url'] == p]
        extra = [{'url': p, 'loc': '', 'gps': None, 'distance_km': None, 'gps_timed': None, 'snr_db': None}
                 for p in pref if p not in {r['url'] for r in out}]
        return front + extra + [r for r in out if r['url'] not in set(pref)]

    def _run(self):
        try:
            self.emit('status', phase='directory', message='selecting a public receiver in range of the transmitter')
            if self.mode == 'band':
                self._run_band()
            else:
                self._run_iq()
        except Exception as e:
            self.state = 'error'
            self.emit('error', message=str(e))
        finally:
            if self.state not in ('error',):
                self.state = 'done'
            self.emit('status', phase='closed', message='session closed')

    def _run_iq(self):
        st = self.st
        tuned = st['frequency_khz'] - st['tuning_offset_hz'] / 1000.0
        errors = []
        for rx in self._receivers()[:6]:
            if self.stop_flag.is_set():
                return
            self.emit('status', phase='connecting', message=f"connecting to {rx['url']} ({rx.get('loc') or 'receiver'})")
            try:
                with kiwi.KiwiIQ(rx['url'], tuned, timeout=8.0) as k:
                    proc = None
                    t_first = None
                    for block, info in k.blocks():
                        if proc is None:
                            t_first = info['gps_unix'] or (info['received_unix'] - len(block) / k.sample_rate)
                            timing = 'gps' if info['gps_unix'] else 'arrival'
                            self.state = 'receiving'
                            self.emit('receiver', url=rx['url'], name=k.meta.get('rx_name') or rx.get('name'),
                                      location=rx.get('loc'), gps=rx.get('gps'), distance_km=rx.get('distance_km'),
                                      gps_timed=bool(info['gps_unix']), rssi_dbm=round(info['rssi_dbm'], 1),
                                      fs_hz=k.sample_rate, tuned_khz=tuned, timing=timing,
                                      t0_utc=dt.datetime.fromtimestamp(t_first, dt.timezone.utc).isoformat(timespec='milliseconds'))
                            proc = LiveProcessor(self.station_key, k.sample_rate, t_first, timing, st['tuning_offset_hz'],
                                                 lambda type_, t=None, **p: self.emit(type_, t=t, **p))
                        proc.feed(block)
                        if proc.seconds >= self.seconds or self.stop_flag.is_set():
                            break
                    self._finish(proc, rx, k, tuned)
                    return
            except (OSError, kiwi.KiwiError) as e:
                errors.append(f"{rx['url']}: {e}")
                self.emit('status', phase='receiver_failed', message=f"{rx['url']}: {e}")
        raise kiwi.KiwiError('no receiver delivered IQ: ' + '; '.join(errors[-3:]))

    def _finish(self, proc, rx, k, tuned):
        if proc is None or proc.seconds < 5:
            raise kiwi.KiwiError('capture too short')
        self.state = 'analysing'
        self.emit('status', phase='analysing', message=f'blind analysis of {proc.seconds:.0f} s over every receiver')
        out, audio = proc.finish()
        folder = os.path.join(LIVE_DIR, self.id)
        os.makedirs(folder, exist_ok=True)
        write_wav(os.path.join(folder, 'capture.wav'), proc.iq(), proc.fs)
        if audio is not None:
            import wave
            with wave.open(os.path.join(folder, 'audio.wav'), 'w') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(int(round(out['runs']['am']['audio_rate_hz'])))
                w.writeframes(audio.tobytes())
        meta = {'id': self.id, 'station_key': self.station_key, 'station': {k2: self.st[k2] for k2 in ('name', 'operator', 'country', 'frequency_khz', 'service', 'site', 'references')},
                'receiver': {'url': rx['url'], 'name': k.meta.get('rx_name'), 'location': rx.get('loc'), 'gps': rx.get('gps'),
                             'distance_km': rx.get('distance_km'), 'gps_timed': proc.timing == 'gps'},
                'capture': {'t0_unix': proc.t0, 't0_utc': dt.datetime.fromtimestamp(proc.t0, dt.timezone.utc).isoformat(timespec='milliseconds'),
                            'timing': proc.timing, 'tuned_khz': tuned, 'fs_hz': proc.fs, 'duration_s': round(proc.seconds, 3),
                            'baseband_shift_hz': 0.0, 'tuning_offset_hz': self.st['tuning_offset_hz']},
                'analysis': out, 'has_audio': audio is not None, 'kind': 'LIVE'}
        json.dump(meta, open(os.path.join(folder, 'session.json'), 'w', encoding='utf-8'), indent=1)
        self.result = meta
        self.emit('result', answer=out['answer'], runs=out['runs'], recording_id=self.id, has_audio=audio is not None)

    def _run_band(self):
        lo, hi = self.st['band_khz']
        cf = (lo + hi) / 2
        errors = []
        for rx in self._receivers()[:4]:
            self.emit('status', phase='connecting', message=f"connecting waterfall {rx['url']}")
            try:
                with kiwi.KiwiWaterfall(rx['url'], cf, 4) as wf:
                    rows = []
                    start = time.time()
                    last_census = start
                    for row, info in wf.rows():
                        if not rows:
                            self.state = 'receiving'
                            self.emit('receiver', url=rx['url'], name=wf.meta.get('rx_name'), location=rx.get('loc'),
                                      gps=rx.get('gps'), span_khz=[float(wf.freqs_khz()[0]), float(wf.freqs_khz()[-1])])
                        rows.append(row)
                        f = wf.freqs_khz()
                        sel = (f >= lo - 20) & (f <= hi + 20)
                        seg = row[sel]
                        q = np.clip((seg + 125.0) / 90.0 * 255, 0, 255)
                        self.emit('spectrum', row=_b64(q), f0_hz=float(f[sel][0] * 1e3), f1_hz=float(f[sel][-1] * 1e3),
                                  db_min=-125.0, db_max=-35.0)
                        if time.time() - last_census > 3 and len(rows) >= 10:
                            last_census = time.time()
                            census = spectrum_census(np.array(rows[-40:]), f)
                            self.emit('census', **census)
                        if time.time() - start >= self.seconds or self.stop_flag.is_set():
                            break
                    census = spectrum_census(np.array(rows), wf.freqs_khz())
                    self.result = {'id': self.id, 'census': census, 'receiver': rx}
                    self.emit('result', answer={'status': 'SIGNAL_NO_CODE', 'summary': f"{sum(1 for c in census['channels'] if c['stations'])} carriers matched to the official AIR list"},
                              census=census, recording_id=None)
                    return
            except (OSError, kiwi.KiwiError) as e:
                errors.append(f"{rx['url']}: {e}")
                self.emit('status', phase='receiver_failed', message=f"{rx['url']}: {e}")
        raise kiwi.KiwiError('no waterfall receiver available: ' + '; '.join(errors[-3:]))


_directory = {'t': 0.0, 'data': None}
_directory_lock = threading.Lock()


def directory_cached(max_age_s=900):
    with _directory_lock:
        if _directory['data'] is None or time.time() - _directory['t'] > max_age_s:
            _directory['data'] = kiwi.fetch_directory()
            _directory['t'] = time.time()
        return _directory['data']


SESSIONS = {}


def start_session(station_key, mode='iq', seconds=None, receiver=None):
    if station_key not in STATIONS:
        raise KeyError(station_key)
    active = [s for s in SESSIONS.values() if s.state in ('starting', 'receiving', 'analysing')]
    if len(active) >= MAX_SESSIONS:
        raise RuntimeError(f'{MAX_SESSIONS} live sessions already running (public receivers are shared; please wait)')
    s = Session(station_key, mode, seconds, receiver)
    SESSIONS[s.id] = s
    s.thread.start()
    return s


def recorded_sessions():
    out = []
    if os.path.isdir(LIVE_DIR):
        for sid in sorted(os.listdir(LIVE_DIR), reverse=True):
            p = os.path.join(LIVE_DIR, sid, 'session.json')
            if os.path.exists(p):
                meta = json.load(open(p, encoding='utf-8'))
                out.append({'id': sid, 'station': meta['station_key'], 't0_utc': meta['capture']['t0_utc'],
                            'answer': meta['analysis']['answer'], 'has_audio': meta.get('has_audio', False)})
    return out
