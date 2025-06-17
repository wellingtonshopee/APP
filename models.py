# models.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_ # Mantido, caso esteja em uso em outro lugar que não o modelo
from datetime import datetime
import pytz # Para manipulação de fuso horário, se get_data_hora_brasilia precisar
from flask_login import UserMixin
import json # NOVO: Importado para lidar com JSON em permissions

# === ADICIONADO: Importações para hashing de senha ===
from werkzeug.security import generate_password_hash, check_password_hash

# Importe get_data_hora_brasilia e outras constantes de config.py
# Certifique-se de que config.py esteja no mesmo nível ou acessível
from config import STATUS_EM_SEPARACAO, STATUS_REGISTRO_PRINCIPAL, get_data_hora_brasilia, PERMISSIONS

# === INICIALIZE O SQLALCHEMY AQUI ===
# db é definido AQUI e será associado ao app em app.py
db = SQLAlchemy()

# --- Definição dos Modelos ---

class Login(db.Model):
    __tablename__ = 'login'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    tipo_veiculo = db.Column(db.String(50))
    data_cadastro = db.Column(db.DateTime, default=get_data_hora_brasilia)

    def __repr__(self):
        return f"<Login(id={self.id}, nome='{self.nome}')>"

class Etapa(db.Model):
    __tablename__ = 'etapa'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome_etapa = db.Column(db.String(80), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<Etapa {self.nome_etapa}>"

class SituacaoPedido(db.Model):
    __tablename__ = 'situacao_pedido'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome_situacao = db.Column(db.String(80), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<SituacaoPedido {self.nome_situacao}>"
    
class Registro(db.Model):
    __tablename__ = 'registro'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(50), nullable=False)
    data_hora_login = db.Column(db.DateTime, default=get_data_hora_brasilia)
    rota = db.Column(db.String(50))
    tipo_entrega = db.Column(db.String(50))
    cidade_entrega = db.Column(db.String(100))
    rua = db.Column(db.String(100))
    estacao = db.Column(db.String(100))
    em_separacao = db.Column(db.Integer, default=STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA'])
    status = db.Column(db.Integer, default=STATUS_REGISTRO_PRINCIPAL['AGUARDANDO_CARREGAMENTO'])
    finalizada = db.Column(db.Integer, default=0)
    cancelado = db.Column(db.Integer, default=0)
    hora_finalizacao = db.Column(db.DateTime)
    motivo_cancelamento = db.Column(db.String(255), nullable=True)

    login_id = db.Column(db.Integer, db.ForeignKey('login.id'), nullable=True)
    login_info = db.relationship('Login', backref='registros_associados', lazy=True)

    tipo_veiculo = db.Column(db.String(50))
    gaiola = db.Column(db.String(50), nullable=True)

    # Relacionamento com Etapa
    etapa_id = db.Column(db.Integer, db.ForeignKey('etapa.id'), nullable=True)
    etapa = db.relationship('Etapa', backref='registros_associados_etapa')

    # NOVOS CAMPOS PARA O PAINEL GERENCIAL
    quantidade_pacotes = db.Column(db.Integer, default=0)
    data_de_entrega = db.Column(db.DateTime, nullable=True)

    # Relacionamento com SituacaoPedido
    situacao_pedido_id = db.Column(db.Integer, db.ForeignKey('situacao_pedido.id'), nullable=True)
    situacao_pedido = db.relationship('SituacaoPedido', backref='registros_associados_situacao')

    def __repr__(self):
        return f"<Registro(id={self.id}, matricula='{self.matricula}', rota='{self.rota}', status='{self.status}')>"

class NoShow(db.Model):
    __tablename__ = 'no_show'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data_hora_login = db.Column(db.DateTime, default=get_data_hora_brasilia)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(50), nullable=False)
    gaiola = db.Column(db.String(50))
    tipo_entrega = db.Column(db.String(50))
    rua = db.Column(db.String(100))
    estacao = db.Column(db.String(100))
    finalizada = db.Column(db.Integer, default=0)
    cancelado = db.Column(db.Integer, default=0)
    em_separacao = db.Column(db.Integer, default=STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA'])
    hora_finalizacao = db.Column(db.DateTime)

    transferred_to_registro_id = db.Column(db.Integer, db.ForeignKey('registro.id'), nullable=True)
    transferred_registro = db.relationship('Registro', backref='no_shows_transferidos', foreign_keys=[transferred_to_registro_id])

    transfer_nome_motorista = db.Column(db.String(100))
    transfer_matricula_motorista = db.Column(db.String(50))
    transfer_cidade_entrega = db.Column(db.String(100))
    transfer_tipo_veiculo = db.Column(db.String(50))
    transfer_login_id = db.Column(db.Integer)
    transfer_gaiola_origem = db.Column(db.String(50))
    transfer_estacao_origem = db.Column(db.String(100))
    transfer_rua_origem = db.Column(db.String(100))
    transfer_data_hora_login_origem = db.Column(db.DateTime)

    def __repr__(self):
        return f"<NoShow(id={self.id}, matricula='{self.matricula}', gaiola='{self.gaiola}', status='{self.em_separacao}')>"

class Cidade(db.Model):
    __tablename__ = 'cidades'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cidade = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f"<Cidade {self.cidade}>"

class PacoteRastreado(db.Model):
    __tablename__ = 'pacote_rastreado'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pacote = db.Column(db.String(100), unique=True, nullable=False)
    etapa_id = db.Column(db.Integer, db.ForeignKey('etapa.id'), nullable=True)
    etapa = db.relationship('Etapa', backref='pacotes_rastreados')
    observacao = db.Column(db.Text, nullable=True)
    data_cadastro = db.Column(db.DateTime, default=get_data_hora_brasilia)

    rota_vinculada = db.Column(db.String(100), nullable=False)
    acoes = db.Column(db.String(255))

    def __repr__(self):
        return f'<PacoteRastreado {self.id_pacote} - Rota: {self.rota_vinculada}>'

# --- Definição do Modelo de Permissão ---
class Permissao(db.Model):
    __tablename__ = 'permissao'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome_pagina = db.Column(db.String(80), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<Permissao {self.nome_pagina}>'

# Tabela de associação para User e Permissao
user_permissoes = db.Table('user_permissoes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('permissao_id', db.Integer, db.ForeignKey('permissao.id'), primary_key=True)
)

# --- CLASSE USER (Modelo de Usuário Principal) ---
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # ATENÇÃO: Hashing de senha é fundamental para segurança em produção!
    password = db.Column(db.String(128), nullable=False) # Armazenará o hash da senha

    # === MÉTODOS DE HASHING DE SENHA REINTRODUZIDOS ===
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    matricula = db.Column(db.String(20), unique=True, nullable=True)
    nome_completo = db.Column(db.String(100), nullable=True)
    is_admin = db.Column(db.Boolean, default=False) # COLUNA is_admin ÚNICA AGORA
    ativo = db.Column(db.Boolean, default=True)

    # Coluna que armazena a lista de chaves de permissão em formato JSON (string)
    permissions = db.Column(db.Text, default='[]') # Use TEXT e manipule JSON

    # Relacionamento para permissões granulares baseadas em Permissao
    permissoes_objeto = db.relationship('Permissao', secondary=user_permissoes, lazy='subquery',
                                         backref=db.backref('users_with_access', lazy=True))

    # --- Métodos para UserMixin e Permissões ---
    def get_id(self):
        return str(self.id)

    def is_active(self):
        return self.ativo

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

    # Método para obter as permissões da coluna JSON
    def get_permissions_list(self):
        """Retorna a lista de chaves de permissão do campo 'permissions' (JSON)."""
        try:
            return json.loads(self.permissions)
        except (json.JSONDecodeError, TypeError):
            return []

    # Método para definir as permissões na coluna JSON
    def set_permissions_list(self, permissions_list):
        """Define a lista de chaves de permissão para o campo 'permissions' (JSON)."""
        self.permissions = json.dumps(permissions_list)

    # === LÓGICA DE HAS_PERMISSION AJUSTADA ===
    def has_permission(self, permission_key):
        """
        Verifica se o usuário tem uma permissão específica.
        Admins têm todas as permissões.
        Outros usuários têm permissões baseadas na coluna 'permissions' (JSON).
        """
        if self.is_admin:
            return True
        # Verifica se a chave está na lista de permissões obtida da coluna JSON
        return permission_key in self.get_permissions_list()

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"


class LogAtividade(db.Model):
    __tablename__ = 'log_atividade' # Adicionado nome da tabela
    # AJUSTE CRÍTICO: Adicionado autoincrement=True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, default=get_data_hora_brasilia) # Usar get_data_hora_brasilia
    # Coluna do ID do usuário, nomeada como 'user_id'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    
    # === DESCOMENTE ESTA LINHA AQUI! ===
    user = db.relationship('User', backref='logs_atividade') # Relacionamento com o modelo User
    
    acao = db.Column(db.String(255), nullable=False)
    detalhes = db.Column(db.Text, nullable=True)
    ip_origem = db.Column(db.String(45), nullable=True)

    def __repr__(self):
        return f"<LogAtividade {self.id} - {self.acao} - {self.timestamp}>"


# --- Função para Criar Permissões Iniciais (manter esta) ---
def criar_permissoes_iniciais():
    """Cria todas as permissões de página no banco de dados, se ainda não existirem."""
    # Garante que as PERMISSIONS do config.py estão disponíveis aqui
    # Esta função será chamada de app.py dentro do app_context
    paginas_para_permissao = list(PERMISSIONS.keys()) # Usa as chaves do seu dicionário PERMISSIONS

    for nome_pagina in paginas_para_permissao:
        permissao_existente = Permissao.query.filter_by(nome_pagina=nome_pagina).first()
        if not permissao_existente:
            nova_permissao = Permissao(nome_pagina=nome_pagina, descricao=PERMISSIONS[nome_pagina])
            db.session.add(nova_permissao)
            print(f"Permissão '{nome_pagina}' adicionada.")
    db.session.commit()
    print("Verificação e criação de permissões iniciais concluída.")