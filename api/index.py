@"
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from routers.motoristas import router as motoristas_router
from routers.contratos import router as contratos_router
from routers.caminhoes import router as caminhoes_router
from routers.abastecimentos import router as abastecimentos_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(motoristas_router, prefix="/motoristas", tags=["motoristas"])
app.include_router(contratos_router, prefix="/contratos", tags=["contratos"])
app.include_router(caminhoes_router, prefix="/caminhoes", tags=["caminhoes"])
app.include_router(abastecimentos_router, prefix="/abastecimentos", tags=["abastecimentos"])

@app.get("/")
def root():
    return {"status": "ok"}

handler = Mangum(app)
"@ | Out-File -FilePath api/index.py -Encoding utf8