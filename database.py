import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
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