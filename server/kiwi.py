"""Live IQ from public KiwiSDR receivers (stdlib only).

A KiwiSDR is a networked HF receiver (0-30 MHz). Its audio channel, in `iq` mode, streams
uncompressed 16-bit complex baseband at ~12 kHz with a GPS timestamp per block when the receiver
has a GPS fix. Protocol follows jks-prv/kiwiclient (kiwi/client.py): websocket /<ts>/SND,
`SET auth`, `SET AR OK`, `SET mod=iq ...`, one `SET keepalive` per second.

    python server/kiwi.py --freq-khz 7850 --seconds 12 --near 45.295,-75.756 --out capture.npz
"""

import base64
import json
import math
import os
import re
import socket
import struct
import threading
import time
import urllib.parse
import urllib.request

import numpy as np

LIST_URL = 'http://rx.linkfanel.net/kiwisdr_com.js'
GPS_UTC_OFFSET_S = 18                      # GPS - UTC since 2017-01-01 (no leap second announced since)
GPS_EPOCH = 315964800                      # 1980-01-06T00:00:00Z as Unix time
USER_AGENT = 'SIH26147-research'


class KiwiError(RuntimeError):
    pass


# ---------------------------------------------------------------- websocket (RFC 6455, client side)

class WebSocket:
    def __init__(self, host, port, path, timeout=10.0, redirects=2):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
               f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: {USER_AGENT}\r\n\r\n')
        self.sock.sendall(req.encode())
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise KiwiError('connection closed during handshake')
            head += chunk
        status, _, rest = head.partition(b'\r\n\r\n')
        lines = status.split(b'\r\n')
        code = lines[0].split(b' ')[1] if len(lines[0].split(b' ')) > 1 else b''
        if redirects and code in (b'301', b'302', b'307', b'308'):
            # proxy.kiwisdr.com answers with the receiver's actual address as an HTTP redirect
            location = next((ln.split(b':', 1)[1].strip().decode() for ln in lines[1:]
                             if ln.lower().startswith(b'location:')), None)
            self.sock.close()
            if location:
                u = urllib.parse.urlparse(location)
                self.__init__(u.hostname, u.port or 80, path, timeout, redirects - 1)
                return
        if code != b'101':
            raise KiwiError('handshake refused: ' + status.split(b'\r\n')[0].decode(errors='replace'))
        self.buf = rest
        self.lock = threading.Lock()

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise KiwiError('connection closed by receiver')
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send_text(self, text, opcode=0x1):
        payload = text.encode() if isinstance(text, str) else text
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | opcode])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack('>H', n)
        else:
            head += bytes([0x80 | 127]) + struct.pack('>Q', n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self.lock:
            self.sock.sendall(head + mask + masked)

    def recv(self):
        """Next complete data message (bytes). Answers pings; raises on close."""
        message = b''
        while True:
            b0, b1 = self._read(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack('>H', self._read(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:
                raise KiwiError('receiver closed the connection' + (f': {data[2:].decode(errors="replace")}' if len(data) > 2 else ''))
            if opcode == 0x9:
                self.send_text(data, opcode=0xA)
                continue
            if opcode == 0xA:
                continue
            message += data
            if b0 & 0x80:
                return message

    def close(self):
        try:
            self.send_text(b'', opcode=0x8)
        except OSError:
            pass
        self.sock.close()


# ---------------------------------------------------------------- receiver directory

def _latlon(text):
    m = re.findall(r'-?\d+\.?\d*', text or '')
    return (float(m[0]), float(m[1])) if len(m) >= 2 else None


def great_circle_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    c = math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo1 - lo2)
    return 6371.0 * math.acos(max(-1.0, min(1.0, c)))


def fetch_directory(timeout=20):
    req = urllib.request.Request(LIST_URL, headers={'User-Agent': USER_AGENT})
    text = urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='replace')
    body = re.sub(r',\s*\]\s*$', ']', text[text.index('['):text.rindex(']') + 1])
    return json.loads(body)


def rank_receivers(directory, freq_khz, near=None, min_km=250, max_km=2500):
    """Receivers with a free slot covering freq, GPS-timed first, then by distance (skip-zone aware).

    The public directory lists some receivers more than once; each URL is returned once."""
    out = []
    seen = set()
    for r in directory:
        if r.get('url') in seen:
            continue
        seen.add(r.get('url'))
        try:
            if r.get('offline') != 'no' or r.get('status') != 'active':
                continue
            if int(r['users']) >= int(r['users_max']):
                continue
            lo, hi = (float(x) for x in r.get('bands', '0-30000000').split('-'))
            if not lo <= freq_khz * 1e3 <= hi:
                continue
            pos = _latlon(r.get('gps'))
            d = great_circle_km(pos, near) if (near and pos) else None
            if d is not None and not (min_km <= d <= max_km):
                continue
            gps_timed = int(r.get('fixes_min') or 0) > 0
            snr = int((r.get('snr') or '0').split(',')[0] or 0)
            out.append({'url': r['url'], 'name': r.get('name', ''), 'loc': r.get('loc', ''), 'gps': pos,
                        'distance_km': None if d is None else round(d), 'gps_timed': gps_timed, 'snr_db': snr,
                        'users': int(r['users']), 'users_max': int(r['users_max'])})
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(out, key=lambda r: (not r['gps_timed'], -(r['snr_db'] or 0) // 10, r['distance_km'] or 0))


# ---------------------------------------------------------------- IQ stream

def gps_to_unix(gpssec, gpsnsec, near_unix):
    """Kiwi GPS time is seconds into the GPS week; resolve the week from the local clock."""
    week = 604800
    gps_now = near_unix - GPS_EPOCH + GPS_UTC_OFFSET_S
    t = math.floor(gps_now / week) * week + gpssec + gpsnsec * 1e-9
    if t - gps_now > week / 2:
        t -= week
    elif gps_now - t > week / 2:
        t += week
    return t + GPS_EPOCH - GPS_UTC_OFFSET_S


class KiwiIQ:
    """Context manager yielding (iq_block, block_info) from one receiver."""

    def __init__(self, url, freq_khz, low_cut=-5000, high_cut=5000, agc=True, man_gain=50, timeout=10.0):
        u = urllib.parse.urlparse(url if '://' in url else 'http://' + url)
        self.host, self.port = u.hostname, u.port or 8073
        self.url = f'http://{self.host}:{self.port}'
        self.freq_khz, self.low_cut, self.high_cut = freq_khz, low_cut, high_cut
        self.agc, self.man_gain, self.timeout = agc, man_gain, timeout
        self.ws = None
        self.sample_rate = None
        self.meta = {}
        self._stop = threading.Event()

    def __enter__(self):
        self.ws = WebSocket(self.host, self.port, f'/{int(time.time())}/SND', self.timeout)
        self.ws.send_text('SET auth t=kiwi p=')
        self._last_keepalive = 0.0
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self.ws:
            self.ws.close()

    def _set(self, cmd):
        self.ws.send_text('SET ' + cmd)

    def _handle_msg(self, text):
        for pair in text.split(' '):
            name, _, value = pair.partition('=')
            value = urllib.parse.unquote(value)
            if name == 'too_busy':
                raise KiwiError(f'{self.url}: all {value} client slots taken')
            if name == 'badp' and value not in ('0', ''):
                raise KiwiError(f'{self.url}: access refused (badp={value})')
            if name in ('down', 'redirect', 'camp_disconnect'):
                raise KiwiError(f'{self.url}: {name} {value}')
            if name == 'audio_rate':
                self._set(f'AR OK in={int(float(value))} out=44100')
            elif name == 'sample_rate':
                self.sample_rate = float(value)
                self._set('squelch=0 max=0')
                self._set('genattn=0')
                self._set('gen=0 mix=-1')
                self._set(f'ident_user={USER_AGENT}')
                self._set(f'mod=iq low_cut={self.low_cut} high_cut={self.high_cut} freq={self.freq_khz:.3f}')
                self._set(f'agc={int(self.agc)} hang=0 thresh=-100 slope=6 decay=1000 manGain={self.man_gain}')
                self._set('compression=0')
                self._set('keepalive')
            elif name in ('version_maj', 'version_min', 'freq_offset', 'bandwidth'):
                self.meta[name] = value
            elif name == 'load_cfg':
                try:
                    cfg = json.loads(value)
                    self.meta['rx_name'] = cfg.get('rx_name')
                    self.meta['rx_gps'] = cfg.get('rx_gps')
                except ValueError:
                    pass

    def blocks(self):
        while not self._stop.is_set():
            msg = self.ws.recv()
            now = time.time()
            if now - self._last_keepalive >= 1.0:
                self._set('keepalive')
                self._last_keepalive = now
            tag = msg[:3]
            if tag == b'MSG':
                self._handle_msg(msg[4:].decode('utf-8', errors='replace'))
            elif tag == b'SND' and self.sample_rate:
                body = msg[3:]
                flags, seq = struct.unpack('<BI', body[0:5])
                smeter = struct.unpack('>H', body[5:7])[0]
                data = body[7:]
                if not flags & 0x08:                       # not stereo: IQ mode not yet active
                    continue
                last_sol, _, gpssec, gpsnsec = struct.unpack('<BBII', data[0:10])
                raw = np.frombuffer(data[10:], dtype='<i2' if flags & 0x80 else '>i2').astype(np.float32)
                iq = (raw[0::2] + 1j * raw[1::2]).astype(np.complex64) / 32768.0
                gps_ok = last_sol != 255 and gpssec != 0
                yield iq, {'seq': seq, 'rssi_dbm': 0.1 * smeter - 127, 'received_unix': now,
                           'gps_unix': gps_to_unix(gpssec, gpsnsec, now) if gps_ok else None,
                           'gps_age_s': None if last_sol == 255 else last_sol, 'adc_overflow': bool(flags & 0x02)}


class KiwiWaterfall:
    """Context manager yielding (row_dbm[1024], info) spectra: span = 30000/2**zoom kHz centred on cf_khz."""

    BINS = 1024

    def __init__(self, url, cf_khz, zoom, speed=4, timeout=10.0):
        u = urllib.parse.urlparse(url if '://' in url else 'http://' + url)
        self.host, self.port = u.hostname, u.port or 8073
        self.url = f'http://{self.host}:{self.port}'
        self.cf_khz, self.zoom, self.speed, self.timeout = cf_khz, zoom, speed, timeout
        self.max_khz = 30000.0
        self.wf_cal = 0.0
        self.ready = False
        self.meta = {}

    @property
    def span_khz(self):
        return self.max_khz / 2 ** self.zoom

    def freqs_khz(self):
        return self.cf_khz - self.span_khz / 2 + (np.arange(self.BINS) + 0.5) * self.span_khz / self.BINS

    def __enter__(self):
        self.ws = WebSocket(self.host, self.port, f'/{int(time.time())}/W/F', self.timeout)
        self.ws.send_text('SET auth t=kiwi p=')
        self._last_keepalive = 0.0
        return self

    def __exit__(self, *exc):
        self.ws.close()

    def _setup(self):
        for cmd in (f'zoom={self.zoom} cf={self.cf_khz:.3f}', 'maxdb=-10 mindb=-110', 'wf_speed=%d' % self.speed,
                    'wf_comp=0', 'interp=13', 'keepalive'):
            self.ws.send_text('SET ' + cmd)
        self.ready = True

    def rows(self):
        while True:
            msg = self.ws.recv()
            now = time.time()
            if now - self._last_keepalive >= 1.0:
                self.ws.send_text('SET keepalive')
                self._last_keepalive = now
            tag = msg[:3]
            if tag == b'MSG':
                for pair in msg[4:].decode('utf-8', errors='replace').split(' '):
                    name, _, value = pair.partition('=')
                    value = urllib.parse.unquote(value)
                    if name == 'too_busy':
                        raise KiwiError(f'{self.url}: all {value} client slots taken')
                    if name == 'badp' and value not in ('0', ''):
                        raise KiwiError(f'{self.url}: access refused (badp={value})')
                    if name == 'bandwidth':
                        self.max_khz = float(value) / 1000
                    elif name == 'wf_cal':
                        self.wf_cal = float(value)
                    elif name == 'load_cfg':
                        try:
                            cfg = json.loads(value)
                            self.meta['rx_name'] = cfg.get('rx_name')
                        except ValueError:
                            pass
                    elif name in ('wf_setup', 'zoom_max') and not self.ready:
                        self._setup()
            elif tag == b'W/F' and self.ready:
                body = msg[4:]
                data = np.frombuffer(body[12:], dtype=np.uint8)
                if len(data) >= self.BINS:
                    yield data[:self.BINS].astype(np.float32) - 255.0 + self.wf_cal, {'received_unix': now}


def capture(url, freq_khz, seconds, on_block=None, **kw):
    """Record `seconds` of IQ. Returns dict(iq, fs, t0_unix, timing, receiver meta, rssi)."""
    chunks, infos = [], []
    with KiwiIQ(url, freq_khz, **kw) as rx:
        for iq, info in rx.blocks():
            chunks.append(iq)
            infos.append(info)
            if on_block:
                on_block(iq, info, rx)
            if sum(len(c) for c in chunks) >= seconds * rx.sample_rate:
                break
        fs = rx.sample_rate
        meta = dict(rx.meta)
    iq = np.concatenate(chunks)
    # Sample-accurate start time: GPS stamps if present (Kiwi stamps the first sample of each block).
    gps = [(k, i['gps_unix']) for k, i in enumerate(infos) if i['gps_unix']]
    if gps:
        offsets = np.cumsum([0] + [len(c) for c in chunks[:-1]])
        t0s = np.array([t - offsets[k] / fs for k, t in gps])
        t0, timing = float(np.median(t0s)), 'gps'
        spread = float(np.ptp(t0s))
    else:
        t0, timing, spread = infos[0]['received_unix'] - len(chunks[0]) / fs, 'arrival', None
    return {'iq': iq, 'fs': fs, 't0_unix': t0, 'timing': timing, 'gps_stamp_spread_s': spread,
            'receiver': {'url': url, **meta}, 'freq_khz': freq_khz,
            'rssi_dbm': float(np.median([i['rssi_dbm'] for i in infos])),
            'adc_overflow_blocks': sum(i['adc_overflow'] for i in infos)}


def capture_best(freq_khz, seconds, near=None, attempts=6, log=print, directory=None, **kw):
    directory = directory or fetch_directory()
    errors = []
    for rx in rank_receivers(directory, freq_khz, near)[:attempts]:
        try:
            log(f'connecting {rx["url"]} ({rx["loc"]}, {rx["distance_km"]} km, gps_timed={rx["gps_timed"]})')
            cap = capture(rx['url'], freq_khz, seconds, **kw)
            cap['receiver'].update({k: rx[k] for k in ('name', 'loc', 'gps', 'distance_km', 'gps_timed', 'snr_db')})
            return cap
        except (OSError, KiwiError) as e:
            errors.append(f'{rx["url"]}: {e}')
            log(f'  failed: {e}')
    raise KiwiError('no receiver delivered IQ: ' + '; '.join(errors))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--freq-khz', type=float, required=True)
    ap.add_argument('--seconds', type=float, default=10)
    ap.add_argument('--near', help='lat,lon of the transmitter (pick receivers in range)')
    ap.add_argument('--url')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    near = tuple(float(x) for x in a.near.split(',')) if a.near else None
    cap = capture(a.url, a.freq_khz, a.seconds) if a.url else capture_best(a.freq_khz, a.seconds, near)
    np.savez_compressed(a.out, iq=cap['iq'], meta=json.dumps({k: v for k, v in cap.items() if k != 'iq'}))
    print(len(cap['iq']), 'samples @', cap['fs'], 'Hz; timing', cap['timing'], 't0', cap['t0_unix'], cap['receiver'])
