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
    status: Optional[str] = "ABERTO"
    obs: Optional[str] = ""

class Frota(BaseModel):
    id: Optional[UUID] = None
    nome: str
    descricao: Optional[str] = ""

class Caminhao(BaseModel):
    id: Optional[UUID] = None
    placa: str
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