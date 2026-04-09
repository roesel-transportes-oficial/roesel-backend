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
    for campo in ["vencimento_cnh", "vencimento_permissao", "vencimento_toxicologico", "vencimento_periodico"]:
        if campo in data and data[campo]:
            data[campo] = str(data[campo])
    if "caminhao_id" in data:
        data["caminhao_id"] = str(data["caminhao_id"])
    if "substituto_id" in data:
        data["substituto_id"] = str(data["substituto_id"])
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
        "adiantamento": m.adiantamento,
        "dt_desligamento": str(m.dt_desligamento) if m.dt_desligamento else None,
        "vencimento_cnh": str(m.vencimento_cnh) if m.vencimento_cnh else None,
        "vencimento_permisso": str(m.vencimento_permisso) if m.vencimento_permisso else None,
        "vencimento_toxicologico": str(m.vencimento_toxicologico) if m.vencimento_toxicologico else None,
        "vencimento_periodico": str(m.vencimento_periodico) if m.vencimento_periodico else None,
        "caminhao_id": str(m.caminhao_id) if m.caminhao_id else None,
        "de_ferias": m.de_ferias,
        "ferias_inicio": m.ferias_inicio,
        "ferias_fim": m.ferias_fim,
        "substituto_id": str(m.substituto_id) if m.substituto_id else None,
    }

    result = sb_patch("motoristas", f"id=eq.{id}", data)

    if nome_novo != nome_antigo:
        sb_patch("contratos", f"motorista=eq.{quote(nome_antigo)}", {"motorista": nome_novo})

    return result

@router.delete("/{id}")
def excluir(id: str):
    sb_delete("motoristas", f"id=eq.{id}")
    return {"ok": True}