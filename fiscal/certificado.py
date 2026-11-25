"""Leitura do certificado digital A1 da empresa.

O arquivo .pfx fica em variável secreta da Vercel, em base64:
  CERT_PFX_BASE64  -> conteúdo do .pfx convertido para base64
  CERT_SENHA       -> senha do certificado

Nada disso pode ir para o frontend nem para variável NEXT_PUBLIC_*.
"""
import base64
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives.serialization import pkcs12


class CertificadoNaoConfigurado(RuntimeError):
    pass


def carregar_certificado() -> tuple[bytes, str]:
    b64 = os.getenv("CERT_PFX_BASE64", "").strip()
    senha = os.getenv("CERT_SENHA", "")
    if not b64:
        raise CertificadoNaoConfigurado(
            "Certificado digital não configurado. Cadastre CERT_PFX_BASE64 e "
            "CERT_SENHA nas variáveis de ambiente do backend na Vercel."
        )
    try:
        dados = base64.b64decode(b64)
    except Exception:
        raise CertificadoNaoConfigurado("CERT_PFX_BASE64 não é um base64 válido.")
    return dados, senha


def info_certificado() -> dict:
    """Titular e validade, para avisar antes de vencer."""
    dados, senha = carregar_certificado()
    try:
        _, cert, _ = pkcs12.load_key_and_certificates(dados, senha.encode())
    except ValueError:
        raise CertificadoNaoConfigurado("Senha do certificado incorreta ou arquivo inválido.")
    validade = cert.not_valid_after_utc
    dias = (validade - datetime.now(timezone.utc)).days
    return {
        "titular": cert.subject.rfc4514_string(),
        "valido_ate": validade.isoformat(),
        "dias_para_vencer": dias,
        "vencido": dias < 0,
    }
