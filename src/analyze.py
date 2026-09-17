"""Signal analysis primitives: symbol-rate spectrum, matched filter, phase, symbol SNR, LLRs."""

import numpy as np
from scipy.signal import welch


def estimate_symbol_rate(iq, fs=1e6, sps_range=(2, 20)):
    """Raw symbol-rate estimate from the spectral line of |x| and |x|² at 1/T.

    Note: nperseg = min(N, 4096), so every capture shorter than 4096 samples gets a single
    Hann-windowed periodogram (no Welch averaging). Returns (rate_hz, significance)."""
    N = len(iq)
    results = []
    for y in (np.abs(iq), np.abs(iq) ** 2):
        y = y - np.mean(y)
        nperseg = min(N, 4096)
        freqs, psd = welch(y, fs=fs, nperseg=nperseg, noverlap=nperseg // 2,
                           window='hann', return_onesided=True)
        mask = (freqs >= max(0.01 * fs, fs / sps_range[1])) & (freqs <= fs / sps_range[0])
        if not np.any(mask):
            continue
        peak_idx = np.argmax(np.where(mask, psd, 0))
        median_psd = np.median(psd[mask])
        mad = np.median(np.abs(psd[mask] - median_psd))
        significance = ((psd[peak_idx] - median_psd) / (1.4826 * mad) if mad > 0
                        else psd[peak_idx] / max(median_psd, 1e-20))
        results.append((float(freqs[peak_idx]), float(significance)))
    if not results:
        return fs / 4, 0.0
    return max(results, key=lambda r: r[1])


def lag1_correlation(v):
    """|E[v(k+1)·v*(k)]| / E[|v|²] — near 1 for a constant sequence up to a slow rotation."""
    v = np.asarray(v)
    if len(v) < 2:
        return 0.0
    return float(np.abs(np.mean(v[1:] * np.conj(v[:-1]))) / (np.mean(np.abs(v) ** 2) + 1e-30))


def estimate_carrier_phase(symbols, mod):
    """M-power phase: BPSK angle(E[s²])/2, QPSK (angle(E[s⁴]) − π)/4."""
    if mod == 'BPSK':
        return float(np.angle(np.mean(symbols ** 2)) / 2)
    return float((np.angle(np.mean(symbols ** 4)) - np.pi) / 4)


def matched_filter_demod(iq, h, sps):
    """Matched filter + downsample; assumes TX and RX filters of equal length (delay len(h)-1)."""
    return np.convolve(iq, h)[len(h) - 1::sps]


def symbol_snr_m2m4(symbols):
    """M2M4 estimate for constant-modulus symbols in complex Gaussian noise.

    m2 = S + N and m4 = S² + 4SN + 2N², so S = sqrt(2·m2² − m4) and N = m2 − S.
    Returns (signal_power S, noise_power N) per complex symbol sample."""
    m2 = float(np.mean(np.abs(symbols) ** 2))
    m4 = float(np.mean(np.abs(symbols) ** 4))
    S = float(np.sqrt(max(2 * m2 * m2 - m4, 0.0)))
    return S, max(m2 - S, 1e-12 * m2 + 1e-30)


def psk_llrs(symbols, mod, S, N):
    """Calibrated LLRs (LLR > 0 ⇒ bit 0) for phase-corrected BPSK/QPSK symbols.

    BPSK: y = √S·(1−2b) + n, Re(n) variance N/2 → L = 4√S·Re(y)/N.
    QPSK: each axis carries √(S/2)·(1−2b), variance N/2 → L = 2√2·√S·Re|Im(y)/N."""
    a = np.sqrt(S)
    if mod == 'BPSK':
        return 4.0 * a * np.real(symbols) / N
    scale = 2.0 * np.sqrt(2.0) * a / N
    return np.column_stack([scale * np.real(symbols), scale * np.imag(symbols)]).ravel()
