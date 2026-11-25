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
from routers.mdfes import router as mdfes_router
from routers.gnres import router as gnres_router
from routers.notas_diversas import router as notas_diversas_router

app = FastAPI()

# ✅ CORS restrito ao domínio do frontend (antes estava "*", aberto
# pra qualquer site — outra coisa que nunca tinha ido pro ar de
# verdade até agora).
ORIGENS_PERMITIDAS = [
    "https://roesel-frontend.vercel.app",
    "https://roesel-homologacao.vercel.app",
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
app.include_router(mdfes_router, prefix="/mdfes", tags=["mdfes"])
app.include_router(gnres_router, prefix="/gnres", tags=["gnres"])
app.include_router(notas_diversas_router, prefix="/notas-diversas", tags=["notas_diversas"])

# Qualquer erro não tratado volta como JSON com o motivo, em vez de um
# "Internal Server Error" sem explicação. Ajuda a achar tabela faltando etc.
from fastapi import Request
from fastapi.responses import JSONResponse
import requests as _requests


@app.exception_handler(Exception)
async def erro_geral(request: Request, exc: Exception):
    if type(exc).__name__ in ("ErroEmissao", "CertificadoNaoConfigurado", "ErroGnre", "ErroMdfe"):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    if isinstance(exc, _requests.HTTPError) and exc.response is not None:
        corpo = exc.response.text[:400]
        dica = ""
        if "does not exist" in corpo or "PGRST205" in corpo or "Could not find the table" in corpo:
            dica = " -> Falta criar a tabela no Supabase: rode o arquivo .sql correspondente no SQL Editor."
        return JSONResponse(status_code=500, content={"detail": f"Erro no Supabase ({exc.response.status_code}): {corpo}{dica}"})
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


@app.get("/")
def root():
    return {"status": "ok"}

handler = Mangum(app)