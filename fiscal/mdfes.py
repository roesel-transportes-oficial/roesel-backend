"""MDF-e: rascunho, emissão, encerramento e cancelamento direto na SEFAZ."""
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import usuario_atual
from database import sb_delete, sb_get, sb_patch, sb_post
from fiscal.certificado import CertificadoNaoConfigurado
from fiscal.cte_emissao import ErroEmissao
from fiscal.mdfe_emissao import cancelar_mdfe, consultar_mdfe, emitir_mdfe, encerrar_mdfe, nao_encerrados
from fiscal.supabase_fiscal import link_temporario

router = APIRouter()


class Mdfe(BaseModel):
    placa: Optional[str] = None
    motorista: Optional[str] = None
    cte_ids: Optional[list[str]] = None
    uf_ini: Optional[str] = None
    uf_fim: Optional[str] = None
    obs: Optional[str] = None
    dados_fiscais: Optional[dict] = None


class Veiculo(BaseModel):
    renavam: Optional[str] = None
    tara: Optional[int] = None
    cap_kg: Optional[int] = None
    tp_rod: Optional[str] = None
    tp_car: Optional[str] = None
    uf: Optional[str] = None


class Cancelamento(BaseModel):
    justificativa: str


def _erro_fiscal(e: Exception):
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, (ErroEmissao, CertificadoNaoConfigurado)):
        raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=502, detail=f"Falha ao falar com a SEFAZ: {type(e).__name__}: {e}")


def _placa(p: str) -> str:
    return "".join(c for c in (p or "").upper() if c.isalnum())


# Rotas fixas antes das rotas com {id}
@router.get("/fiscal/nao-encerrados")
def abertos(usuario: dict = Depends(usuario_atual)):
    try:
        return nao_encerrados()
    except Exception as e:
        _erro_fiscal(e)


# Dados do veículo que o MDF-e pede (tara, RENAVAM...). Ficam guardados por placa.
@router.get("/fiscal/veiculos/{placa}")
def veiculo(placa: str, usuario: dict = Depends(usuario_atual)):
    linhas = sb_get("fiscal_veiculos", f"placa=eq.{_placa(placa)}&select=*")
    return linhas[0] if linhas else {}


@router.put("/fiscal/veiculos/{placa}")
def salvar_veiculo(placa: str, v: Veiculo, usuario: dict = Depends(usuario_atual)):
    p = _placa(placa)
    data = v.model_dump(exclude_none=True)
    if sb_get("fiscal_veiculos", f"placa=eq.{p}&select=placa"):
        return sb_patch("fiscal_veiculos", f"placa=eq.{p}", data)
    return sb_post("fiscal_veiculos", {"placa": p, **data})


@router.get("/")
def listar(usuario: dict = Depends(usuario_atual)):
    return sb_get("mdfes", "order=created_at.desc&select=*")


@router.post("/")
def criar(m: Mdfe, usuario: dict = Depends(usuario_atual)):
    data = m.model_dump(exclude_none=True)
    data["id"] = str(uuid4())
    data["status"] = "rascunho"
    return sb_post("mdfes", data)


@router.put("/{id}")
def atualizar(id: str, m: Mdfe, usuario: dict = Depends(usuario_atual)):
    atual = sb_get("mdfes", f"id=eq.{id}&select=status")
    if not atual:
        raise HTTPException(status_code=404, detail="MDF-e não encontrado")
    if atual[0]["status"] not in ("rascunho", "rejeitado"):
        raise HTTPException(status_code=400, detail="MDF-e já enviado não pode ser alterado.")
    return sb_patch("mdfes", f"id=eq.{id}", m.model_dump(exclude_unset=True, exclude_none=True))


@router.delete("/{id}")
def excluir(id: str, usuario: dict = Depends(usuario_atual)):
    atual = sb_get("mdfes", f"id=eq.{id}&select=status")
    if atual and atual[0]["status"] not in ("rascunho", "rejeitado"):
        raise HTTPException(status_code=400, detail="Só dá para apagar rascunho ou rejeitado.")
    sb_delete("mdfes", f"id=eq.{id}")
    return {"ok": True}


@router.post("/{id}/emitir")
def emitir(id: str, usuario: dict = Depends(usuario_atual)):
    try:
        return emitir_mdfe(id)
    except Exception as e:
        _erro_fiscal(e)


@router.post("/{id}/consultar")
def consultar(id: str, usuario: dict = Depends(usuario_atual)):
    try:
        return consultar_mdfe(id)
    except Exception as e:
        _erro_fiscal(e)


@router.post("/{id}/encerrar")
def encerrar(id: str, usuario: dict = Depends(usuario_atual)):
    try:
        return encerrar_mdfe(id)
    except Exception as e:
        _erro_fiscal(e)


@router.post("/{id}/cancelar")
def cancelar(id: str, c: Cancelamento, usuario: dict = Depends(usuario_atual)):
    try:
        return cancelar_mdfe(id, c.justificativa)
    except Exception as e:
        _erro_fiscal(e)


@router.get("/{id}/xml")
def baixar_xml(id: str, usuario: dict = Depends(usuario_atual)):
    linhas = sb_get("mdfes", f"id=eq.{id}&select=xml_url")
    if not linhas or not linhas[0].get("xml_url"):
        raise HTTPException(status_code=404, detail="XML ainda não disponível.")
    return {"url": link_temporario(linhas[0]["xml_url"])}
