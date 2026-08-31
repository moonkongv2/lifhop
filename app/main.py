from fastapi import FastAPI
from app.api.entries import router as entries_router
from app.api.auth import router as auth_router
from app.api.attachments import router as attachments_router
from app.api.imports import router as imports_router
from app.db import check_database_connection
from app.api.import_artifacts import router as import_artifacts_router

app = FastAPI(title="Lifhop")

app.include_router(entries_router)
app.include_router(auth_router)
app.include_router(attachments_router)
app.include_router(imports_router)
app.include_router(import_artifacts_router)

@app.get("/health")
def health() -> dict[str, str]:
    check_database_connection()

    return {"status": "ok"}
