# Render deployment runbook

This repository contains two separately deployed services. Deploy the Python API first, then the Next.js dashboard.

## 1. Python API service

Create a Render **Web Service** from this repository.

- Name: `veracust-api`
- Root directory: `veracust-engine`
- Runtime: Python
- Build command:
  ```bash
  python -m pip install --upgrade pip
  pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio
  pip install -r requirements.txt
  ```
- Start command:
  ```bash
  uvicorn api.main:app --host 0.0.0.0 --port $PORT
  ```
- Health check path: `/health`

Set these environment variables in the API service's private Render environment:

| Key | Value |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase publishable key (`sb_publishable_...`) or legacy anon JWT |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase secret key (`sb_secret_...`) or legacy service_role JWT |
| `VERACUST_COOKIE_SECURE` | `true` |
| `VERACUST_CORS_ORIGINS` | Exact HTTPS dashboard origin |
| `VERACUST_MAX_UPLOAD_BYTES` | `52428800` |
| `VERACUST_ANONYMOUS_MONTHLY_CREDITS` | `1000` |

Optional: set `VERACUST_CHECKPOINT` only after a compatible, evaluated model checkpoint has been trained and deployed. Leave it empty for the current experimental non-neural path.

**Secret handling:** the Supabase secret/service-role key must exist only in this API service's environment. Never add it to the dashboard environment, GitHub, browser code, or a client-side `NEXT_PUBLIC_*` variable.

## 2. Next.js dashboard service

Create a second Render **Web Service** from the same repository.

- Name: `veracust-dashboard`
- Root directory: `veracust-dashboard`
- Runtime: Node
- Build command: `npm install --no-audit --no-fund && npm run build`
- Start command: `npm start`

Set:

| Key | Value |
|---|---|
| `VERACUST_API_URL` | The API service's reachable base URL, without a trailing slash |

Use the API service's private/internal URL when the two services are configured for private networking in the same region; otherwise use its HTTPS public URL.

## 3. First deployment smoke test

1. Wait for both services to finish deploying.
2. Open `https://YOUR-API-DOMAIN/health`; expect HTTP 200 and a healthy status.
3. Open the dashboard domain and create a customer account.
4. Confirm login, logout and session refresh.
5. Upload a short, non-sensitive WAV file. Confirm the API returns a report and the dashboard displays its evidence sections.
6. Confirm the analysis row and 10-credit ledger entry appear in Supabase.
7. Confirm the temporary uploaded audio is deleted after processing and is not stored in Supabase.
8. Retry a failed/invalid upload and verify it does not leave a permanent charge.
9. Create and revoke an API key; verify the raw key is shown only at creation and only its hash is stored.
10. Test quota exhaustion and monthly refresh before enabling public traffic.

## 4. Promote the separate owner account

1. Sign up through the deployed dashboard using the separate owner email.
2. In Supabase SQL Editor, open `scripts/promote-admin.sql`.
3. Replace the placeholder email with that exact owner email and run the script.
4. Verify the final SELECT shows `role=admin` and `account_type=admin`.
5. Sign out and back in, then confirm the owner account is exempt from credit deductions.

Do not promote the account by exposing or using the Supabase secret key in the browser.

## 5. Release gates and current limitations

- Keep PR #1 unmerged until CI is green and the live upload/history/quota flow is tested.
- The neural classifier has no trained checkpoint yet. Do not advertise the current heuristic score as a validated probability or universal AI-voice detector.
- Payment plans and payment processing are not implemented.
- Render deployment, real authentication, owner promotion and end-to-end API tests have not been completed by this runbook.
