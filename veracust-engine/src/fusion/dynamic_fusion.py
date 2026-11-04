from __future__ import annotations
from typing import Any
import numpy as np

def sniff_codec(metadata: dict[str, Any], sample_rate: int) -> dict[str, Any]:
    original_sr = int(metadata.get("original_rate", sample_rate))
    telephony = original_sr <= 8000 or sample_rate <= 8000
    lossy = bool(metadata.get("lossy_codec", False))
    return {"telephony_bandwidth": telephony, "lossy_codec": lossy,
            "original_sample_rate": original_sr,
            "codec_evidence": "decoder metadata unavailable; sample-rate heuristic only"}

def _sigmoid(z: float) -> float:
    z = float(np.clip(z, -30.0, 30.0))
    return 1.0 / (1.0 + np.exp(-z))

def fuse_scores(digital: dict[str, Any], biology: dict[str, Any],
                physics: dict[str, Any], deep_score: float | None,
                codec: dict[str, Any], config: dict[str, Any],
                model_available: bool) -> dict[str, Any]:
    fc = config or {}
    weights = dict(fc.get("weights", {}))
    w = {"digital": float(weights.get("digital", .24)),
         "biology": float(weights.get("biology", .18)),
         "physics": float(weights.get("physics", .13)),
         "deep": float(weights.get("deep", .45))}
    if codec.get("lossy_codec"):
        w["digital"] *= float(fc.get("lossy_hf_discount", .45))
        w["physics"] *= float(fc.get("lossy_hf_discount", .45))
    if codec.get("telephony_bandwidth"):
        w["digital"] *= float(fc.get("telephony_hf_discount", .30))
        w["physics"] *= float(fc.get("telephony_hf_discount", .30))
    if not model_available or deep_score is None:
        w["deep"] = 0.0
    d = float(np.clip(digital.get("digital_score", 0.0), 0, 1))
    b = 0.0
    if biology.get("valid"):
        jitter, shimmer = biology.get("jitter_local"), biology.get("shimmer_local")
        entropy = float(biology.get("lpc_residual_entropy_bits", 0))
        cues = []
        if jitter is not None: cues.append(np.clip(abs(float(jitter) - .01) / .04, 0, 1))
        if shimmer is not None: cues.append(np.clip(abs(float(shimmer) - .04) / .12, 0, 1))
        cues.append(np.clip(abs(entropy - 5.0) / 5.0, 0, 1))
        b = float(np.mean(cues))
    p = float(np.clip((physics.get("mgd_deviation", 0) / 10.0 +
                       physics.get("h2_h5_ratio", 0) / 2.0) / 2.0, 0, 1))
    q = float(np.clip(deep_score, 0, 1)) if deep_score is not None else 0.0
    total_w = sum(w.values())
    if total_w <= 0:
        raise ValueError("Fusion weights must have positive sum.")
    raw = (w["digital"]*d + w["biology"]*b + w["physics"]*p + w["deep"]*q) / total_w
    temp = max(float(fc.get("sigmoid_temperature", 1.0)), 1e-6)
    bias = float(fc.get("bias", 0.0))
    clipped = float(np.clip(raw, 1e-5, 1 - 1e-5))
    calibrated = _sigmoid((np.log(clipped / (1-clipped)) + bias) / temp)
    threshold = float(fc.get("threshold", .5))
    return {"confidence_score": calibrated, "is_synthetic": bool(calibrated >= threshold),
            "decision_threshold": threshold, "raw_fused_score": raw,
            "component_scores": {"digital": d, "biology": b, "physics": p, "deep": q},
            "effective_weights": w}

def build_report(digital: dict[str, Any], biology: dict[str, Any],
                 physics: dict[str, Any], deep_score: float | None,
                 deep_meta: dict[str, Any], codec: dict[str, Any],
                 fusion: dict[str, Any], duration: float) -> dict[str, Any]:
    anomalies = []
    if digital.get("hard_anomaly"): anomalies.append("extreme_digital_artifact_gate")
    if digital.get("nyquist_flag"): anomalies.append("high_frequency_nyquist_energy")
    if digital.get("silence_entropy_flag"): anomalies.append("silence_or_low_entropy")
    if digital.get("spectral_grid_flag"): anomalies.append("spectral_grid_modulation")
    if biology.get("valid") and biology.get("jitter_local") is not None and biology["jitter_local"] > .04:
        anomalies.append("elevated_local_jitter")
    if physics.get("h2_h5_ratio", 0) > 1.0: anomalies.append("elevated_harmonic_distortion")
    primary = anomalies[0] if anomalies else ("model_score" if deep_score is not None else "insufficient_evidence")
    return {"engine": "Veracust", "version": "1.0.0",
        "classification": "synthetic" if fusion["is_synthetic"] else "bona_fide",
        "is_synthetic": fusion["is_synthetic"],
        "confidence_score": round(float(fusion["confidence_score"]), 6),
        "primary_anomaly": primary, "attack_type": primary,
        "duration_seconds": round(float(duration), 4), "codec": codec,
        "scores": fusion["component_scores"], "effective_weights": fusion["effective_weights"],
        "forensic_trace": {"check0": digital, "biology": biology, "physics": physics,
            "deep": {"synthetic_probability": deep_score, **deep_meta}},
        "limitations": ["Heuristic features are not proof of synthesis.",
            "A trained, domain-calibrated checkpoint is required for validated use."]}
