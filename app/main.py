from fastapi import FastAPI
from app.db import check_database_connection

app = FastAPI(title="Lifhop")

@app.get("/health")
def health() -> dict[str, str]:
    check_database_connection()

    return {"status": "ok"}
