"""Chave de acesso de 44 dígitos (CT-e, MDF-e, NF-e usam o mesmo formato)."""
import random


def digito_verificador(chave43: str) -> str:
    """Módulo 11 com pesos 2 a 9, da direita para a esquerda."""
    soma = 0
    peso = 2
    for d in reversed(chave43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    dv = 0 if resto in (0, 1) else 11 - resto
    return str(dv)


def codigo_numerico(numero: int) -> str:
    """cCT: 8 dígitos aleatórios, diferente do número do documento."""
    while True:
        c = f"{random.randint(0, 99999999):08d}"
        if int(c) != numero:
            return c


def montar_chave(
    cuf: str, ano_mes: str, cnpj: str, modelo: str, serie: int,
    numero: int, tp_emis: str, codigo: str,
) -> str:
    """Retorna a chave completa (44 dígitos), já com o DV."""
    chave43 = (
        f"{cuf:0>2}{ano_mes}{cnpj:0>14}{modelo:0>2}{serie:03d}"
        f"{numero:09d}{tp_emis}{codigo:0>8}"
    )
    if len(chave43) != 43 or not chave43.isdigit():
        raise ValueError(f"Chave inválida: {chave43}")
    return chave43 + digito_verificador(chave43)
