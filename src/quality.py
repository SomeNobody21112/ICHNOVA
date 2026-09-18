"""Capture data-quality gate (Constitution v2.5 §13.1 note on orthogonal flags).

This answers a different question from the decode verdict: *can this capture be trusted as a
measurement at all?* A clipped, truncated or gappy recording can make a refusal look like a property
of the signal when it is a property of the capture. The flag is reported beside the verdict and never
changes it.

Outcome: GOOD / DEGRADED / FAILED, with the measured numbers that produced it.

Thresholds are declared here, not fitted: each is the point where a metric starts to change what the
receiver sees, and every check reports what it measured so an operator can disagree with the label.
"""

import numpy as np

# Declared thresholds.
CLIP_DEGRADED = 0.001      # 0.1 % of samples at full scale: visible spectral regrowth
CLIP_FAILED = 0.02         # 2 %: the waveform is no longer the signal that arrived
DC_DEGRADED = 0.05         # |mean| / RMS: a DC term this large puts a false line at zero offset
DC_FAILED = 0.25
GAP_DEGRADED = 0.002       # fraction of samples inside runs of identical zeros (dropped blocks)
GAP_FAILED = 0.02
IMBALANCE_DEGRADED = 1.5   # ratio of I to Q power (or its inverse)
IMBALANCE_FAILED = 3.0
MIN_SAMPLES = 64
SHORT_CAPTURE = 4096       # below this a refusal may simply mean "not enough signal"
GAP_RUN = 8                # identical consecutive zero samples counted as a dropout


def _zero_run_fraction(x, run=GAP_RUN):
    """Fraction of samples inside runs of at least `run` exactly-zero samples."""
    zero = ((x.real == 0) & (x.imag == 0)).astype(np.int8)
    if not zero.any():
        return 0.0
    idx = np.flatnonzero(np.diff(np.concatenate([[0], zero, [0]])))
    starts, ends = idx[0::2], idx[1::2]
    lengths = ends - starts
    return float(lengths[lengths >= run].sum() / len(x))


def assess(iq, fs=None, *, declared_samples=None):
    """Assess one capture. Returns a dict with `status` (GOOD/DEGRADED/FAILED), `reasons`, `checks`
    and `metrics`. `declared_samples` is the sample count the container claimed, when known."""
    iq = np.asarray(iq)
    n = int(iq.size)
    checks, reasons = [], []

    if n == 0:
        return {'status': 'FAILED', 'reasons': ['the capture contains no samples'],
                'metrics': {'samples': 0}, 'checks': [], 'note': ''}

    finite = np.isfinite(iq.real) & np.isfinite(iq.imag)
    n_nonfinite = int((~finite).sum())
    clean = iq[finite]
    peak = float(np.max(np.abs(clean))) if clean.size else 0.0
    rms = float(np.sqrt(np.mean(np.abs(clean) ** 2))) if clean.size else 0.0
    clip = float((np.abs(clean) >= peak * (1 - 1e-9)).sum() / n) if peak > 0 else 0.0
    dc = float(abs(np.mean(clean)) / rms) if rms > 0 else 0.0
    gaps = _zero_run_fraction(iq)
    ip = float(np.mean(clean.real ** 2)) if clean.size else 0.0
    qp = float(np.mean(clean.imag ** 2)) if clean.size else 0.0
    imbalance = (max(ip, qp) / min(ip, qp)) if (ip > 0 and qp > 0) else float('inf')
    crest = float(peak / rms) if rms > 0 else 0.0

    def check(name, status, detail):
        checks.append({'check': name, 'status': status, 'detail': detail})
        if status != 'GOOD':
            reasons.append(detail)

    # 1. structural integrity
    if n_nonfinite:
        check('samples', 'FAILED', f'{n_nonfinite} of {n} samples are NaN or infinite')
    elif n < MIN_SAMPLES:
        check('samples', 'FAILED', f'only {n} samples: below the {MIN_SAMPLES}-sample minimum')
    elif declared_samples is not None and n < declared_samples:
        check('samples', 'DEGRADED', f'file ends early: {n} of {declared_samples} declared samples')
    elif n < SHORT_CAPTURE:
        check('samples', 'DEGRADED', f'short capture ({n} samples): a refusal may mean too little signal')
    else:
        check('samples', 'GOOD', f'{n} samples, all finite')

    # 2. energy
    if rms == 0:
        check('level', 'FAILED', 'the capture is all zeros')
    elif crest < 1.05 and n > MIN_SAMPLES:
        check('level', 'DEGRADED', f'near-constant envelope (crest factor {crest:.2f}): carrier or DC only')
    else:
        check('level', 'GOOD', f'RMS {rms:.4g}, peak {peak:.4g}, crest factor {crest:.2f}')

    # 3. clipping
    if clip >= CLIP_FAILED:
        check('clipping', 'FAILED', f'{clip:.2%} of samples at full scale: reduce gain and recapture')
    elif clip >= CLIP_DEGRADED:
        check('clipping', 'DEGRADED', f'{clip:.2%} of samples at full scale')
    else:
        check('clipping', 'GOOD', f'{clip:.3%} of samples at full scale')

    # 4. DC offset
    if dc >= DC_FAILED:
        check('dc_offset', 'FAILED', f'DC offset is {dc:.0%} of RMS: a false carrier sits at zero offset')
    elif dc >= DC_DEGRADED:
        check('dc_offset', 'DEGRADED', f'DC offset is {dc:.0%} of RMS')
    else:
        check('dc_offset', 'GOOD', f'DC offset {dc:.1%} of RMS')

    # 5. dropouts
    if gaps >= GAP_FAILED:
        check('gaps', 'FAILED', f'{gaps:.1%} of samples are in zero runs: the recording has dropouts')
    elif gaps >= GAP_DEGRADED:
        check('gaps', 'DEGRADED', f'{gaps:.2%} of samples are in zero runs')
    else:
        check('gaps', 'GOOD', 'no dropouts detected')

    # 6. I/Q balance (a real-valued or one-sided capture shows here)
    if ip == 0 or qp == 0:
        check('iq_balance', 'FAILED', 'one quadrature carries no power: the capture may be real-valued, not I/Q')
    elif imbalance >= IMBALANCE_FAILED:
        check('iq_balance', 'DEGRADED', f'I/Q power ratio {imbalance:.1f}')
    elif imbalance >= IMBALANCE_DEGRADED:
        check('iq_balance', 'DEGRADED', f'I/Q power ratio {imbalance:.1f}')
    else:
        check('iq_balance', 'GOOD', f'I/Q power ratio {imbalance:.2f}')

    # 7. sample-rate plausibility (only when one was supplied)
    if fs is not None:
        if not np.isfinite(fs) or fs <= 0:
            check('sample_rate', 'FAILED', f'declared sample rate {fs!r} is not a positive number')
        elif fs < 1e3 or fs > 1e9:
            check('sample_rate', 'DEGRADED', f'declared sample rate {fs:g} Hz is outside 1 kHz - 1 GHz')
        else:
            check('sample_rate', 'GOOD', f'declared sample rate {fs:g} Hz')

    order = {'GOOD': 0, 'DEGRADED': 1, 'FAILED': 2}
    status = max((c['status'] for c in checks), key=lambda s: order[s])
    return {
        'status': status,
        'reasons': reasons,
        'checks': checks,
        'metrics': {'samples': n, 'nonfinite': n_nonfinite, 'rms': rms, 'peak': peak,
                    'crest_factor': crest, 'clipped_fraction': clip, 'dc_over_rms': dc,
                    'zero_run_fraction': gaps,
                    'iq_power_ratio': imbalance if np.isfinite(imbalance) else None,
                    'duration_s': (n / fs) if (fs and np.isfinite(fs) and fs > 0) else None},
        'note': ('Capture quality is reported beside the decode verdict and never changes it: '
                 'a bad capture explains a refusal, it does not create one.'),
    }
