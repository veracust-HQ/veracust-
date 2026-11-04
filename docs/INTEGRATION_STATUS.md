# Veracust integration status

This document defines the required integration contract and prevents incomplete or heuristic components from being described as production-ready.

## Required backend layers

| Layer | Responsibility | Required output |
|---|---|---|
| Ingestion | File validation, safe decoding, channel/sample-rate normalization, duration limits, temporary-file lifecycle | Audio descriptor, normalized waveform, metadata, validation warnings |
| Digital gate | RIFF/container inspection, silence/entropy and spectral-grid checks, Nyquist/high-frequency checks where meaningful | Named observations, measurements, limitations; never a binary verdict alone |
| Physical/acoustic forensics | LPC/residual, modified group delay, jitter/shimmer and relevant acoustic/production-chain features | Feature values, quality flags, unavailable reasons |
| Voice/biological forensics | Voice-production and vocal-consistency analysis | Feature values and quality flags; no overclaiming biological certainty |
| Neural classifier | Pretrained SSL speech encoder plus trained classifier; optional RawBoost augmentation during training | Logits/probability only with model/checkpoint identity and calibration status |
| Codec-aware fusion | Reliability-aware combination of layer outputs, calibrated thresholding and abstention | Verdict, confidence semantics, contributing evidence, model/policy versions |
| Report persistence | Persist result metadata and evidence summary without storing uploaded audio | Analysis record and audit metadata |

## Important implementation distinctions

- **Implemented** means code exists and is called by the runtime path.
- **Connected** means the preceding and following stages exchange validated, typed data.
- **Trained** means a compatible checkpoint was produced from a documented dataset and training run.
- **Validated** means independent speaker/generator-held-out evaluation and calibration have been completed.

A file existing in the repository does not establish any of these runtime or scientific properties.

## Current known limitations from the available integration bundle

The previously assembled bundle contains modular ingestion, digital, physics, biology, neural-model, fusion and FastAPI modules, plus a Next.js dashboard, Supabase migrations and a starter training workflow. It is an experimental integration, not a fully validated detector.

Known limitations that must remain visible until resolved:

1. No trained production neural checkpoint is included.
2. The neural graph model must be audited against the intended AASIST-L architecture; an inspired implementation must not be labelled canonical AASIST-L without verification.
3. Several forensic signals are heuristic or dependent on audio quality and codec conditions.
4. Codec identification must not be reduced to sample-rate-only guesses.
5. Fusion scores require calibration on independent data; an uncalibrated sigmoid is not a probability.
6. t-DCF and threshold selection require a defined evaluation protocol and suitable bona-fide/spoof data.
7. End-to-end API, dashboard, Supabase quota, authentication and deployment tests are still required.
8. Training data provenance, licensing and generator coverage must be documented.

## Required end-to-end request flow

1. Authenticate the user or establish the supported anonymous identity.
2. Enforce upload limits and validate content server-side.
3. Reserve/consume 10 credits atomically before expensive analysis; refund on a failed analysis according to the idempotent ledger policy.
4. Write the upload to a temporary location only.
5. Execute each available pipeline stage and record stage status.
6. Fuse only valid outputs; include explicit unavailable/low-quality states.
7. Persist the report and model/pipeline versions, not the uploaded audio.
8. Delete temporary audio in a guaranteed cleanup path, including exceptions/timeouts where possible.
9. Return a typed report to the dashboard.
10. Verify history and credit balance using user-scoped authorization.

## Original product decisions

- 10 credits per audio analysis, independent of audio duration, subject to server-side upload/duration caps.
- Anonymous allowance: 1,000 credits per month.
- Owner/admin account: unlimited usage through a trusted database role/account flag, never through possession of the Supabase secret key.
- Supabase is the system of record for profiles, usage accounts, analyses, usage ledger, API-key metadata and subscriptions.
- Uploaded audio is not retained after processing.

## Before production

- Complete source import and dependency lockfiles.
- Run Python unit tests and API integration tests.
- Run Next.js typecheck, lint and production build.
- Verify Supabase migrations, RLS policies and RPC permissions in the target project.
- Test quota concurrency, idempotency, refunds, monthly refresh and admin exemption.
- Test audio cleanup on success and every failure path.
- Train a checkpoint and run held-out speaker and generator evaluation.
- Calibrate decision thresholds and document operating characteristics.
- Configure deployment secrets only in the backend hosting environment.
