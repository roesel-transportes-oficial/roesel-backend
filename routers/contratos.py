from fastapi import APIRouter, HTTPException
from database import sb_get, sb_post, sb_patch, sb_delete
from models import Contrato
from uuid import uuid4

router = APIRouter()

@router.get("/")
def listar(motorista: str = "", status: str = "", mes: int = 0, ano: int = 0):
    params = "order=data.desc"
    if motorista:
        from urllib.parse import quote
        params += f"&motorista=eq.{quote(motorista)}"
    if status:
        params += f"&status=eq.{status}"
    dados = sb_get("contratos", params)
    if mes or ano:
        filtrados = []
        for c in dados:
            if c.get("data"):
                partes = c["data"].split("-")
                if ano and int(partes[0]) != ano: continue
                if mes and int(partes[1]) != mes: continue
            filtrados.append(c)
        return filtrados
    return dados

@router.post("/")
def criar(c: Contrato):
    data = c.model_dump(exclude_none=True)
    data["id"] = str(uuid4())
    return sb_post("contratos", data)

@router.put("/{id}")
def atualizar(id: str, c: Contrato):
    data = c.model_dump(exclude={"id"}, exclude_none=True)
    result = sb_patch("contratos", f"id=eq.{id}", data)
    if not result:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return result

@router.delete("/{id}")
def excluir(id: str):
    sb_delete("contratos", f"id=eq.{id}")
    return {"ok": True}