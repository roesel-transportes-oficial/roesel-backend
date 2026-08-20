import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")

# ✅ Trocado de SUPABASE_KEY (chave anônima — a mesma que o frontend usa)
# pra SUPABASE_SERVICE_ROLE_KEY (chave secreta). Essa é a diferença que
# dá privilégio real ao backend: com a service_role, o backend consegue
# ignorar RLS e fazer o que precisar no banco — coisa que o frontend,
# usando a chave anônima, nunca deveria conseguir fazer sozinho.
#
# ⚠️ Essa chave é SECRETA — nunca pode aparecer em código do frontend,
# nem em variável NEXT_PUBLIC_*, nem em nenhum lugar que o navegador
# consiga ver. Fica só aqui, no ambiente do backend na Vercel.
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY não configurada nas variáveis de ambiente. "
        "Pegue a chave 'service_role' em Supabase → Project Settings → API."
    )

HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def sb_get(tabela: str, query: str = ""):
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?{query}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def sb_post(tabela: str, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{tabela}"
    r = requests.post(url, headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def sb_patch(tabela: str, query: str, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?{query}"
    r = requests.patch(url, headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def sb_delete(tabela: str, query: str):
    url = f"{SUPABASE_URL}/rest/v1/{tabela}?{query}"
    r = requests.delete(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()