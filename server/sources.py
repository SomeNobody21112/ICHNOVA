"""Where signal data can come from, what may legally be done with it, and whether it is reachable now.

Every source declares three things the console shows verbatim:

- **Provenance**: who operates it and under what terms. A source whose terms are not established says
  so; it does not get a permissive default.
- **What it feeds**: `ENGINE` means samples reach the blind analysis and a verdict may be asserted
  from them. `REFERENCE ONLY` means the data is used to check a decode the engine reached on its own
  and can never produce one. `METADATA ONLY` means no signal samples are available at all, only
  descriptions of observations.
- **Health**: measured when asked, never assumed. `last_data_utc` is read from what this installation
  actually received, so "last received" is a fact about this machine, not a claim about the service.

Scope is deliberate. Only publicly accessible, openly documented transmissions are listed: standard
time and frequency stations, public broadcast, volunteer receiver networks and open satellite
telemetry archives. Nothing here reaches restricted government telemetry, command links, encrypted
services or private RF infrastructure, and no source is added that would need credentials to a
closed system.
"""

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import kiwi                                       # noqa: E402
from stations import STATIONS                     # noqa: E402

# Both ledgers this installation writes: the running server's, and the one exported with the build.
LEDGERS = (os.path.join(ROOT, 'results', 'ledger.jsonl'),
           os.path.join(ROOT, 'frontend', 'public', 'evidence', 'ledger.jsonl'))
LIVE_DIR = os.path.join(ROOT, 'results', 'live')
SATNOGS_API = 'https://network.satnogs.org/api/stations/?format=json'
USER_AGENT = 'SIH26147-research'

# Health states. AVAILABLE and DEGRADED are measured; UNAVAILABLE means a check ran and failed;
# NOT CONFIGURED means the source needs something this installation has not been given.
AVAILABLE, DEGRADED, UNAVAILABLE, NOT_CONFIGURED = 'AVAILABLE', 'DEGRADED', 'UNAVAILABLE', 'NOT CONFIGURED'
ENGINE, REFERENCE_ONLY, METADATA_ONLY = 'ENGINE', 'REFERENCE ONLY', 'METADATA ONLY'


def _utc_now():
    return dt.datetime.now(dt.timezone.utc)


def _iso(when):
    return when.astimezone(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z') if when else None


def _get_json(url, timeout=8):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def _ledger_last(predicate):
    """When this installation last analysed a capture matching `predicate`. None if never."""
    latest = None
    for path in LEDGERS:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                created = rec.get('created_utc')
                if created and predicate(rec.get('source') or {}) and (latest is None or created > latest):
                    latest = created
    return latest


class SignalSource:
    """One place signal data can come from. Subclasses implement `check`."""

    key = name = operator = ''
    kind = 'SOURCE'
    feeds = METADATA_ONLY
    licence = 'NOT ESTABLISHED'
    licence_note = ''
    references = ()
    needs_network = True

    def check(self, timeout=8):
        """Return (state, detail). Subclasses measure; they never assume."""
        raise NotImplementedError

    def last_data_utc(self):
        """When this installation last took data from this source, or None."""
        return None

    def status(self, timeout=8, probe=True):
        """`probe=False` skips the reachability check but still reports what this machine received."""
        if not probe:
            state, detail = NOT_CONFIGURED, 'not checked: this request asked for the offline answer'
        else:
            try:
                state, detail = self.check(timeout)
            except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
                state, detail = UNAVAILABLE, f'{type(e).__name__}: {e}'
        last = self.last_data_utc()
        age = None
        if last:
            try:
                age = int((_utc_now() - dt.datetime.fromisoformat(last.replace('Z', '+00:00'))).total_seconds())
            except ValueError:
                age = None
        return {
            'key': self.key, 'name': self.name, 'kind': self.kind, 'operator': self.operator,
            'feeds': self.feeds, 'licence': self.licence, 'licence_note': self.licence_note,
            'references': list(self.references), 'needs_network': self.needs_network,
            'health': {'state': state, 'detail': detail, 'checked_utc': _iso(_utc_now()),
                       'last_data_utc': last, 'age_s': age},
        }


class PublicSDRSource(SignalSource):
    """Volunteer-operated KiwiSDR receivers, which publish an open directory and stream IQ to anyone.

    This is the one source that puts live radio into the blind analysis: the samples are real
    baseband from a real antenna, and what is received are public transmissions (standard time
    stations, broadcast) whose format the operator publishes."""

    key, kind = 'public_sdr', 'PublicSDRSource'
    name = 'Public KiwiSDR receiver network'
    operator = 'Volunteer receiver operators, listed at rx.linkfanel.net'
    feeds = ENGINE
    licence = 'Public service, no registration'
    licence_note = ('Receivers are offered publicly by their operators; this client identifies itself '
                    'and takes one short capture at a time. No licence is asserted over the received '
                    'signal itself: the transmissions are public broadcasts.')
    references = ({'title': 'KiwiSDR public receiver directory', 'url': 'http://rx.linkfanel.net/'},)

    def check(self, timeout=8):
        directory = kiwi.fetch_directory(timeout=timeout)
        if not directory:
            return UNAVAILABLE, 'the receiver directory returned no receivers'
        usable = {}
        for key, st in STATIONS.items():
            site = (st['site']['lat'], st['site']['lon'])
            rx = kiwi.rank_receivers(directory, st['frequency_khz'], near=site,
                                     min_km=st['receivers']['min_km'], max_km=st['receivers']['max_km'])
            usable[key] = len(rx)
        reachable = sum(1 for n in usable.values() if n)
        if reachable == 0:
            return UNAVAILABLE, f'{len(directory)} receivers listed, none in range of a catalogued station'
        detail = f'{len(directory)} receivers listed; in range: ' + ', '.join(
            f'{k} {n}' for k, n in usable.items() if n)
        return (AVAILABLE if reachable >= len(STATIONS) // 2 else DEGRADED), detail

    def last_data_utc(self):
        if not os.path.isdir(LIVE_DIR):
            return None
        newest = None
        for sid in os.listdir(LIVE_DIR):
            p = os.path.join(LIVE_DIR, sid, 'session.json')
            if not os.path.exists(p):
                continue
            try:
                t0 = json.load(open(p, encoding='utf-8'))['capture']['t0_utc']
            except (KeyError, ValueError, OSError):
                continue
            if newest is None or t0 > newest:
                newest = t0
        return newest


class SatNOGSSource(SignalSource):
    """SatNOGS, the open satellite ground-station network.

    Its observations are public and openly licensed, but what it publishes is demodulated frames,
    audio artefacts and waterfall images, not raw IQ. There is nothing there for a blind receiver to
    work on, so this source is metadata only and no verdict is ever produced from it."""

    key, kind = 'satnogs', 'SatNOGSSource'
    name = 'SatNOGS open ground-station network'
    operator = 'Libre Space Foundation and volunteer stations'
    feeds = METADATA_ONLY
    licence = 'CC BY-SA 4.0 (observation data)'
    licence_note = ('Observations are published openly, but as demodulated frames, audio and waterfall '
                    'images rather than IQ. Attribution is required for anything reproduced from them.')
    references = ({'title': 'SatNOGS Network', 'url': 'https://network.satnogs.org/'},
                  {'title': 'SatNOGS Network API', 'url': 'https://network.satnogs.org/api/'})

    def check(self, timeout=8):
        data = _get_json(SATNOGS_API, timeout=timeout)
        rows = data if isinstance(data, list) else data.get('results', [])
        if not rows:
            return DEGRADED, 'the network API replied with no stations'
        online = sum(1 for s in rows if str(s.get('status', '')).lower() in ('online', '2'))
        return (AVAILABLE if online else DEGRADED), f'{len(rows)} stations on this page, {online} online'


class UserCaptureSource(SignalSource):
    """Recordings an operator supplies: the primary path for a signal this system has no receiver for.

    A .wav carries its sample rate in the header; a raw .iq does not, and none is invented for it."""

    key, kind = 'user_capture', 'UserCaptureSource'
    name = 'Operator-supplied capture'
    operator = 'The operator running this installation'
    feeds = ENGINE
    licence = 'Supplied by the operator'
    licence_note = ('Whoever uploads a capture is responsible for holding the right to analyse it. '
                    'Nothing leaves this machine: the file is read locally.')
    needs_network = False

    def check(self, timeout=8):
        return AVAILABLE, 'POST /api/analyze accepts .iq and .wav captures up to 64 MB'

    def last_data_utc(self):
        return _ledger_last(lambda s: s.get('kind') == 'UPLOAD')


class PublicReferenceSource(SignalSource):
    """The published specifications of the transmissions in the catalogue.

    Used one way only: to check an answer the engine reached blind. Nothing from a specification is
    fed into the analysis, because a receiver told what to expect proves nothing."""

    key, kind = 'public_reference', 'PublicReferenceSource'
    name = 'Published transmission specifications'
    operator = 'NIST, PTB, NPL, NICT, DWD, NRC and All India Radio'
    feeds = REFERENCE_ONLY
    licence = 'Official public documentation'
    licence_note = ('Operator documentation, cited and linked. Used to check a decode after the fact, '
                    'never as an input to it.')
    needs_network = False

    @property
    def references(self):
        out = []
        for st in STATIONS.values():
            out.extend(st.get('references', []))
        return out

    def check(self, timeout=8):
        refs = sum(len(st.get('references', [])) for st in STATIONS.values())
        return AVAILABLE, f'{len(STATIONS)} catalogued transmissions with {refs} operator references, held offline'


class SimulationSource(SignalSource):
    """The benchmark generator. Labelled SIMULATED wherever its output appears."""

    key, kind = 'simulation', 'SimulationSource'
    name = 'Benchmark generator (src/generate.py)'
    operator = 'This project'
    feeds = ENGINE
    licence = 'Generated by this project'
    licence_note = ('Synthetic captures with known ground truth, used for measurement. Every result '
                    'from them is labelled SIMULATED or BENCHMARK and is never presented as reception.')
    needs_network = False

    def check(self, timeout=8):
        have = os.path.isdir(os.path.join(ROOT, 'data', 'sealed'))
        return ((AVAILABLE, 'sealed and training sets present under data/') if have else
                (NOT_CONFIGURED, 'no generated data on this machine: run python src/generate.py sealed'))

    def last_data_utc(self):
        return _ledger_last(lambda s: s.get('kind') in ('BENCHMARK', 'SIMULATED'))


SOURCES = [PublicSDRSource(), SatNOGSSource(), UserCaptureSource(), PublicReferenceSource(),
           SimulationSource()]


def status_all(timeout=8, include_network=True):
    """Every source's provenance and current health. Network checks run in parallel and are bounded
    by `timeout`; a source needing the network is reported NOT CONFIGURED when it is excluded."""
    def one(src):
        return src.status(timeout, probe=include_network or not src.needs_network)

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        return list(pool.map(one, SOURCES))


if __name__ == '__main__':
    for s in status_all():
        h = s['health']
        print(f"{s['name']}\n  feeds {s['feeds']} | licence {s['licence']}")
        print(f"  {h['state']}: {h['detail']}")
        print(f"  last received here: {h['last_data_utc'] or 'never'}")
