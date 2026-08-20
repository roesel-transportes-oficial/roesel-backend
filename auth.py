import os
import requests
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL")

# ✅ "Porteiro" da API: verifica se quem está chamando um endpoint
# protegido realmente está logado no sistema.
#
# Como funciona: o frontend, depois que o usuário loga, já tem um
# "token de sessão" (o Supabase guarda isso automaticamente). Toda
# chamada pro backend precisa vir com esse token no cabeçalho
# "Authorization: Bearer <token>". Essa função pega esse token e
# pergunta pro próprio Supabase "esse token é válido? de quem é?" —
# se não for válido (expirado, forjado, ausente), a chamada é
# recusada com erro 401 ANTES de qualquer código do endpoint rodar.
#
# Isso fecha o buraco que existia antes: hoje QUALQUER chamada pro
# backend era aceita, sem checar login nenhum.
async def usuario_atual(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticação ausente.")

    token = authorization.replace("Bearer ", "")

    resposta = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "apikey": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            "Authorization": f"Bearer {token}",
        },
        timeout=10,
    )

    if resposta.status_code != 200:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")

    dados = resposta.json()
    return {"id": dados.get("id"), "email": dados.get("email")}