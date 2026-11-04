from __future__ import annotations
from typing import Any
import numpy as np
from scipy.signal import lfilter

def levinson_durbin(x: np.ndarray, order: int) -> tuple[np.ndarray, float]:
    y = np.asarray(x, dtype=np.float64).reshape(-1)
    if y.size <= order + 1 or order < 1:
        raise ValueError("LPC requires more samples than the requested order.")
    y = y - y.mean()
    r = np.correlate(y, y, mode="full")[y.size - 1:y.size + order]
    if r[0] <= 1e-12:
        return np.r_[1.0, np.zeros(order)], 0.0
    a = np.zeros(order + 1, dtype=np.float64)
    a[0], err = 1.0, float(r[0])
    for i in range(1, order + 1):
        acc = r[i] + np.dot(a[1:i], r[i-1:0:-1])
        k = float(np.clip(-acc / max(err, 1e-12), -0.999, 0.999))
        prev = a.copy()
        a[i] = k
        if i > 1:
            a[1:i] = prev[1:i] + k * prev[i-1:0:-1]
        err = max(err * (1.0 - k * k), 1e-12)
    return a, err

def _praat_metrics(x: np.ndarray, sr: int, cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        import parselmouth
        snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
        pitch = snd.to_pitch(time_step=0.01, pitch_floor=float(cfg.get("min_f0", 60)),
                             pitch_ceiling=float(cfg.get("max_f0", 450)))
        f0 = pitch.selected_array["frequency"]
        f0 = f0[f0 > 0]
        point = snd.to_point_process_cc(pitch_floor=float(cfg.get("min_f0", 60)),
                                        pitch_ceiling=float(cfg.get("max_f0", 450)))
        jitter = float(parselmouth.praat.call(point, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)) if point.get_number_of_points() > 2 else None
        shimmer = float(parselmouth.praat.call([snd, point], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)) if point.get_number_of_points() > 2 else None
        continuity = float(np.mean(np.abs(np.diff(f0)) / np.maximum(f0[:-1], 1.0))) if f0.size > 2 else None
        return {"jitter_local": jitter, "shimmer_local": shimmer,
                "f0_mean_hz": float(np.mean(f0)) if f0.size else None,
                "f0_continuity": continuity, "praat_available": True}
    except Exception as exc:
        return {"jitter_local": None, "shimmer_local": None, "f0_mean_hz": None,
                "f0_continuity": None, "praat_available": False, "praat_error": str(exc)}

def analyze_biology(waveform: np.ndarray, sample_rate: int,
                    config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    x = np.asarray(waveform, dtype=np.float64).reshape(-1)
    if x.size < max(512, sample_rate // 5):
        return {"valid": False, "reason": "Audio too short for stable biological analysis."}
    frame = max(256, int(sample_rate * float(cfg.get("frame_ms", 30)) / 1000))
    hop = max(128, int(sample_rate * float(cfg.get("hop_ms", 10)) / 1000))
    order = int(cfg.get("lpc_order", 16))
    residuals, flatness = [], []
    for start in range(0, x.size - frame + 1, hop):
        seg = x[start:start+frame] * np.hamming(frame)
        try:
            a, _ = levinson_durbin(seg, order)
            res = lfilter(a, [1.0], seg)
            residuals.append(res)
            p = np.abs(np.fft.rfft(res)) ** 2 + 1e-12
            flatness.append(float(np.exp(np.mean(np.log(p))) / np.mean(p)))
        except (ValueError, FloatingPointError):
            continue
    if not residuals:
        return {"valid": False, "reason": "No valid LPC frames."}
    residual = np.concatenate(residuals)
    hist, _ = np.histogram(residual, bins=128, density=True)
    p = hist[hist > 0]
    p = p / p.sum()
    entropy = float(-(p * np.log2(p)).sum()) if p.size else 0.0
    centered = residual - residual.mean()
    denom = float(np.dot(centered, centered)) + 1e-12
    predictability = abs(float(np.dot(centered[1:], centered[:-1])) / denom)
    praat = _praat_metrics(x, sample_rate, cfg)
    return {"valid": True, "lpc_residual_entropy_bits": entropy,
            "lpc_residual_spectral_flatness": float(np.mean(flatness)),
            "pulse_decay_predictability": predictability, **praat}
