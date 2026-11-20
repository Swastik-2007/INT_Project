# Project Progress - LPU Wayfinder

## Phase 1 – Research & Data Architecture
- [x] Created project scaffolding (backend, frontend, data, docs, Docker, README).
- [x] Extracted baseline block numbers (28, 29, 30, 34, 36) in `data/blocks_unverified.json`.
- [x] Clear data distinction: unverified blocks stored with `verified: false` and null coordinates pending physical ground-truth survey.
- [x] SQLite fallback enabled for local environments without PostGIS dependencies.

## Phase 2 – Backend Setup & Core APIs
- [x] FastAPI server running on `http://127.0.0.1:8000` with uvicorn.
- [x] Idempotent database seeding script (`backend/scripts/seed_locations.py`).
- [x] Database models with SQLite compatibility for `Location`, `Walkway`, and `Survey`.
- [x] Location endpoints: `GET /api/locations`, `GET /api/locations/{id}`.
- [x] Secure JWT admin authentication (`POST /api/admin/token`) using bcrypt.
- [x] Protected Survey API: `GET /api/admin/surveys`, `POST /api/admin/surveys`, `DELETE /api/admin/surveys/{id}`.
- [x] Pedestrian Route API: `GET /api/route?origin_id={orig}&destination_id={dest}` with NetworkX graph routing. Returns `"available": false` with message `"Walking route not yet available. This area is awaiting mapping."` when verified walkway graph is incomplete.

## Phase 3 – Interactive Campus Map & Public UI
- [x] Public-facing interactive React + TypeScript frontend running via Vite on `http://localhost:5173`.
- [x] LPU-inspired design system:
  - Primary Orange: `#E66A27`
  - Deep Charcoal: `#20252D`
  - Soft Cream: `#FFF8F1`
  - Neutral Gray: `#6B7280`
- [x] Public Homepage (`/`):
  - Hero section with search destination bar.
  - Three primary action cards: "Use My Location", "Explore Campus Map", and "Find Walking Route".
  - Quick category filtering (Academic Blocks, Hostels, Gates, Facilities).
  - Live campus block directory fetched from backend.
  - Informative GPS & permissions guide.
- [x] Interactive Campus Map (`/map`):
  - Leaflet map centered at LPU Campus coordinates (`31.2534, 75.7037`).
  - Real-time GPS user tracking with pulsating accuracy ring.
  - Destination search bar overlay.
  - Campus block markers distinguishing verified entrances vs survey-pending blocks.
  - Dynamic route preview and distance calculation.
  - "Walking route not yet available" notice when route geometry is awaiting ground survey.
  - Full walking navigation HUD with arrival confirmation.
  - Recenter-on-GPS floating button.
  - Mobile bottom sheet designed for one-hand smartphone navigation.

## Phase 4 – Mobile GPS Survey Tool (Preserved Admin Functionality)
- [x] Admin Login at `/admin/login` with JWT authentication.
- [x] GPS Survey Tool at `/admin/survey`:
  - Automatic GPS point recording every 2.5 seconds.
  - Start, Pause, Resume, and Stop controls.
  - Live stats: lat, lon, accuracy, point count, elapsed time, distance.
  - Automatic IndexedDB draft saving across page reloads.
  - Direct phone GeoJSON export.
  - GPX file import support for OsmAnd recordings.
  - Backend survey sync with `verified: false` default.

## Phase 5 – Map Tile & Usability Polish (Verified)
- [x] **Map Tile Watermark Resolution:**
  - Replaced API-key-gated CartoDB tiles in `/map` with official OpenStreetMap Standard basemap (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`).
  - Added visible attribution: `© OpenStreetMap contributors`.
  - Zero API key requirement, fully compliant with OSM tile usage guidelines.
- [x] **Homepage Layout Polish:**
  - Reduced excessive vertical desktop whitespace across hero, quick actions, directory, and guide.
  - Changed badge text to "LPU Campus Navigation".
  - Prominent destination search and unverified status badges preserved in the directory.
- [x] **Mobile Map UX & No Fake Routes Strictness:**
  - Responsive bottom sheet height adjusted: collapsed state is compact (`54px`), expanded state capped at `clamp(220px, 36vh, 340px)` to avoid obscuring the map on mobile.
  - Removed straight-line distance fallback when a route is unmapped; displays strictly: *"Walking route not yet available. This area is awaiting mapping."*
  - "Start Walking Navigation" button is disabled with label *"Route Awaiting Survey"* when route is unmapped, preventing simulated walks on unverified routes.
- [x] **Automated Verification:**
  - Production build (`npm run build`) succeeded with 0 TypeScript/bundler errors.
  - 10-step automated verification suite (`backend/scripts/run_verification_tests.py`) passed 10/10 tests.
  - Existing SQLite database (`lpu_wayfinder.db`) preserved with no data loss.
