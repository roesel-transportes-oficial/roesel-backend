from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.motoristas import router as motoristas_router
from routers.contratos import router as contratos_router
from routers.caminhoes import router as caminhoes_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(motoristas_router, prefix="/motoristas", tags=["motoristas"])
app.include_router(contratos_router, prefix="/contratos", tags=["contratos"])
app.include_router(caminhoes_router, prefix="/caminhoes", tags=["caminhoes"])

@app.get("/")
def root():
    return {"status": "ok"}