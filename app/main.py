from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, SessionLocal
from app.core.seed import seed
from app.models.models import Base
from app.api.routes import claims, members, policies


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="RealFast Claims Processing System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(policies.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
