from __future__ import annotations
import torch
from torch import nn

class SSLEncoder(nn.Module):
    """Frozen WavLM/Wav2Vec2 feature extractor with lazy HF initialization."""
    def __init__(self, model_name: str = "microsoft/wavlm-base-plus",
                 local_files_only: bool = False, freeze: bool = True):
        super().__init__()
        try:
            from transformers import AutoModel
        except ImportError as exc:
            raise RuntimeError("transformers is required for SSL encoding.") from exc
        self.encoder = AutoModel.from_pretrained(model_name, local_files_only=local_files_only)
        self.hidden_size = int(self.encoder.config.hidden_size)
        if freeze:
            for p in self.encoder.parameters():
                p.requires_grad_(False)
            self.encoder.eval()

    def train(self, mode: bool = True):
        super().train(mode)
        self.encoder.eval()
        return self

    def forward(self, waveform: torch.Tensor, attention_mask: torch.Tensor | None = None) -> torch.Tensor:
        if waveform.ndim == 3:
            waveform = waveform.squeeze(1)
        if waveform.ndim != 2:
            raise ValueError("SSL input must have shape [batch, samples] or [batch, 1, samples].")
        with torch.no_grad():
            out = self.encoder(input_values=waveform, attention_mask=attention_mask)
        return out.last_hidden_state
