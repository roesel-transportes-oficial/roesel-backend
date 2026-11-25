"""MDF-e: emitir, consultar, encerrar e cancelar (direto na SEFAZ, via SVRS)."""
from base64 import b64encode
from datetime import datetime
from xml.sax.saxutils import escape

from nfelib.mdfe.bindings.v3_0.ev_canc_mdfe_v3_00 import EvCancMdfe, EvCancMdfeDescEvento
from nfelib.mdfe.bindings.v3_0.ev_enc_mdfe_v3_00 import EvEncMdfe, EvEncMdfeDescEvento
from nfelib.mdfe.bindings.v3_0.evento_mdfe_v3_00 import EventoMdfe
from nfelib.mdfe.client.v3_0.mdfe import MdfeClient
from nfelib.mdfe.soap.v3_0.mdferecepcaoevento import MdfeRecepcaoEventoSoap12MdfeRecepcaoEvento

from database import sb_get, sb_patch, sb_post

from .certificado import carregar_certificado
from .cte_emissao import ErroEmissao, carregar_emitente
from .cte_xml import COD_UF, FUSO_BRASILIA, so_digitos
from .mdfe_xml import MODELO, ErroMdfe, montar_mdfe, municipio_encerramento
from .modelos import DadosFiscaisMdfe
from .sefaz_envio import enviar_mdfe
from .supabase_fiscal import ambiente_atual, proximo_numero, salvar_arquivo

NS = "http://www.portalfiscal.inf.br/mdfe"
AUTORIZADO = {"100"}
EVENTO_OK = {"135", "136"}


def cliente_mdfe(uf: str, ambiente: str) -> MdfeClient:
    pfx, senha = carregar_certificado()
    return MdfeClient(ambiente=ambiente, uf=COD_UF[uf], pkcs12_data=pfx, pkcs12_password=senha, timeout=30)


def _registro(mdfe_id: str) -> dict:
    linhas = sb_get("mdfes", f"id=eq.{mdfe_id}&select=*")
    if not linhas:
        raise ErroEmissao("MDF-e não encontrado.")
    return linhas[0]


def _ctes_da_viagem(registro: dict) -> list[dict]:
    ids = registro.get("cte_ids") or []
    if not ids:
        raise ErroEmissao("Escolha os CT-es da viagem antes de emitir o MDF-e.")
    linhas = sb_get("ctes", f"id=in.({','.join(ids)})&select=id,numero_cte,status,chave_acesso,dados_fiscais")
    por_id = {l["id"]: l for l in linhas}
    ctes = [por_id[i] for i in ids if i in por_id]
    pendentes = [c.get("numero_cte") or c["id"][:8] for c in ctes if c.get("status") != "autorizado"]
    if pendentes:
        raise ErroEmissao("Só entram no MDF-e CT-es autorizados. Ainda não autorizados: " + ", ".join(pendentes))
    if len(ctes) != len(ids):
        raise ErroEmissao("Algum CT-e escolhido foi apagado. Revise a lista.")
    return ctes


def _sem_declaracao(xml: str) -> str:
    return xml[xml.index("?>") + 2:].lstrip() if xml.startswith("<?xml") else xml


def _xml_protocolo(prot) -> str:
    i = prot.infProt
    dig = i.digVal
    if isinstance(dig, (bytes, bytearray)):
        dig = b64encode(dig).decode()
    campos = [
        ("tpAmb", getattr(i.tpAmb, "value", i.tpAmb)), ("verAplic", i.verAplic), ("chMDFe", i.chMDFe),
        ("dhRecbto", i.dhRecbto), ("nProt", i.nProt), ("digVal", dig), ("cStat", i.cStat), ("xMotivo", i.xMotivo),
    ]
    corpo = "".join(f"<{n}>{escape(str(v))}</{n}>" for n, v in campos if v not in (None, ""))
    id_attr = f' Id="{i.Id}"' if i.Id else ""
    return f'<protMDFe versao="{prot.versao or "3.00"}"><infProt{id_attr}>{corpo}</infProt></protMDFe>'


def emitir_mdfe(mdfe_id: str) -> dict:
    registro = _registro(mdfe_id)
    if registro.get("status") in ("autorizado", "encerrado", "cancelado"):
        raise ErroEmissao(f"Este MDF-e já está {registro['status']}.")
    if registro.get("status") == "processando":
        raise ErroEmissao("O último envio ficou sem resposta. Use 'Consultar na SEFAZ' antes de reenviar.")
    if not registro.get("dados_fiscais"):
        raise ErroEmissao("Preencha veículo e motorista antes de emitir.")

    dados = DadosFiscaisMdfe.model_validate(registro["dados_fiscais"])
    ctes = _ctes_da_viagem(registro)
    emitente = carregar_emitente()
    amb = ambiente_atual()
    serie = int(emitente.get("serie_mdfe") or 1)

    numero = registro.get("numero")
    if not numero or str(registro.get("ambiente") or "") != amb:
        numero = proximo_numero(MODELO, serie, amb)
        sb_patch("mdfes", f"id=eq.{mdfe_id}", {"numero": str(numero), "serie": serie, "ambiente": amb})
    numero = int(numero)

    try:
        mdfe = montar_mdfe(dados, ctes, emitente, numero=numero, serie=serie, tp_amb=amb)
    except ErroMdfe as e:
        raise ErroEmissao(str(e))
    chave = mdfe.infMDFe.Id[4:]
    pfx, senha = carregar_certificado()
    xml_assinado = mdfe.to_xml(pkcs12_data=pfx, pkcs12_password=senha, doc_id=mdfe.infMDFe.Id)
    erros = type(mdfe).schema_validation(xml_assinado)
    if erros:
        sb_patch("mdfes", f"id=eq.{mdfe_id}", {"status": "rejeitado", "motivo_rejeicao": "; ".join(erros)[:1000]})
        raise ErroEmissao("O XML ficou fora do padrão da SEFAZ: " + "; ".join(erros)[:500])

    sb_patch("mdfes", f"id=eq.{mdfe_id}", {"status": "processando", "chave_acesso": chave})
    ret = enviar_mdfe(cliente_mdfe(emitente["uf"], amb), xml_assinado)

    prot = ret.protMDFe.infProt if ret.protMDFe and ret.protMDFe.infProt else None
    cstat = (prot.cStat if prot else None) or ret.cStat
    motivo = (prot.xMotivo if prot else None) or ret.xMotivo

    if cstat in AUTORIZADO:
        proc = (
            f'<?xml version="1.0" encoding="UTF-8"?><mdfeProc xmlns="{NS}" versao="3.00">'
            f"{_sem_declaracao(xml_assinado)}{_xml_protocolo(ret.protMDFe)}</mdfeProc>"
        )
        caminho = f"mdfe/{amb}/{datetime.now(FUSO_BRASILIA):%Y/%m}/{chave}-procMDFe.xml"
        salvar_arquivo(caminho, proc.encode("utf-8"))
        sb_patch("mdfes", f"id=eq.{mdfe_id}", {
            "status": "autorizado", "protocolo": prot.nProt, "cstat": cstat,
            "motivo_rejeicao": "", "xml_url": caminho, "dh_autorizacao": prot.dhRecbto,
        })
        return {"status": "autorizado", "chave": chave, "numero": numero, "protocolo": prot.nProt, "motivo": motivo}

    sb_patch("mdfes", f"id=eq.{mdfe_id}", {"status": "rejeitado", "cstat": cstat, "motivo_rejeicao": f"{cstat} - {motivo}"})
    return {"status": "rejeitado", "chave": chave, "numero": numero, "cStat": cstat, "motivo": motivo}


def consultar_mdfe(mdfe_id: str) -> dict:
    r = _registro(mdfe_id)
    if not r.get("chave_acesso"):
        raise ErroEmissao("MDF-e sem chave de acesso; ainda não foi enviado.")
    emitente = carregar_emitente()
    ret = cliente_mdfe(emitente["uf"], r.get("ambiente") or ambiente_atual()).consulta_documento(r["chave_acesso"])
    return {"cStat": ret.cStat, "motivo": ret.xMotivo}


def nao_encerrados() -> dict:
    """MDF-es abertos na SEFAZ. Um aberto para o mesmo veículo e estado bloqueia o próximo."""
    emitente = carregar_emitente()
    ret = cliente_mdfe(emitente["uf"], ambiente_atual()).consulta_nao_encerrados(so_digitos(emitente["cnpj"]))
    itens = [{"chave": i.chMDFe, "protocolo": i.nProt} for i in (getattr(ret, "infMDFe", None) or [])]
    return {"cStat": ret.cStat, "motivo": ret.xMotivo, "abertos": itens}


def _enviar_evento(cliente: MdfeClient, chave: str, cnpj: str, tp_evento: str, det) -> tuple[object, str]:
    """Igual ao envia_evento da nfelib, mas devolve também o XML assinado para guardar."""
    inf = EventoMdfe.InfEvento(
        Id=f"ID{tp_evento}{chave}001", cOrgao=cliente.uf, tpAmb=cliente.ambiente, CNPJ=cnpj,
        chMDFe=chave, dhEvento=cliente._timestamp(), tpEvento=tp_evento, nSeqEvento="1",
        detEvento=EventoMdfe.InfEvento.DetEvento(any_element=det, versaoEvento="3.00"),
    )
    evento = EventoMdfe(versao="3.00", infEvento=inf)
    assinado = evento.to_xml(pkcs12_data=cliente.pkcs12_data, pkcs12_password=cliente.pkcs12_password, doc_id=inf.Id)
    ret = cliente.send(
        MdfeRecepcaoEventoSoap12MdfeRecepcaoEvento, EventoMdfe(versao="3.00"),
        placeholder_exp=r"<eventoMDFe[^>]*/>|<eventoMDFe.*?>.*?</eventoMDFe>",
        placeholder_content=assinado,
    )
    return ret, assinado


def _registrar_evento(mdfe_id: str, r: dict, tipo: str, ret, assinado: str) -> dict:
    i = ret.infEvento
    cstat, motivo = i.cStat, i.xMotivo
    caminho = None
    if cstat in EVENTO_OK:
        caminho = f"mdfe/{r.get('ambiente') or '2'}/eventos/{r['chave_acesso']}-{tipo}.xml"
        salvar_arquivo(caminho, _sem_declaracao(assinado).encode("utf-8"))
    sb_post("fiscal_eventos", {
        "mdfe_id": mdfe_id, "tipo": tipo, "sequencia": 1, "protocolo": i.nProt,
        "cstat": cstat, "motivo": motivo, "xml_path": caminho,
    })
    return {"ok": cstat in EVENTO_OK, "cStat": cstat, "motivo": motivo, "protocolo": i.nProt}


def encerrar_mdfe(mdfe_id: str) -> dict:
    r = _registro(mdfe_id)
    if r.get("status") != "autorizado":
        raise ErroEmissao("Só dá para encerrar um MDF-e autorizado.")
    uf, cod_mun = municipio_encerramento(_ctes_da_viagem(r))
    emitente = carregar_emitente()
    cliente = cliente_mdfe(emitente["uf"], r.get("ambiente") or ambiente_atual())
    det = EvEncMdfe(
        descEvento=EvEncMdfeDescEvento.ENCERRAMENTO, nProt=r["protocolo"],
        dtEnc=datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d"), cUF=COD_UF[uf], cMun=cod_mun,
    )
    ret, assinado = _enviar_evento(cliente, r["chave_acesso"], so_digitos(emitente["cnpj"]), "110112", det)
    res = _registrar_evento(mdfe_id, r, "110112", ret, assinado)
    if res["ok"]:
        sb_patch("mdfes", f"id=eq.{mdfe_id}", {"status": "encerrado", "encerrado_em": datetime.now(FUSO_BRASILIA).isoformat()})
    return res


def cancelar_mdfe(mdfe_id: str, justificativa: str) -> dict:
    just = " ".join((justificativa or "").split())
    if not 15 <= len(just) <= 255:
        raise ErroEmissao("A justificativa precisa ter entre 15 e 255 letras.")
    r = _registro(mdfe_id)
    if r.get("status") != "autorizado":
        raise ErroEmissao("Só dá para cancelar um MDF-e autorizado e ainda não encerrado.")
    emitente = carregar_emitente()
    cliente = cliente_mdfe(emitente["uf"], r.get("ambiente") or ambiente_atual())
    det = EvCancMdfe(descEvento=EvCancMdfeDescEvento.CANCELAMENTO, nProt=r["protocolo"], xJust=just)
    ret, assinado = _enviar_evento(cliente, r["chave_acesso"], so_digitos(emitente["cnpj"]), "110111", det)
    res = _registrar_evento(mdfe_id, r, "110111", ret, assinado)
    if res["ok"]:
        sb_patch("mdfes", f"id=eq.{mdfe_id}", {"status": "cancelado"})
    return res
