"""Analogue broadcast characterisation (AM double sideband): the parameters a monitoring analyst reports.

carrier frequency offset (Hz, with its standard error), carrier-to-noise ratio, modulation depth, audio
bandwidth, sideband symmetry (DSB vs SSB), and the demodulated programme audio.
"""

import math

import numpy as np
from scipy.signal import butter, sosfiltfilt, welch


def _lp(x, fs, fc, order=6):
    return sosfiltfilt(butter(order, min(fc, 0.45 * fs), fs=fs, output='sos'), x)


def analyze_am(iq, fs, search_hz=600.0, audio_rate=8000):
    iq = np.asarray(iq, dtype=complex)
    n = len(iq)
    nfft = 1 << int(min(math.log2(n), 16))
    f, P = welch(iq, fs=fs, nperseg=nfft, return_onesided=False, detrend=False)
    order = np.argsort(f)
    f, P = f[order], P[order]
    near = np.abs(f) <= search_hz
    i = int(np.flatnonzero(near)[np.argmax(P[near])])
    floor = float(np.median(P))
    cnr_db = 10 * math.log10(P[i] / floor)
    # Carrier offset: linear fit to the unwrapped phase of the carrier line (0.5 Hz lowpass).
    t = np.arange(n) / fs
    x = iq * np.exp(-2j * np.pi * f[i] * t)
    dec = max(1, int(fs // 50))
    c = _lp(x, fs, 2.0, order=4)[::dec]
    tc = t[::dec]
    ph = np.unwrap(np.angle(c))
    A = np.vstack([tc, np.ones_like(tc)]).T
    coef, res, *_ = np.linalg.lstsq(A, ph, rcond=None)
    dof = max(len(tc) - 2, 1)
    sigma = math.sqrt(float(res[0]) / dof) if len(res) else 0.0
    slope_se = sigma / math.sqrt(float(np.sum((tc - tc.mean()) ** 2)) + 1e-12)
    offset = float(f[i] + coef[0] / (2 * math.pi))
    offset_se = slope_se / (2 * math.pi)
    # Receiver passband: some receivers deliver one sideband only; detect it instead of misreading it.
    base = iq * np.exp(-2j * np.pi * offset * t)
    fa, Pa = welch(base, fs=fs, nperseg=nfft, return_onesided=False, detrend=False)
    audio_band = min(0.45 * fs, 4800.0)
    noise = float(np.median(Pa))
    usb = float(np.mean(Pa[(fa > 150) & (fa < 2500)]))
    lsb = float(np.mean(Pa[(fa < -150) & (fa > -2500)]))
    usb_db, lsb_db = 10 * math.log10(usb / noise), 10 * math.log10(lsb / noise)
    # A full carrier with only one sideband is a receiver passband effect (true SSB suppresses the carrier).
    one_sided = abs(usb_db - lsb_db) > 15 and cnr_db > 40
    symmetry_db = usb_db - lsb_db
    # Coherent product detection against the carrier's own phase (valid for DSB and single sideband).
    car = _lp(base, fs, 5.0, order=4)
    ref = car / (np.abs(car) + 1e-30)
    y = _lp(base, fs, audio_band) * np.conj(ref)
    carrier_level = float(np.median(np.abs(car)))
    m = (np.real(y) - np.abs(car)) / (carrier_level + 1e-30)
    if one_sided:
        m = 2 * m                                   # one sideband carries half the modulation power
    depth_rms = float(np.std(m))
    depth_peak = float(np.percentile(np.abs(m - np.mean(m)), 99.5))
    fm, Pm = welch(m - m.mean(), fs=fs, nperseg=4096)
    band = (fm > 50) & (fm < audio_band)
    cum = np.cumsum(Pm[band])
    bw99 = float(fm[band][np.searchsorted(cum, 0.99 * cum[-1])]) if len(cum) and cum[-1] > 0 else None
    step = max(1, int(round(fs / audio_rate)))
    audio = _lp(m, fs, 0.45 * fs / step)[::step]
    audio = audio / (np.percentile(np.abs(audio), 99.9) + 1e-12)
    pcm = np.clip(audio * 0.9 * 32767, -32768, 32767).astype(np.int16)
    if depth_rms < 0.05:
        kind = 'unmodulated carrier'
    elif one_sided:
        kind = 'AM (receiver delivered one sideband)'
    elif abs(symmetry_db) < 3 and depth_rms > 0.02:
        kind = 'AM (double sideband, full carrier)'
    elif abs(symmetry_db) >= 3:
        kind = 'single sideband'
    else:
        kind = 'unmodulated carrier'
    return {
        'kind': 'AM_BROADCAST', 'modulation': kind,
        'carrier_offset_hz': round(offset, 4), 'carrier_offset_se_hz': round(offset_se, 5),
        'carrier_to_noise_db': round(cnr_db, 1),
        # With one sideband cut by the receiver, the carrier sits on the filter edge: depth is not measurable.
        'modulation_depth_rms': None if one_sided else round(depth_rms, 3),
        'modulation_depth_peak': None if one_sided else round(min(depth_peak, 2.0), 3), 'audio_bandwidth_99_hz': None if bw99 is None else round(bw99),
        'sideband_symmetry_db': round(symmetry_db, 2), 'receiver_passband': 'one sideband' if one_sided else 'both sidebands',
        'depth_is_approximate': one_sided, 'audio_rate_hz': fs / step,
        'status': 'SIGNAL_NO_CODE' if cnr_db > 15 else 'UNKNOWN', '_audio_pcm': pcm,
    }
