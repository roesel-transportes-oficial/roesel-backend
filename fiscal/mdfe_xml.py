"""Monta o XML do MDF-e 3.00 (modal rodoviário) a partir dos CT-es da viagem."""
from datetime import datetime
from typing import Optional

from nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00 import Rodo
from nfelib.mdfe.bindings.v3_0.mdfe_tipos_basico_v3_00 import TendeEmi, Tmdfe
from nfelib.mdfe.bindings.v3_0.mdfe_v3_00 import Mdfe
from nfelib.mdfe.client.v3_0.servers import Endpoint
from nfelib.mdfe.client.v3_0.servers import servers as SERVIDORES_MDFE

from .chave import codigo_numerico, montar_chave
from .cte_xml import COD_UF, FUSO_BRASILIA, VERSAO_SISTEMA, _texto, dinheiro, so_digitos
from .modelos import DadosFiscaisCte, DadosFiscaisMdfe

VERSAO = "3.00"
MODELO = "58"

I = Tmdfe.InfMdfe


class ErroMdfe(ValueError):
    pass


def _placa(p: str) -> str:
    return "".join(c for c in (p or "").upper() if c.isalnum())


def _peso_kg(d: DadosFiscaisCte) -> float:
    total = 0.0
    for q in d.carga.quantidades:
        if q.unidade == "01":
            total += q.quantidade
        elif q.unidade == "02":
            total += q.quantidade * 1000
    return total


def _tomador(d: DadosFiscaisCte):
    return {0: d.remetente, 1: d.expedidor, 2: d.recebedor, 3: d.destinatario, 4: d.outro_tomador}.get(d.tomador)


def montar_mdfe(
    dados: DadosFiscaisMdfe,
    ctes: list[dict],
    emitente: dict,
    numero: int,
    serie: int,
    tp_amb: str = "2",
    tp_emis: str = "1",
) -> Mdfe:
    """ctes: registros da tabela ctes (já autorizados), com chave_acesso e dados_fiscais."""
    if not ctes:
        raise ErroMdfe("Escolha pelo menos um CT-e autorizado.")
    docs = []
    for c in ctes:
        if not c.get("chave_acesso") or not c.get("dados_fiscais"):
            raise ErroMdfe(f"CT-e {c.get('numero_cte') or c.get('id')} sem chave ou sem dados fiscais.")
        docs.append((c["chave_acesso"], DadosFiscaisCte.model_validate(c["dados_fiscais"])))

    ufs_ini = {d.inicio.uf for _, d in docs}
    ufs_fim = {d.fim.uf for _, d in docs}
    if len(ufs_ini) > 1:
        raise ErroMdfe("Os CT-es começam em estados diferentes. Faça um MDF-e para cada estado de carregamento.")
    if len(ufs_fim) > 1:
        raise ErroMdfe("Os CT-es terminam em estados diferentes. Faça um MDF-e para cada estado de descarga.")
    uf_ini, uf_fim = ufs_ini.pop(), ufs_fim.pop()

    cuf = COD_UF[emitente["uf"]]
    agora = datetime.now(FUSO_BRASILIA)
    codigo = codigo_numerico(numero)
    cnpj = so_digitos(emitente["cnpj"])
    chave = montar_chave(cuf, agora.strftime("%y%m"), cnpj, MODELO, serie, numero, tp_emis, codigo)

    # Cidades de carregamento (sem repetir, na ordem dos CT-es)
    carrega, vistos = [], set()
    for _, d in docs:
        if d.inicio.cod not in vistos:
            vistos.add(d.inicio.cod)
            carrega.append(I.Ide.InfMunCarrega(cMunCarrega=d.inicio.cod, xMunCarrega=_texto(d.inicio.nome, 60)))

    percurso = [u for u in dados.percurso if u not in (uf_ini, uf_fim)]
    ide = I.Ide(
        cUF=cuf, tpAmb=tp_amb, tpEmit="1", mod=MODELO, serie=str(serie), nMDF=str(numero),
        cMDF=codigo, cDV=chave[-1], modal="1", dhEmi=agora.isoformat(timespec="seconds"),
        tpEmis=tp_emis, procEmi="0", verProc=VERSAO_SISTEMA, UFIni=uf_ini, UFFim=uf_fim,
        infMunCarrega=carrega,
        infPercurso=[I.Ide.InfPercurso(UFPer=u) for u in percurso],
    )

    emit = I.Emit(
        CNPJ=cnpj, IE=so_digitos(emitente["ie"]),
        xNome=_texto(emitente["razao_social"], 60), xFant=_texto(emitente.get("nome_fantasia"), 60),
        enderEmit=TendeEmi(
            xLgr=_texto(emitente["logradouro"], 60), nro=_texto(emitente.get("numero"), 60) or "S/N",
            xCpl=_texto(emitente.get("complemento"), 60), xBairro=_texto(emitente["bairro"], 60),
            cMun=emitente["cod_municipio"], xMun=_texto(emitente["municipio"], 60),
            CEP=so_digitos(emitente.get("cep")) or None, UF=emitente["uf"],
            fone=so_digitos(emitente.get("fone")) or None,
        ),
    )

    # Cidades de descarga, cada uma com os seus CT-es
    descargas: dict[str, I.InfDoc.InfMunDescarga] = {}
    for ch, d in docs:
        m = descargas.get(d.fim.cod)
        if not m:
            m = descargas[d.fim.cod] = I.InfDoc.InfMunDescarga(cMunDescarga=d.fim.cod, xMunDescarga=_texto(d.fim.nome, 60))
        m.infCTe.append(I.InfDoc.InfMunDescarga.InfCte(chCTe=ch))

    # Seguro: o mesmo dos CT-es (sem repetir apólice)
    segs, apolices = [], set()
    for _, d in docs:
        s = d.seguro
        if not s or s.apolice in apolices:
            continue
        apolices.add(s.apolice)
        resp_doc = so_digitos(s.responsavel_cnpj) if s.responsavel == 2 else cnpj
        segs.append(I.Seg(
            infResp=I.Seg.InfResp(
                respSeg=str(s.responsavel),
                CNPJ=resp_doc if len(resp_doc) == 14 else None,
                CPF=resp_doc if len(resp_doc) == 11 else None,
            ),
            infSeg=I.Seg.InfSeg(xSeg=_texto(s.seguradora, 30), CNPJ=so_digitos(s.seguradora_cnpj) or None),
            nApol=_texto(s.apolice, 20),
            nAver=[_texto(a, 40) for a in s.averbacoes if a],
        ))
    if not segs:
        raise ErroMdfe("Os CT-es não têm seguro preenchido. Corrija o CT-e (campo Seguro da carga).")

    # Produto predominante: do primeiro CT-e
    d0 = docs[0][1]
    ncm = next((so_digitos(p.ncm) for _, d in docs for p in d.carga.produtos if p.ncm), None)
    lotacao = None
    if len(docs) == 1:
        # Com um documento só, a SEFAZ exige o CEP de carga e de descarga
        orig = d0.expedidor or d0.remetente
        dest = d0.recebedor or d0.destinatario
        cep_ori, cep_dest = so_digitos(orig.endereco.cep), so_digitos(dest.endereco.cep)
        if len(cep_ori) != 8 or len(cep_dest) != 8:
            raise ErroMdfe("Com um CT-e só, o MDF-e precisa do CEP do remetente e do destinatário. Preencha no CT-e.")
        P = I.ProdPred.InfLotacao
        lotacao = P(infLocalCarrega=P.InfLocalCarrega(CEP=cep_ori), infLocalDescarrega=P.InfLocalDescarrega(CEP=cep_dest))
    prod = I.ProdPred(tpCarga=dados.tipo_carga, xProd=_texto(d0.carga.produto_predominante, 120), NCM=ncm, infLotacao=lotacao)

    tot = I.Tot(
        qCTe=str(len(docs)),
        vCarga=dinheiro(sum(d.carga.valor for _, d in docs)),
        cUnid="01",
        qCarga=f"{sum(_peso_kg(d) for _, d in docs):.4f}",
    )

    # Contratantes = quem paga o frete de cada CT-e
    contratantes, docs_vistos = [], set()
    for _, d in docs:
        t = _tomador(d)
        doc = so_digitos(t.cnpj) or so_digitos(t.cpf) if t else ""
        if not t or not doc or doc in docs_vistos:
            continue
        docs_vistos.add(doc)
        contratantes.append(Rodo.InfAntt.InfContratante(
            xNome=_texto(t.nome, 60),
            CNPJ=doc if len(doc) == 14 else None, CPF=doc if len(doc) == 11 else None,
        ))

    v = dados.veiculo
    rodo = Rodo(
        infANTT=Rodo.InfAntt(
            RNTRC=so_digitos(emitente["rntrc"]).zfill(8)[-8:],
            infCIOT=[
                Rodo.InfAntt.InfCiot(
                    CIOT=so_digitos(c.numero),
                    CNPJ=so_digitos(c.cnpj_cpf) if len(so_digitos(c.cnpj_cpf)) == 14 else None,
                    CPF=so_digitos(c.cnpj_cpf) if len(so_digitos(c.cnpj_cpf)) == 11 else None,
                ) for c in dados.ciots
            ],
            infContratante=contratantes,
        ),
        veicTracao=Rodo.VeicTracao(
            placa=_placa(v.placa), RENAVAM=so_digitos(v.renavam) or None, tara=str(v.tara),
            capKG=str(v.cap_kg) if v.cap_kg else None,
            condutor=[Rodo.VeicTracao.Condutor(xNome=_texto(c.nome, 60), CPF=so_digitos(c.cpf)) for c in dados.condutores],
            tpRod=v.tp_rod, tpCar=v.tp_car, UF=v.uf,
        ),
        veicReboque=[
            Rodo.VeicReboque(
                placa=_placa(r.placa), RENAVAM=so_digitos(r.renavam) or None, tara=str(r.tara),
                capKG=str(r.cap_kg), tpCar=r.tp_car, UF=r.uf,
            ) for r in dados.reboques
        ],
    )

    inf = I(
        versao=VERSAO, Id=f"MDFe{chave}",
        ide=ide, emit=emit,
        infModal=I.InfModal(versaoModal=VERSAO, any_element=rodo),
        infDoc=I.InfDoc(infMunDescarga=list(descargas.values())),
        seg=segs, prodPred=prod, tot=tot,
        infAdic=I.InfAdic(infCpl=_texto(dados.observacoes, 5000)) if dados.observacoes else None,
    )
    s = SERVIDORES_MDFE["SVRS"]
    url = (s["prod_endpoints"] if tp_amb == "1" else s["dev_endpoints"])[Endpoint.QRCODE]
    return Mdfe(
        infMDFe=inf,
        infMDFeSupl=Tmdfe.InfMdfeSupl(qrCodMDFe=f"{url}?chMDFe={chave}&tpAmb={tp_amb}"),
    )


def municipio_encerramento(ctes: list[dict]) -> tuple[str, str]:
    """UF e código IBGE da última cidade de descarga (onde o MDF-e é encerrado)."""
    d = DadosFiscaisCte.model_validate(ctes[-1]["dados_fiscais"])
    return d.fim.uf, d.fim.cod
