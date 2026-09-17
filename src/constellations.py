"""8PSK and 16-QAM for catalogue v1 (Constitution v2.5 §12.1): mapping, soft demapping, carrier phase,
symbol SNR and the two modulation gates. BPSK/QPSK stay in modem.py / analyze.py unchanged.

Mappings (bits MSB first per symbol):
  8PSK   symbol k = exp(j2πk/8), bits = Gray(k) = k XOR (k >> 1)
  16-QAM I from bits (b0,b1), Q from bits (b2,b3); per axis 00→+1, 01→+3, 10→−1, 11→−3; scaled 1/√10
LLR convention: LLR > 0 favours bit 0; max-log approximation.
"""

import numpy as np
from scipy.special import bdtrc
from scipy.stats import ncx2

BITS_PER_SYMBOL = {'BPSK': 1, 'QPSK': 2, '8PSK': 3, '16QAM': 4}
ROTATIONS = {'BPSK': (0.0,), 'QPSK': (0.0, np.pi / 2), '8PSK': tuple(k * np.pi / 4 for k in range(8)),
             '16QAM': tuple(k * np.pi / 2 for k in range(4))}
KURTOSIS = {'BPSK': 1.0, 'QPSK': 1.0, '8PSK': 1.0, '16QAM': 1.32}   # E|s|⁴ / (E|s|²)²

_K8 = np.arange(8)
PSK8_POINTS = np.exp(2j * np.pi * _K8 / 8)
PSK8_BITS = np.array([[(g >> (2 - b)) & 1 for b in range(3)] for g in (_K8 ^ (_K8 >> 1))], dtype=np.uint8)
PAM4_LEVEL = {(0, 0): 1.0, (0, 1): 3.0, (1, 0): -1.0, (1, 1): -3.0}
PAM4_POINTS = np.array([PAM4_LEVEL[(a, b)] for a in (0, 1) for b in (0, 1)]) / np.sqrt(10)
PAM4_BITS = np.array([(a, b) for a in (0, 1) for b in (0, 1)], dtype=np.uint8)


def modulate(bits, mod):
    bits = np.asarray(bits, dtype=np.uint8)
    m = BITS_PER_SYMBOL[mod]
    if len(bits) % m:
        bits = np.concatenate([bits, np.zeros(m - len(bits) % m, dtype=np.uint8)])
    b = bits.reshape(-1, m)
    if mod == '8PSK':
        gray = b[:, 0] * 4 + b[:, 1] * 2 + b[:, 2]
        k = np.array([int(np.flatnonzero((_K8 ^ (_K8 >> 1)) == g)[0]) for g in range(8)])[gray]
        return PSK8_POINTS[k]
    if mod == '16QAM':
        lv = np.array([[PAM4_LEVEL[(a, c)] for a, c in ((x[0], x[1]), (x[2], x[3]))] for x in b])
        return (lv[:, 0] + 1j * lv[:, 1]) / np.sqrt(10)
    raise ValueError(mod)


def carrier_phase(y, mod):
    """M-power phase estimate for the rotation-free constellation (ambiguity = rotation hypotheses)."""
    if mod == '8PSK':
        return float(np.angle(np.mean(y ** 8)) / 8)
    if mod == '16QAM':
        return float((np.angle(np.mean(y ** 4)) - np.pi) / 4)     # E[s⁴] < 0 for square QAM
    raise ValueError(mod)


def symbol_snr(y, mod):
    """M2M4 estimate (S, N) with the constellation kurtosis: m4 = ka·S² + 4SN + 2N²."""
    m2 = float(np.mean(np.abs(y) ** 2))
    m4 = float(np.mean(np.abs(y) ** 4))
    ka = KURTOSIS[mod]
    S = float(np.sqrt(max((2 * m2 * m2 - m4) / (2 - ka), 0.0)))
    S = min(S, m2)
    return S, max(m2 - S, 1e-12 * m2 + 1e-30)


def llrs(y, mod, S, N):
    """Max-log LLRs (LLR > 0 favours 0) for phase-corrected symbols y with signal power S, noise N."""
    a = np.sqrt(S)
    if mod == '8PSK':
        d = np.abs(y[:, None] - a * PSK8_POINTS[None, :]) ** 2 / N          # (n, 8)
        out = np.empty((len(y), 3))
        for b in range(3):
            out[:, b] = d[:, PSK8_BITS[:, b] == 1].min(axis=1) - d[:, PSK8_BITS[:, b] == 0].min(axis=1)
        return out.ravel()
    if mod == '16QAM':
        out = np.empty((len(y), 4))
        for axis, comp in ((0, np.real(y)), (2, np.imag(y))):
            d = (comp[:, None] - a * PAM4_POINTS[None, :]) ** 2 / (N / 2)
            for b in range(2):
                out[:, axis + b] = (d[:, PAM4_BITS[:, b] == 1].min(axis=1) - d[:, PAM4_BITS[:, b] == 0].min(axis=1)) / 2
        return out.ravel()
    raise ValueError(mod)


def qpsk_signature_log10p(y):
    """w = y⁴ is data-free for BPSK/QPSK: pairs v = w(2m+1)·conj(w(2m)) have Re(v) > 0. For 8PSK, w = ±e^{jθ}
    flips with the data (fair coin). Exact one-sided binomial p of the positive count."""
    w = np.asarray(y) ** 4
    m = len(w) // 2
    if m == 0:
        return 0.0
    v = w[1:2 * m:2] * np.conj(w[0:2 * m:2])
    pos = int(np.count_nonzero(np.real(v) > 0))
    return float(np.log10(max(bdtrc(pos - 1, m, 0.5), 1e-300))) if pos > 0 else 0.0


def constant_modulus_contradiction_log10p(y, q=0.1):
    """Test of a constant-modulus model (BPSK/QPSK/8PSK plus complex Gaussian noise, M2M4 plug-in S, N).
    Under that model 2|y|²/N ~ noncentral χ²(2, 2S/N), so exactly a fraction q of symbols falls below its
    q-quantile. An excess count (inner points of 16-QAM) gives a small upper-tail binomial p."""
    y = np.asarray(y)
    n = len(y)
    if n < 16:
        return 0.0
    m2 = float(np.mean(np.abs(y) ** 2))
    m4 = float(np.mean(np.abs(y) ** 4))
    S = float(np.sqrt(max(2 * m2 * m2 - m4, 0.0)))
    N = max(m2 - S, 1e-12 * m2 + 1e-30)
    tau = ncx2.ppf(q, 2, 2 * S / N) * N / 2 if S > 0 else -np.log(1 - q) * N
    below = int(np.count_nonzero(np.abs(y) ** 2 < tau))
    return float(np.log10(max(bdtrc(below - 1, n, q), 1e-300))) if below > 0 else 0.0
