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
    # exclude_unset: só grava o que a tela mandou. Antes, os campos com
    # valor padrão ("" / "rascunho") apagavam número, chave e status do CT-e.
    data = c.model_dump(exclude={"id"}, exclude_unset=True, exclude_none=True)
    for campo in ("status", "numero_cte", "chave_acesso", "protocolo", "xml_url"):
        data.pop(campo, None)  # esses só o próprio backend muda, na emissão
    resultado = sb_patch("ctes", f"id=eq.{id}", data)
    if not resultado:
        raise HTTPException(status_code=404, detail="CT-e não encontrado")
    return resultado

@router.delete("/{id}")
def excluir(id: str, usuario: dict = Depends(usuario_atual)):
    sb_delete("ctes", f"id=eq.{id}")
    return {"ok": True}

# Emissão direta na SEFAZ (sem provedor pago). A lógica fica em fiscal/.
# O ambiente (homologação ou produção) vem da variável FISCAL_AMBIENTE.
from fiscal.certificado import CertificadoNaoConfigurado, info_certificado
from fiscal.cte_emissao import ErroEmissao, consultar_cte, emitir_cte, status_sefaz
from fiscal.supabase_fiscal import link_temporario
from fiscal.cte_eventos import cancelar_cte, carta_correcao
from fiscal.pdfs import link_dacte
from pydantic import BaseModel
from typing import Optional


def _erro_fiscal(e: Exception):
    if isinstance(e, (ErroEmissao, CertificadoNaoConfigurado)):
        raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=502, detail=f"Falha ao falar com a SEFAZ: {type(e).__name__}: {e}")


@router.get("/fiscal/status-sefaz")
def sefaz_status(usuario: dict = Depends(usuario_atual)):
    try:
        return status_sefaz()
    except Exception as e:
        _erro_fiscal(e)


@router.get("/fiscal/certificado")
def certificado(usuario: dict = Depends(usuario_atual)):
    try:
        return info_certificado()
    except Exception as e:
        _erro_fiscal(e)


@router.post("/{id}/emitir")
def emitir(id: str, usuario: dict = Depends(usuario_atual)):
    try:
        return emitir_cte(id)
    except Exception as e:
        _erro_fiscal(e)


@router.post("/{id}/consultar")
def consultar(id: str, usuario: dict = Depends(usuario_atual)):
    try:
        return consultar_cte(id)
    except Exception as e:
        _erro_fiscal(e)


@router.get("/{id}/xml")
def baixar_xml(id: str, usuario: dict = Depends(usuario_atual)):
    linhas = sb_get("ctes", f"id=eq.{id}&select=xml_url")
    if not linhas or not linhas[0].get("xml_url"):
        raise HTTPException(status_code=404, detail="XML ainda não disponível.")
    return {"url": link_temporario(linhas[0]["xml_url"])}


class Cancelamento(BaseModel):
    justificativa: str


class Correcao(BaseModel):
    grupo: str
    campo: str
    valor: str
    item: Optional[int] = None


class CartaCorrecao(BaseModel):
    correcoes: list[Correcao]


@router.post("/{id}/cancelar")
def cancelar(id: str, c: Cancelamento, usuario: dict = Depends(usuario_atual)):
    try:
        return cancelar_cte(id, c.justificativa)
    except Exception as e:
        _erro_fiscal(e)


@router.post("/{id}/carta-correcao")
def corrigir(id: str, c: CartaCorrecao, usuario: dict = Depends(usuario_atual)):
    try:
        return carta_correcao(id, [x.model_dump() for x in c.correcoes])
    except Exception as e:
        _erro_fiscal(e)


@router.get("/{id}/eventos")
def eventos(id: str, usuario: dict = Depends(usuario_atual)):
    return sb_get("fiscal_eventos", f"cte_id=eq.{id}&order=created_at.desc&select=*")


@router.get("/{id}/dacte")
def dacte(id: str, usuario: dict = Depends(usuario_atual)):
    try:
        return {"url": link_dacte(id)}
    except Exception as e:
        _erro_fiscal(e)
