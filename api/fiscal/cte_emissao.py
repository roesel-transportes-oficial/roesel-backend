"""Fluxo completo de emissão do CT-e: monta, assina, envia, guarda."""
from datetime import datetime

from nfelib.cte.client.v4_0.cte import CteClient

from database import sb_get, sb_patch

from .certificado import carregar_certificado
from .cte_xml import COD_UF, MODELO, FUSO_BRASILIA, montar_cte
from .modelos import DadosFiscaisCte
from .sefaz_envio import enviar_cte
from .supabase_fiscal import ambiente_atual, proximo_numero, salvar_arquivo

NS_CTE = "http://www.portalfiscal.inf.br/cte"
# Códigos da SEFAZ que significam "autorizado"
AUTORIZADO = {"100", "150"}


class ErroEmissao(Exception):
    pass


def carregar_emitente() -> dict:
    linhas = sb_get("fiscal_emitente", "select=*&limit=1")
    if not linhas:
        raise ErroEmissao("Cadastre os dados da transportadora em fiscal_emitente antes de emitir.")
    return linhas[0]


def cliente_sefaz(uf: str, ambiente: str) -> CteClient:
    pfx, senha = carregar_certificado()
    return CteClient(ambiente=ambiente, uf=COD_UF[uf], pkcs12_data=pfx, pkcs12_password=senha, timeout=30)


def status_sefaz() -> dict:
    emitente = carregar_emitente()
    amb = ambiente_atual()
    ret = cliente_sefaz(emitente["uf"], amb).status_servico()
    return {"ambiente": amb, "cStat": ret.cStat, "motivo": ret.xMotivo}


def _xml_protocolo(prot) -> str:
    """Monta o <protCTe> do arquivo final com os dados que a SEFAZ devolveu."""
    from base64 import b64encode
    from xml.sax.saxutils import escape

    i = prot.infProt
    dig = i.digVal
    if isinstance(dig, (bytes, bytearray)):
        dig = b64encode(dig).decode()
    tp_amb = getattr(i.tpAmb, "value", i.tpAmb)
    campos = [
        ("tpAmb", tp_amb), ("verAplic", i.verAplic), ("chCTe", i.chCTe),
        ("dhRecbto", i.dhRecbto), ("nProt", i.nProt), ("digVal", dig),
        ("cStat", i.cStat), ("xMotivo", i.xMotivo),
    ]
    corpo = "".join(f"<{n}>{escape(str(v))}</{n}>" for n, v in campos if v not in (None, ""))
    id_attr = f' Id="{i.Id}"' if i.Id else ""
    return f'<protCTe versao="{prot.versao or "4.00"}"><infProt{id_attr}>{corpo}</infProt></protCTe>'


def _sem_declaracao(xml: str) -> str:
    if xml.startswith("<?xml"):
        return xml[xml.index("?>") + 2:].lstrip()
    return xml


def emitir_cte(cte_id: str) -> dict:
    linhas = sb_get("ctes", f"id=eq.{cte_id}&select=*")
    if not linhas:
        raise ErroEmissao("CT-e não encontrado.")
    registro = linhas[0]
    if registro.get("status") == "autorizado":
        raise ErroEmissao("Este CT-e já foi autorizado.")
    if registro.get("status") == "processando":
        # O último envio não teve resposta (queda de rede ou da SEFAZ).
        # Reenviar sem consultar pode gerar duplicidade.
        raise ErroEmissao("O último envio ficou sem resposta. Use 'Consultar na SEFAZ' antes de reenviar.")
    if not registro.get("dados_fiscais"):
        raise ErroEmissao("Preencha os dados fiscais do CT-e antes de emitir.")

    dados = DadosFiscaisCte.model_validate(registro["dados_fiscais"])
    emitente = carregar_emitente()
    amb = ambiente_atual()
    serie = int(emitente.get("serie_cte") or 1)

    # O número é reservado uma vez e reaproveitado se a SEFAZ rejeitar,
    # para não abrir buraco na numeração.
    numero = registro.get("numero_cte")
    if not numero or str(registro.get("ambiente") or "") != amb:
        numero = proximo_numero(MODELO, serie, amb)
        sb_patch("ctes", f"id=eq.{cte_id}", {"numero_cte": str(numero), "serie": serie, "ambiente": amb})
    numero = int(numero)

    cte = montar_cte(dados, emitente, numero=numero, serie=serie, tp_amb=amb)
    chave = cte.infCte.Id[3:]
    pfx, senha = carregar_certificado()
    xml_assinado = cte.to_xml(pkcs12_data=pfx, pkcs12_password=senha, doc_id=cte.infCte.Id)
    erros = type(cte).schema_validation(xml_assinado)
    if erros:
        sb_patch("ctes", f"id=eq.{cte_id}", {"status": "rejeitado", "motivo_rejeicao": "; ".join(erros)[:1000]})
        raise ErroEmissao("O XML ficou fora do padrão da SEFAZ: " + "; ".join(erros)[:500])

    sb_patch("ctes", f"id=eq.{cte_id}", {"status": "processando", "chave_acesso": chave})
    ret = enviar_cte(cliente_sefaz(emitente["uf"], amb), xml_assinado)

    prot = ret.protCTe.infProt if ret.protCTe and ret.protCTe.infProt else None
    cstat = (prot.cStat if prot else None) or ret.cStat
    motivo = (prot.xMotivo if prot else None) or ret.xMotivo

    if cstat in AUTORIZADO:
        proc = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<cteProc xmlns="{NS_CTE}" versao="4.00">'
            f"{_sem_declaracao(xml_assinado)}{_xml_protocolo(ret.protCTe)}</cteProc>"
        )
        hoje = datetime.now(FUSO_BRASILIA)
        caminho = f"cte/{amb}/{hoje:%Y/%m}/{chave}-procCTe.xml"
        salvar_arquivo(caminho, proc.encode("utf-8"))
        sb_patch("ctes", f"id=eq.{cte_id}", {
            "status": "autorizado", "protocolo": prot.nProt, "cstat": cstat,
            "motivo_rejeicao": "", "xml_url": caminho, "dh_autorizacao": prot.dhRecbto,
        })
        return {"status": "autorizado", "chave": chave, "numero": numero, "protocolo": prot.nProt, "motivo": motivo}

    sb_patch("ctes", f"id=eq.{cte_id}", {"status": "rejeitado", "cstat": cstat, "motivo_rejeicao": f"{cstat} - {motivo}"})
    return {"status": "rejeitado", "chave": chave, "numero": numero, "cStat": cstat, "motivo": motivo}


def consultar_cte(cte_id: str) -> dict:
    linhas = sb_get("ctes", f"id=eq.{cte_id}&select=chave_acesso,ambiente")
    if not linhas or not linhas[0].get("chave_acesso"):
        raise ErroEmissao("CT-e sem chave de acesso; ainda não foi enviado.")
    emitente = carregar_emitente()
    amb = linhas[0].get("ambiente") or ambiente_atual()
    ret = cliente_sefaz(emitente["uf"], amb).consulta_documento(linhas[0]["chave_acesso"])
    return {"cStat": ret.cStat, "motivo": ret.xMotivo}
