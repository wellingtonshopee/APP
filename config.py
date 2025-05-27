# config.py

from datetime import datetime
import pytz # Para fuso horário de Brasília

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///seu_banco_de_dados.db' # Mude para seu DB real (PostgreSQL, etc.)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'sua_chave_secreta_aqui' # Mude para uma chave secreta forte!
    PERMANENT_SESSION_LIFETIME = 3600 # Exemplo: sessão dura 1 hora

# Constantes de Status (Melhor lugar para elas, pois são configurações globais de estado)
STATUS_EM_SEPARACAO = {
    'AGUARDANDO_MOTORISTA': 0,
    'SEPARACAO': 1,
    'FINALIZADO': 2,
    'CANCELADO': 3,
    'TRANSFERIDO': 4,
    'AGUARDANDO_ENTREGADOR': 5
}

STATUS_REGISTRO_PRINCIPAL = {
    'AGUARDANDO_CARREGAMENTO': 0,
    'CARREGAMENTO_LIBERADO': 1,
    'FINALIZADO': 2,
    'CANCELADO': 3
}

def get_data_hora_brasilia():
    """Retorna a data e hora atual no fuso horário de Brasília."""
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(brasilia_tz)