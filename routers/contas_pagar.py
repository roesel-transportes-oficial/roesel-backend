from fastapi import APIRouter, HTTPException, Depends
from database import sb_get, sb_post, sb_patch, sb_delete
from models import ContaPagar, ImportarNFeRequest
from auth import usuario_atual
from uuid import uuid4

router = APIRouter()

@router.get("/")
def listar(status: str = "", venc_inicio: str = "", venc_fim: str = "", usuario: dict = Depends(usuario_atual)):
    params = "order=data_vencimento.asc&select=*"
    if status:
        params += f"&status=eq.{status}"
    if venc_inicio:
        params += f"&data_vencimento=gte.{venc_inicio}"
    if venc_fim:
        params += f"&data_vencimento=lte.{venc_fim}"
    return sb_get("contas_pagar", params)

@router.post("/")
def criar(c: ContaPagar, usuario: dict = Depends(usuario_atual)):
    data = c.model_dump(exclude_none=True, exclude={"id"})
    data["id"] = str(uuid4())
    data["fornecedor_cnpj"] = (data.get("fornecedor_cnpj") or "").replace(".", "").replace("/", "").replace("-", "")
    resultado = sb_post("contas_pagar", data)
    return resultado

@router.put("/{id}")
def atualizar(id: str, c: ContaPagar, usuario: dict = Depends(usuario_atual)):
    data = c.model_dump(exclude={"id"}, exclude_none=True)
    if "fornecedor_cnpj" in data:
        data["fornecedor_cnpj"] = data["fornecedor_cnpj"].replace(".", "").replace("/", "").replace("-", "")
    resultado = sb_patch("contas_pagar", f"id=eq.{id}", data)
    if not resultado:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return resultado

@router.delete("/{id}")
def excluir(id: str, usuario: dict = Depends(usuario_atual)):
    sb_delete("contas_pagar", f"id=eq.{id}")
    return {"ok": True}

# ✅ Importação de NF-e: antes essa sequência (criar nota_fiscal → criar
# conta_pagar → vincular abastecimento) rodava direto no frontend, em
# 3 chamadas separadas ao Supabase com a chave anônima — se qualquer
# uma falhasse no meio, ficava com dado pela metade (nota criada sem
# conta, por exemplo). Agora é uma operação só no backend: se algo
# falhar no meio, a gente sabe exatamente onde parou.
@router.post("/importar-nfe")
def importar_nfe(req: ImportarNFeRequest, usuario: dict = Depends(usuario_atual)):
    dados = req.dados_nfe

    # Verifica se essa NF-e já foi importada antes (pela chave de acesso)
    existentes = sb_get("notas_fiscais", f"chave_acesso=eq.{dados.chave_acesso}&select=id&limit=1")
    if existentes:
        raise HTTPException(status_code=409, detail="Esta NF-e já foi importada anteriormente.")

    nfe_id = str(uuid4())
    nfe_data = {
        "id": nfe_id,
        "chave_acesso": dados.chave_acesso,
        "numero_nf": dados.numero_nf,
        "serie": dados.serie,
        "data_emissao": dados.data_emissao,
        "emitente_cnpj": dados.emitente_cnpj,
        "emitente_nome": dados.emitente_nome,
        "emitente_fantasia": dados.emitente_fantasia,
        "emitente_cidade": dados.emitente_cidade,
        "emitente_uf": dados.emitente_uf,
        "valor_total": dados.valor_total,
        "natureza_operacao": dados.natureza_operacao,
        "cfop": dados.cfop,
        "produtos": dados.produtos,
        "info_adicional": dados.info_adicional,
    }
    sb_post("notas_fiscais", nfe_data)

    conta_id = str(uuid4())
    conta_data = {
        "id": conta_id,
        "descricao": f"NF-e {dados.numero_nf} — {dados.emitente_nome}",
        "fornecedor_nome": dados.emitente_nome,
        "fornecedor_cnpj": dados.emitente_cnpj,
        "valor": dados.valor_total,
        "data_emissao": dados.data_emissao,
        "data_vencimento": req.vencimento,
        "status": "PENDENTE",
        "nota_fiscal_id": nfe_id,
        "nota_fiscal_chave": dados.chave_acesso,
        "obs": req.obs,
    }
    sb_post("contas_pagar", conta_data)

    if req.abastecimento_id:
        sb_patch("abastecimentos", f"id=eq.{req.abastecimento_id}", {
            "nota_fiscal_id": nfe_id,
            "nota_fiscal_chave": dados.chave_acesso,
        })

    return {"ok": True, "nota_fiscal_id": nfe_id, "conta_pagar_id": conta_id}