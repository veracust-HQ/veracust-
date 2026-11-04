# Veracust

Experimental synthetic-audio triage product with a Next.js console, modular Python/FastAPI engine and Supabase persistence/usage layer.

## Repository map
- `veracust-dashboard/`: workbench, login/signup, analysis history and API-key management.
- `veracust-engine/`: audio ingestion, digital integrity, biological/acoustic analysis, optional WavLM + graph classifier, fusion and FastAPI.
- `supabase/migrations/`: schema, RLS, credit RPCs and indexes.
- `tests/`: engine smoke and fusion tests.
- `scripts/promote-admin.sql`: one-time promotion of a separate owner login.

## Local development
1. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` in `veracust-engine/.env`. Keep the service-role key only on the Python API host.
2. From `veracust-engine`: `pip install -r requirements.txt` then `uvicorn api.main:app --host 127.0.0.1 --port 8000`.
3. Set `VERACUST_API_URL=http://127.0.0.1:8000` in `veracust-dashboard/.env.local`.
4. From `veracust-dashboard`: `npm install && npm run dev`.
5. Open `http://localhost:3000/workbench`.

## Usage policy
Anonymous browser identities receive 1,000 credits per UTC calendar month; each audio analysis costs 10 credits regardless of duration. Registered customer accounts start at zero credits pending plan configuration. A separately promoted admin account has unlimited use. Payment processing is not implemented.

## Model and forensic limitations
No trained neural checkpoint is included. The graph classifier is AASIST-inspired rather than a verified canonical AASIST-L reproduction. Codec clues are partly sample-rate heuristics. Fusion is uncalibrated and must not be represented as a validated probability or used as sole evidence in high-impact decisions.
