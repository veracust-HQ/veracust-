# Veracust dashboard

Next.js 14 frontend for the Veracust inference service.

## Local development

```bash
npm install
cp .env.example .env.local
# Set VERACUST_API_URL=http://localhost:8000
npm run dev
```

The catch-all API route proxies requests to FastAPI and forwards the browser's authorization and visitor cookies. Keep the Supabase service-role key exclusively in the FastAPI environment. The dashboard does not receive it.

The initial workbench displays the real API response and errors. It intentionally does not replace backend failures with mock verdicts. Auth screens, analysis history, API-key management UI and richer forensic visualizations remain to be imported/implemented in the next integration pass.
