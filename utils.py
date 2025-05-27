# utils.py


# Se get_status_text usa STATUS_EM_SEPARACAO, ele precisa importar de config.py
from config import STATUS_EM_SEPARACAO 

def formatar_texto_title(texto):
    """
    Formata uma string para ter a primeira letra de cada palavra em maiúscula.
    Retorna None se a entrada for None ou vazia após strip.
    """
    if texto is None:
        return None
    texto_limpo = str(texto).strip()
    if not texto_limpo:
        return None
    return texto_limpo.title()

# --- Função Auxiliar para Traduzir o Status (para exibir no HTML) ---
def get_status_text(status_code):
    """Traduz o código numérico do status 'em_separacao' para texto amigável."""
    # Criar um mapeamento inverso para facilitar a busca
    status_map = {v: k for k, v in STATUS_EM_SEPARACAO.items()}
    text = status_map.get(status_code, 'DESCONHECIDO')
    return text.replace('_', ' ').title() # Ex: 'AGUARDANDO_MOTORISTA' -> 'Aguardando Motorista'