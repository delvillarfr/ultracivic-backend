# app/main.py
from fastapi import FastAPI
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="Ultra Civic Backend")

# Routers are added here
@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}

