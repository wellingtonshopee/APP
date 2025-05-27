from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
# Importe as constantes e a função de data/hora do config.py
from config import STATUS_EM_SEPARACAO, STATUS_REGISTRO_PRINCIPAL, get_data_hora_brasilia

# Certifique-se de que 'app' é inicializado em algum lugar antes de importar db
# Ex: from sua_aplicacao import db
# Ou, se você inicializar o db aqui, precisará passar o app depois:
db = SQLAlchemy()

# --- Constantes de Status ---
# Você pode colocá-las aqui ou em um arquivo de configuração separado (ex: config.py)
# Se estiverem aqui, importe-as junto com os modelos.

# Status para o processo de separação/carregamento (usado em Registro e NoShow)
STATUS_EM_SEPARACAO = {
    'AGUARDANDO_MOTORISTA': 0, # Motorista chegou, aguardando ser direcionado (ou NoShow inicial)
    'SEPARACAO': 1,            # Pedido/item em processo de separação/preparação
    'FINALIZADO': 2,           # Carregamento do registro principal finalizado (ou NoShow processado)
    'CANCELADO': 3,            # Registro principal ou NoShow cancelado
    'TRANSFERIDO': 4,          # NoShow transferido para um registro principal
    'AGUARDANDO_ENTREGADOR': 5 # NoShow associado e aguardando o entregador para retirada
}

# Status para o registro principal (tabela 'registro')
STATUS_REGISTRO_PRINCIPAL = {
    'AGUARDANDO_CARREGAMENTO': 0, # Motorista logado, aguardando atribuição de carregamento
    'CARREGAMENTO_LIBERADO': 1,   # Carregamento associado e liberado (pode ser "em separação" na prática)
    'FINALIZADO': 2,              # Carregamento concluído e motorista saiu
    'CANCELADO': 3                # Registro cancelado
}

# --- Funções Auxiliares (se necessárias, podem estar em utils.py) ---
# Se get_data_hora_brasilia() estiver em outro arquivo, importe-o.
# Caso contrário, você pode definir uma função simples aqui para fins de demonstração.
def get_data_hora_brasilia():
    """Retorna a data e hora atual no fuso horário de Brasília."""
    # Para uma implementação real, você usaria bibliotecas como pytz
    # Ex: import pytz; return datetime.now(pytz.timezone('America/Sao_Paulo'))
    return datetime.now()


# --- Definição dos Modelos ---

class Login(db.Model):
    __tablename__ = 'login'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    tipo_veiculo = db.Column(db.String(50))
    data_cadastro = db.Column(db.DateTime, default=get_data_hora_brasilia)

    def __repr__(self):
        return f"<Login(id={self.id}, nome='{self.nome}')>"


class Registro(db.Model):
    __tablename__ = 'registro' # Tabela principal de registros de carregamento
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(50), nullable=False)
    data_hora_login = db.Column(db.DateTime, default=get_data_hora_brasilia)
    rota = db.Column(db.String(50)) # Ex: T4, Rota-Azul
    tipo_entrega = db.Column(db.String(50)) # Ex: 'Normal', 'No-Show'
    cidade_entrega = db.Column(db.String(100))
    rua = db.Column(db.String(100))
    estacao = db.Column(db.String(100))
    # Status mais granular do processo de separação/carregamento
    em_separacao = db.Column(db.Integer, default=STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA'])
    # Status geral do registro (para relatórios ou filtros de alto nível)
    status = db.Column(db.Integer, default=STATUS_REGISTRO_PRINCIPAL['AGUARDANDO_CARREGAMENTO'])
    finalizada = db.Column(db.Integer, default=0) # 0 = não finalizado, 1 = finalizado
    cancelado = db.Column(db.Integer, default=0)  # 0 = não cancelado, 1 = cancelado
    hora_finalizacao = db.Column(db.DateTime)     # Hora que o carregamento foi FINALIZADO (ou cancelado/transferido)

    # Campos que podem ser preenchidos se o motorista tiver um 'login_id'
    login_id = db.Column(db.Integer, db.ForeignKey('login.id'), nullable=True)
    login_info = db.relationship('Login', backref='registros_associados', lazy=True)
    
    # Campo tipo_veiculo copiado do login, para auditoria (opcional)
    tipo_veiculo = db.Column(db.String(50)) 

    def __repr__(self):
        return f"<Registro(id={self.id}, matricula='{self.matricula}', rota='{self.rota}', status='{self.status}')>"

class NoShow(db.Model):
    __tablename__ = 'no_show' # Tabela para registros de 'No-Show'
    id = db.Column(db.Integer, primary_key=True)
    data_hora_login = db.Column(db.DateTime, default=get_data_hora_brasilia)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(50), nullable=False)
    gaiola = db.Column(db.String(50)) # Representa a "rota" do no-show
    tipo_entrega = db.Column(db.String(50)) # Ex: 'No-Show'
    rua = db.Column(db.String(100))
    estacao = db.Column(db.String(100))
    finalizada = db.Column(db.Integer, default=0) # 0 = não finalizado, 1 = finalizado
    cancelado = db.Column(db.Integer, default=0)  # 0 = não cancelado, 1 = cancelado
    
    # Status granular para o processo do NoShow
    em_separacao = db.Column(db.Integer, default=STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA'])
    hora_finalizacao = db.Column(db.DateTime)     # Hora que o NoShow foi FINALIZADO/CANCELADO/TRANSFERIDO

    # Campos para auditoria de transferência:
    # Registra o ID do registro principal para o qual este NoShow foi transferido
    transferred_to_registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'), nullable=True)
    transferred_registro = db.relationship('Registro', backref='no_shows_transferidos', foreign_keys=[transferred_to_registro_id])

    # Dados do motorista/registro principal que "assumiu" este NoShow
    transfer_nome_motorista = db.Column(db.String(100))
    transfer_matricula_motorista = db.Column(db.String(50))
    transfer_cidade_entrega = db.Column(db.String(100))
    transfer_tipo_veiculo = db.Column(db.String(50))
    transfer_login_id = db.Column(db.Integer) # Não FK para evitar ciclos, apenas registra o ID
    transfer_gaiola_origem = db.Column(db.String(50)) # Rota do registro principal que assumiu
    transfer_estacao_origem = db.Column(db.String(100))
    transfer_rua_origem = db.Column(db.String(100))
    transfer_data_hora_login_origem = db.Column(db.DateTime) # Data/hora do login do motorista no registro principal que assumiu

    def __repr__(self):
        return f"<NoShow(id={self.id}, matricula='{self.matricula}', gaiola='{self.gaiola}', status='{self.em_separacao}')>"