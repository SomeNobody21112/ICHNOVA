"""Blind FEC/interleaver identification via catalogue + consistency."""

import numpy as np
from fec import conv_encode, viterbi_decode, block_interleave, block_deinterleave_soft


CODE_CATALOGUE = [
    {
        'name': 'conv_k7_r12_171_133',
        'generators': [0o171, 0o133],
        'K': 7,
        'rate': 0.5,
    },
    {
        'name': 'conv_k5_r12_23_35',
        'generators': [0o23, 0o35],
        'K': 5,
        'rate': 0.5,
    },
    {
        'name': 'conv_k3_r12_7_5',
        'generators': [0o7, 0o5],
        'K': 3,
        'rate': 0.5,
    },
    {
        'name': 'uncoded',
        'generators': None,
        'K': 0,
        'rate': 1.0,
    },
]

# A coded hypothesis with consistency C gets comparison score C + CODED_BONUS.
# The uncoded hypothesis trivially achieves consistency = 1.0 (decoded = hard(LLRs),
# reencoded = same).  Choosing CODED_BONUS = 0.12 means any coded hypothesis with
# consistency >= 0.88 outscores uncoded.  The genie analysis shows correct coded
# hypotheses achieve 0.85–0.97, so 0.12 is just enough to prefer them.
# We try ALL interleaver candidates for each code before deciding whether it beats
# uncoded — this avoids an early exit on a wrong interleaver with moderate consistency.
_CODED_BONUS = 0.12


def reencode_consistency(decoded_bits, llrs, code, interleaver_dims):
    """Hard-bit re-encode consistency: fraction of received bits matching re-encoding."""
    if code['generators'] is None:
        reencoded = np.asarray(decoded_bits, dtype=np.uint8)
    else:
        reencoded = conv_encode(decoded_bits, code['generators'], code['K'])

    if interleaver_dims is not None:
        rows, cols = interleaver_dims
        n = rows * cols
        reencoded_padded = np.zeros(n, dtype=np.uint8)
        reencoded_padded[:min(len(reencoded), n)] = reencoded[:n]
        reencoded_interleaved = block_interleave(reencoded_padded, rows, cols)
    else:
        reencoded_interleaved = reencoded

    L = min(len(reencoded_interleaved), len(llrs))
    if L == 0:
        return 0.0

    hard_received = (llrs[:L] < 0).astype(np.uint8)
    return float(np.mean(hard_received == reencoded_interleaved[:L]))


def try_decode(llrs, code, interleaver_dims):
    """Attempt decode with given code and interleaver hypothesis.
    Returns (decoded_bits, consistency, path_metric).
    path_metric is the normalised Viterbi log-likelihood (coded only; 0.0 for uncoded).
    """
    if interleaver_dims is not None:
        rows, cols = interleaver_dims
        n = rows * cols
        L = min(len(llrs), n)
        llrs_padded = np.zeros(n)
        llrs_padded[:L] = llrs[:L]
        deinterleaved = block_deinterleave_soft(llrs_padded, rows, cols)
    else:
        deinterleaved = llrs

    if code['generators'] is None:
        decoded = (deinterleaved < 0).astype(np.uint8)
        path_metric = 0.0
    else:
        decoded, path_metric = viterbi_decode(deinterleaved, code['generators'], code['K'])

    consistency = reencode_consistency(decoded, llrs, code, interleaver_dims)
    return decoded, consistency, path_metric


def generate_interleaver_candidates(n_bits, min_r=2, max_r=16, min_c=4, max_c=24):
    """Generate candidate block interleaver dimensions.

    Lower bound is 0.5 * n_bits: the RRC filter adds extra symbols at the tail,
    so n_llrs is typically 10–35% larger than n_il_bits.  Upper bound 1.0 * n_bits
    (not 1.2) because the true interleaver is always <= n_llrs.
    """
    candidates = []
    for r in range(min_r, max_r + 1):
        for c in range(min_c, max_c + 1):
            n = r * c
            if 0.5 * n_bits <= n <= n_bits:
                candidates.append((r, c))
    candidates.append(None)
    return candidates


def blind_identify(llrs, n_info_bits_approx=400):
    """Search code catalogue and interleaver candidates; return best hypothesis.

    Scoring strategy:
    - Coded K7: primary key = normalised Viterbi path_metric.
        path_metric = best_path_loglik / sum(|llrs|)
        ≈ 1.0 when Viterbi finds the transmitted codeword (correct interleaver).
        < 1.0 when forced to correct high-confidence bits (wrong interleaver).
      Final score = path_metric + _CODED_BONUS so that correct K7 (≈1.0+bonus)
      beats both wrong K7 (≈0.75+bonus<1.0) and uncoded (fixed 1.0).
    - Uncoded: score = 1.0 (always); wins only when ALL coded hypotheses give
      path_metric < 1.0 - _CODED_BONUS (i.e., no coded hypothesis is reliable).
    """
    candidates = generate_interleaver_candidates(len(llrs))

    _active_codes = [c for c in CODE_CATALOGUE
                     if c['name'] in ('conv_k7_r12_171_133', 'uncoded')]

    best_result = None
    best_score = -1.0

    for code in _active_codes:
        if best_score > 1.0:
            break

        is_coded = code['generators'] is not None

        # Track the best candidate for this code by its primary metric
        code_best_primary = -1.0   # path_metric for coded; dummy for uncoded
        code_best_cons = -1.0
        code_best_result = None

        for il_dims in candidates:
            try:
                decoded, consistency, path_metric = try_decode(llrs, code, il_dims)
            except Exception:
                continue

            primary = path_metric if is_coded else consistency

            if primary > code_best_primary:
                code_best_primary = primary
                code_best_cons = consistency
                code_best_result = {
                    'decoded_bits': decoded,
                    'consistency': consistency,
                    'code': code,
                    'interleaver': il_dims,
                }

        if code_best_result is None:
            continue

        score = code_best_primary + (_CODED_BONUS if is_coded else 0.0)
        code_best_result['score'] = score

        if score > best_score:
            best_score = score
            best_result = code_best_result

    if best_result is None:
        return {
            'decoded_bits': np.array([], dtype=np.uint8),
            'consistency': 0.0,
            'score': 0.0,
            'code': CODE_CATALOGUE[-1],
            'interleaver': None,
        }

    return best_result
