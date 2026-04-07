from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import motoristas, contratos, frotas, caminhoes, ia

app = FastAPI(title="Roesel Transportes API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(motoristas.router, prefix="/api/motoristas", tags=["Motoristas"])
app.include_router(contratos.router, prefix="/api/contratos", tags=["Contratos"])
app.include_router(frotas.router, prefix="/api/frotas", tags=["Frotas"])
app.include_router(caminhoes.router, prefix="/api/caminhoes", tags=["Caminhões"])
app.include_router(ia.router, prefix="/api/ia", tags=["IA"])

@app.get("/")
def root():
    return {"status": "Roesel Transportes API rodando"}