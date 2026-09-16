"""BPSK/QPSK modem: modulation, RRC pulse shaping, channel, IQ I/O."""

import numpy as np
from scipy.signal import firwin, lfilter
import struct, wave


def rrc_filter(beta, sps, ntaps=None):
    """Root-raised-cosine filter."""
    if ntaps is None:
        ntaps = 10 * sps + 1
    ntaps |= 1
    t = np.arange(ntaps) - (ntaps - 1) / 2
    t = t / sps
    h = np.zeros(ntaps)
    for i, ti in enumerate(t):
        if ti == 0:
            h[i] = 1.0 + beta * (4 / np.pi - 1)
        elif abs(abs(ti) - 1 / (4 * beta)) < 1e-12 and beta > 0:
            h[i] = (beta / np.sqrt(2)) * (
                (1 + 2 / np.pi) * np.sin(np.pi / (4 * beta))
                + (1 - 2 / np.pi) * np.cos(np.pi / (4 * beta))
            )
        else:
            num = np.sin(np.pi * ti * (1 - beta)) + 4 * beta * ti * np.cos(np.pi * ti * (1 + beta))
            den = np.pi * ti * (1 - (4 * beta * ti) ** 2)
            if abs(den) < 1e-20:
                h[i] = 0.0
            else:
                h[i] = num / den
    h /= np.sqrt(np.sum(h ** 2))
    return h


def modulate(bits, mod):
    """BPSK/QPSK modulation. bits: uint8 array."""
    bits = np.asarray(bits, dtype=np.float64)
    if mod == 'BPSK':
        return 1.0 - 2.0 * bits
    elif mod == 'QPSK':
        if len(bits) % 2 != 0:
            bits = np.append(bits, 0)
        I = 1.0 - 2.0 * bits[0::2]
        Q = 1.0 - 2.0 * bits[1::2]
        return (I + 1j * Q) / np.sqrt(2)
    else:
        raise ValueError(f"Unknown modulation: {mod}")


def demodulate_soft(symbols, mod, noise_var=1.0):
    """Soft demodulation to LLRs. LLR > 0 favors bit=0."""
    symbols = np.asarray(symbols, dtype=np.complex128)
    if noise_var <= 0:
        noise_var = 1e-10
    if mod == 'BPSK':
        return (2.0 / noise_var) * np.real(symbols)
    elif mod == 'QPSK':
        scale = 2.0 * np.sqrt(2) / noise_var
        llr_I = scale * np.real(symbols)
        llr_Q = scale * np.imag(symbols)
        return np.column_stack([llr_I, llr_Q]).ravel()
    else:
        raise ValueError(f"Unknown modulation: {mod}")


def pulse_shape(symbols, sps, h):
    """Upsample and pulse-shape."""
    up = np.zeros(len(symbols) * sps, dtype=np.complex128)
    up[::sps] = symbols
    return np.convolve(up, h)


def channel(sig, snr_db, cfo_cyc, timing_offset, phase_offset, rng):
    """Apply channel: CFO, timing, phase, AWGN."""
    n = np.arange(len(sig))
    sig = sig * np.exp(1j * (2 * np.pi * cfo_cyc * n + phase_offset))
    sig_power = np.mean(np.abs(sig) ** 2)
    noise_var = sig_power / (10 ** (snr_db / 10))
    noise = np.sqrt(noise_var / 2) * (rng.standard_normal(len(sig)) + 1j * rng.standard_normal(len(sig)))
    sig = sig + noise
    if abs(timing_offset) > 0:
        N = len(sig)
        freqs = np.fft.fftfreq(N)
        sig = np.fft.ifft(np.fft.fft(sig) * np.exp(-1j * 2 * np.pi * freqs * timing_offset))
    return sig, noise_var


def save_iq(filename, sig):
    """Save IQ as interleaved float32."""
    out = np.zeros(2 * len(sig), dtype=np.float32)
    out[0::2] = np.real(sig).astype(np.float32)
    out[1::2] = np.imag(sig).astype(np.float32)
    out.tofile(filename)


def load_iq(filename):
    """Load IQ from interleaved float32."""
    raw = np.fromfile(filename, dtype=np.float32)
    return raw[0::2] + 1j * raw[1::2]


def save_wav(filename, sig, fs):
    """Save IQ as int16 stereo WAV."""
    scale = 32767.0 / max(np.max(np.abs(np.real(sig))), np.max(np.abs(np.imag(sig))), 1e-10)
    I = np.clip(np.real(sig) * scale, -32768, 32767).astype(np.int16)
    Q = np.clip(np.imag(sig) * scale, -32768, 32767).astype(np.int16)
    stereo = np.column_stack([I, Q]).ravel()
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(int(fs))
        wf.writeframes(stereo.tobytes())


def load_wav(filename):
    """Load IQ from int16 stereo WAV."""
    with wave.open(filename, 'r') as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        nf = wf.getnframes()
        fs = wf.getframerate()
        raw = wf.readframes(nf)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    if nch == 2:
        return data[0::2] + 1j * data[1::2], fs
    else:
        return data + 0j, fs
