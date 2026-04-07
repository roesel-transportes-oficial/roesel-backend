import os, base64, json
from fastapi import APIRouter, UploadFile, File, HTTPException
import httpx
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

PROMPT = """Analise este contrato de transporte rodoviário e retorne APENAS um JSON puro, sem markdown, sem explicação.

Extraia os seguintes campos:
- contrato: número do contrato
- data: data do contrato no formato DD/MM/AAAA
- cliente: nome curto da empresa contratante (ex: AUTOPORT)
- cliente_nome_completo: razão social completa
- cnpj: CNPJ da empresa contratante
- frota: número da frota do veículo
- placa: placa do caminhão
- qtd_veiculos: quantidade de veículos transportados (número)
- origem: cidade/UF de origem
- destino: cidade/UF de destino final
- motorista: nome do motorista em MAIUSCULAS
- motorista_cpf: CPF do motorista
- motorista_rg: RG do motorista
- fat_bruto: valor do frete contratado (número decimal)
- chapa: 0.0

Retorne SOMENTE o JSON com esses campos."""

@router.post("/ler-contrato")
async def ler_contrato(arquivo: UploadFile = File(...)):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY não configurada")

    conteudo = await arquivo.read()
    b64 = base64.b64encode(conteudo).decode("utf-8")
    media_type = arquivo.content_type or "image/jpeg"

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": PROMPT}
            ]
        }]
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        if not r.is_success:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        
        data = r.json()
        texto = data["content"][0]["text"]
        clean = texto.replace("```json", "").replace("```", "").strip()
        s = clean.find("{"); e = clean.rfind("}") + 1
        if s >= 0 and e > s:
            return json.loads(clean[s:e])

    raise HTTPException(status_code=422, detail="Não foi possível extrair JSON do contrato")