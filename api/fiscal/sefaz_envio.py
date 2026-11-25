"""Envio à SEFAZ do jeito que o leiaute pede.

CT-e 4.00 (CTeRecepcaoSincV4) e MDF-e 3.00 (MDFeRecepcaoSinc) exigem o XML
compactado em GZip e codificado em Base64 dentro da mensagem. Sem isso a SEFAZ
devolve "244 - Falha na descompactação da área de dados".
Os eventos (cancelamento, carta de correção, encerramento) vão sem compactar.
"""
import base64
import gzip

from brazil_fiscal_client.fiscal_client import FiscalClient
from nfelib.cte.bindings.v4_0.evento_cte_v4_00 import EventoCte
from nfelib.cte.client.v4_0.cte import CteClient
from nfelib.cte.client.v4_0.servers import Endpoint as EndpointCte
from nfelib.cte.soap.v4_0.cterecepcaoeventov4 import CteRecepcaoEventoV4Soap12CteRecepcaoEvento
from nfelib.cte.soap.v4_0.cterecepcaosincv4 import CteRecepcaoSincV4Soap12CteRecepcao
from nfelib.mdfe.client.v3_0.mdfe import MdfeClient
from nfelib.mdfe.client.v3_0.servers import Endpoint as EndpointMdfe
from nfelib.mdfe.soap.v3_0.mdferecepcaosinc import MdfeRecepcaoSincSoap12MdfeRecepcao


def _gzip_b64(xml: str) -> str:
    return base64.b64encode(gzip.compress(xml.encode("utf-8"))).decode("ascii")


def enviar_cte(cliente: CteClient, xml_assinado: str):
    resp = FiscalClient.send(
        cliente,
        action_class=CteRecepcaoSincV4Soap12CteRecepcao,
        location=cliente._get_location(EndpointCte.CTERECEPCAOSINCV4),
        wrapped_obj={"Body": {"cteDadosMsg": {"value": _gzip_b64(xml_assinado)}}},
    )
    return resp.body.cteRecepcaoResult.content[0]


def enviar_mdfe(cliente: MdfeClient, xml_assinado: str):
    resp = FiscalClient.send(
        cliente,
        action_class=MdfeRecepcaoSincSoap12MdfeRecepcao,
        location=cliente._get_location(EndpointMdfe.MDFERECEPCAOSINC),
        wrapped_obj={"Body": {"mdfeDadosMsg": {"value": _gzip_b64(xml_assinado)}}},
    )
    return MdfeClient._unwrap_body(resp.body)


def enviar_evento_cte(cliente: CteClient, evento_assinado: str):
    """Evento do CT-e (XML já assinado). Devolve o retEventoCTe."""
    resp = FiscalClient.send(
        cliente,
        action_class=CteRecepcaoEventoV4Soap12CteRecepcaoEvento,
        location=cliente._get_location(EndpointCte.CTERECEPCAOEVENTOV4),
        wrapped_obj={"Body": {"cteDadosMsg": {"content": [EventoCte(versao="4.00")]}}},
        placeholder_exp=r"<eventoCTe[^>]*/>|<eventoCTe.*?>.*?</eventoCTe>",
        placeholder_content=evento_assinado,
    )
    return resp.body.cteRecepcaoEventoResult.content[0]
