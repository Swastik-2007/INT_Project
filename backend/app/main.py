from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .router import api_router

app = FastAPI(title="LPU Wayfinder Backend")

@app.on_event("startup")
async def startup_event():
    # Initialize database tables
    from .db import init_db
    init_db()

# Allow frontend (localhost:5173) to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
