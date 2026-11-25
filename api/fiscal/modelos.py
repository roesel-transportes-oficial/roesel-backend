"""Dados que o sistema precisa para montar um CT-e.

Ficam guardados na coluna `dados_fiscais` (jsonb) da tabela `ctes`.
Os dados da própria transportadora (emitente) ficam na tabela
`fiscal_emitente`, preenchida uma vez só.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Endereco(BaseModel):
    logradouro: str
    numero: str = "S/N"
    complemento: Optional[str] = None
    bairro: str
    cod_municipio: str = Field(..., description="Código IBGE do município, 7 dígitos")
    municipio: str
    cep: Optional[str] = None
    uf: str


class Participante(BaseModel):
    """Remetente, destinatário, expedidor ou recebedor."""
    cnpj: Optional[str] = None
    cpf: Optional[str] = None
    ie: Optional[str] = None  # vazio ou "ISENTO" quando não tem
    nome: str
    fone: Optional[str] = None
    email: Optional[str] = None
    endereco: Endereco


class Municipio(BaseModel):
    cod: str  # código IBGE, 7 dígitos
    nome: str
    uf: str


class Componente(BaseModel):
    nome: str  # ex.: "FRETE PESO", "PEDAGIO"
    valor: float


class Icms(BaseModel):
    # "00" tributado | "20" com redução de base | "40" isento | "41" não tributado
    # "51" diferido | "90" outros | "SN" Simples Nacional
    cst: Literal["00", "20", "40", "41", "51", "90", "SN"]
    base: float = 0.0
    aliquota: float = 0.0
    valor: float = 0.0
    reducao_base: float = 0.0  # % de redução (CST 20 e 90)


class IbsCbs(BaseModel):
    """Reforma Tributária. Em 2026: CBS 0,9% e IBS-UF 0,1% (fase de teste)."""
    cst: str = "000"
    cclass_trib: str = "000001"
    base: Optional[float] = None  # se vazio, usa o valor da prestação
    p_ibs_uf: float = 0.10
    p_ibs_mun: float = 0.0
    p_cbs: float = 0.90


class Quantidade(BaseModel):
    # 00 M3 | 01 KG | 02 TON | 03 UNIDADE | 04 LITROS | 05 MMBTU
    unidade: Literal["00", "01", "02", "03", "04", "05"] = "01"
    tipo_medida: str = "PESO BRUTO"
    quantidade: float


class Produto(BaseModel):
    """Vem da NF-e. O CT-e não tem campo de NCM, mas o MDF-e e a GNRE usam."""
    ncm: str
    descricao: Optional[str] = None


class Carga(BaseModel):
    valor: float
    produto_predominante: str
    quantidades: list[Quantidade]
    produtos: list[Produto] = []


class DocAnterior(BaseModel):
    """CT-e da transportadora que contratou (subcontratação) ou do trecho anterior (redespacho)."""
    cnpj: str
    ie: Optional[str] = None
    uf: str
    nome: str
    chaves_cte: list[str]


class Seguro(BaseModel):
    """Seguro da carga. O CT-e 4.00 não tem grupo próprio: vai nas observações.
    O MDF-e usa estes mesmos dados no grupo <seg>."""
    # 1 emitente do MDF-e (a própria transportadora) | 2 contratante do serviço
    responsavel: Literal[1, 2] = 1
    responsavel_cnpj: Optional[str] = None  # só quando responsavel = 2
    seguradora: str
    seguradora_cnpj: Optional[str] = None
    apolice: str
    averbacoes: list[str] = []


class DadosFiscaisCte(BaseModel):
    # 0 normal | 1 subcontratação | 2 redespacho
    tipo_servico: Literal[0, 1, 2] = 0
    doc_anterior: Optional[DocAnterior] = None  # obrigatório quando tipo_servico = 1 ou 2
    cfop: str  # ex.: 5353 / 6353 (ou 5352 / 6352 etc., conforme o contador)
    natureza_operacao: str = "PRESTACAO DE SERVICO DE TRANSPORTE"
    # quem paga o frete: 0 remetente | 1 expedidor | 2 recebedor | 3 destinatário | 4 outro
    tomador: Literal[0, 1, 2, 3, 4] = 0
    outro_tomador: Optional[Participante] = None  # só quando tomador = 4
    remetente: Participante
    destinatario: Participante
    expedidor: Optional[Participante] = None
    recebedor: Optional[Participante] = None
    inicio: Municipio  # onde começa a prestação
    fim: Municipio  # onde termina
    valor_prestacao: float
    valor_receber: Optional[float] = None  # se vazio, igual ao valor da prestação
    componentes: list[Componente] = []
    icms: Icms
    ibscbs: Optional[IbsCbs] = None
    carga: Carga
    seguro: Optional[Seguro] = None
    chaves_nfe: list[str] = Field(default_factory=list, description="Chaves das NF-e transportadas")
    observacoes: Optional[str] = None
