"""Acesso ao Supabase específico da parte fiscal (numeração e guarda de XML)."""
import os

import requests

from database import HEADERS, SUPABASE_URL

BUCKET_XML = "fiscal-xml"


def proximo_numero(modelo: str, serie: int, ambiente: str) -> int:
    """Pega o próximo número sem risco de repetir (função no banco com trava)."""
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/fiscal_proximo_numero",
        headers=HEADERS,
        json={"p_modelo": modelo, "p_serie": serie, "p_ambiente": ambiente},
        timeout=15,
    )
    r.raise_for_status()
    return int(r.json())


def salvar_arquivo(caminho: str, conteudo: bytes, tipo: str = "application/xml") -> str:
    """Grava no bucket privado e devolve o caminho dentro do bucket."""
    headers = {
        "apikey": HEADERS["apikey"],
        "Authorization": HEADERS["Authorization"],
        "Content-Type": tipo,
        "x-upsert": "true",
    }
    r = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET_XML}/{caminho}",
        headers=headers, data=conteudo, timeout=30,
    )
    r.raise_for_status()
    return caminho


def link_temporario(caminho: str, segundos: int = 600) -> str:
    """Link de download que expira (o bucket não é público)."""
    r = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/sign/{BUCKET_XML}/{caminho}",
        headers=HEADERS, json={"expiresIn": segundos}, timeout=15,
    )
    r.raise_for_status()
    return f"{SUPABASE_URL}/storage/v1{r.json()['signedURL']}"


def ambiente_atual() -> str:
    """1 = produção, 2 = homologação. Padrão: homologação, por segurança."""
    amb = os.getenv("FISCAL_AMBIENTE", "2").strip()
    return "1" if amb == "1" else "2"


def baixar_arquivo(caminho: str) -> bytes:
    """Lê um arquivo do bucket privado (usado para gerar o PDF a partir do XML)."""
    r = requests.get(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET_XML}/{caminho}",
        headers={"apikey": HEADERS["apikey"], "Authorization": HEADERS["Authorization"]},
        timeout=30,
    )
    r.raise_for_status()
    return r.content
