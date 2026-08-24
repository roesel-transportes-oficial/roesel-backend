import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ✅ VOLTA a ter o app definido diretamente aqui (igual funcionava
# antes pra /contratos/), em vez de importar de main.py. Descobrimos
# que importar o app de outro arquivo quebra o roteamento de rotas
# que não sejam a raiz nesse ambiente específico da Vercel — então,
# por segurança, esse arquivo passa a ser a ÚNICA fonte de verdade de
# verdade (é o que a Vercel roda, conforme o vercel.json). O main.py
# continua existindo mas não é mais o que vai pro ar — daqui pra
# frente, qualquer mudança de rota precisa ser feita AQUI também.
from routers.motoristas import router as motoristas_router
from routers.contratos import router as contratos_router
from routers.caminhoes import router as caminhoes_router
from routers.abastecimentos import router as abastecimentos_router
from routers.contas_pagar import router as contas_pagar_router
from routers.ctes import router as ctes_router
from routers.notas_diversas import router as notas_diversas_router

app = FastAPI()

# ✅ CORS restrito ao domínio do frontend (antes estava "*", aberto
# pra qualquer site — outra coisa que nunca tinha ido pro ar de
# verdade até agora).
ORIGENS_PERMITIDAS = [
    "https://roesel-frontend.vercel.app",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENS_PERMITIDAS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(motoristas_router, prefix="/motoristas", tags=["motoristas"])
app.include_router(contratos_router, prefix="/contratos", tags=["contratos"])
app.include_router(caminhoes_router, prefix="/caminhoes", tags=["caminhoes"])
app.include_router(abastecimentos_router, prefix="/abastecimentos", tags=["abastecimentos"])
app.include_router(contas_pagar_router, prefix="/contas-pagar", tags=["contas_pagar"])
app.include_router(ctes_router, prefix="/ctes", tags=["ctes"])
app.include_router(notas_diversas_router, prefix="/notas-diversas", tags=["notas_diversas"])

@app.get("/")
def root():
    return {"status": "ok"}

handler = Mangum(app)