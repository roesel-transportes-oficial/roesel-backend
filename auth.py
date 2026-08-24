import os
import requests
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL")

# ✅ "Porteiro" da API: verifica se quem está chamando um endpoint
# protegido realmente está logado no sistema.
#
# ⚠️ CORREÇÃO: antes, a chamada pro Supabase (requests.get) não tinha
# NENHUM tratamento de erro. Se essa chamada falhasse por qualquer
# instabilidade de rede (timeout, DNS, etc.), a exceção subia sem
# passar por nenhum try/except — o FastAPI então devolvia um
# "Internal Server Error" em texto puro, SEM JSON, o que quebrava o
# parse no frontend (o erro "Unexpected token 'I'..." que aparecia).
# Isso acontecia ANTES até de chegar no código da rota em si (tipo
# contratos.py), porque essa função roda como "Depends" — ou seja,
# roda primeiro, e se ela quebrar sem tratamento, nem entra na rota.
async def usuario_atual(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticação ausente.")

    token = authorization.replace("Bearer ", "")

    try:
        resposta = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
        )
    except requests.RequestException as e:
        # Erro de rede/timeout ao tentar validar o token — agora vira
        # um erro 503 com JSON explicando, em vez de derrubar o
        # servidor com um erro cru sem formato.
        raise HTTPException(status_code=503, detail=f"Não foi possível validar a sessão (conexão com o Supabase falhou): {str(e)}")

    if resposta.status_code != 200:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")

    try:
        dados = resposta.json()
    except ValueError:
        raise HTTPException(status_code=503, detail="Resposta inesperada do Supabase ao validar sessão.")

    return {"id": dados.get("id"), "email": dados.get("email")}