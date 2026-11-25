"""GNRE do ICMS do frete (Portal GNRE)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import usuario_atual
from database import sb_get, sb_patch
from fiscal.certificado import CertificadoNaoConfigurado
from fiscal.cte_emissao import ErroEmissao, carregar_emitente
from fiscal.gnre_emissao import config_uf, consultar_gnre, gerar_gnre, precisa_gnre
from fiscal.supabase_fiscal import ambiente_atual, link_temporario

router = APIRouter()


class Gerar(BaseModel):
    vencimento: Optional[str] = None   # AAAA-MM-DD; vazio = hoje
    extras: Optional[dict] = None      # campos extras que o estado pedir e o sistema não souber


def _erro(e: Exception):
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, (ErroEmissao, CertificadoNaoConfigurado)):
        raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=502, detail=f"Falha ao falar com o Portal GNRE: {type(e).__name__}: {e}")


@router.get("/")
def listar(usuario: dict = Depends(usuario_atual)):
    return sb_get("gnres", "order=created_at.desc&select=*")


# CT-es autorizados que precisam de GNRE e ainda não têm uma válida
@router.get("/pendentes")
def pendentes(usuario: dict = Depends(usuario_atual)):
    emitente = carregar_emitente()
    ctes = sb_get("ctes", "status=eq.autorizado&order=created_at.desc&select=id,numero_cte,origem,destino,remetente_nome,tomador_nome,dados_fiscais,created_at")
    com_guia = {g["cte_id"] for g in sb_get("gnres", "status=in.(processando,emitida,paga)&select=cte_id")}
    saida = []
    for c in ctes:
        if c["id"] in com_guia or not precisa_gnre(c, emitente):
            continue
        d = c["dados_fiscais"]
        saida.append({
            "id": c["id"], "numero_cte": c["numero_cte"], "origem": c["origem"], "destino": c["destino"],
            "remetente_nome": c["remetente_nome"], "tomador_nome": c["tomador_nome"],
            "uf": d["inicio"]["uf"], "valor_icms": d["icms"]["valor"], "created_at": c["created_at"],
        })
    return saida


@router.get("/regras/{uf}")
def regras(uf: str, atualizar: bool = False, usuario: dict = Depends(usuario_atual)):
    try:
        return config_uf(uf.upper(), ambiente_atual(), forcar=atualizar)
    except Exception as e:
        _erro(e)


@router.post("/cte/{cte_id}")
def gerar(cte_id: str, g: Gerar, usuario: dict = Depends(usuario_atual)):
    try:
        return gerar_gnre(cte_id, g.vencimento, g.extras)
    except Exception as e:
        _erro(e)


@router.post("/{id}/consultar")
def consultar(id: str, usuario: dict = Depends(usuario_atual)):
    try:
        return consultar_gnre(id)
    except Exception as e:
        _erro(e)


@router.post("/{id}/paga")
def marcar_paga(id: str, usuario: dict = Depends(usuario_atual)):
    linhas = sb_get("gnres", f"id=eq.{id}&select=status")
    if not linhas or linhas[0]["status"] != "emitida":
        raise HTTPException(status_code=400, detail="Só dá para marcar como paga uma guia emitida.")
    return sb_patch("gnres", f"id=eq.{id}", {"status": "paga"})


@router.get("/{id}/pdf")
def pdf(id: str, usuario: dict = Depends(usuario_atual)):
    linhas = sb_get("gnres", f"id=eq.{id}&select=pdf_path")
    if not linhas or not linhas[0].get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF da guia ainda não disponível. Clique em Consultar.")
    return {"url": link_temporario(linhas[0]["pdf_path"])}
