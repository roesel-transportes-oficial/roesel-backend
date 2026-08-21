from fastapi import APIRouter, HTTPException, Depends
from database import sb_get, sb_post, sb_patch, sb_delete
from models import Cte
from auth import usuario_atual
from uuid import uuid4

router = APIRouter()

@router.get("/")
def listar(tipo: str = "", usuario: dict = Depends(usuario_atual)):
    params = "order=created_at.desc&select=*"
    if tipo:
        params += f"&tipo=eq.{tipo}"
    return sb_get("ctes", params)

@router.post("/")
def criar(c: Cte, usuario: dict = Depends(usuario_atual)):
    data = c.model_dump(exclude_none=True, exclude={"id"})
    data["id"] = str(uuid4())
    for campo in ("remetente_cnpj", "destinatario_cnpj", "tomador_cnpj", "redespachante_cnpj"):
        if campo in data:
            data[campo] = (data[campo] or "").replace(".", "").replace("/", "").replace("-", "")
    if "cte_anterior_chave" in data:
        data["cte_anterior_chave"] = (data["cte_anterior_chave"] or "").replace(" ", "")
    return sb_post("ctes", data)

@router.put("/{id}")
def atualizar(id: str, c: Cte, usuario: dict = Depends(usuario_atual)):
    data = c.model_dump(exclude={"id"}, exclude_none=True)
    resultado = sb_patch("ctes", f"id=eq.{id}", data)
    if not resultado:
        raise HTTPException(status_code=404, detail="CT-e não encontrado")
    return resultado

@router.delete("/{id}")
def excluir(id: str, usuario: dict = Depends(usuario_atual)):
    sb_delete("ctes", f"id=eq.{id}")
    return {"ok": True}

# ⚠️ Emissão real (integração com a SEFAZ via provedor) ainda não está
# implementada — falta o token do provedor. Quando o token existir, a
# chamada real pro provedor entra aqui, dentro do backend, nunca no
# frontend — assim a lógica fiscal fica centralizada e protegida.
@router.post("/{id}/emitir")
def emitir(id: str, usuario: dict = Depends(usuario_atual)):
    raise HTTPException(status_code=501, detail="Emissão de CT-e ainda não configurada — falta o token do provedor.")

@router.post("/{id}/cancelar")
def cancelar(id: str, usuario: dict = Depends(usuario_atual)):
    raise HTTPException(status_code=501, detail="Cancelamento de CT-e ainda não configurado — falta o token do provedor.")