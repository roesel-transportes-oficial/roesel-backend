from fastapi import APIRouter, HTTPException, Depends
from database import sb_get, sb_post, sb_patch, sb_delete
from models import Contrato
from auth import usuario_atual
from uuid import uuid4

router = APIRouter()

# ✅ Depends(usuario_atual) em cada rota: antes de qualquer código aqui
# dentro rodar, o FastAPI já checou se o token de login é válido. Se
# não for, a requisição nem chega a entrar na função — o "porteiro"
# barra na entrada com erro 401.

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
    data = c.model_dump(exclude_none=True)
    data["id"] = str(uuid4())
    result = sb_post("contratos", data)

    # Gera comissão automaticamente
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

@router.put("/{id}")
def atualizar(id: str, c: Contrato, usuario: dict = Depends(usuario_atual)):
    data = c.model_dump(exclude={"id"}, exclude_none=True)
    result = sb_patch("contratos", f"id=eq.{id}", data)
    if not result:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    # Atualiza comissão se fat_bruto mudou
    fat_bruto = c.fat_bruto or 0
    comissao_total = round(fat_bruto * 0.10, 2)
    comissao_carga = round(fat_bruto * 0.05, 2)
    comissao_folha = round(fat_bruto * 0.05, 2)
    sb_patch("comissoes", f"contrato_id=eq.{id}", {
        "fat_bruto": fat_bruto,
        "comissao_total": comissao_total,
        "comissao_carga": comissao_carga,
        "comissao_folha": comissao_folha,
        "motorista": c.motorista,
        "data": c.data,
    })

    return result

@router.delete("/{id}")
def excluir(id: str, usuario: dict = Depends(usuario_atual)):
    sb_delete("contratos", f"id=eq.{id}")
    sb_delete("comissoes", f"contrato_id=eq.{id}")
    return {"ok": True}