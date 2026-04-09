from fastapi import APIRouter
from database import sb_get, sb_post, sb_patch, sb_delete
from models import Caminhao
from uuid import uuid4

router = APIRouter()

@router.get("/")
def listar(frota_id: str = ""):
    if frota_id:
        return sb_get("caminhoes", f"frota_id=eq.{frota_id}&order=placa.asc")
    return sb_get("caminhoes", "order=placa.asc")

@router.post("/")
def criar(c: Caminhao):
    data = c.model_dump(exclude_none=True)
    data["id"] = str(uuid4())
    data["placa"] = data["placa"].upper()
    if "frota_id" in data:
        data["frota_id"] = str(data["frota_id"])
    for campo in ["venc_licenca", "venc_tacografo", "venc_outros"]:
        if campo in data and data[campo]:
            data[campo] = str(data[campo])
    return sb_post("caminhoes", data)

@router.put("/{id}")
def atualizar(id: str, c: Caminhao):
    data = {
        "placa": c.placa.upper() if c.placa else None,
        "modelo": c.modelo,
        "ano": c.ano,
        "frota": c.frota,
        "motorista_atual": c.motorista_atual,
        "status": c.status,
        "motivo_parado": c.motivo_parado,
        "dt_parado": c.dt_parado,
        "venc_licenca": str(c.venc_licenca) if c.venc_licenca else None,
        "venc_tacografo": str(c.venc_tacografo) if c.venc_tacografo else None,
        "venc_outros": str(c.venc_outros) if c.venc_outros else None,
        "obs_documentos": c.obs_documentos,
    }
    if c.frota_id:
        data["frota_id"] = str(c.frota_id)
    return sb_patch("caminhoes", f"id=eq.{id}", data)

@router.delete("/{id}")
def excluir(id: str):
    sb_delete("caminhoes", f"id=eq.{id}")
    return {"ok": True}