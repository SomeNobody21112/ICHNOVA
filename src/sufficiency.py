"""Evidence sufficiency: why a result was refused, and what capture would settle it.

Every number here comes from the acceptance statistic that actually refused the result
(Constitution v2.5 §13.1), never from a guess.

The burst and stream families accept on an exact sign test over parity checks: with n checks and k
agreeing, p = P(Binomial(n, 1/2) >= k), and a hypothesis is accepted when log10 p <= bar, where the
bar already carries the multiple-testing correction. Under the alternative the checks agree with some
fixed probability q > 1/2, so the expected evidence grows linearly with n:

    E[-log10 p] ~= n * D(q || 1/2) / ln(10),     D(q || 1/2) = q ln(2q) + (1-q) ln(2(1-q))

Estimating q from the best hypothesis actually tested (q_hat = k/n) and solving for the n that reaches
the bar gives the number of additional parity checks the evidence needs. That converts to coded bits
(a rate-1/2 catalogue code produces one check per trellis step, two coded bits per step) and, when the
symbol rate and sample rate are known, to seconds.

Two honest outcomes matter as much as the number:

- ACHIEVABLE: more of the same signal would reach the bar, and by how much.
- IMPOSSIBLE_IN_DOMAIN: no capture length can, because the structure itself is too small. A 32-bit
  interleaver block yields at most ~10 parity checks, whose smallest attainable p (every check
  agreeing) is 2^-10 = 10^-3.0, above a bar of about 10^-6. More signal cannot help; only a different
  structure or a narrower search domain would.
"""

import math

import numpy as np

BITS_PER_CHECK = 2          # rate-1/2 catalogue codes: one parity check per two coded bits
MIN_AGREEMENT = 0.52        # below this the estimate is too weak to extrapolate from
SAFETY = 1.25               # the estimate is a mean; ask for 25 % more so the capture is likely enough


def _kl_to_fair(q):
    """D(q || 1/2) in nats: the expected evidence per check under agreement rate q."""
    q = min(max(q, 1e-6), 1 - 1e-6)
    return q * math.log(2 * q) + (1 - q) * math.log(2 * (1 - q))


def checks_needed(agreement, bar_log10):
    """Parity checks required for the expected evidence to reach `bar_log10` (a negative number)."""
    d = _kl_to_fair(agreement)
    if d <= 0:
        return None
    return int(math.ceil(SAFETY * abs(bar_log10) * math.log(10) / d))


def best_attainable_log10p(n_checks):
    """The smallest p-value a hypothesis with n checks can ever reach: every check agreeing."""
    return -n_checks * math.log10(2) if n_checks > 0 else 0.0


def assess(result, *, fs=None):
    """Explain a refusal and state what would settle it.

    `result` is the dict from pipeline.analyze_iq. Returns None for an accepted decode; otherwise a
    dict with the verdict, the measured statistics and the required extra capture."""
    status = result.get('status')
    if status == 'DECODED':
        return None

    accept = result.get('accept') or {}
    bar = accept.get('log10_threshold')
    diagnostics = result.get('diagnostics') or {}
    tops = diagnostics.get('top_hypotheses') or []
    best = tops[0] if tops else None

    out = {'verdict': 'UNKNOWN_CAUSE', 'status': status, 'bar_log10_p': bar,
           'best_log10_p': accept.get('log10_p'), 'hypotheses_tested': accept.get('n_hypotheses'),
           'reason': None, 'what_would_prove_it': None, 'required': None, 'measured': {}}

    # No structure was even tested: the front end found nothing to test.
    if not best or not accept.get('n_hypotheses'):
        out.update(verdict='NO_SIGNAL_EVIDENCE',
                   reason='No symbol structure reached the front end, so no code hypothesis was tested.',
                   what_would_prove_it=('A capture with a detectable carrier or symbol rate: a longer '
                                        'observation, a stronger signal, or a receiver pointed at the '
                                        'transmission.'),
                   measured={'detection_log10_p': diagnostics.get('detection_log10_p')})
        return out

    n = int(best.get('n_checks') or 0)
    k = int(best.get('n_positive') or 0)
    agreement = (k / n) if n else 0.0
    out['measured'] = {'best_hypothesis': {'code': best.get('code'), 'interleaver': best.get('interleaver'),
                                           'modulation': best.get('modulation'), 'sps': best.get('sps')},
                       'parity_checks': n, 'checks_agreeing': k, 'agreement_rate': agreement,
                       'symbol_snr_db': best.get('symbol_snr_db')}

    # Can this structure ever reach the bar, even with every check agreeing?
    ceiling = best_attainable_log10p(n)
    if bar is not None and ceiling > bar:
        out.update(verdict='IMPOSSIBLE_IN_DOMAIN',
                   reason=(f'The best structure tested yields only {n} parity checks. Even if every one '
                           f'agreed, the strongest attainable evidence is 10^{ceiling:.1f}, above the '
                           f'bar of 10^{bar:.1f} that {accept.get("n_hypotheses")} hypotheses require.'),
                   what_would_prove_it=('More signal cannot help. This block is too short to prove at '
                                        'alpha = 0.01 under the declared search domain. A longer '
                                        'interleaver block, a different structure, or a narrower search '
                                        'would be needed.'),
                   required={'achievable': False,
                             'parity_checks_for_any_proof': checks_needed(1.0, bar)})
        return out

    # Otherwise: how much more of the same signal would reach the bar?
    if agreement < MIN_AGREEMENT:
        out.update(verdict='NO_TREND',
                   reason=(f'The best hypothesis agrees on {k} of {n} parity checks '
                           f'({agreement:.1%}), which is consistent with chance.'),
                   what_would_prove_it=('Nothing about this hypothesis is trending. A longer capture of '
                                        'the same signal is not expected to change it; a better '
                                        'signal-to-noise ratio, a different receiver, or a structure '
                                        'outside the current catalogue would be needed.'),
                   required={'achievable': False})
        return out

    need = checks_needed(agreement, bar if bar is not None else -6.0)
    if need is None:
        return out
    extra_checks = max(0, need - n)
    extra_bits = extra_checks * BITS_PER_CHECK
    sps = best.get('sps')
    bits_per_symbol = 1 if (best.get('modulation') or 'BPSK') == 'BPSK' else 2
    extra_symbols = extra_bits / bits_per_symbol
    extra_samples = extra_symbols * sps if sps else None
    extra_seconds = (extra_samples / fs) if (extra_samples is not None and fs) else None

    out.update(verdict='ACHIEVABLE',
               reason=(f'The best hypothesis ({best.get("code")}) agrees on {k} of {n} parity checks '
                       f'({agreement:.1%}), giving 10^{best.get("log10_p", 0):.1f} against a bar of '
                       f'10^{bar:.1f}. The trend is real but the capture is too short to prove it.'),
               what_would_prove_it=(
                   f'About {extra_checks} more parity checks, which is roughly {extra_bits} more coded '
                   f'bits of the same transmission'
                   + (f' (~{extra_seconds:.2f} s at this symbol rate).' if extra_seconds
                      else ' (duration unknown: no absolute sample rate established).')),
               required={'achievable': True, 'parity_checks_now': n, 'parity_checks_needed': need,
                         'extra_parity_checks': extra_checks, 'extra_coded_bits': extra_bits,
                         'extra_symbols': extra_symbols, 'extra_samples': extra_samples,
                         'extra_seconds': extra_seconds,
                         'assumption': ('Agreement rate stays at the observed value, and the evidence '
                                        'grows linearly with the number of checks.')})
    return out


def truncate_capture(iq, fraction):
    """Helper for the truncation experiment: the first `fraction` of a capture."""
    n = max(1, int(len(np.asarray(iq)) * fraction))
    return np.asarray(iq)[:n]
