"""PDF do CT-e (DACTE) e do MDF-e (DAMDFE), gerados a partir do XML autorizado."""
from database import sb_get, sb_patch

from .cte_emissao import ErroEmissao
from .supabase_fiscal import baixar_arquivo, link_temporario, salvar_arquivo


def _pdf(tabela: str, registro_id: str, gerar) -> str:
    linhas = sb_get(tabela, f"id=eq.{registro_id}&select=xml_url,status")
    if not linhas or not linhas[0].get("xml_url"):
        raise ErroEmissao("O documento ainda não foi autorizado, então não tem PDF.")
    xml_path = linhas[0]["xml_url"]
    pdf_path = xml_path.rsplit(".", 1)[0] + ".pdf"
    xml = baixar_arquivo(xml_path).decode("utf-8")
    pdf = bytes(gerar(xml))
    salvar_arquivo(pdf_path, pdf, "application/pdf")
    return link_temporario(pdf_path)


def _dacte(xml: str) -> bytes:
    from brazilfiscalreport.dacte import Dacte
    return Dacte(xml=xml).output()


def _damdfe(xml: str) -> bytes:
    from brazilfiscalreport.damdfe import Damdfe
    return Damdfe(xml=xml).output()


def link_dacte(cte_id: str) -> str:
    url = _pdf("ctes", cte_id, _dacte)
    sb_patch("ctes", f"id=eq.{cte_id}", {"dacte_url": "gerado"})
    return url


def link_damdfe(mdfe_id: str) -> str:
    return _pdf("mdfes", mdfe_id, _damdfe)
