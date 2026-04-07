import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def sb_get(table: str, params: str = ""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    r = httpx.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def sb_post(table: str, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = httpx.post(url, headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def sb_patch(table: str, filter: str, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter}"
    r = httpx.patch(url, headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def sb_delete(table: str, filter: str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter}"
    h = {**HEADERS, "Prefer": ""}
    r = httpx.delete(url, headers=h)
    r.raise_for_status()
    return True