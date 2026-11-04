from pathlib import Path
import numpy as np
import soundfile as sf
from src.pipeline import VeracustPipeline

ENGINE_DIR=Path(__file__).resolve().parents[1]

def test_pipeline_runs_non_neural_stages(tmp_path):
    sr=16000
    t=np.arange(sr,dtype=np.float32)/sr
    audio=(0.18*np.sin(2*np.pi*170*t)+0.04*np.sin(2*np.pi*340*t)).astype(np.float32)
    path=tmp_path/"smoke.wav"
    sf.write(path,audio,sr)
    report=VeracustPipeline(ENGINE_DIR/"configs"/"default_config.yaml").analyze(path)
    assert report["engine"]=="Veracust"
    assert set(report["forensic_trace"])=={"check0","biology","physics","deep"}
    assert report["forensic_trace"]["deep"]["available"] is False
    assert 0.0<=report["confidence_score"]<=1.0
