from __future__ import annotations
from typing import Any
import numpy as np
from scipy.signal import stft
from scipy.fft import fft2

def _entropy_bits(x: np.ndarray, bins: int = 256) -> float:
    if x.size == 0:
        return 0.0
    hist, _ = np.histogram(x, bins=bins, range=(-1.0, 1.0))
    p = hist.astype(np.float64)
    p = p[p > 0] / max(float(hist.sum()), 1.0)
    return float(-(p * np.log2(p)).sum())

def _band_ratio(x: np.ndarray, sr: int, low: float, high: float) -> float:
    if x.size < 32 or sr <= 0 or high <= low:
        return 0.0
    n = min(8192, max(256, 2 ** int(np.floor(np.log2(x.size)))))
    spec = np.abs(np.fft.rfft(x[:n] * np.hanning(n))) ** 2
    freq = np.fft.rfftfreq(n, 1.0 / sr)
    return float(spec[(freq >= low) & (freq <= min(high, sr / 2))].sum() / (spec.sum() + 1e-12))

def _grid_score(x: np.ndarray, sr: int) -> float:
    if x.size < 1024:
        return 0.0
    _, _, z = stft(x, fs=sr, nperseg=512, noverlap=384, boundary=None)
    mag = np.abs(z)
    band = mag[int(0.55 * mag.shape[0]):]
    if band.size < 64:
        return 0.0
    centered = np.log1p(band) - np.log1p(band).mean()
    power = np.abs(fft2(centered)) ** 2
    power[0, 0] = 0.0
    flat = power.ravel()
    if flat.size < 16:
        return 0.0
    top = np.partition(flat, -max(1, flat.size // 100))[-max(1, flat.size // 100):]
    return float(top.sum() / (power.sum() + 1e-12))

def analyze_check0(waveform: np.ndarray, sample_rate: int,
                   original_waveform: np.ndarray | None = None,
                   original_sample_rate: int | None = None,
                   config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    x = np.asarray(waveform, dtype=np.float64).reshape(-1)
    ox = np.asarray(original_waveform if original_waveform is not None else x, dtype=np.float64).reshape(-1)
    osr = int(original_sample_rate or sample_rate)
    r11025 = _band_ratio(ox, osr, 11025.0, osr / 2) if osr > 22050 else 0.0
    r12000 = _band_ratio(ox, osr, 12000.0, osr / 2) if osr > 24000 else 0.0
    zero_fraction = float(np.mean(np.abs(x) < 1e-12)) if x.size else 1.0
    entropy = _entropy_bits(x.astype(np.float32))
    grid = _grid_score(x, sample_rate)
    nyq_thr = float(cfg.get("nyquist_threshold", 0.08))
    extreme_thr = float(cfg.get("extreme_nyquist_threshold", 0.35))
    zero_run = int(float(cfg.get("zero_run_seconds", 0.10)) * sample_rate)
    max_zero_run = run = 0
    for value in np.abs(x) < 1e-12:
        run = run + 1 if value else 0
        max_zero_run = max(max_zero_run, run)
    silence_flag = (zero_fraction > 0.25 and entropy < float(cfg.get("entropy_floor_bits", 1.0))) or max_zero_run >= zero_run
    nyquist_flag = max(r11025, r12000) >= extreme_thr
    grid_flag = grid >= float(cfg.get("grid_threshold", 0.18))
    hard = bool(nyquist_flag and (grid_flag or entropy < 0.5))
    score = float(np.clip(max(r11025, r12000) / max(extreme_thr, 1e-6), 0, 1)) if hard else 0.0
    return {"nyquist_ratio_11025": r11025, "nyquist_ratio_12000": r12000,
        "zero_fraction": zero_fraction, "max_zero_run_seconds": max_zero_run / max(sample_rate, 1),
        "amplitude_entropy_bits": entropy, "spectral_grid_score": grid,
        "nyquist_flag": bool(max(r11025, r12000) >= nyq_thr),
        "silence_entropy_flag": bool(silence_flag), "spectral_grid_flag": bool(grid_flag),
        "hard_anomaly": hard, "digital_score": score,
        "note": "Indicators are recording-chain dependent; a hard gate is not proof of synthesis."}
