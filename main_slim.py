"""Minimal ARPIA server para diagnóstico de deploy."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Arpia-Slim")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status": "ok", "app": "arpia-slim", "db": "not-checked"}

@app.get("/api/conselho/blueprint")
async def blueprint():
    return {"status": "arpia-slim online — full app loading"}
