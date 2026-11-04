from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
import numpy as np
import torch
from ingestion.preprocessor import load_audio
from forensics.check0_digital import analyze_check0
from forensics.biology import analyze_biology
from forensics.physics import analyze_physics
from models.ssl_encoder import SSLEncoder
from models.aasist_l import AASISTL
from fusion.dynamic_fusion import sniff_codec, fuse_scores, build_report

class VeracustPipeline:
    def __init__(self, config: dict[str, Any] | str | Path = "configs/default_config.yaml",
                 checkpoint: str | Path | None = None, device: str | None = None):
        if isinstance(config, (str, Path)):
            with open(config, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = config
        requested = device or self.config.get("device", "auto")
        self.device = torch.device("cuda" if requested == "auto" and torch.cuda.is_available()
                                   else ("cpu" if requested == "auto" else requested))
        self.ssl: SSLEncoder | None = None
        self.classifier: AASISTL | None = None
        self.model_available = False
        model_cfg = self.config.get("model", {})
        ckpt = checkpoint or model_cfg.get("checkpoint")
        if ckpt:
            self._load_model(str(ckpt), model_cfg)

    def _load_model(self, checkpoint: str, cfg: dict[str, Any]) -> None:
        self.ssl = SSLEncoder(cfg.get("ssl_name", "microsoft/wavlm-base-plus"),
                              bool(cfg.get("local_files_only", False))).to(self.device)
        self.classifier = AASISTL(self.ssl.hidden_size, int(cfg.get("hidden_dim", 128)),
                                  int(cfg.get("graph_heads", 4)),
                                  float(cfg.get("dropout", .15))).to(self.device)
        try:
            state = torch.load(checkpoint, map_location=self.device, weights_only=True)
            self.classifier.load_state_dict(state.get("model", state))
        except Exception as exc:
            raise RuntimeError(f"Could not load Veracust checkpoint {checkpoint!r}: {exc}") from exc
        self.classifier.eval()
        self.model_available = True

    @torch.inference_mode()
    def _deep_inference(self, waveform: torch.Tensor) -> tuple[float | None, dict[str, Any]]:
        if not self.model_available or self.ssl is None or self.classifier is None:
            return None, {"available": False, "reason": "No trained checkpoint configured."}
        feats = self.ssl(waveform.to(self.device))
        logits, attn = self.classifier(feats, return_attention=True)
        prob = torch.sigmoid(logits).mean().item()
        return float(prob), {"available": True,
            "graph_attn_peak": float(attn["graph_attn_peak"].item())}

    def analyze(self, audio_path: str | Path) -> dict[str, Any]:
        cfg = self.config
        record = load_audio(audio_path, int(cfg.get("sample_rate", 16000)),
            float(cfg.get("peak_dbfs", -1.0)), cfg.get("vad", {}))
        x = record.waveform.squeeze(0).cpu().numpy()
        original = record.metadata.get("original_waveform")
        digital = analyze_check0(x, record.sample_rate,
            original.numpy() if isinstance(original, torch.Tensor) else None,
            record.original_sample_rate, cfg.get("check0", {}))
        biology = analyze_biology(x, record.sample_rate, cfg.get("biology", {}))
        physics = analyze_physics(x, record.sample_rate)
        codec = sniff_codec(record.metadata, record.sample_rate)
        if digital.get("hard_anomaly"):
            deep_score, deep_meta = None, {"available": False,
                "skipped": "deterministic extreme gate"}
        else:
            deep_score, deep_meta = self._deep_inference(record.waveform)
        fusion = fuse_scores(digital, biology, physics, deep_score, codec,
            cfg.get("fusion", {}), self.model_available and deep_score is not None)
        report = build_report(digital, biology, physics, deep_score, deep_meta,
            codec, fusion, record.duration_seconds)
        report["preprocessing"] = {"sample_rate": record.sample_rate,
            "original_sample_rate": record.original_sample_rate,
            "original_channels": record.original_channels, **record.metadata["trim"]}
        return report
