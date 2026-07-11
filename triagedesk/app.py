from fastapi import FastAPI

app = FastAPI(title="TriageDesk")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
