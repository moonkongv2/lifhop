from fastapi import FastAPI
from app.api.entries import router as entries_router
from app.db import check_database_connection

app = FastAPI(title="Lifhop")

app.include_router(entries_router)

@app.get("/health")
def health() -> dict[str, str]:
    check_database_connection()

    return {"status": "ok"}
