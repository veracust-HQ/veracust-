# Veracust integration status

## Runtime integration map

| Layer | Runtime status | Current implementation and caveat |
|---|---|---|
| Ingestion | Connected | Upload allow-list and size cap; decoder, mono conversion, resampling, trimming/VAD and temporary-file handling. Content decoding remains the final format check. |
| Digital integrity / Check 0 | Connected | Digital artifact, entropy, silence and spectral/Nyquist indicators feed the pipeline. Recording-chain effects can produce similar signals. |
| Biological voice features | Connected | LPC and voice-periodicity/perturbation metrics; Praat-dependent values may be unavailable. Not proof of biological identity. |
| Physical/acoustic forensics | Connected | Modified group-delay and harmonic/acoustic features are computed and included in the engine report. |
| Neural classifier | Optional runtime hook | WavLM SSL encoder plus compact AASIST-inspired graph head loads from VERACUST_CHECKPOINT. No trained checkpoint is included yet; this is not a canonical AASIST-L claim. |
| Codec-aware fusion | Connected, heuristic | Reliability weights discount some indicators for lossy/telephony clues. Codec clues are currently metadata/sample-rate heuristics; fusion is uncalibrated. |
| Report persistence | Connected in API code | Supabase stores report JSON and metadata, usage and audit rows. Audio bytes are written to a temporary file and deleted in a finally block. |
| Quotas and identity | Connected in API/SQL design | 1,000 anonymous monthly credits, 10 credits per analysis, registered customers start at zero until plans are configured, admin account is unlimited. |
| Auth and API keys | Connected in API/dashboard | Supabase Auth via server endpoints and HttpOnly cookies; API keys are generated server-side and only their hashes are stored. |
| Dashboard | Connected to API routes | Workbench, verdict, per-layer evidence, login/signup, report history and API-key developer hub. |

## Required end-to-end request flow

1. Resolve an authenticated user, API key or anonymous browser identity.
2. Enforce upload size and extension limits; decode/validate the audio in the ingestion layer.
3. Create a report row and atomically charge 10 credits before inference; failed inference attempts use an idempotent refund.
4. Decode, normalize and process the upload in temporary storage.
5. Execute digital, biological and acoustic stages; execute neural inference only when a compatible checkpoint is configured.
6. Fuse available evidence and persist report JSON plus engine metadata.
7. Delete the temporary audio in a guaranteed cleanup path.
8. Return the structured report to the Next.js workbench; history and API-key pages use authenticated API endpoints.

## Verification status (2026-11-04)

- Python engine syntax compilation passed on the local integration snapshot.
- FastAPI /health smoke test returned HTTP 200 on the local integration snapshot.
- Synthetic waveform smoke test exercised ingestion, digital, biology, physics, fusion and report construction successfully with the neural stage correctly marked unavailable.
- Four local engine tests passed (fusion bounds, codec heuristic labeling and pipeline smoke checks).
- Next.js dependency installation timed out in this environment. Therefore a TypeScript check and production build have not been verified.
- Live Supabase end-to-end upload, quota concurrency/refund, API-key auth and deployment smoke tests have not been run against the connected project in this pass.

## Important scientific distinctions

- Implemented means code exists and is called by the runtime path.
- Connected means adjacent stages exchange data through the pipeline/API.
- Trained means a compatible checkpoint was produced from a documented dataset and run.
- Validated means independent speaker/generator-held-out evaluation and calibration have been completed.

No trained neural checkpoint is bundled. The graph head is AASIST-inspired, not verified canonical AASIST-L. The fusion score is a heuristic score, not a calibrated probability. Codec identification is limited. Do not use the output as sole evidence for a high-impact decision.

## Product and security decisions

- 10 credits per audio analysis, independent of duration; upload cap is 50 MB.
- Anonymous allowance is 1,000 credits per UTC calendar month.
- Registered customer accounts start at zero credits until plans are configured.
- A separate owner/admin account is unlimited through a database role/account type, never through possession of the Supabase secret key.
- Supabase is the system of record for profiles, usage accounts, analyses, usage ledger, API-key hashes and subscriptions.
- Uploaded audio and transcripts are not retained; only report/evidence metadata is persisted.
- Supabase service-role credentials belong only in the private FastAPI environment, never in Next.js client code or Git.
- Payment processing is not implemented.

## Before production

- Install frontend dependencies and run npm run typecheck and npm run build.
- Run Python tests from the actual checked-out branch.
- Test upload failures, concurrent quota consumption, idempotency, refunds and monthly refresh against the provisioned Supabase project.
- Verify owner promotion and unlimited use with the real owner account.
- Train a model using documented, licensed data and generator-disjoint test data.
- Calibrate thresholds and report false-positive/false-negative operating characteristics.
- Configure Render health checks, timeouts, CPU/RAM sizing and private secrets.
