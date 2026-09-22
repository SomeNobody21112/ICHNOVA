"""Signal fingerprints and similarity search (roadmap Phase 2, EXPERIMENTAL).

A fingerprint is a fixed-length vector of what the engine *measured* about a capture: signal
presence, the spectral lines, symbol-structure strength, the BPSK/QPSK statistic, the best evidence
found for each convolutional-code family, and the verdict. Nothing is learned and no ground truth
enters it; it is read off a finished `pipeline.analyze_iq` result.

It is never part of a decision. The verdict, acceptance rule and evidence are computed before any
fingerprint exists and are unaffected by it. Its only use is to find *other captures that look
alike*, for example recurrences of a signal the engine refused to decode.

    fp = fingerprint(result)                  # np.ndarray, len(FEATURES)
    lib = Library().fit(reference_fps)        # standardisation from the reference set only
    lib.query(fp, k=5)                        # [(index, distance), ...]
"""

import math

import numpy as np

FEATURES = [
    'presence',          # -log10 p of the signal-presence line test, squashed
    'line_x2_db',        # strongest x^2 spectral line above floor (BPSK carrier signature)
    'line_x4_db',        # strongest x^4 spectral line above floor (BPSK and QPSK)
    'structure_q4',      # best lag-1 y^4 correlation over the symbol-rate search
    'symbol_rate',       # 1 / sps at that best correlation
    'raw_rate',          # 1 / raw spectral symbol-rate estimate
    'bpsk_ratio',        # q2/q4 statistic at the best-margin candidate (BPSK ~ >1, QPSK ~ <1)
    'evidence_k3',       # best -log10 p among K=3 hypotheses, squashed
    'evidence_k5',       # best -log10 p among K=5 hypotheses, squashed
    'evidence_k7',       # best -log10 p among K=7 hypotheses, squashed
    'symbol_snr',        # symbol SNR of the best hypothesis (dB, clipped)
    'interleaver_bits',  # log2 of the bits the best hypothesis covers
    'margin',            # runner-up margin, log10
    'v_decoded', 'v_signal_no_code', 'v_unknown',   # the verdict, one-hot
]

_FAMILIES = ('k3', 'k5', 'k7')


def _squash(x, scale):
    """Monotone, bounded: large -log10 p values do not dominate the distance."""
    return float(math.log1p(max(0.0, x)) / math.log1p(scale))


def _family_of(code_name):
    name = str(code_name).lower()
    return next((f for f in _FAMILIES if f in name), None)


def fingerprint(result):
    """Fingerprint of one engine result. Needs `analyze_iq(..., _all_hypotheses=True)` for the
    per-family evidence; without it those three features fall back to the top hypotheses."""
    d = result.get('diagnostics', {})
    lines = d.get('cfo_candidates') or []
    x2 = max((c['peak_to_floor_db'] for c in lines if c.get('order') == 2), default=0.0)
    x4 = max((c['peak_to_floor_db'] for c in lines if c.get('order') == 4), default=0.0)
    table = d.get('sps_table') or []
    best = max(table, key=lambda r: r.get('q4', 0.0), default=None)
    mods = d.get('modulation_stats') or []
    mod = max(mods, key=lambda m: m.get('margin', 0.0), default=None)
    raw = d.get('raw_sps_estimate') or 0.0

    fam = {f: 0.0 for f in _FAMILIES}
    ah = d.get('all_hypotheses')
    pairs = zip(ah['code'], ah['log10_p']) if ah else ((h['code'], h['log10_p']) for h in d.get('top_hypotheses') or [])
    for code, lp in pairs:
        f = _family_of(code)
        if f:
            fam[f] = max(fam[f], -float(lp))

    top = (d.get('top_hypotheses') or [None])[0]
    snr = float(np.clip(top['symbol_snr_db'], -10.0, 30.0)) if top and top.get('symbol_snr_db') is not None else -10.0
    bits = float(top.get('covered_bits') or 0) if top else 0.0
    status = result.get('status')
    v = [
        _squash(-d.get('detection_log10_p', 0.0), 60.0),
        float(np.clip(x2, 0.0, 40.0)) / 40.0,
        float(np.clip(x4, 0.0, 40.0)) / 40.0,
        float(best['q4']) if best else 0.0,
        1.0 / best['sps'] if best and best.get('sps') else 0.0,
        1.0 / raw if raw and raw > 0 else 0.0,
        float(np.clip(mod['bpsk_ratio'], 0.0, 5.0)) / 5.0 if mod else 0.0,
        *[_squash(fam[f], 60.0) for f in _FAMILIES],
        (snr + 10.0) / 40.0,
        math.log2(bits + 1) / math.log2(385),
        float(np.clip(d.get('runner_up_margin_log10') or 0.0, 0.0, 30.0)) / 30.0,
        float(status == 'DECODED'), float(status == 'SIGNAL_NO_CODE'), float(status == 'UNKNOWN'),
    ]
    out = np.asarray(v, dtype=float)
    assert out.shape == (len(FEATURES),) and np.all(np.isfinite(out))
    return out


class Library:
    """Nearest-neighbour search over fingerprints, standardised with statistics from the reference
    set alone (a query never influences the scaling it is measured with)."""

    def fit(self, fps):
        X = np.asarray(fps, dtype=float)
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        self.std[self.std < 1e-9] = 1.0          # a constant feature carries no distance
        self.Z = (X - self.mean) / self.std
        return self

    def query(self, fp, k=5, exclude=None):
        z = (np.asarray(fp, dtype=float) - self.mean) / self.std
        dist = np.sqrt(((self.Z - z) ** 2).sum(axis=1))
        if exclude is not None:
            dist[exclude] = np.inf
        idx = np.argsort(dist, kind='stable')[:k]
        return [(int(i), float(dist[i])) for i in idx]
