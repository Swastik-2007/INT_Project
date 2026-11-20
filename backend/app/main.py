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

# The frontend uses bearer tokens and relative API routes in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
