from fastapi import APIRouter
from database import sb_get, sb_post, sb_patch, sb_delete
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4

router = APIRouter()

class Abastecimento(BaseModel):
    id: Optional[str] = None
    data: Optional[str] = None
    caminhao_id: Optional[str] = None
    caminhao_placa: Optional[str] = ""
    motorista: Optional[str] = ""
    posto: Optional[str] = ""
    litros_combustivel: Optional[float] = 0
    valor_litro_combustivel: Optional[float] = 0
    litros_arla: Optional[float] = 0
    valor_litro_arla: Optional[float] = 0
    total: Optional[float] = 0
    obs: Optional[str] = ""

@router.get("/")
def listar(caminhao_id: str = ""):
    if caminhao_id:
        return sb_get("abastecimentos", f"caminhao_id=eq.{caminhao_id}&order=data.desc")
    return sb_get("abastecimentos", "order=data.desc")

@router.post("/")
def criar(a: Abastecimento):
    data = a.model_dump(exclude_none=True)
    data["id"] = str(uuid4())
    return sb_post("abastecimentos", data)

@router.put("/{id}")
def atualizar(id: str, a: Abastecimento):
    data = a.model_dump(exclude={"id"}, exclude_none=True)
    return sb_patch("abastecimentos", f"id=eq.{id}", data)

@router.delete("/{id}")
def excluir(id: str):
    sb_delete("abastecimentos", f"id=eq.{id}")
    return {"ok": True}