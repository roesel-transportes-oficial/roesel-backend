from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import date

class Motorista(BaseModel):
    id: Optional[UUID] = None
    nome: str
    cpf: Optional[str] = ""
    rg: Optional[str] = ""
    tipo: Optional[str] = "Com adiantamento"
    ativo: Optional[bool] = True
    adiantamento: Optional[bool] = True
    dt_desligamento: Optional[str] = None
    vencimento_cnh: Optional[date] = None
    vencimento_permisso: Optional[date] = None
    vencimento_toxicologico: Optional[date] = None
    vencimento_periodico: Optional[date] = None
    caminhao_id: Optional[UUID] = None
    caminhao_temp_id: Optional[UUID] = None
    de_ferias: Optional[bool] = False
    ferias_inicio: Optional[str] = None
    ferias_fim: Optional[str] = None
    substituto_id: Optional[UUID] = None

class Contrato(BaseModel):
    id: Optional[UUID] = None
    motorista: str
    cliente: str
    cliente_nome_completo: Optional[str] = ""
    cnpj: Optional[str] = ""
    placa: Optional[str] = ""
    placa_carreta: Optional[str] = ""
    frota: Optional[str] = ""
    contrato: str
    data: Optional[str] = None
    fat_bruto: Optional[float] = 0.0
    chapa: Optional[float] = 0.0
    origem: Optional[str] = ""
    destino: Optional[str] = ""
    qtd_veiculos: Optional[int] = 0
    adiantamento_pago: Optional[bool] = False
    dt_pagamento: Optional[str] = None
    valor_adiantamento: Optional[float] = 0.0
    dt_pagamento_adiantamento: Optional[str] = None
    status: Optional[str] = "ABERTO"
    obs: Optional[str] = ""

class Frota(BaseModel):
    id: Optional[UUID] = None
    nome: str
    descricao: Optional[str] = ""

class Caminhao(BaseModel):
    id: Optional[UUID] = None
    placa: str
    placa_carreta: Optional[str] = ""
    modelo: Optional[str] = ""
    ano: Optional[str] = ""
    frota_id: Optional[UUID] = None
    frota: Optional[str] = ""
    motorista_atual: Optional[str] = ""
    status: Optional[str] = "rodando"
    motivo_parado: Optional[str] = ""
    dt_parado: Optional[str] = None
    venc_licenca: Optional[date] = None
    venc_tacografo: Optional[date] = None
    venc_outros: Optional[date] = None
    obs_documentos: Optional[str] = ""

# ✅ Novo: modelo pra Contas a Pagar (Fase 2 da migração pro backend)
class ContaPagar(BaseModel):
    id: Optional[UUID] = None
    descricao: Optional[str] = ""
    fornecedor_nome: str
    fornecedor_cnpj: Optional[str] = ""
    valor: float
    data_emissao: Optional[str] = None
    data_vencimento: str
    status: Optional[str] = "PENDENTE"
    nota_fiscal_id: Optional[UUID] = None
    nota_fiscal_chave: Optional[str] = ""
    obs: Optional[str] = ""

# ✅ Dados de uma NF-e já extraídos do XML pelo frontend (o parse do XML
# em si continua no navegador — só a gravação no banco passa a ser
# feita pelo backend, com autenticação e validação).
class DadosNFe(BaseModel):
    chave_acesso: str
    numero_nf: Optional[str] = ""
    serie: Optional[str] = ""
    data_emissao: Optional[str] = None
    emitente_cnpj: str
    emitente_nome: str
    emitente_fantasia: Optional[str] = ""
    emitente_cidade: Optional[str] = ""
    emitente_uf: Optional[str] = ""
    valor_total: float
    natureza_operacao: Optional[str] = ""
    cfop: Optional[str] = ""
    produtos: Optional[str] = ""
    info_adicional: Optional[str] = ""

class ImportarNFeRequest(BaseModel):
    dados_nfe: DadosNFe
    vencimento: str
    obs: Optional[str] = ""
    abastecimento_id: Optional[UUID] = None  # se um abastecimento foi identificado pra vincular

# ✅ Fase 3 da migração: CT-e e Notas Fiscais (NFS-e / Devolução / Remessa)
class Cte(BaseModel):
    id: Optional[UUID] = None
    tipo: str  # 'normal' | 'redespacho'
    status: Optional[str] = "rascunho"
    remetente_nome: Optional[str] = ""
    remetente_cnpj: Optional[str] = ""
    destinatario_nome: Optional[str] = ""
    destinatario_cnpj: Optional[str] = ""
    tomador_nome: Optional[str] = ""
    tomador_cnpj: Optional[str] = ""
    origem: Optional[str] = ""
    destino: Optional[str] = ""
    valor_prestacao: Optional[float] = 0.0
    natureza_operacao: Optional[str] = ""
    placa: Optional[str] = ""
    motorista: Optional[str] = ""
    cte_anterior_chave: Optional[str] = ""
    redespachante_nome: Optional[str] = ""
    redespachante_cnpj: Optional[str] = ""
    chave_acesso: Optional[str] = ""
    numero_cte: Optional[str] = ""
    xml_url: Optional[str] = ""
    dacte_url: Optional[str] = ""
    motivo_rejeicao: Optional[str] = ""
    obs: Optional[str] = ""

class NotaDiversa(BaseModel):
    id: Optional[UUID] = None
    tipo: str  # 'nfse' | 'devolucao' | 'remessa'
    status: Optional[str] = "rascunho"
    destinatario_nome: Optional[str] = ""
    destinatario_cnpj: Optional[str] = ""
    valor: Optional[float] = 0.0
    data_emissao: Optional[str] = None
    obs: Optional[str] = ""
    descricao_servico: Optional[str] = ""
    aliquota_iss: Optional[float] = 0.0
    iss_retido: Optional[bool] = False
    nota_fiscal_original_chave: Optional[str] = ""
    motivo_devolucao: Optional[str] = ""
    natureza_remessa: Optional[str] = ""
    produtos_descricao: Optional[str] = ""
    placa: Optional[str] = ""
    motorista: Optional[str] = ""
    origem: Optional[str] = ""
    destino: Optional[str] = ""
    chave_acesso: Optional[str] = ""
    numero_nota: Optional[str] = ""
    xml_url: Optional[str] = ""
    pdf_url: Optional[str] = ""
    motivo_rejeicao: Optional[str] = ""