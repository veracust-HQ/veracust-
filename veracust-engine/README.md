# Veracust inference engine

Experimental modular audio-forensics pipeline. Run from this directory after installing dependencies:

```bash
python -m pip install -r requirements.txt
python scripts/infer.py path/to/audio.wav
```

Set `VERACUST_CHECKPOINT` to load a trained classifier. Without a checkpoint the neural stage reports unavailable; heuristic fusion is experimental and is not a calibrated probability. The compact graph head is AASIST-inspired, not a canonical AASIST-L implementation.

Core stages: ingestion/resampling/VAD, digital artifact checks, LPC and Praat-derived voice features, modified group delay/harmonic features, optional WavLM encoder + graph classifier, and codec-aware heuristic fusion. Codec detection currently uses limited metadata/sample-rate clues; do not treat it as full codec identification.

The FastAPI adapter and Supabase integration are documented in the root project integration notes. Never store raw uploads as analysis history. Keep service-role credentials server-side only.
