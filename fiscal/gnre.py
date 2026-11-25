"""GNRE do ICMS do frete, direto no Portal GNRE (webservice 2.00, sem mensalidade).

Quando é preciso: o CT-e começa em outro estado (fora de MG) e tem ICMS destacado.
O ICMS do transporte é do estado onde a prestação começa (receita 100030).

Fluxo do Portal GNRE (é em duas etapas):
1. Envia o lote (GnreLoteRecepcao) e recebe um número de recibo.
2. Alguns segundos depois consulta o resultado (GnreResultadoLote): vem a linha
   digitável, o código de barras e o PDF da guia.

Cada estado tem regras próprias (campos extras, tipo de documento de origem...).
Elas vêm do próprio portal (GnreConfigUF) e ficam guardadas por 7 dias.

A empresa precisa estar habilitada no Portal GNRE para usar o webservice
(gnre.pe.gov.br > Área restrita > Solicitar acesso ao web service, com o certificado).
"""
import json
import os
from base64 import b64decode
from datetime import datetime, timedelta
from typing import Optional
from xml.sax.saxutils import escape

import requests
from lxml import etree
from requests_pkcs12 import Pkcs12Adapter

from .certificado import carregar_certificado
from .cte_xml import FUSO_BRASILIA, so_digitos
from .modelos import DadosFiscaisCte

NS = "http://www.gnre.pe.gov.br"
RECEITA_ICMS_TRANSPORTE = "100030"

SERVIDORES = {
    "1": "https://www.gnre.pe.gov.br/gnreWS/services",
    "2": "https://www.testegnre.pe.gov.br/gnreWS/services",
}


class ErroGnre(Exception):
    pass


# ---------------------------------------------------------------- SOAP
def _sessao() -> requests.Session:
    pfx, senha = carregar_certificado()
    s = requests.Session()
    s.mount("https://", Pkcs12Adapter(pkcs12_data=pfx, pkcs12_password=senha))
    return s


def _soap(servico: str, acao: str, corpo: str, ambiente: str) -> etree._Element:
    ns_ws = f"http://www.gnre.pe.gov.br/webservice/{servico}"
    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
        f'<soap12:Header><gnreCabecMsg xmlns="{ns_ws}"><versaoDados>2.00</versaoDados></gnreCabecMsg></soap12:Header>'
        f'<soap12:Body><gnreDadosMsg xmlns="{ns_ws}">{corpo}</gnreDadosMsg></soap12:Body>'
        "</soap12:Envelope>"
    )
    r = _sessao().post(
        f"{SERVIDORES[ambiente]}/{servico}",
        data=envelope.encode("utf-8"),
        headers={"Content-Type": f'application/soap+xml; charset=utf-8; action="{ns_ws}/{acao}"'},
        timeout=40,
        verify=os.getenv("GNRE_VERIFY_SSL", "1") != "0",
    )
    if r.status_code >= 500 and b"Fault" not in r.content:
        raise ErroGnre(f"Portal GNRE fora do ar (HTTP {r.status_code}).")
    try:
        raiz = etree.fromstring(r.content)
    except etree.XMLSyntaxError:
        raise ErroGnre(f"Resposta inesperada do Portal GNRE (HTTP {r.status_code}).")
    falha = _achar(raiz, "Fault")
    if falha is not None:
        raise ErroGnre("Portal GNRE recusou a chamada: " + " ".join(falha.itertext()).strip()[:300])
    return raiz


# Busca por nome sem se preocupar com namespace (as respostas variam)
def _achar(el, nome: str):
    if el is None:
        return None
    r = el.xpath(f".//*[local-name()='{nome}']")
    return r[0] if r else None


def _todos(el, nome: str) -> list:
    return [] if el is None else el.xpath(f".//*[local-name()='{nome}']")


def _texto(el, nome: str) -> str:
    x = _achar(el, nome)
    return (x.text or "").strip() if x is not None else ""


def _sim(el, nome: str) -> bool:
    return _texto(el, nome).upper() == "S"


# ---------------------------------------------------------------- regras por estado
def consultar_config_uf(uf: str, ambiente: str, receita: str = RECEITA_ICMS_TRANSPORTE) -> dict:
    corpo = (
        f'<TConsultaConfigUf xmlns="{NS}"><ambiente>{ambiente}</ambiente><uf>{uf}</uf>'
        f'<receita courier="N">{receita}</receita></TConsultaConfigUf>'
    )
    raiz = _soap("GnreConfigUF", "consultar", corpo, ambiente)
    sit = _achar(raiz, "situacaoConsulta")
    codigo = _texto(sit, "codigo")
    if codigo and codigo != "450":
        raise ErroGnre(f"Portal GNRE ({uf}): {codigo} - {_texto(sit, 'descricao')}")
    rec = _achar(raiz, "receita")
    if rec is None:
        raise ErroGnre(f"O estado {uf} não aceita GNRE pela receita {receita}.")
    tipos_doc = [
        {"codigo": _texto(t, "codigo"), "descricao": _texto(t, "descricao")}
        for t in _todos(_achar(rec, "tiposDocumentosOrigem"), "tipoDocumentoOrigem")
    ]
    detalhes = [
        {"codigo": _texto(t, "codigo"), "descricao": _texto(t, "descricao")}
        for t in _todos(_achar(rec, "detalhamentosReceita"), "detalhamentoReceita")
    ]
    campos = [
        {
            "codigo": _texto(c, "codigo"), "tipo": _texto(c, "tipo"), "tamanho": _texto(c, "tamanho"),
            "titulo": _texto(c, "titulo"), "obrigatorio": _sim(c, "obrigatorio"),
        }
        for c in _todos(_achar(rec, "camposAdicionais"), "campoAdicional")
    ]
    return {
        "uf": uf, "receita": receita,
        "exige_detalhamento": _sim(rec, "exigeDetalhamentoReceita"),
        "detalhamentos": detalhes,
        "exige_documento_origem": _sim(rec, "exigeDocumentoOrigem"),
        "tipos_documento_origem": tipos_doc,
        "exige_destinatario": _sim(rec, "exigeContribuinteDestinatario"),
        "exige_data_vencimento": _sim(rec, "exigeDataVencimento"),
        "exige_periodo_referencia": _sim(rec, "exigePeriodoReferencia"),
        "exige_parcela": _sim(rec, "exigeParcela"),
        "exige_data_pagamento": _sim(rec, "exigeDataPagamento"),
        "campos_extras": campos,
    }


# ---------------------------------------------------------------- montar a guia
def _mun5(cod_ibge: str) -> str:
    """O Portal GNRE usa o código do município sem os 2 dígitos da UF."""
    c = so_digitos(cod_ibge)
    return c[2:] if len(c) == 7 else c


def _tomador(d: DadosFiscaisCte):
    return {0: d.remetente, 1: d.expedidor, 2: d.recebedor, 3: d.destinatario, 4: d.outro_tomador}.get(d.tomador)


def _escolher_tipo_doc(config: dict) -> Optional[dict]:
    """Prefere o tipo de documento 'chave do CT-e'; depois 'número do CT-e'."""
    tipos = config["tipos_documento_origem"]
    def tem(t, *palavras):
        desc = (t["descricao"] or "").upper().replace("-", "")
        return all(p in desc for p in palavras)
    for filtro in (("CHAVE", "CTE"), ("CTE",), ("CONHECIMENTO",)):
        for t in tipos:
            if tem(t, *filtro):
                return t
    return None


def _valor_campo_extra(campo: dict, chave: str, numero: str, data_emissao: str) -> Optional[str]:
    titulo = (campo["titulo"] or "").upper().replace("-", "")
    if "CHAVE" in titulo:
        return chave
    if "DATA" in titulo and ("EMISS" in titulo or "CTE" in titulo or "DOC" in titulo):
        return data_emissao
    if "NUMERO" in titulo.replace("Ú", "U") and "CTE" in titulo:
        return numero
    return None


def montar_lote(
    cte: dict, emitente: dict, config: dict, ambiente: str,
    vencimento: Optional[str] = None, extras_manuais: Optional[dict] = None,
) -> tuple[str, float, str]:
    """Devolve (xml do lote, valor, uf favorecida). cte = registro da tabela ctes (autorizado)."""
    d = DadosFiscaisCte.model_validate(cte["dados_fiscais"])
    uf = d.inicio.uf
    valor = round(d.icms.valor, 2)
    if valor <= 0:
        raise ErroGnre("Este CT-e não tem ICMS destacado, então não precisa de GNRE.")
    chave = cte.get("chave_acesso") or ""
    numero = str(cte.get("numero_cte") or "")
    emissao = str(cte.get("dh_autorizacao") or cte.get("created_at") or "")[:10] or datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d")
    hoje = datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d")
    venc = vencimento or hoje
    extras_manuais = extras_manuais or {}

    item = [f"<receita>{config['receita']}</receita>"]
    if config["exige_detalhamento"]:
        if not config["detalhamentos"]:
            raise ErroGnre(f"{uf} exige detalhamento da receita, mas o portal não informou as opções.")
        cod = extras_manuais.get("detalhamento") or config["detalhamentos"][0]["codigo"]
        item.append(f"<detalhamentoReceita>{escape(cod)}</detalhamentoReceita>")
    if config["exige_documento_origem"]:
        tipo = _escolher_tipo_doc(config)
        if not tipo:
            opcoes = ", ".join(f"{t['codigo']} ({t['descricao']})" for t in config["tipos_documento_origem"])
            raise ErroGnre(f"{uf} pede um documento de origem que não é CT-e: {opcoes}.")
        valor_doc = chave if "CHAVE" in tipo["descricao"].upper() else numero
        item.append(f'<documentoOrigem tipo="{escape(tipo["codigo"])}">{escape(valor_doc)}</documentoOrigem>')
    if config["exige_periodo_referencia"]:
        ano, mes = emissao[:4], emissao[5:7]
        parcela = "<parcela>1</parcela>" if config["exige_parcela"] else ""
        item.append(f"<referencia><periodo>0</periodo><mes>{mes}</mes><ano>{ano}</ano>{parcela}</referencia>")
    item.append(f"<dataVencimento>{venc}</dataVencimento>")
    item.append(f'<valor tipo="11">{valor:.2f}</valor>')
    if config["exige_destinatario"]:
        t = _tomador(d) or d.destinatario
        doc = so_digitos(t.cnpj) or so_digitos(t.cpf)
        tag = "CNPJ" if len(doc) == 14 else "CPF"
        ie = so_digitos(t.ie)
        ident = f"<IE>{ie}</IE>" if ie and t.endereco.uf == uf else f"<{tag}>{doc}</{tag}>"
        item.append(
            f"<contribuinteDestinatario><identificacao>{ident}</identificacao>"
            f"<razaoSocial>{escape(t.nome[:60])}</razaoSocial>"
            f"<municipio>{_mun5(t.endereco.cod_municipio)}</municipio></contribuinteDestinatario>"
        )
    extras, faltando = [], []
    for c in config["campos_extras"]:
        v = extras_manuais.get(c["codigo"]) or _valor_campo_extra(c, chave, numero, emissao)
        if v:
            extras.append(f"<campoExtra><codigo>{escape(c['codigo'])}</codigo><valor>{escape(v)}</valor></campoExtra>")
        elif c["obrigatorio"]:
            faltando.append(f"{c['codigo']} - {c['titulo']}")
    if faltando:
        raise ErroGnre(f"{uf} pede campos que o sistema não sabe preencher sozinho: " + "; ".join(faltando))
    if extras:
        item.append(f"<camposExtras>{''.join(extras)}</camposExtras>")

    cep = so_digitos(emitente.get("cep"))
    fone = so_digitos(emitente.get("fone"))
    endereco = f"{emitente['logradouro']}, {emitente.get('numero') or 'S/N'} - {emitente['bairro']}"
    dados = (
        f'<TDadosGNRE versao="2.00">'
        f"<ufFavorecida>{uf}</ufFavorecida><tipoGnre>0</tipoGnre>"
        f"<contribuinteEmitente><identificacao><CNPJ>{so_digitos(emitente['cnpj'])}</CNPJ></identificacao>"
        f"<razaoSocial>{escape(emitente['razao_social'][:60])}</razaoSocial>"
        f"<endereco>{escape(endereco[:60])}</endereco>"
        f"<municipio>{_mun5(emitente['cod_municipio'])}</municipio><uf>{emitente['uf']}</uf>"
        + (f"<cep>{cep}</cep>" if cep else "")
        + (f"<telefone>{fone}</telefone>" if fone else "")
        + "</contribuinteEmitente>"
        f"<itensGNRE><item>{''.join(item)}</item></itensGNRE>"
        f"<valorGNRE>{valor:.2f}</valorGNRE>"
        f"<dataPagamento>{venc}</dataPagamento>"
        "</TDadosGNRE>"
    )
    lote = f'<TLote_GNRE xmlns="{NS}" versao="2.00"><guias>{dados}</guias></TLote_GNRE>'
    return lote, valor, uf


# ---------------------------------------------------------------- envio e resultado
def enviar_lote(lote_xml: str, ambiente: str) -> str:
    raiz = _soap("GnreLoteRecepcao", "processar", lote_xml, ambiente)
    sit = _achar(raiz, "situacaoRecepcao")
    codigo, desc = _texto(sit, "codigo"), _texto(sit, "descricao")
    if codigo != "100":
        raise ErroGnre(f"Portal GNRE recusou o lote: {codigo} - {desc}")
    recibo = _texto(_achar(raiz, "recibo"), "numero")
    if not recibo:
        raise ErroGnre("O Portal GNRE não devolveu o número do recibo.")
    return recibo


def consultar_lote(recibo: str, ambiente: str) -> dict:
    corpo = (
        f'<TConsLote_GNRE xmlns="{NS}"><ambiente>{ambiente}</ambiente>'
        f"<numeroRecibo>{recibo}</numeroRecibo><incluirPDFGuias>S</incluirPDFGuias></TConsLote_GNRE>"
    )
    raiz = _soap("GnreResultadoLote", "consultar", corpo, ambiente)
    sit = _achar(raiz, "situacaoProcess")
    codigo, desc = _texto(sit, "codigo"), _texto(sit, "descricao")
    res = {"codigo": codigo, "descricao": desc, "processando": codigo in ("400", "401")}
    guia = _achar(raiz, "guia")
    if guia is not None:
        res.update({
            "situacao_guia": _texto(guia, "situacaoGuia"),
            "linha_digitavel": _texto(guia, "linhaDigitavel"),
            "codigo_barras": _texto(guia, "codigoBarras"),
            "nosso_numero": _texto(guia, "nossoNumero"),
            "motivos": [
                f"{_texto(m, 'codigo')} {_texto(m, 'descricao')}".strip()
                + (f" (campo {_texto(m, 'campo')})" if _texto(m, "campo") else "")
                for m in _todos(guia, "motivo")
            ],
        })
    pdf = _texto(raiz, "pdfGuias")
    if pdf:
        try:
            res["pdf"] = b64decode(pdf)
        except Exception:
            pass
    res["ok"] = codigo == "402" and bool(res.get("linha_digitavel") or res.get("codigo_barras"))
    return res
