from fastapi import APIRouter, HTTPException, Depends
from database import sb_get, sb_post, sb_patch, sb_delete
from models import NotaDiversa
from auth import usuario_atual
from uuid import uuid4

router = APIRouter()

@router.get("/")
def listar(tipo: str = "", usuario: dict = Depends(usuario_atual)):
    params = "order=created_at.desc&select=*"
    if tipo:
        params += f"&tipo=eq.{tipo}"
    return sb_get("notas_diversas", params)

@router.post("/")
def criar(n: NotaDiversa, usuario: dict = Depends(usuario_atual)):
    data = n.model_dump(exclude_none=True, exclude={"id"})
    data["id"] = str(uuid4())
    if "destinatario_cnpj" in data:
        data["destinatario_cnpj"] = (data["destinatario_cnpj"] or "").replace(".", "").replace("/", "").replace("-", "")
    if "nota_fiscal_original_chave" in data:
        data["nota_fiscal_original_chave"] = (data["nota_fiscal_original_chave"] or "").replace(" ", "")
    return sb_post("notas_diversas", data)

@router.put("/{id}")
def atualizar(id: str, n: NotaDiversa, usuario: dict = Depends(usuario_atual)):
    data = n.model_dump(exclude={"id"}, exclude_none=True)
    resultado = sb_patch("notas_diversas", f"id=eq.{id}", data)
    if not resultado:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    return resultado

@router.delete("/{id}")
def excluir(id: str, usuario: dict = Depends(usuario_atual)):
    sb_delete("notas_diversas", f"id=eq.{id}")
    return {"ok": True}

# ⚠️ Mesmo caso do CT-e: emissão real depende do token do provedor.
@router.post("/{id}/emitir")
def emitir(id: str, usuario: dict = Depends(usuario_atual)):
    raise HTTPException(status_code=501, detail="Emissão ainda não configurada — falta o token do provedor.")

@router.post("/{id}/cancelar")
def cancelar(id: str, usuario: dict = Depends(usuario_atual)):
    raise HTTPException(status_code=501, detail="Cancelamento ainda não configurado — falta o token do provedor.")