# config.py
from datetime import datetime
import pytz

# --- Constantes de Status ---
# Status para o processo de separação/carregamento (usado em Registro e NoShow)
STATUS_EM_SEPARACAO = {
    'AGUARDANDO_MOTORISTA': 0,
    'SEPARACAO': 1,
    'FINALIZADO': 2,
    'CANCELADO': 3,
    'TRANSFERIDO': 4,
    'AGUARDANDO_ENTREGADOR': 5
}

# Status para o registro principal (tabela 'registro')
STATUS_REGISTRO_PRINCIPAL = {
    'AGUARDANDO_CARREGAMENTO': 0,
    'CARREGAMENTO_LIBERADO': 1,
    'FINALIZADO': 2,
    'CANCELADO': 3
}

# Constante de paginação (se você usa em múltiplos lugares)
REGISTROS_POR_PAGINA = 10 # Ou outro valor padrão

# --- Permissões de Acesso às Páginas ---
# Mapeia o nome da função da rota (endpoint) para uma descrição amigável
# ATENÇÃO: As chaves devem corresponder EXATAMENTE aos nomes das funções de rota no seu app.py
PERMISSIONS = {
    'get_dashboard_data': 'Acessar API - Dados do Dashboard',
    'get_news_headlines': 'Acessar API - Notícias',
    'get_noshow_aguardando_motorista': 'Acessar API - NoShow Aguardando Motorista',
    'get_operational_info': 'Acessar API - Info Operacional',
    'get_pacotes_por_rota': 'Acessar API - Pacotes por Rota',
    'get_registros_em_separacao': 'Acessar API - Registros Em Separação',
    'alterar_senha': 'Alterar Senha de Usuário',
    'apagar_etapa': 'Apagar Etapas',
    'apagar_situacao_pedido': 'Apagar Situações de Pedido',
    'alternar_status_usuario': 'Ativar/Desativar Usuários',
    'associacao':'Associação',
    'associacao_no_show': 'Criar Registros No-Show',
    'cadastro_usuario': 'Cadastro de Usuario',
    'dashboard': 'Dashboard',
    'editar_etapa': 'Editar Etapas',
    'editar_situacao_pedido': 'Editar Situações de Pedido',
    'gerenciar_usuarios': 'Gerenciar Usuários',
    'adicionar_etapa': 'Etapas Entregas',
    'pacotes_rota': 'Pacotes por Rota',
    'listar_registros':'Lista Registros',
    'log_de_atividades':'Log de Atividades',
    'menu_principal': 'Menu Principal',
    'painel_final_page': 'Acessar Painel de Atendimento',
    'painel_gerencial': 'Gerenciamento de Rota',
    'registros': 'Painel do Operador',
    'registro_no_show': 'Listar Registro no Show',
    'registros_finalizados': 'Relatorio de Registros',
    'adicionar_situacao_pedido': 'Situações de Pedido',
    'status_entrega':'Entregas por Motorista',
    # Adicione outras rotas conforme necessário, mantendo a chave como o nome da função da rota
}

# --- Funções Auxiliares ---
def get_data_hora_brasilia():
    """
    Retorna a data e hora atual em Brasília, convertida para UTC e timezone-aware.
    Ideal para armazenamento no banco de dados.
    """
    # Define o fuso horário de Brasília
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    # Obtém a hora atual em Brasília, já com o fuso horário definido
    now_brasilia = datetime.now(tz_brasilia)
    
    # Converte para UTC. Esta é a MELHOR PRÁTICA para armazenamento no banco de dados.
    # O banco de dados vai armazenar este datetime, que já está em UTC.
    return now_brasilia.astimezone(pytz.utc)
