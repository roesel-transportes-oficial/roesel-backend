from fastapi import APIRouter
from database import sb_get, sb_post, sb_patch, sb_delete
from models import Frota
from uuid import uuid4

router = APIRouter()

@router.get("/")
def listar():
    return sb_get("frotas", "order=nome.asc")

@router.post("/")
def criar(f: Frota):
    data = f.model_dump(exclude_none=True)
    data["id"] = str(uuid4())
    data["nome"] = data["nome"].upper()
    return sb_post("frotas", data)

@router.put("/{id}")
def atualizar(id: str, f: Frota):
    return sb_patch("frotas", f"id=eq.{id}", {"nome": f.nome.upper(), "descricao": f.descricao})

@router.delete("/{id}")
def excluir(id: str):
    sb_delete("frotas", f"id=eq.{id}")
    return {"ok": True}