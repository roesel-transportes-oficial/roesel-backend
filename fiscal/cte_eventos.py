"""Eventos do CT-e: cancelamento (110111) e carta de correção (110110)."""
import os

import nfelib

from nfelib.cte.bindings.v4_0.ev_canc_cte_v4_00 import EvCancCte, EvCancCteDescEvento
from nfelib.cte.bindings.v4_0.ev_cce_cte_v4_00 import EvCceCte, EvCceCteDescEvento, EvCceCteXCondUso
from nfelib.cte.bindings.v4_0.evento_cte_v4_00 import EventoCte

from database import sb_get, sb_patch, sb_post

from .certificado import carregar_certificado
from .cte_emissao import ErroEmissao, carregar_emitente, cliente_sefaz
from .cte_xml import COD_UF, FUSO_BRASILIA, so_digitos
from .sefaz_envio import enviar_evento_cte
from .supabase_fiscal import ambiente_atual, salvar_arquivo

EVENTO_OK = {"134", "135", "136"}
XSD_EVENTO = os.path.join(os.path.dirname(nfelib.__file__), "cte", "schemas", "v4_0", "eventoCTe_v4.00.xsd")
CANCELAMENTO = "110111"
CARTA_CORRECAO = "110110"


def _cte_autorizado(cte_id: str) -> dict:
    linhas = sb_get("ctes", f"id=eq.{cte_id}&select=*")
    if not linhas:
        raise ErroEmissao("CT-e não encontrado.")
    c = linhas[0]
    if c.get("status") != "autorizado" or not c.get("protocolo"):
        raise ErroEmissao("Só dá para fazer isso com um CT-e autorizado.")
    return c


def _enviar(c: dict, tp_evento: str, seq: int, det) -> dict:
    emitente = carregar_emitente()
    amb = c.get("ambiente") or ambiente_atual()
    chave = c["chave_acesso"]
    cliente = cliente_sefaz(emitente["uf"], amb)
    inf = EventoCte.InfEvento(
        Id=f"ID{tp_evento}{chave}{seq:03d}", cOrgao=COD_UF[emitente["uf"]], tpAmb=amb,
        CNPJ=so_digitos(emitente["cnpj"]), chCTe=chave, dhEvento=cliente._timestamp(),
        tpEvento=tp_evento, nSeqEvento=str(seq),
        detEvento=EventoCte.InfEvento.DetEvento(any_element=det, versaoEvento="4.00"),
    )
    evento = EventoCte(versao="4.00", infEvento=inf)
    pfx, senha = carregar_certificado()
    assinado = evento.to_xml(pkcs12_data=pfx, pkcs12_password=senha, doc_id=inf.Id)
    erros = EventoCte.schema_validation(assinado, XSD_EVENTO)
    if erros:
        raise ErroEmissao("O evento ficou fora do padrão da SEFAZ: " + "; ".join(erros)[:500])

    ret = enviar_evento_cte(cliente, assinado)
    i = ret.infEvento
    ok = i.cStat in EVENTO_OK
    caminho = None
    if ok:
        caminho = f"cte/{amb}/eventos/{chave}-{tp_evento}-{seq:02d}.xml"
        corpo = assinado[assinado.index("?>") + 2:] if assinado.startswith("<?xml") else assinado
        salvar_arquivo(caminho, corpo.encode("utf-8"))
    sb_post("fiscal_eventos", {
        "cte_id": c["id"], "tipo": tp_evento, "sequencia": seq, "protocolo": i.nProt,
        "cstat": i.cStat, "motivo": i.xMotivo, "xml_path": caminho,
    })
    return {"ok": ok, "cStat": i.cStat, "motivo": i.xMotivo, "protocolo": i.nProt}


def cancelar_cte(cte_id: str, justificativa: str) -> dict:
    just = " ".join((justificativa or "").split())
    if not 15 <= len(just) <= 255:
        raise ErroEmissao("A justificativa precisa ter entre 15 e 255 letras.")
    c = _cte_autorizado(cte_id)
    det = EvCancCte(descEvento=EvCancCteDescEvento.CANCELAMENTO, nProt=c["protocolo"], xJust=just)
    res = _enviar(c, CANCELAMENTO, 1, det)
    if res["ok"]:
        sb_patch("ctes", f"id=eq.{cte_id}", {"status": "cancelado"})
    return res


def carta_correcao(cte_id: str, correcoes: list[dict]) -> dict:
    """correcoes: [{"grupo": "compl", "campo": "xObs", "valor": "...", "item": None}]"""
    if not correcoes:
        raise ErroEmissao("Informe pelo menos uma correção.")
    c = _cte_autorizado(cte_id)
    anteriores = sb_get("fiscal_eventos", f"cte_id=eq.{cte_id}&tipo=eq.{CARTA_CORRECAO}&cstat=in.(134,135,136)&select=sequencia")
    seq = max([int(a["sequencia"]) for a in anteriores] or [0]) + 1
    if seq > 20:
        raise ErroEmissao("Este CT-e já tem 20 cartas de correção, que é o limite.")
    infos = []
    for x in correcoes:
        grupo, campo, valor = (x.get("grupo") or "").strip(), (x.get("campo") or "").strip(), " ".join((x.get("valor") or "").split())
        if not grupo or not campo or not valor:
            raise ErroEmissao("Cada correção precisa de grupo, campo e valor novo.")
        infos.append(EvCceCte.InfCorrecao(
            grupoAlterado=grupo[:20], campoAlterado=campo[:20], valorAlterado=valor[:500],
            nroItemAlterado=str(x["item"]) if x.get("item") else None,
        ))
    det = EvCceCte(
        descEvento=EvCceCteDescEvento.CARTA_DE_CORRECAO, infCorrecao=infos,
        xCondUso=list(EvCceCteXCondUso)[1],  # texto fixo sem acentos
    )
    res = _enviar(c, CARTA_CORRECAO, seq, det)
    res["sequencia"] = seq
    return res
