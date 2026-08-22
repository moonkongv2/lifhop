from fastapi import FastAPI

app = FastAPI(title="Lifhop")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
