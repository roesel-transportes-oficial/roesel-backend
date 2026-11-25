"""Monta o XML do CT-e 4.00 (modal rodoviário) a partir dos dados do sistema."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from nfelib.cte.bindings.v4_0.cte_modal_rodoviario_v4_00 import Rodo
from nfelib.cte.bindings.v4_0.cte_tipos_basico_v4_00 import (
    TendeEmi,
    Tendereco,
    Timp,
    Tcte,
)
from nfelib.cte.bindings.v4_0.cte_v4_00 import Cte
from nfelib.cte.bindings.v4_0.dfe_tipos_basicos_v1_00 import Tcibs, TtribCte
from nfelib.cte.client.v4_0.servers import Endpoint
from nfelib.cte.client.v4_0.servers import servers as SERVIDORES_CTE

from .chave import codigo_numerico, montar_chave
from .modelos import DadosFiscaisCte, Participante

FUSO_BRASILIA = timezone(timedelta(hours=-3))
VERSAO = "4.00"
MODELO = "57"
VERSAO_SISTEMA = "ROESEL-1.0"

COD_UF = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
    "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
    "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53",
}


def so_digitos(v: Optional[str]) -> str:
    return "".join(c for c in (v or "") if c.isdigit())


def dinheiro(v: float) -> str:
    return f"{v:.2f}"


def percentual(v: float) -> str:
    return f"{v:.2f}"


def _texto(v: Optional[str], limite: int) -> Optional[str]:
    if not v:
        return None
    return " ".join(v.split())[:limite]


def _endereco(e) -> Tendereco:
    return Tendereco(
        xLgr=_texto(e.logradouro, 255), nro=_texto(e.numero, 60) or "S/N",
        xCpl=_texto(e.complemento, 60), xBairro=_texto(e.bairro, 60),
        cMun=e.cod_municipio, xMun=_texto(e.municipio, 60),
        CEP=so_digitos(e.cep) or None, UF=e.uf,
    )


def _participante(cls, p: Participante, campo_endereco: str, tp_amb: str):
    nome = p.nome
    if tp_amb == "2":
        # Regra da SEFAZ: em homologação o nome tem que ser este.
        nome = "CTE EMITIDO EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    kwargs = dict(
        CNPJ=so_digitos(p.cnpj) or None,
        CPF=None if p.cnpj else (so_digitos(p.cpf) or None),
        IE=(p.ie.strip().upper() if p.ie and p.ie.strip().upper() == "ISENTO" else so_digitos(p.ie) or None),
        xNome=_texto(nome, 60),
        fone=so_digitos(p.fone) or None,
        email=p.email or None,
    )
    kwargs[campo_endereco] = _endereco(p.endereco)
    return cls(**kwargs)


def _icms(d: DadosFiscaisCte) -> Timp:
    i = d.icms
    if i.cst == "00":
        return Timp(ICMS00=Timp.Icms00(CST="00", vBC=dinheiro(i.base), pICMS=percentual(i.aliquota), vICMS=dinheiro(i.valor)))
    if i.cst == "20":
        return Timp(ICMS20=Timp.Icms20(CST="20", pRedBC=percentual(i.reducao_base), vBC=dinheiro(i.base), pICMS=percentual(i.aliquota), vICMS=dinheiro(i.valor)))
    if i.cst in ("40", "41", "51"):
        return Timp(ICMS45=Timp.Icms45(CST=i.cst))
    if i.cst == "90":
        return Timp(ICMS90=Timp.Icms90(CST="90", pRedBC=percentual(i.reducao_base) if i.reducao_base else None, vBC=dinheiro(i.base), pICMS=percentual(i.aliquota), vICMS=dinheiro(i.valor), vCred="0.00"))
    if i.cst == "SN":
        return Timp(ICMSSN=Timp.Icmssn(CST="90", indSN="1"))
    raise ValueError(f"CST de ICMS não suportado: {i.cst}")


def _ibscbs(d: DadosFiscaisCte) -> Optional[TtribCte]:
    t = d.ibscbs
    if not t:
        return None
    if t.cst.startswith("4"):
        # imunidade / não incidência: só CST e classificação, sem valores
        return TtribCte(CST=t.cst, cClassTrib=t.cclass_trib)
    base = t.base if t.base is not None else d.valor_prestacao
    v_uf = round(base * t.p_ibs_uf / 100, 2)
    v_mun = round(base * t.p_ibs_mun / 100, 2)
    v_cbs = round(base * t.p_cbs / 100, 2)
    return TtribCte(
        CST=t.cst,
        cClassTrib=t.cclass_trib,
        gIBSCBS=Tcibs(
            vBC=dinheiro(base),
            gIBSUF=Tcibs.GIbsuf(pIBSUF=f"{t.p_ibs_uf:.4f}", vIBSUF=dinheiro(v_uf)),
            gIBSMun=Tcibs.GIbsmun(pIBSMun=f"{t.p_ibs_mun:.4f}", vIBSMun=dinheiro(v_mun)),
            vIBS=dinheiro(v_uf + v_mun),
            gCBS=Tcibs.GCbs(pCBS=f"{t.p_cbs:.4f}", vCBS=dinheiro(v_cbs)),
        ),
    )


def url_qrcode(uf: str, tp_amb: str) -> str:
    chave_servidor = uf if uf in SERVIDORES_CTE else "SVRS"
    s = SERVIDORES_CTE[chave_servidor]
    endpoints = s["prod_endpoints"] if tp_amb == "1" else s["dev_endpoints"]
    return endpoints[Endpoint.QRCODE]


def montar_cte(
    dados: DadosFiscaisCte,
    emitente: dict,
    numero: int,
    serie: int,
    tp_amb: str = "2",
    tp_emis: str = "1",
    data_emissao: Optional[datetime] = None,
) -> Cte:
    """Retorna o objeto do CT-e pronto para assinar e enviar.

    `emitente` é a linha da tabela fiscal_emitente.
    """
    agora = (data_emissao or datetime.now(FUSO_BRASILIA)).astimezone(FUSO_BRASILIA).replace(microsecond=0)
    uf_emit = emitente["uf"]
    cuf = COD_UF[uf_emit]
    cnpj = so_digitos(emitente["cnpj"])
    codigo = codigo_numerico(numero)
    chave = montar_chave(cuf, agora.strftime("%y%m"), cnpj, MODELO, serie, numero, tp_emis, codigo)

    I = Tcte.InfCte
    ide = I.Ide(
        cUF=cuf, cCT=codigo, CFOP=dados.cfop, natOp=_texto(dados.natureza_operacao, 60),
        mod=MODELO, serie=str(serie), nCT=str(numero),
        dhEmi=agora.isoformat(), tpImp="1", tpEmis=tp_emis, cDV=chave[-1],
        tpAmb=tp_amb, tpCTe="0", procEmi="0", verProc=VERSAO_SISTEMA,
        cMunEnv=emitente["cod_municipio"], xMunEnv=_texto(emitente["municipio"], 60), UFEnv=uf_emit,
        modal="01", tpServ=str(dados.tipo_servico),
        cMunIni=dados.inicio.cod, xMunIni=_texto(dados.inicio.nome, 60), UFIni=dados.inicio.uf,
        cMunFim=dados.fim.cod, xMunFim=_texto(dados.fim.nome, 60), UFFim=dados.fim.uf,
        retira="1", indIEToma=_ind_ie_tomador(dados),
        toma3=I.Ide.Toma3(toma=str(dados.tomador)) if dados.tomador != 4 else None,
        toma4=_toma4(dados.outro_tomador, tp_amb) if dados.tomador == 4 else None,
    )

    emit = I.Emit(
        CNPJ=cnpj, IE=so_digitos(emitente["ie"]),
        xNome=_texto(emitente["razao_social"], 60), xFant=_texto(emitente.get("nome_fantasia"), 60),
        enderEmit=TendeEmi(
            xLgr=_texto(emitente["logradouro"], 255), nro=emitente.get("numero") or "S/N",
            xCpl=_texto(emitente.get("complemento"), 60), xBairro=_texto(emitente["bairro"], 60),
            cMun=emitente["cod_municipio"], xMun=_texto(emitente["municipio"], 60),
            CEP=so_digitos(emitente.get("cep")) or None, UF=uf_emit,
            fone=so_digitos(emitente.get("fone")) or None,
        ),
        CRT=str(emitente["crt"]),
    )

    v_prest = dados.valor_prestacao
    comps = dados.componentes or [{"nome": "FRETE", "valor": v_prest}]
    vprest = I.VPrest(
        vTPrest=dinheiro(v_prest),
        vRec=dinheiro(dados.valor_receber if dados.valor_receber is not None else v_prest),
        comp=[I.VPrest.Comp(xNome=_texto(c["nome"] if isinstance(c, dict) else c.nome, 15),
                            vComp=dinheiro(c["valor"] if isinstance(c, dict) else c.valor)) for c in comps],
    )

    imp = I.Imp(ICMS=_icms(dados), IBSCBS=_ibscbs(dados))

    N = I.InfCteNorm
    carga = N.InfCarga(
        vCarga=dinheiro(dados.carga.valor),
        proPred=_texto(dados.carga.produto_predominante, 60),
        infQ=[N.InfCarga.InfQ(cUnid=q.unidade, tpMed=_texto(q.tipo_medida, 20), qCarga=f"{q.quantidade:.4f}")
              for q in dados.carga.quantidades],
    )
    docs = N.InfDoc(infNFe=[N.InfDoc.InfNfe(chave=so_digitos(c)) for c in dados.chaves_nfe]) if dados.chaves_nfe else None
    doc_ant = None
    if dados.tipo_servico in (1, 2):
        a = dados.doc_anterior
        if not a or not a.chaves_cte:
            raise ValueError("Subcontratação e redespacho precisam da chave do CT-e da transportadora anterior.")
        E = N.DocAnt.EmiDocAnt
        doc_ant = N.DocAnt(emiDocAnt=[E(
            CNPJ=so_digitos(a.cnpj), IE=so_digitos(a.ie) or None,
            UF=a.uf if so_digitos(a.ie) else None,  # a UF só vai junto com a IE
            xNome=_texto(a.nome, 60),
            idDocAnt=[E.IdDocAnt(idDocAntEle=[E.IdDocAnt.IdDocAntEle(chCTe=so_digitos(c)) for c in a.chaves_cte])],
        )])
    modal = N.InfModal(versaoModal=VERSAO, any_element=Rodo(RNTRC=so_digitos(emitente["rntrc"])))

    # O CT-e não tem campo próprio de NCM: ele vai nas observações.
    ncms = sorted({p.ncm for p in dados.carga.produtos if p.ncm})
    seg = ""
    if dados.seguro:
        sg = dados.seguro
        resp = "TRANSPORTADORA" if sg.responsavel == 1 else "CONTRATANTE"
        seg = f"SEGURO: {sg.seguradora}"
        if sg.seguradora_cnpj:
            seg += f" CNPJ {so_digitos(sg.seguradora_cnpj)}"
        seg += f" APOLICE {sg.apolice}"
        if sg.averbacoes:
            seg += " AVERBACAO " + ", ".join(sg.averbacoes)
        seg += f" RESP. {resp}"
    obs = " ".join(x for x in [dados.observacoes or "", ("NCM: " + ", ".join(ncms)) if ncms else "", seg] if x)

    inf = I(
        versao=VERSAO, Id=f"CTe{chave}",
        ide=ide,
        compl=I.Compl(xObs=_texto(obs, 2000)) if obs else None,
        emit=emit,
        rem=_participante(I.Rem, dados.remetente, "enderReme", tp_amb),
        exped=_participante(I.Exped, dados.expedidor, "enderExped", tp_amb) if dados.expedidor else None,
        receb=_participante(I.Receb, dados.recebedor, "enderReceb", tp_amb) if dados.recebedor else None,
        dest=_participante(I.Dest, dados.destinatario, "enderDest", tp_amb),
        vPrest=vprest, imp=imp,
        infCTeNorm=N(infCarga=carga, infDoc=docs, docAnt=doc_ant, infModal=modal),
    )
    qr = f"{url_qrcode(uf_emit, tp_amb)}?chCTe={chave}&tpAmb={tp_amb}"
    return Cte(infCte=inf, infCTeSupl=Tcte.InfCteSupl(qrCodCTe=qr))


def _toma4(p: Optional[Participante], tp_amb: str):
    if p is None:
        raise ValueError("Tomador 'outro' escolhido, mas os dados dele não foram preenchidos.")
    t = _participante(Tcte.InfCte.Ide.Toma4, p, "enderToma", tp_amb)
    t.toma = "4"
    return t


def _ind_ie_tomador(d: DadosFiscaisCte) -> str:
    """1 contribuinte | 2 isento | 9 não contribuinte."""
    tomador = {0: d.remetente, 1: d.expedidor, 2: d.recebedor, 3: d.destinatario, 4: d.outro_tomador}[d.tomador]
    if tomador is None:
        raise ValueError("O tomador escolhido não foi preenchido no CT-e.")
    ie = (tomador.ie or "").strip().upper()
    if ie == "ISENTO":
        return "2"
    return "1" if so_digitos(ie) else "9"
