from __future__ import annotations
import numpy as np

def modified_group_delay(waveform: np.ndarray, sample_rate: int) -> dict[str, float]:
    x = np.asarray(waveform, dtype=np.float64).reshape(-1)
    if x.size < 512:
        return {"mgd_deviation": 0.0, "phase_continuity": 0.0}
    n = min(2048, 2 ** int(np.floor(np.log2(x.size))))
    frame = x[:n] * np.hamming(n)
    X = np.fft.rfft(frame)
    nX = np.fft.rfft(np.arange(n) * frame)
    tau = np.imag(nX * np.conj(X)) / (np.abs(X) ** 2 + 1e-10)
    valid = np.isfinite(tau) & (np.abs(X) > np.percentile(np.abs(X), 25))
    vals = tau[valid]
    if vals.size < 8:
        return {"mgd_deviation": 0.0, "phase_continuity": 0.0}
    med = np.median(vals)
    mad = np.median(np.abs(vals - med)) + 1e-9
    deviation = float(np.median(np.abs(vals - med)) / mad)
    continuity = float(1.0 / (1.0 + np.std(np.diff(np.unwrap(np.angle(X))))))
    return {"mgd_deviation": deviation, "phase_continuity": continuity}

def harmonic_distortion(waveform: np.ndarray, sample_rate: int) -> dict[str, float]:
    x = np.asarray(waveform, dtype=np.float64).reshape(-1)
    if x.size < sample_rate // 4:
        return {"h2_h5_ratio": 0.0, "lnlr": 0.0}
    n = min(x.size, 2 * sample_rate)
    spec = np.abs(np.fft.rfft(x[:n] * np.hanning(n))) ** 2
    freq = np.fft.rfftfreq(n, 1 / sample_rate)
    band = (freq >= 60) & (freq <= 450)
    if not np.any(band):
        return {"h2_h5_ratio": 0.0, "lnlr": 0.0}
    f0 = float(freq[band][np.argmax(spec[band])])
    if f0 <= 0:
        return {"h2_h5_ratio": 0.0, "lnlr": 0.0}
    powers = []
    for h in range(1, 6):
        mask = np.abs(freq - h * f0) <= max(8.0, f0 * 0.04)
        powers.append(float(spec[mask].sum()))
    fundamental, higher = powers[0] + 1e-12, sum(powers[1:])
    return {"h2_h5_ratio": float(higher / fundamental),
            "lnlr": float(10 * np.log10((fundamental + 1e-12) / (higher + 1e-12)))}

def analyze_physics(waveform: np.ndarray, sample_rate: int) -> dict[str, float]:
    return {**modified_group_delay(waveform, sample_rate),
            **harmonic_distortion(waveform, sample_rate)}
