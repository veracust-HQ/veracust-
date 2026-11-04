# Veracust

Veracust is an experimental AI voice-clone and synthetic-audio detection platform. It combines digital-signal checks, physical/acoustic and voice-biological forensic features, a neural audio classifier, and codec-aware evidence fusion.

> **Research status:** This project is not a validated universal deepfake detector. Heuristic scores are not calibrated probabilities. A neural checkpoint and independent evaluation are required before making accuracy or forensic-reliability claims.

## Repository layout

The intended monorepo layout is:

- `veracust-dashboard/` — Next.js dashboard and user-facing API proxy.
- `veracust-engine/` — FastAPI service and modular audio-forensics pipeline.
- `supabase/migrations/` — database schema, RLS, usage accounting and API-key metadata.
- `training/` (inside the engine) — dataset manifest validation, training and evaluation.
- `docs/` — architecture, integration contracts, deployment and validation notes.

The application should use a server-side API boundary. Supabase service credentials must never be exposed to browser code or committed to this repository.

## Detection pipeline

1. **Ingestion:** validate audio, decode, normalize to the model's expected format, and extract file/container metadata.
2. **Digital integrity gate:** inspect signal-level and spectral anomalies. These are indicators, not standalone proof of synthesis.
3. **Physical/acoustic forensics:** extract acoustic and production-chain features.
4. **Voice/biological forensics:** extract voice-production consistency features, with missing/low-quality signals reported explicitly.
5. **Neural analysis:** run the trained self-supervised speech encoder and classifier when a compatible checkpoint is installed.
6. **Codec-aware fusion:** combine available evidence with explicit per-layer status, calibration metadata and abstention/uncertainty handling.
7. **Reporting:** return a traceable verdict, evidence, model version and limitations.

Each stage must report whether it ran, its version, and why it was skipped or unavailable. A placeholder score must never be presented as a completed model result.

## Product integration requirements

- Audio uploads are processed temporarily; raw audio is deleted after processing and is not retained as an analysis-history artifact.
- Persist report metadata and evidence summaries, not uploaded audio.
- Authentication and user-scoped history use Supabase Auth and Row Level Security.
- Usage is charged server-side: 10 credits per analysis. The agreed anonymous allowance is 1,000 credits per month (100 analyses); authenticated customer balances and owner/admin exemptions are enforced by trusted backend logic.
- API keys are stored as hashes; plaintext keys are shown only once at creation.
- All privileged Supabase operations use a server-side secret stored in deployment environment variables.
- The dashboard must display backend errors; it must not silently substitute mock verdicts for failed real analyses.

## Development

See `docs/INTEGRATION_STATUS.md` for the implementation audit and current known gaps. Each service has its own README and dependency manifest once its source directory is imported.

## Research and evaluation

The initial model plan is a pretrained WavLM/Wav2Vec2 encoder with a lightweight classifier, trained and evaluated on speaker-separated data and multiple synthetic generators. Evaluation should include held-out speakers and held-out generators, class-wise metrics, calibration and false-positive/false-negative analysis. Do not describe training-set performance as generalization.

## Security

Never commit `.env` files, Supabase secret/service-role keys, API-key plaintext, user audio, model credentials or private datasets. Use `.env.example` files containing placeholders only.
