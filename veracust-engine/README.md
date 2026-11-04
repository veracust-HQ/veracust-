# Veracust inference engine

Experimental modular audio-forensics pipeline and FastAPI service.

## Local run

From this directory:

```bash
python -m pip install -r requirements.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

For a direct engine smoke run, use `python scripts/infer.py path/to/audio.wav`.

Set `VERACUST_CHECKPOINT` to load a trained classifier. Without a checkpoint the neural stage reports unavailable; heuristic fusion is experimental and is not a calibrated probability. The compact graph head is AASIST-inspired, not a canonical AASIST-L implementation.

Core stages: ingestion/resampling/VAD, digital artifact checks, LPC and Praat-derived voice features, modified group delay/harmonic features, optional WavLM encoder + graph classifier, and codec-aware heuristic fusion. Codec detection currently uses limited metadata/sample-rate clues; do not treat it as full codec identification.

The service requires SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY to enable identity, history and quotas. The service-role key belongs only in the private API environment. Never store raw uploads as analysis history.
