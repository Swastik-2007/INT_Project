from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .router import api_router

app = FastAPI(title="LPU Wayfinder Backend")

@app.on_event("startup")
async def startup_event():
    # Create missing tables; never drop or overwrite existing data.
    from .db import init_db
    init_db()
    # Seed the five unverified campus blocks on a newly created database.
    # The importer is idempotent and never changes existing location rows.
    from scripts.seed_locations import seed_data
    seed_data()
    # Hydrate durable verification records (Phase 2B persistent storage strategy)
    try:
        from .db import SessionLocal
        from .verification_store import hydrate_database
        db_session = SessionLocal()
        try:
            hydrate_database(db_session)
        finally:
            db_session.close()
    except Exception as e:
        print(f"Verification store hydration note: {e}")

# The frontend uses bearer tokens and relative API routes in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
