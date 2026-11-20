# LPU Wayfinder — Vercel + Render deployment

This configuration is for a public **prototype**, not a production persistence setup. 
It does **not** make still-unverified GPS tracks automatically routable.

## 1. Render backend

1. Merge the deployment patch to `main`.
2. Sign in at https://dashboard.render.com and use **New → Blueprint**, selecting this GitHub repository and `render.yaml`. Alternatively, create a Python Web Service with repository root `.` and the commands from `render.yaml`.
3. When asked for `ADMIN_PASSWORD_HASH`, paste your already-existing bcrypt hash from the local `.env` privately into Render (never commit it). Render generates `JWT_SECRET_KEY`.
4. `DATABASE_URL` is set to `sqlite:////tmp/lpu_wayfinder.db`. The startup event creates the tables and seeds five unverified locations without overwriting existing rows.
5. Wait for the service to become healthy, then visit `https://YOUR-SERVICE.onrender.com/api/locations` and `/api/survey-tracks`. Both should return JSON.

**Important:** The Render Free service sleeps after inactivity and its local SQLite data is *ephemeral*: it may disappear after a sleep, restart or redeploy. The five block records are recreated on next startup, but admin-added data and survey submissions are NOT persistent. Do not rely on this for permanent user data. For lasting storage, migrate the data model to persistent Postgres or use a paid service with a persistent disk; existing PostGIS Geometry types require matching PostGIS support.

## 2. Vercel frontend

1. Sign in to https://vercel.com/new and import `Swastik-2007/INT_Project`.
2. Root Directory: `frontend`, Framework Preset: `Vite`, Install Command: `npm ci`, Build Command: `npm run build`, Output Directory: `dist`.
3. Set environment variable `VITE_BACKEND_URL` to the Render HTTPS service URL, **without a trailing slash**, e.g. `https://YOUR-SERVICE.onrender.com`. It is a public URL, not a secret.
4. Deploy. The `frontend/vercel.json` rewrite lets `/map` and `/admin/login` load directly on refresh.

## 3. Verify

- On the backend, `GET /api/locations` should return five records, all unverified; `GET /api/survey-tracks` should return four LineString survey tracks and 8 endpoint markers.
- On the frontend, open `/`, `/map`, and `/admin/login` on the deployed URL. Check search, survey layer toggle, and unavailable-route message (until verified routing is implemented).
- If the Vercel map shows zero blocks, inspect Render service logs and `VITE_BACKEND_URL`. Changing a Vercel environment variable requires a **new deployment**.
- Render and Vercel automatically deploy successful pushes to linked `main` by default. Do not push real `.env`, raw passwords or JWT secrets.
