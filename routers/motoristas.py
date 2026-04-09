from fastapi import APIRouter, HTTPException
from database import sb_get, sb_post, sb_patch, sb_delete
from models import Motorista
from uuid import uuid4
from urllib.parse import quote

router = APIRouter()

@router.get("/")
def listar(busca: str = ""):
    if busca:
        return sb_get("motoristas", f"nome=ilike.*{quote(busca)}*&order=nome.asc")
    return sb_get("motoristas", "order=nome.asc")

@router.post("/")
def criar(m: Motorista):
    data = m.model_dump(exclude_none=True)
    data["id"] = str(uuid4())
    data["nome"] = data["nome"].upper()
    if "vencimento_cnh" in data and data["vencimento_cnh"]:
        data["vencimento_cnh"] = str(data["vencimento_cnh"])
    if "vencimento_permissor" in data and data["vencimento_permissor"]:
        data["vencimento_permissor"] = str(data["vencimento_permissor"])
    if "vencimento_toxicologico" in data and data["vencimento_toxicologico"]:
        data["vencimento_toxicologico"] = str(data["vencimento_toxicologico"])
    return sb_post("motoristas", data)

@router.put("/{id}")
def atualizar(id: str, m: Motorista):
    existente = sb_get("motoristas", f"id=eq.{id}")
    if not existente:
        raise HTTPException(status_code=404, detail="Motorista não encontrado")
    
    nome_antigo = existente[0]["nome"]
    nome_novo = m.nome.upper()
    
    data = {
        "nome": nome_novo,
        "cpf": m.cpf,
        "rg": m.rg,
        "tipo": m.tipo,
        "ativo": m.ativo,
        "vencimento_cnh": str(m.vencimento_cnh) if m.vencimento_cnh else None,
        "vencimento_permissor": str(m.vencimento_permissor) if m.vencimento_permissor else None,
        "vencimento_toxicologico": str(m.vencimento_toxicologico) if m.vencimento_toxicologico else None,
    }
    
    result = sb_patch("motoristas", f"id=eq.{id}", data)
    
    if nome_novo != nome_antigo:
        sb_patch("contratos", f"motorista=eq.{quote(nome_antigo)}", {"motorista": nome_novo})
    
    return result

@router.delete("/{id}")
def excluir(id: str):
    sb_delete("motoristas", f"id=eq.{id}")
    return {"ok": True}