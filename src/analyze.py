"""Signal analysis: detection, estimation, modulation ID, demodulation."""

import numpy as np
from scipy.signal import welch


def detect_signal(iq, fs=1e6):
    """Energy-based signal detection and SNR estimation (M2M4)."""
    power = np.mean(np.abs(iq) ** 2)
    m2 = np.mean(np.abs(iq) ** 2)
    m4 = np.mean(np.abs(iq) ** 4)
    kurtosis = m4 / (m2 ** 2) if m2 > 0 else 0
    # M2M4 SNR estimator
    # For complex Gaussian noise: kurtosis = 2
    # For signal + noise: kurtosis depends on modulation
    # Rough estimate: SNR = sqrt(2*m2^2 - m4) / (m2 - sqrt(2*m2^2 - m4))
    # Simplified approach
    snr_est_db = 10 * np.log10(max(power, 1e-20))
    detected = power > 1e-10
    return {
        'detected': detected,
        'power': power,
        'snr_est_db': snr_est_db,
        'kurtosis': kurtosis,
    }


def estimate_snr_m2m4(iq):
    """M2M4 SNR estimator."""
    m2 = np.mean(np.abs(iq) ** 2)
    m4 = np.mean(np.abs(iq) ** 4)
    if m2 <= 0:
        return 0.0
    k = m4 / (m2 ** 2)
    # For PSK + Gaussian noise:
    # k = 1 + 1/SNR + 1/SNR^2 (complex BPSK/QPSK approx)
    # Solve quadratic: SNR = (k-1 + sqrt((k-1)^2 - 4)) / 2 ... simplified
    # Use Pauluzzi-Beaulieu approximation
    if k <= 1:
        return 30.0
    noise_frac = max(k - 1, 0.01)
    snr_linear = max(1.0 / noise_frac, 0.01)
    return 10 * np.log10(snr_linear)


def estimate_symbol_rate(iq, fs=1e6, sps_range=(2, 20)):
    """Symbol-rate estimation using |x| and |x|² spectral analysis.
    Combined method with 1%-of-fs guard."""
    N = len(iq)

    results = []
    for transform in ['abs', 'abs2']:
        if transform == 'abs':
            y = np.abs(iq)
        else:
            y = np.abs(iq) ** 2
        y = y - np.mean(y)

        # Welch PSD for better noise averaging
        nperseg = min(N, 4096)
        freqs, psd = welch(y, fs=fs, nperseg=nperseg, noverlap=nperseg // 2,
                           window='hann', return_onesided=True)

        # Guard: skip low freq (< 1% of fs) and constrain to valid sps range
        min_freq = 0.01 * fs
        max_freq = fs / sps_range[0]
        min_sym_freq = fs / sps_range[1]

        mask = (freqs >= max(min_freq, min_sym_freq)) & (freqs <= max_freq)
        if not np.any(mask):
            continue

        psd_masked = psd.copy()
        psd_masked[~mask] = 0

        # Find peak
        peak_idx = np.argmax(psd_masked)
        peak_freq = freqs[peak_idx]
        peak_val = psd[peak_idx]

        # Significance: compare to median
        median_psd = np.median(psd[mask])
        mad = np.median(np.abs(psd[mask] - median_psd))
        if mad > 0:
            significance = (peak_val - median_psd) / (1.4826 * mad)
        else:
            significance = peak_val / max(median_psd, 1e-20)

        results.append({
            'freq': peak_freq,
            'significance': significance,
            'method': transform,
        })

    if not results:
        return fs / 4, 0.0  # fallback

    # Pick the most significant peak
    best = max(results, key=lambda r: r['significance'])
    symbol_rate = best['freq']
    confidence = best['significance']

    return symbol_rate, confidence


def identify_modulation(syms, fs=1e6):
    """Lag-1 autocorrelation of s² for CFO- and rotation-invariant BPSK/QPSK classification.

    BPSK: s²(t) = A²·exp(j·2φ(t)) — data-independent; consecutive s² values differ only
    by the (tiny) per-symbol CFO rotation, so |corr(s²(t), s²(t+1))| ≈ A⁴ (high).

    QPSK: s²(t) = ±A²·exp(j·2φ(t)) — the ±1 data sign alternates randomly, so
    E[s²(t)·s̄²(t+1)] = 0 (low) regardless of CFO or rotation.
    Returns 'BPSK' or 'QPSK'.
    """
    syms = np.asarray(syms, dtype=complex)
    syms = syms / (np.sqrt(np.mean(np.abs(syms) ** 2)) + 1e-20)
    s2 = syms ** 2
    r1 = np.abs(np.mean(s2[1:] * np.conj(s2[:-1])))
    power = np.mean(np.abs(s2) ** 2) + 1e-20
    return 'BPSK' if r1 / power > 0.5 else 'QPSK'


def estimate_carrier_phase(symbols, mod):
    """M-power carrier/phase estimation.
    BPSK: angle(mean(s^2))/2
    QPSK: (angle(mean(s^4)) - pi)/4
    """
    if mod == 'BPSK':
        ph = np.angle(np.mean(symbols ** 2)) / 2
    elif mod == 'QPSK':
        ph = (np.angle(np.mean(symbols ** 4)) - np.pi) / 4
    else:
        ph = 0.0
    return ph


def matched_filter_demod(iq, h, sps):
    """Matched filter + downsample to symbols.
    Total delay = len(h) - 1 (two convolutions: TX + RX).
    """
    filtered = np.convolve(iq, h)
    # total group delay from TX+RX RRC filtering
    delay = len(h) - 1
    # downsample
    symbols = filtered[delay::sps]
    return symbols


def estimate_noise_variance(iq, snr_est_db):
    """Estimate noise variance from SNR estimate."""
    sig_power = np.mean(np.abs(iq) ** 2)
    snr_lin = 10 ** (snr_est_db / 10)
    noise_var = sig_power / (1 + snr_lin)
    return max(noise_var, 1e-10)
