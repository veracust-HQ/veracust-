from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
import torch
import torchaudio
import soundfile as sf
from scipy.signal import resample_poly

@dataclass
class AudioRecord:
    waveform: torch.Tensor
    sample_rate: int
    original_sample_rate: int
    original_channels: int
    duration_seconds: float
    metadata: dict[str, Any]

def _decode(path: str | Path) -> tuple[torch.Tensor, int]:
    p = str(path)
    try:
        wav, sr = torchaudio.load(p)
        return wav.float(), int(sr)
    except Exception as first:
        try:
            arr, sr = sf.read(p, dtype="float32", always_2d=True)
            return torch.from_numpy(arr.T.copy()), int(sr)
        except Exception as second:
            raise RuntimeError(f"Could not decode audio {p!r}: {first}; fallback: {second}") from second

def _resample(wav: torch.Tensor, old_sr: int, new_sr: int) -> torch.Tensor:
    if old_sr == new_sr:
        return wav
    import math
    g = math.gcd(old_sr, new_sr)
    x = resample_poly(wav.detach().cpu().numpy(), new_sr // g, old_sr // g, axis=-1)
    return torch.from_numpy(np.asarray(x, dtype=np.float32))

def _trim_edges(wav: torch.Tensor, sr: int, frame_ms: int, hop_ms: int,
                threshold_db: float, min_edge_silence: float) -> tuple[torch.Tensor, dict[str, float]]:
    x = wav.squeeze(0)
    frame = max(1, int(sr * frame_ms / 1000))
    hop = max(1, int(sr * hop_ms / 1000))
    if x.numel() < frame:
        return wav, {"trimmed_start_seconds": 0.0, "trimmed_end_seconds": 0.0}
    rms = torch.stack([torch.sqrt(torch.mean(x[i:i+frame] ** 2) + 1e-12)
                       for i in range(0, x.numel() - frame + 1, hop)])
    db = 20.0 * torch.log10(rms.clamp_min(1e-8))
    active = torch.where(db >= threshold_db)[0]
    if active.numel() == 0:
        return wav, {"trimmed_start_seconds": 0.0, "trimmed_end_seconds": 0.0}
    start = int(active[0]) * hop
    end = min(x.numel(), int(active[-1]) * hop + frame)
    start = 0 if start / sr < min_edge_silence else start
    end = x.numel() if (x.numel() - end) / sr < min_edge_silence else end
    if end <= start:
        return wav, {"trimmed_start_seconds": 0.0, "trimmed_end_seconds": 0.0}
    return x[start:end].unsqueeze(0), {"trimmed_start_seconds": start / sr,
                                      "trimmed_end_seconds": (x.numel() - end) / sr}

def load_audio(path: str | Path, target_sr: int = 16000, peak_dbfs: float = -1.0,
               vad_config: dict[str, Any] | None = None) -> AudioRecord:
    wav, sr = _decode(path)
    if wav.ndim != 2 or wav.shape[0] < 1:
        raise ValueError("Decoded audio must have shape [channels, samples].")
    original_channels, original_sr = int(wav.shape[0]), int(sr)
    original_mono = wav.mean(dim=0, keepdim=True)
    mono = _resample(original_mono, sr, target_sr) if sr != target_sr else original_mono
    cfg = vad_config or {}
    mono, trim = _trim_edges(mono, target_sr, int(cfg.get("frame_ms", 25)),
        int(cfg.get("hop_ms", 10)), float(cfg.get("energy_threshold_db", -42.0)),
        float(cfg.get("edge_silence_seconds", 0.30)))
    peak = float(mono.abs().max().item()) if mono.numel() else 0.0
    target_peak = 10.0 ** (peak_dbfs / 20.0)
    if peak > 1e-9:
        mono = mono * (target_peak / peak)
    mono = mono.clamp(-1.0, 1.0).contiguous()
    return AudioRecord(mono, target_sr, original_sr, original_channels,
        mono.shape[-1] / target_sr, {"trim": trim, "original_peak": peak,
        "target_peak": target_peak, "original_waveform": original_mono.squeeze(0).detach().cpu(),
        "original_rate": original_sr})
