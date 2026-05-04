import os
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests as http_requests
from dotenv import load_dotenv
from routers.motoristas import router as motoristas_router
from routers.contratos import router as contratos_router
from routers.caminhoes import router as caminhoes_router
from routers.abastecimentos import router as abastecimentos_router

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://roesel-frontend.vercel.app",
        "https://roesel-transportes.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(motoristas_router, prefix="/motoristas", tags=["motoristas"])
app.include_router(contratos_router, prefix="/contratos", tags=["contratos"])
app.include_router(caminhoes_router, prefix="/caminhoes", tags=["caminhoes"])
app.include_router(abastecimentos_router, prefix="/abastecimentos", tags=["abastecimentos"])

ultimo_ping = {"timestamp": None}

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health-ping", include_in_schema=False)
def health_ping():
    try:
        url = f"{SUPABASE_URL}/rest/v1/motoristas?select=id&limit=1"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        r = http_requests.get(url, headers=headers, timeout=10)
        db_status = "connected" if r.status_code == 200 else f"error:{r.status_code}"
    except Exception as e:
        db_status = f"error:{str(e)}"

    agora = datetime.now(timezone.utc)
    segundos_desde_ultimo = None
    if ultimo_ping["timestamp"]:
        delta = (agora - ultimo_ping["timestamp"]).total_seconds()
        segundos_desde_ultimo = int(delta)
    ultimo_ping["timestamp"] = agora

    return {
        "status": "awake",
        "db": db_status,
        "agora_utc": agora.isoformat(),
        "ultimo_ping_ha_segundos": segundos_desde_ultimo,
        "proximo_ping_esperado_em_segundos": 120,
    }