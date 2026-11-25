"""GNRE: gera a guia do ICMS do frete a partir de um CT-e autorizado."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from database import sb_get, sb_patch, sb_post

from .cte_emissao import ErroEmissao, carregar_emitente
from .cte_xml import FUSO_BRASILIA
from .gnre import RECEITA_ICMS_TRANSPORTE, ErroGnre, consultar_config_uf, consultar_lote, enviar_lote, montar_lote
from .modelos import DadosFiscaisCte
from .supabase_fiscal import ambiente_atual, salvar_arquivo

DIAS_CACHE_CONFIG = 7


def config_uf(uf: str, ambiente: str, forcar: bool = False) -> dict:
    """Regras do estado no Portal GNRE, guardadas por 7 dias para não consultar toda hora."""
    if not forcar:
        linhas = sb_get("gnre_config_uf", f"uf=eq.{uf}&receita=eq.{RECEITA_ICMS_TRANSPORTE}&ambiente=eq.{ambiente}&select=*")
        if linhas:
            quando = datetime.fromisoformat(linhas[0]["atualizado_em"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - quando < timedelta(days=DIAS_CACHE_CONFIG):
                return linhas[0]["config"]
    cfg = consultar_config_uf(uf, ambiente)
    agora = datetime.now(timezone.utc).isoformat()
    if sb_get("gnre_config_uf", f"uf=eq.{uf}&receita=eq.{RECEITA_ICMS_TRANSPORTE}&ambiente=eq.{ambiente}&select=uf"):
        sb_patch("gnre_config_uf", f"uf=eq.{uf}&receita=eq.{RECEITA_ICMS_TRANSPORTE}&ambiente=eq.{ambiente}", {"config": cfg, "atualizado_em": agora})
    else:
        sb_post("gnre_config_uf", {"uf": uf, "receita": RECEITA_ICMS_TRANSPORTE, "ambiente": ambiente, "config": cfg, "atualizado_em": agora})
    return cfg


def precisa_gnre(cte: dict, emitente: dict) -> bool:
    """CT-e que começa fora do estado da Roesel e tem ICMS destacado."""
    if not cte.get("dados_fiscais"):
        return False
    d = DadosFiscaisCte.model_validate(cte["dados_fiscais"])
    return d.inicio.uf != emitente["uf"] and d.icms.valor > 0


def gerar_gnre(cte_id: str, vencimento: Optional[str] = None, extras: Optional[dict] = None) -> dict:
    linhas = sb_get("ctes", f"id=eq.{cte_id}&select=*")
    if not linhas:
        raise ErroEmissao("CT-e não encontrado.")
    cte = linhas[0]
    if cte.get("status") != "autorizado":
        raise ErroEmissao("A GNRE só pode ser gerada para um CT-e autorizado.")
    ativas = sb_get("gnres", f"cte_id=eq.{cte_id}&status=in.(processando,emitida,paga)&select=id,status")
    if ativas:
        raise ErroEmissao(f"Este CT-e já tem GNRE ({ativas[0]['status']}). Consulte a existente.")

    emitente = carregar_emitente()
    amb = ambiente_atual()
    d = DadosFiscaisCte.model_validate(cte["dados_fiscais"])
    try:
        cfg = config_uf(d.inicio.uf, amb)
        lote, valor, uf = montar_lote(cte, emitente, cfg, amb, vencimento, extras)
    except ErroGnre as e:
        raise ErroEmissao(str(e))

    registro = sb_post("gnres", {
        "cte_id": cte_id, "numero_cte": cte.get("numero_cte"), "uf_favorecida": uf,
        "receita": RECEITA_ICMS_TRANSPORTE, "valor": valor, "ambiente": amb,
        "data_vencimento": vencimento or datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d"),
        "status": "processando",
    })[0]
    hoje = datetime.now(FUSO_BRASILIA)
    caminho_lote = f"gnre/{amb}/{hoje:%Y/%m}/{registro['id']}-lote.xml"
    salvar_arquivo(caminho_lote, lote.encode("utf-8"))
    try:
        recibo = enviar_lote(lote, amb)
    except ErroGnre as e:
        sb_patch("gnres", f"id=eq.{registro['id']}", {"status": "rejeitada", "motivo": str(e)[:1000], "xml_path": caminho_lote})
        raise ErroEmissao(str(e))
    sb_patch("gnres", f"id=eq.{registro['id']}", {"recibo": recibo, "xml_path": caminho_lote})
    # O portal costuma levar alguns segundos; a tela chama "consultar" em seguida.
    return {"id": registro["id"], "status": "processando", "recibo": recibo, "valor": valor, "uf": uf}


def consultar_gnre(gnre_id: str) -> dict:
    linhas = sb_get("gnres", f"id=eq.{gnre_id}&select=*")
    if not linhas:
        raise ErroEmissao("GNRE não encontrada.")
    g = linhas[0]
    if not g.get("recibo"):
        raise ErroEmissao("Esta GNRE não chegou a ser enviada ao portal.")
    try:
        res = consultar_lote(g["recibo"], g.get("ambiente") or ambiente_atual())
    except ErroGnre as e:
        raise ErroEmissao(str(e))
    if res["processando"]:
        return {"status": "processando", "motivo": res["descricao"]}
    if res["ok"]:
        dados = {
            "status": "emitida", "linha_digitavel": res.get("linha_digitavel"),
            "codigo_barras": res.get("codigo_barras"), "nosso_numero": res.get("nosso_numero"), "motivo": "",
        }
        if res.get("pdf"):
            hoje = datetime.now(FUSO_BRASILIA)
            caminho = f"gnre/{g.get('ambiente') or '2'}/{hoje:%Y/%m}/{g['id']}-guia.pdf"
            salvar_arquivo(caminho, res["pdf"], "application/pdf")
            dados["pdf_path"] = caminho
        sb_patch("gnres", f"id=eq.{gnre_id}", dados)
        return {"status": "emitida", "linha_digitavel": dados["linha_digitavel"], "tem_pdf": bool(res.get("pdf"))}
    motivo = "; ".join(res.get("motivos") or []) or f"{res['codigo']} - {res['descricao']}"
    sb_patch("gnres", f"id=eq.{gnre_id}", {"status": "rejeitada", "motivo": motivo[:1000]})
    return {"status": "rejeitada", "motivo": motivo}
