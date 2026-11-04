# Veracust dashboard
Next.js 14 console for the Veracust FastAPI inference service.

## Local run
```bash
npm install
cp .env.example .env.local
# Set VERACUST_API_URL=http://127.0.0.1:8000
npm run dev
```
Open /workbench. Routes include workbench, login/signup, analysis history, and API-key management. The server-side API proxy forwards the HttpOnly access cookie to FastAPI. Supabase service-role credentials must never be placed in this app or exposed to the browser.

The workbench uploads audio to the API and renders the actual returned evidence. It does not silently substitute mock results. History stores report metadata only; uploaded audio is temporary and deleted by the API.