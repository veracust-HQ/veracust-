from __future__ import annotations
import random
import torch

class RawBoost:
    """Lightweight waveform augmentation inspired by RawBoost; training only."""
    def __init__(self, probability: float = 0.5):
        self.probability = probability
    def __call__(self, waveform: torch.Tensor) -> torch.Tensor:
        if random.random() > self.probability:
            return waveform
        x = waveform.clone()
        if random.random() < 0.6:
            gain = random.uniform(0.75, 1.25)
            x = x * gain
        if random.random() < 0.5:
            noise_scale = random.uniform(0.0005, 0.008)
            x = x + torch.randn_like(x) * noise_scale
        if random.random() < 0.35 and x.numel() > 1000:
            # Mild random band-like coloration via first-order difference blending.
            alpha = random.uniform(0.02, 0.12)
            x = (1-alpha) * x + alpha * torch.cat((x[:1], x[:-1]))
        return x.clamp(-1.0, 1.0)
