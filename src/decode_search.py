"""Rotation/offset search for QPSK phase ambiguity + decode hypothesis search."""

import numpy as np
from modem import rrc_filter, demodulate_soft
from analyze import estimate_carrier_phase, estimate_noise_variance, matched_filter_demod
from blind_id import blind_identify


def search_rotations(iq, sps, mod, fs=1e6, beta=0.35, snr_est_db=10.0,
                     n_info_bits=400):
    """Search over all (sps, beta, rotation) combinations; return global-best result.

    No early exit: trying all combinations avoids spurious early exits when a wrong
    sps accidentally scores higher than 1.0 before the correct sps is reached.
    The global maximum score across all combinations is the final answer.
    """
    sps_candidates = list(sps) if isinstance(sps, (list, tuple)) else [sps]
    beta_candidates = list(beta) if isinstance(beta, (list, tuple)) else [beta]
    rotations = [0, np.pi] if mod == 'BPSK' else [0, np.pi / 2, np.pi, 3 * np.pi / 2]

    best = None
    best_score = -1.0

    for sps_try in sps_candidates:
        for beta_try in beta_candidates:
            h = rrc_filter(beta_try, int(round(sps_try)))
            symbols = matched_filter_demod(iq, h, int(round(sps_try)))
            if len(symbols) == 0:
                continue

            phase_est = estimate_carrier_phase(symbols, mod)
            symbols_corrected = symbols * np.exp(-1j * phase_est)
            noise_var = estimate_noise_variance(iq, snr_est_db)

            for rot in rotations:
                syms_rot = symbols_corrected * np.exp(-1j * rot)
                llrs = demodulate_soft(syms_rot, mod, noise_var)
                result = blind_identify(llrs, n_info_bits)

                score = result.get('score', result['consistency'])
                if score > best_score:
                    best_score = score
                    best = {
                        'decoded_bits': result['decoded_bits'],
                        'consistency': result['consistency'],
                        'code': result['code'],
                        'interleaver': result['interleaver'],
                        'sps_used': sps_try,
                        'beta_used': beta_try,
                        'phase': phase_est + rot,
                        'rotation': rot,
                        'symbols': syms_rot,
                        'llrs': llrs,
                        'symbol_rate_est': fs / sps_try,
                    }

    if best is None:
        return {
            'decoded_bits': np.array([], dtype=np.uint8),
            'consistency': 0.0,
            'code': {'name': 'unknown'},
            'interleaver': None,
            'sps_used': sps_candidates[0] if sps_candidates else 4,
            'beta_used': 0.35,
            'phase': 0.0,
            'rotation': 0.0,
            'symbols': np.array([]),
            'llrs': np.array([]),
            'symbol_rate_est': fs / (sps_candidates[0] if sps_candidates else 4),
        }

    return best
