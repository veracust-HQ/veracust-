from __future__ import annotations
import numpy as np
import pytest
from src.fusion.dynamic_fusion import fuse_scores, sniff_codec

def test_fusion_returns_bounded_score_without_checkpoint():
    result=fuse_scores(
        {"digital_score":0.2},
        {"valid":False},
        {"mgd_deviation":0.1,"h2_h5_ratio":0.1},
        None,
        {"telephony_bandwidth":False,"lossy_codec":False},
        {"threshold":0.5},
        False,
    )
    assert 0.0 <= result["confidence_score"] <= 1.0
    assert result["effective_weights"]["deep"] == 0.0
    assert isinstance(result["is_synthetic"],bool)

def test_codec_sniff_is_explicitly_heuristic():
    result=sniff_codec({"original_rate":8000},16000)
    assert result["telephony_bandwidth"] is True
    assert "heuristic" in result["codec_evidence"]

def test_extreme_digital_flags_do_not_break_fusion():
    result=fuse_scores(
        {"digital_score":1.0,"hard_anomaly":True},
        {"valid":False},{"mgd_deviation":0.0,"h2_h5_ratio":0.0},
        None,{"telephony_bandwidth":True,"lossy_codec":False},{},False)
    assert np.isfinite(result["confidence_score"])
