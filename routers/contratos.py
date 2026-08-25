from fastapi import APIRouter, HTTPException, Depends
from database import sb_get, sb_post, sb_patch, sb_delete
from models import Contrato
from auth import usuario_atual
from uuid import uuid4

router = APIRouter()

# ✅ Helper: monta a mensagem de erro com o corpo real da resposta do
# Supabase, se existir. É onde o Postgrest explica o motivo verdadeiro
# do erro (tipo "coluna não existe" ou "campo obrigatório faltando"),
# que antes ficava escondido atrás de um "400 Bad Request" genérico.
def erro_detalhado(e: Exception) -> str:
    detalhe_resposta = ''
    resposta_http = getattr(e, 'response', None)
    if resposta_http is not None:
        try:
            detalhe_resposta = f" | Resposta do Supabase: {resposta_http.text}"
        except Exception:
            pass
    return f"ERRO REAL: {type(e).__name__}: {str(e)}{detalhe_resposta}"

@router.get("/")
def listar(motorista: str = "", status: str = "", mes: int = 0, ano: int = 0, usuario: dict = Depends(usuario_atual)):
    params = "order=data.desc"
    if motorista:
        from urllib.parse import quote
        params += f"&motorista=eq.{quote(motorista)}"
    if status:
        params += f"&status=eq.{status}"
    dados = sb_get("contratos", params)
    if mes or ano:
        filtrados = []
        for c in dados:
            if c.get("data"):
                partes = c["data"].split("-")
                if ano and int(partes[0]) != ano: continue
                if mes and int(partes[1]) != mes: continue
            filtrados.append(c)
        return filtrados
    return dados

@router.post("/")
def criar(c: Contrato, usuario: dict = Depends(usuario_atual)):
    try:
        data = c.model_dump(exclude_none=True)
        data["id"] = str(uuid4())
        result = sb_post("contratos", data)

        fat_bruto = c.fat_bruto or 0
        comissao_total = round(fat_bruto * 0.10, 2)
        comissao_carga = round(fat_bruto * 0.05, 2)
        comissao_folha = round(fat_bruto * 0.05, 2)

        mes = 0
        ano = 0
        if c.data:
            try:
                partes = c.data.split("-")
                ano = int(partes[0])
                mes = int(partes[1])
            except:
                pass

        comissao = {
            "id": str(uuid4()),
            "contrato_id": data["id"],
            "contrato": c.contrato,
            "motorista": c.motorista,
            "data": c.data,
            "fat_bruto": fat_bruto,
            "comissao_total": comissao_total,
            "comissao_carga": comissao_carga,
            "comissao_folha": comissao_folha,
            "carga_paga": False,
            "folha_paga": False,
            "mes": mes,
            "ano": ano,
        }
        sb_post("comissoes", comissao)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=erro_detalhado(e))

@router.put("/{id}")
def atualizar(id: str, c: Contrato, usuario: dict = Depends(usuario_atual)):
    try:
        data = c.model_dump(exclude={"id"}, exclude_none=True)
        result = sb_patch("contratos", f"id=eq.{id}", data)
        if not result:
            raise HTTPException(status_code=404, detail="Contrato não encontrado")

        fat_bruto = c.fat_bruto or 0
        comissao_total = round(fat_bruto * 0.10, 2)
        comissao_carga = round(fat_bruto * 0.05, 2)
        comissao_folha = round(fat_bruto * 0.05, 2)
        try:
            sb_patch("comissoes", f"contrato_id=eq.{id}", {
                "fat_bruto": fat_bruto,
                "comissao_total": comissao_total,
                "comissao_carga": comissao_carga,
                "comissao_folha": comissao_folha,
                "motorista": c.motorista,
                "data": c.data,
            })
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=erro_detalhado(e))

@router.delete("/{id}")
def excluir(id: str, usuario: dict = Depends(usuario_atual)):
    sb_delete("contratos", f"id=eq.{id}")
    sb_delete("comissoes", f"contrato_id=eq.{id}")
    return {"ok": True}
