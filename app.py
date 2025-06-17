# app.py

# Importações principais do Flask e extensões
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, abort,current_app , session # Adicionado 'session'
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash # Adicionado/Confirmado ambos os hashes!
from collections import Counter
from io import BytesIO

# Importações de tempo e data
from datetime import datetime, timedelta, timezone # Adicionado 'timezone' para datetime.now(timezone.utc)
import pytz # Para fusos horários específicos se necessário para outras lógicas
from dateutil import tz # Adicionado de volta, pois você pode usá-lo em outros projetos para manipulação de TZ.
from functools import wraps # Para o decorador role_required (se você usar a lógica de permissões)

# Importações de SQLAlchemy e funções de banco de dados
from sqlalchemy import distinct, func, or_ # Adicionado 'or_' - comum para queries complexas

# Importações de componentes do seu projeto (models, forms, config)
from models import db, Login, Registro, NoShow, Etapa, Cidade, SituacaoPedido, PacoteRastreado, User, Permissao, LogAtividade
from forms import SistemaLoginForm, CadastroUsuarioForm, EditarUsuarioForm, NovaSenhaForm # Ajustado
from config import STATUS_EM_SEPARACAO, STATUS_REGISTRO_PRINCIPAL, REGISTROS_POR_PAGINA, get_data_hora_brasilia, PERMISSIONS
from sqlalchemy.orm import joinedload # Importe joinedload para carregar relacionamentos


# Outras importações (verifique se realmente usa cada uma no app.py)
import os
import threading # Se estiver usando threads no app principal
import random # Se estiver usando números aleatórios
import requests # Para requisições HTTP (APIs, feeds)
import feedparser # Para feeds RSS (se usar)
from math import ceil # Se usar funções matemáticas como ceil
from io import BytesIO # Se manipular bytes para streams/arquivos
import psycopg2 # **ATENÇÃO: Se não estiver usando PostgreSQL, REMOVA esta linha!**
from bs4 import BeautifulSoup # Para web scraping (se usar)
from forms import SistemaLoginForm, CadastroUsuarioForm, EditarUsuarioForm, NovaSenhaForm


# As linhas abaixo não são importações, são comentários, mas mantidas por sua solicitação.
# Removidas (Não usadas, duplicadas ou importadas de outro lugar):
# from mimetypes import inited # Não é um módulo comum para flask apps
# from flask_sqlalchemy import SQLAlchemy # db é inicializado em models.py
# current_app # Não é necessário aqui se login_manager for vinculado diretamente

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# 2. Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.fjurmbfvfuzhyrwkduav:Qaz241059#MLP140308@aws-0-us-east-2.pooler.supabase.com:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# Adicione estas linhas AQUI, após 'app = Flask(__name__)' e antes de qualquer rota
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'txt'} # Certifique-se de que está definido aqui!

# --- INICIALIZAÇÃO DO FLASK-LOGIN ---
login_manager = LoginManager() # Crie a instância do LoginManager
login_manager.init_app(app)    # VINCULE o LoginManager à sua aplicação Flask
login_manager.login_view = 'login2' # Define a rota para onde o Flask-Login deve redirecionar
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# Função de carregamento de usuário para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # CORRIGIDO: de Usuario para User
# --- FIM DA INICIALIZAÇÃO DO FLASK-LOGIN ---


# 3. Bind the SQLAlchemy db object to the Flask app


# 4. Initialize Flask-Migrate AQUI, depois de db.init_app(app)
migrate = Migrate(app, db) # ADICIONE ESTA LINHA

# --- Decorator para Controle de Acesso ---
def permission_required(pagina_nome):
    def decorator(f):
        @wraps(f)
        @login_required # Garante que o usuário esteja logado
        def decorated_function(*args, **kwargs):
            # Admin sempre tem acesso
            if current_user.is_admin:
                return f(*args, **kwargs)

            # Busca a permissão pelo nome da página
            permissao = Permissao.query.filter_by(nome_pagina=pagina_nome).first()

            if not permissao:
                flash(f'Erro: Permissão para "{pagina_nome}" não configurada no sistema.', 'danger')
                return abort(403) # Proibido se a permissão não existir

            # Verifica se o usuário tem esta permissão
            if permissao in current_user.permissoes:
                return f(*args, **kwargs)
            else:
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('dashboard')) # Redireciona para dashboard se não tiver permissão
        return decorated_function
    return decorator

# --- Decorator para Log de Atividades ---
from functools import wraps
from flask import request, redirect, current_app # Adicione current_app se não estiver lá
from flask_login import current_user # Certifique-se de importar current_user
# Importe db e LogAtividade de onde eles são definidos, ex: from models import db, LogAtividade

def log_activity(action_template, details_func=None):
    """
    Um decorador para logar atividades do usuário.

    Args:
        action_template (str): Um template de string para a ação,
                                pode conter '{user}'.
        details_func (callable, optional): Uma função que retorna detalhes adicionais.
                                          Recebe o 'username' capturado como argumento.
                                          Defaults to None.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Capture as informações do usuário e IP antes de executar a função decorada
            # Isso é CRUCIAL para rotas de logout, onde current_user mudará.
            initial_user_id = current_user.id if current_user.is_authenticated else None
            initial_username = current_user.username if current_user.is_authenticated else 'Desconhecido'
            ip_origem = request.remote_addr # Captura o IP de origem da requisição

            response = None
            exception_occurred = False

            try:
                # Executa a função original da rota
                response = f(*args, **kwargs)
            except Exception as e:
                # Loga o erro, mas permite que o traceback original seja propagado
                current_app.logger.error(f"Erro na função decorada '{f.__name__}': {e}", exc_info=True)
                exception_occurred = True
                raise # Re-lança a exceção para que o Flask a trate

            # Apenas loga a atividade se a função decorada não gerou uma exceção
            if not exception_occurred:
                # Determina se a resposta é considerada um "sucesso" para fins de log
                is_successful_response = False
                if isinstance(response, (str, dict)): # Render_template retorna str, jsonify retorna dict
                    is_successful_response = True
                elif isinstance(response, tuple) and len(response) > 1 and isinstance(response[1], int) and response[1] < 400:
                    # Para tuplas (response, status_code)
                    is_successful_response = True
                elif hasattr(response, 'status_code') and response.status_code < 400: # Para objetos Response, RedirectResponse
                    is_successful_response = True
                elif isinstance(response, type(redirect(''))): # Para objetos de redirect
                    is_successful_response = True

                if is_successful_response:
                    # Formata a ação principal usando o username capturado
                    acao = action_template.format(user=initial_username)

                    # Gera os detalhes do log, passando o username capturado para a lambda
                    detalhes = None
                    if details_func:
                        try:
                            # Chama details_func passando o username capturado
                            detalhes = details_func(initial_username, *args, **kwargs)
                        except Exception as e:
                            current_app.logger.error(f"Erro ao gerar detalhes do log para '{acao}': {e}", exc_info=True)
                            detalhes = "Detalhes do log indisponíveis devido a um erro."
                    else:
                        detalhes = acao # Fallback se não houver details_func

                    # Cria e salva o registro de log
                    log_entry = LogAtividade(
                        # === MUDANÇA AQUI: DE 'usuario_id' PARA 'user_id' ===
                        user_id=initial_user_id, # <--- Corrigido para 'user_id'
                        acao=acao,
                        detalhes=detalhes,
                        timestamp=datetime.now(pytz.utc), # Salva o timestamp em UTC
                        ip_origem=ip_origem
                    )
                    db.session.add(log_entry)
                    db.session.commit()
                else:
                    current_app.logger.warning(f"Atividade '{f.__name__}' não logada: resposta não foi bem-sucedida ou não reconhecida.")

            return response
        return decorated_function
    return decorator


# --- Funções Auxiliares (que usam constantes ou modelos e não estão em config.py) ---
def get_status_text(status_code):
    """Traduz o código numérico do status 'em_separacao' para texto amigável."""
    # Criar um mapeamento inverso para facilitar a busca
    status_map = {v: k for k, v in STATUS_EM_SEPARACAO.items()}
    text = status_map.get(status_code, 'DESCONHECIDO')
    return text.replace('_', ' ').title()


# DEFINIÇÃO DAS CONSTANTES DE STATUS (Removido se já estiverem em config.py, mas mantido para contexto se não estiver)
# ====================================================================
# STATUS_REGISTRO_PRINCIPAL = {
#     'AGUARDANDO_CARREGAMENTO': 'Aguardando Carregamento',
#     'CARREGAMENTO_LIBERADO': 'Carregamento Liberado',
#     'EM_CARREGAMENTO': 'Em Carregamento',
#     'EM_ROTA': 'Em Rota',
#     'FINALIZADO': 'Finalizado',
#     'CANCELADO': 'Cancelado'
# }

# Constantes para os estados de 'em_separacao' (Removido se já estiverem em config.py)
# STATUS_EM_SEPARACAO = {
#     'AGUARDANDO_MOTORISTA': 0,
#     'SEPARACAO': 1,
#     'FINALIZADO': 2,
#     'CANCELADO': 3,
#     'TRANSFERIDO': 4,
#     'AGUARDANDO_ENTREGADOR': 5
# }


def formata_data_hora(data_hora):
    if not data_hora:
        return 'Não Finalizado'
    tz_destino = pytz.timezone('America/Sao_Paulo')
    if isinstance(data_hora, datetime):
        if data_hora.tzinfo is None:
            # Se o datetime for naive, assume que já está no fuso horário local e o torna aware.
            data_hora_aware = tz_destino.localize(data_hora)
        else:
            # Se já for aware, converte para o fuso horário de destino.
            data_hora_aware = data_hora.astimezone(tz_destino)
        return data_hora_aware.strftime('%d/%m/%Y %H:%M:%S')
    return 'Erro de Formato Inesperado'

app.jinja_env.filters['formata_data_hora'] = formata_data_hora

def capitalize_words(text):
    if text:
        return ' '.join(word.capitalize() for word in text.split())
    return None


# --- Suas Rotas Existentes ---

# In a separate file like decorators.py or directly in app.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user # Assuming Flask-Login is used

def permission_required(permission_key):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Você precisa estar logado para acessar esta página.', 'warning')
                return redirect(url_for('login')) # Assuming a login route

            if not current_user.has_permission(permission_key):
                flash('Você não tem permissão para acessar esta página.', 'danger')
                abort(403) # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# You might also have an admin_required if it's simpler for some cases
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Você precisa estar logado para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('Você não tem permissão de administrador para acessar esta página.', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# --- Suas rotas ---

@app.route('/', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        matricula = request.form['matricula']
        nome = request.form['nome'].title()
        rota = request.form.get('rota', '').title()
        tipo_entrega = request.form.get('tipo_entrega', '').title()
        cidade_entrega = request.form.get('cidade_entrega', '').title()
        rua = request.form.get('rua', '').title()

        data_hora_atual = get_data_hora_brasilia()
        data_hoje = data_hora_atual.date()  # Pegando só a data (sem hora)

        with app.app_context():
            user_login = db.session.query(Login).filter_by(matricula=matricula).first()

            if user_login:
                login_id = user_login.id
                tipo_veiculo = user_login.tipo_veiculo

                ## =========================
                ## 🔥 Verificação para No-Show (matricula 0001)
                if matricula == '0001' and tipo_entrega == 'No-Show':
                    if tipo_veiculo.lower() != 'moto':
                        registro_existente = db.session.query(NoShow).filter(
                            NoShow.matricula == matricula,
                            NoShow.tipo_entrega == tipo_entrega,
                            db.func.date(NoShow.data_hora_login) == data_hoje
                        ).first()

                        if registro_existente:
                            erro = f"Já existe um registro com matrícula {matricula} e tipo de entrega {tipo_entrega} para hoje."
                            print(erro)
                            return render_template('login.html', erro=erro)

                    no_show_reg = NoShow(
                        nome=nome,
                        matricula=matricula,
                        rota=rota,
                        tipo_entrega=tipo_entrega,
                        cidade_entrega=cidade_entrega,
                        rua=rua,
                        data_hora_login=data_hora_atual,
                        tipo_veiculo=tipo_veiculo,
                        em_separacao=0,
                        finalizada=0,
                        hora_finalizacao=None,
                        cancelado=0,
                        transferred_to_registro_id=None,
                        login_id=login_id
                    )
                    db.session.add(no_show_reg)
                    db.session.commit()
                    new_session_id = no_show_reg.id
                    print(f"Nova sessão No-Show criada com ID: {new_session_id}")
                    return redirect(url_for('status_motorista', matricula=matricula, registro_id=new_session_id))

                ## =========================
                ## 🔥 Verificação para registros normais (qualquer matrícula)
                if tipo_veiculo.lower() != 'moto':
                    registro_existente = db.session.query(Registro).filter(
                        Registro.matricula == matricula,
                        Registro.tipo_entrega == tipo_entrega,
                        db.func.date(Registro.data_hora_login) == data_hoje
                    ).first()

                    if registro_existente:
                        erro = f"Já existe um registro com matrícula {matricula} e tipo de entrega {tipo_entrega} para hoje."
                        print(erro)
                        return render_template('login.html', erro=erro)

                registro = Registro(
                    nome=nome,
                    matricula=matricula,
                    rota=rota,
                    tipo_entrega=tipo_entrega,
                    cidade_entrega=cidade_entrega,
                    rua=rua,
                    data_hora_login=data_hora_atual,
                    tipo_veiculo=tipo_veiculo,
                    em_separacao=0,
                    finalizada=0,
                    hora_finalizacao=None,
                    cancelado=0,
                    login_id=login_id
                )
                db.session.add(registro)
                db.session.commit()
                new_session_id = registro.id
                print(f"Nova sessão Registro criada com ID: {new_session_id}")
                return redirect(url_for('status_motorista', matricula=matricula, registro_id=new_session_id))

            else:
                erro = 'Número de registro não cadastrado. Por favor, cadastre-se primeiro.'
                print(f"Tentativa de login falhou para matrícula {matricula}: Número de registro não cadastrado.")
                return render_template('login.html', erro=erro)

    return render_template('login.html', erro=erro)

#----Fim da Rota Lgin -----

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login2' # ESSENCIAL: Diz ao Flask-Login qual é a rota de login
login_manager.login_message_category = 'info' # Categoria para mensagens de flash padrão do Flask-Login
login_manager.login_message = 'Por favor, faça login para acessar esta página.' # Mensagem padrão

@login_manager.user_loader
def load_user(user_id):
    # Esta linha é o problema. TEM QUE SER 'User', NÃO 'Usuario'.
    return User.query.get(int(user_id))

# --- ROTA /login2 (para referência, ela deve estar no seu app.py) ---
@app.route('/login2', methods=['GET', 'POST'])
def login2():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = SistemaLoginForm()

    if form.validate_on_submit():
        print(f"DEBUG: Formulário enviado. Email: {form.email.data}")
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            print(f"DEBUG: Usuário encontrado: {user.username}. Tentando verificar senha.")
            # ATENÇÃO: A comparação de senha em texto puro (user.password == form.password.data)
            # é EXTREMAMENTE INSEGURA para produção. Use sempre hashing de senhas.
            if user.password == form.password.data: # AGORA COMPARANDO TEXTO PURO!
                print("DEBUG: Senha CORRETA (comparação em texto puro)!")
                
                if user.is_active:
                    print("DEBUG: Usuário está ATIVO. Realizando login.")
                    login_user(user)
                    
                    # --- CORREÇÃO AQUI: Salva o timestamp como naive UTC ---
                    log_entry = LogAtividade(
                        user_id=user.id,
                        acao='Login',
                        detalhes=f'Usuário {user.username} logou no sistema.',
                        timestamp=datetime.now(pytz.utc).replace(tzinfo=None), # Agora, o timestamp é salvo como naive UTC
                        ip_origem=request.remote_addr
                    )
                    db.session.add(log_entry)
                    db.session.commit()

                    flash('Login bem-sucedido!', 'success')
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('dashboard'))
                else:
                    print("DEBUG: Usuário INATIVO. Login recusado.")
                    flash('Sua conta está inativa. Entre em contato com o administrador.', 'warning')
            else:
                print("DEBUG: Senha INCORRETA.")
                flash('Login sem sucesso. Verifique seu email e senha.', 'danger')
        else:
            print("DEBUG: Usuário NÃO encontrado para o email fornecido.")
            flash('Login sem sucesso. Verifique seu email e senha.', 'danger')
    else:
        print("DEBUG: Formulário NÃO validado. Erros: ", form.errors)
    return render_template('login2.html', form=form)



# --- Exemplo de Registro de Usuário (ajustar conforme seu código) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        new_user = User(username=form.username.data, email=form.email.data, 
                        matricula=form.matricula.data, nome_completo=form.nome_completo.data,
                        is_admin=form.is_admin.data)
        # Salva a senha em texto puro diretamente
        new_user.password = form.password.data 
        db.session.add(new_user)
        db.session.commit()
        flash('Usuário registrado com sucesso!', 'success')
        return redirect(url_for('login2'))
    return render_template('cadastro_usuario.html', form=form) # Assumindo que cadastro_usuario.html é para registro


@app.route('/logout')
@login_required # Garante que apenas usuários logados podem acessar esta rota
@log_activity(
    action_template='Logout de {user} (Sistema)',
    # A lambda agora ACEITA UM ARGUMENTO (user_name)
    details_func=lambda user_name, *args, **kwargs: f'Usuário {user_name} deslogou o sistema de rastreamento.'
)
def logout():
    logout_user() # Esta linha executa o logout. O decorador já capturou o username antes.
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login2'))




# --- Rotas de Gerenciamento de Usuários (APENAS ADMIN) ---

@app.route('/usuarios')
@login_required 
@permission_required('Gerenciar Usuários') # Exige permissão para esta página
def listar_usuarios():
    usuarios = Usuario.query.all()
    return render_template('listar_usuarios.html', usuarios=usuarios)

@app.route('/usuario/novo', methods=['GET', 'POST'])
@login_required 
@permission_required('Gerenciar Usuários') # Exige permissão para esta página
def novo_usuario():
    form = RegistroUsuarioForm()
    # Preencher as opções de páginas/permissões dinamicamente
    form.paginas_acesso.choices = [(p.id, p.nome_pagina) for p in Permissao.query.order_by(Permissao.nome_pagina).all()]

    if form.validate_on_submit():
        user = Usuario(username=form.username.data, email=form.email.data, is_admin=form.is_admin.data, matricula="N/A", nome_completo=form.username.data) # Added matricula and nome_completo as required by Usuario model
        user.set_password(form.password.data)

        # Adicionar as permissões selecionadas
        selected_perms = Permissao.query.filter(Permissao.id.in_(form.paginas_acesso.data)).all()
        user.permissoes.extend(selected_perms)

        db.session.add(user)
        db.session.commit()

        # Logar a criação do usuário
        log_entry = LogAtividade(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            acao='Criação de Usuário (Sistema)',
            detalhes=f'Usuário {user.username} (ID: {user.id}) criado por {current_user.username if current_user.is_authenticated else "sistema"}. Permissões: {[p.nome_pagina for p in user.permissoes]}',
            ip_origem=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(f'Usuário {form.username.data} cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_usuarios'))
    return render_template('novo_usuario.html', form=form)

# app.py (sua rota de edição de usuário ajustada)

# Certifique-se de que está importando o nome correto do formulário
from forms import SistemaLoginForm, CadastroUsuarioForm, EditarUsuarioForm, NovaSenhaForm # <-- AQUI!
#                   ^ Use o nome exato da classe definida em forms.py



@app.route('/usuario/deletar/<int:usuario_id>', methods=['POST'])
@login_required 
@permission_required('Gerenciar Usuários') # Exige permissão para esta página
def deletar_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.id == current_user.id:
        flash('Você não pode deletar sua própria conta.', 'danger')
        return redirect(url_for('listar_usuarios'))
    
    # Logar a exclusão do usuário
    log_entry = LogAtividade(
        usuario_id=current_user.id if current_user.is_authenticated else None,
        acao='Exclusão de Usuário (Sistema)',
        detalhes=f'Usuário {usuario.username} (ID: {usuario.id}) excluído por {current_user.username if current_user.is_authenticated else "sistema"}.',
        ip_origem=request.remote_addr
    )
    db.session.add(log_entry) # Adiciona antes de deletar o usuário
    db.session.delete(usuario)
    db.session.commit()

    flash('Usuário deletado com sucesso!', 'success')
    return redirect(url_for('listar_usuarios'))

@app.route('/usuario/alterar_senha/<int:usuario_id>', methods=['GET', 'POST'])
@login_required 
@permission_required('Gerenciar Usuários') # ou 'Alterar Própria Senha' se for para o próprio usuário
def alterar_senha_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    form = NovaSenhaForm()

    if form.validate_on_submit():
        usuario.set_password(form.password.data)
        db.session.commit()

        log_entry = LogAtividade(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            acao='Alteração de Senha (Sistema)',
            detalhes=f'Senha do usuário {usuario.username} (ID: {usuario.id}) alterada por {current_user.username if current_user.is_authenticated else "sistema"}.',
            ip_origem=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(f'Senha do usuário {usuario.username} atualizada com sucesso!', 'success')
        return redirect(url_for('listar_usuarios'))
    return render_template('alterar_senha_usuario.html', form=form, usuario=usuario)


# --- Rotas de Log de Atividades ---
@app.route('/logs')
@login_required 
@permission_required('Visualizar Logs') # Uma nova permissão
def visualizar_logs():
    logs = LogAtividade.query.order_by(LogAtividade.data_hora.desc()).all()
    return render_template('visualizar_logs.html', logs=logs)

@app.route('/cadastro_usuario', methods=['GET', 'POST'])
@login_required # Recomendado: Apenas usuários logados (geralmente admins) podem cadastrar
@permission_required('cadastro_usuario')
def cadastro_usuario():
    # Opcional: Você pode adicionar uma verificação se o usuário atual é admin
    # if not current_user.is_admin:
    #    flash('Você não tem permissão para cadastrar usuários.', 'danger')
    #    return redirect(url_for('painel_gerencial')) # Ou outra rota de sua escolha

    form = CadastroUsuarioForm()
    if form.validate_on_submit():
        # ATENÇÃO: Senha agora armazenada em texto puro. EXTREMAMENTE INSEGURO para produção!
        # REMOVIDA: hashed_password = generate_password_hash(form.password.data)
        new_user = User( # Alterado de 'Usuario' para 'User' para corresponder ao models.py
            username=form.username.data,
            email=form.email.data,
            password=form.password.data, # ALTERADO: Salva a senha em texto puro no campo 'password'
            matricula=form.matricula.data,
            nome_completo=form.nome_completo.data,
            is_admin=form.is_admin.data
        )
        db.session.add(new_user)
        db.session.commit()

        # Logar a criação do usuário
        log_entry = LogAtividade(
            user_id=current_user.id, # ALTERADO: de 'usuario_id' para 'user_id'
            acao=f'Novo usuário "{new_user.username}" cadastrado',
            detalhes=f'Email: {new_user.email}, Matrícula: {new_user.matricula}. Admin: {new_user.is_admin}',
            ip_origem=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(f'Usuário {new_user.username} cadastrado com sucesso!', 'success')
        return redirect(url_for('painel_gerencial')) # Redireciona após o cadastro

    # Se GET ou se o formulário não for validado (erros)
    return render_template('cadastro_usuario.html', form=form)


# --- Integrando as permissões nas suas rotas existentes (exemplos) ---
# Você precisará adicionar permission_required em todas as rotas que deseja proteger

@app.route('/status_entrega')
@login_required
@permission_required('status_entrega')
def status_entrega():
    # Você pode adicionar filtros ou paginação aqui se a lista de registros for muito grande
    registros = Registro.query.order_by(Registro.data_hora_login.desc()).all()
    return render_template('status_entrega.html', registros=registros)

# --- Rota API para Atualizar Etapa de um Registro (POST) ---
@app.route('/api/atualizar_etapa_registro/<int:registro_id>', methods=['POST'])
def api_atualizar_etapa_registro(registro_id):
    registro = Registro.query.get(registro_id)
    if not registro:
        return jsonify({"success": False, "message": "Registro não encontrado."}), 404

    nova_etapa_id = request.json.get('nova_etapa_id')
    if nova_etapa_id is None:
        return jsonify({"success": False, "message": "ID da nova etapa não fornecido."}), 400

    etapa = Etapa.query.get(nova_etapa_id)
    if not etapa:
        return jsonify({"success": False, "message": "Etapa inválida."}), 400

    try:
        registro.etapa = etapa
        db.session.commit()
        # Ao retornar o nome da etapa, garanta que é o nome correto do objeto Etapa
        return jsonify({"success": True, "message": "Etapa atualizada com sucesso!", "etapa_nome": etapa.nome_etapa}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar etapa do registro {registro_id}: {e}")
        return jsonify({"success": False, "message": f"Erro ao atualizar etapa: {str(e)}"}), 500

# --- Rota API para Listar todas as Etapas (GET) ---
@app.route('/api/etapas')
def api_get_etapas():
    etapas = Etapa.query.order_by(Etapa.id).all()
    return jsonify([{"id": etapa.id, "nome": etapa.nome_etapa, "descricao": etapa.descricao} for etapa in etapas])



@app.route('/buscar_nome', methods=['POST'])
def buscar_nome():
    """
    Busca o nome de um usuário na tabela 'login' pela matrícula.
    Usado para preencher o campo nome automaticamente no formulário de login.
    """
    data = request.get_json()
    matricula = data.get('matricula')
    if not matricula:
        return jsonify({'erro': 'Número de registro não informado'}), 400
    with app.app_context():
        usuario = db.session.query(Login.nome).filter_by(matricula=matricula).first()
    if usuario and usuario.nome:
        return jsonify({'nome': usuario.nome.title()})
    else:
        return jsonify({'nome': None})

#Busca as cidades#
@app.route('/buscar_cidades')
def buscar_cidades():
    """
    Retorna uma lista de cidades que correspondem a um termo de busca (para autocomplete).
    """
    termo = request.args.get('termo', '').lower()
    with app.app_context():
        # Usando .ilike para busca case-insensitive no PostgreSQL
        cidades = db.session.query(Cidade.cidade).filter(Cidade.cidade.ilike(f'%{termo}%')).limit(10).all()
    return jsonify([c[0].title() for c in cidades])

# --- Início da Rota Status Motorista ---
@app.route('/status_motorista/<string:matricula>', methods=['GET'])
def status_motorista(matricula):
    """
    Renderiza a página de status do motorista, passando a matrícula.
    """
    print(f"DEBUG: /status_motorista/{matricula} - Rota acessada.")
    # Passa a matrícula para o template
    return render_template('status_motorista.html', matricula=matricula)

# --- Rota API para buscar o status do motorista pela matrícula (AJUSTADA) ---
@app.route('/api/status_registro_by_matricula/<string:matricula>', methods=['GET'])
def api_status_registro_by_matricula(matricula):
    print(f"DEBUG: /api/status_registro_by_matricula/{matricula} - Rota API acessada.")

    registro_id = request.args.get('registro_id')
    registro_principal = None
    tabela_origem = None

    with current_app.app_context():
        # --- Lógica de Busca do Registro Principal ---
        if registro_id:
            try:
                registro_id_int = int(registro_id)
                registro_principal = db.session.query(Registro).filter_by(id=registro_id_int).first()
                if registro_principal:
                    tabela_origem = 'registros'
                    print(f"DEBUG: Registro encontrado em 'registros' pelo ID: {registro_id_int}")
                else:
                    registro_principal = db.session.query(NoShow).filter_by(id=registro_id_int).first()
                    if registro_principal:
                        tabela_origem = 'no_show'
                        print(f"DEBUG: Registro encontrado em 'no_show' pelo ID: {registro_id_int}")
                    else:
                        print(f"DEBUG: Nenhum registro encontrado com ID {registro_id_int} em Registro ou NoShow.")
                        return jsonify({'message': 'Nenhum registro encontrado para o ID especificado.'}), 404
            except ValueError:
                print(f"DEBUG: registro_id inválido: {registro_id}")
                return jsonify({'message': 'ID de registro inválido.'}), 400
        else:
            registro_principal = db.session.query(Registro).filter(
                Registro.matricula == matricula,
                Registro.finalizada == 0,
                Registro.cancelado == 0
            ).order_by(Registro.data_hora_login.desc()).first()

            if registro_principal:
                tabela_origem = 'registros'
                print(f"DEBUG: Registro ATIVO encontrado em 'registros' para matrícula: {matricula}")
            else:
                registro_principal = db.session.query(Registro).filter(
                    Registro.matricula == matricula,
                    or_(Registro.finalizada == 1, Registro.cancelado == 1)
                ).order_by(Registro.data_hora_login.desc()).first()
                if registro_principal:
                    tabela_origem = 'registros'
                    print(f"DEBUG: Registro FINALIZADO/CANCELADO encontrado em 'registros' para matrícula: {matricula}")
                else:
                    registro_principal = db.session.query(NoShow).filter(
                        NoShow.matricula == matricula,
                        NoShow.finalizada == 0,
                        NoShow.cancelado == 0,
                    ).order_by(NoShow.data_hora_login.desc()).first()
                    if registro_principal:
                        tabela_origem = 'no_show'
                        print(f"DEBUG: Registro ATIVO encontrado em 'no_show' para matrícula: {matricula}")
                    else:
                        registro_principal = db.session.query(NoShow).filter(
                            NoShow.matricula == matricula,
                            or_(NoShow.finalizada == 1, NoShow.cancelado == 1)
                        ).order_by(NoShow.data_hora_login.desc()).first()
                        if registro_principal:
                            tabela_origem = 'no_show'
                            print(f"DEBUG: Registro FINALIZADO/CANCELADO encontrado em 'no_show' para matrícula: {matricula}")

        # --- Construção da Resposta JSON ---
        if registro_principal:
            response_data = {
                'id': registro_principal.id,
                'nome': getattr(registro_principal, 'nome', 'N/A'),
                'matricula': getattr(registro_principal, 'matricula', 'N/A'),
                'data_hora_login': registro_principal.data_hora_login.strftime('%Y-%m-%d - %H:%M') if registro_principal.data_hora_login else None,
                'finalizada': getattr(registro_principal, 'finalizada', 0),
                'cancelado': getattr(registro_principal, 'cancelado', 0),
                'em_separacao': getattr(registro_principal, 'em_separacao', 0),
                'tipo_entrega': getattr(registro_principal, 'tipo_entrega', 'N/A'),
                'tabela_origem': tabela_origem,
                'estado': None
            }

            response_data['rota'] = 'Aguarde'
            response_data['cidade_entrega'] = 'Aguarde'
            response_data['rua'] = 'Aguarde'
            response_data['gaiola'] = 'Aguarde'
            response_data['estacao'] = 'Aguarde'


            if tabela_origem == 'registros':
                response_data['rota'] = getattr(registro_principal, 'rota', 'Aguarde')
                response_data['cidade_entrega'] = getattr(registro_principal, 'cidade_entrega', 'Aguarde')
                response_data['rua'] = getattr(registro_principal, 'rua', 'Aguarde')
                response_data['gaiola'] = getattr(registro_principal, 'gaiola', 'Aguarde')
                response_data['estacao'] = getattr(registro_principal, 'estacao', 'Aguarde')

                if response_data['tipo_entrega'] == 'No-Show':
                    # Agora, a busca em no_show usa matricula '0001' e a rota do registro principal
                    noshow_detalhes = db.session.query(NoShow).filter(
                        NoShow.matricula == '0001', # <<< Matrícula fixa '0001'
                        NoShow.gaiola == registro_principal.rota # Vínculo pela rota/gaiola
                    ).order_by(NoShow.data_hora_login.desc()).first() # Pega o mais recente para essa rota e 0001

                    if noshow_detalhes:
                        print(f"DEBUG: Dados complementares de NoShow encontrados e usados (NoShow ID: {noshow_detalhes.id}, Matrícula '0001').")
                        response_data['rua'] = getattr(noshow_detalhes, 'rua', 'Aguarde')
                        response_data['gaiola'] = getattr(noshow_detalhes, 'gaiola', 'Aguarde')
                        response_data['estacao'] = getattr(noshow_detalhes, 'estacao', 'Aguarde')
                    else:
                        print(f"DEBUG: Registro de 'No-Show' em 'registros' (ID: {registro_principal.id}) sem correspondência em 'no_show' (matrícula '0001' e rota {registro_principal.rota}).")

            elif tabela_origem == 'no_show':
                response_data['rota'] = getattr(registro_principal, 'gaiola', 'Aguarde')
                response_data['rua'] = getattr(registro_principal, 'rua', 'Aguarde')
                response_data['gaiola'] = getattr(registro_principal, 'gaiola', 'Aguarde')
                response_data['estacao'] = getattr(registro_principal, 'estacao', 'Aguarde')

            print(f"DEBUG: Dados de resposta final: {response_data}")
            return jsonify(response_data)
        else:
            print(f"DEBUG: Nenhum registro principal encontrado para matrícula {matricula} e ID {registro_id}.")
            return jsonify({'message': 'Nenhum registro encontrado para esta matrícula e ID.'}), 404

### Rota de atualização

REGISTROS_POR_PAGINA = 10 # Defina o número de registros por página
def permission_required(permission):
    """
    Um decorador para verificar se o usuário logado tem uma permissão específica.
    Redireciona para 'menu_principal' com mensagem de erro se a permissão for negada.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # --- DEBUG PRINTS INÍCIO ---
            print(f"\n--- Verificando Permissão para: {f.__name__} ---")
            print(f"Permissão Requerida: '{permission}'")
            print(f"Usuário Autenticado: {current_user.is_authenticated}")
            
            if current_user.is_authenticated:
                print(f"ID do Usuário: {current_user.id}")
                print(f"Nome de Usuário: {current_user.username}")
                print(f"É Administrador: {current_user.is_admin}")
                
                # Para ver as permissões do usuário como uma lista
                user_perms_list = current_user.get_permissions_list() 
                print(f"Permissões do Usuário (da coluna JSON): {user_perms_list}")
                
                # Verifique se a permissão requerida está na lista do usuário
                has_req_perm = current_user.has_permission(permission)
                print(f"User.has_permission('{permission}'): {has_req_perm}")
            else:
                print("Usuário não autenticado.")
            # --- DEBUG PRINTS FIM ---

            if not current_user.is_authenticated or not current_user.has_permission(permission):
                flash('Você não tem permissão para acessar esta página.', 'danger')
                print(f"*** Acesso NEGADO para '{current_user.username if current_user.is_authenticated else 'Anônimo'}' à página '{permission}' ***")
                return redirect(url_for('menu_principal'))
            
            print(f"--- Acesso PERMITIDO para '{current_user.username}' à página '{permission}' ---\n")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/registros') # Ajuste a rota para o seu endpoint
@login_required # Garante que o usuário esteja logado
@permission_required('registros') # Exige a permissão 'Acessar Registros'
def registros():
    

    page = request.args.get('pagina', 1, type=int)
    per_page = 10 # Quantidade de itens por página

    rota = request.args.get('rota')
    tipo_entrega = request.args.get('tipo_entrega')
    cidade = request.args.get('cidade')
    em_separacao = request.args.get('em_separacao') # <--- CAPTURA O FILTRO DE EM_SEPARACAO

    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    # Query inicial para todos os registros
    query = Registro.query

    # Aplica filtros opcionais
    if rota:
        query = query.filter(Registro.rota.ilike(f'%{rota}%'))
    if tipo_entrega:
        query = query.filter(Registro.tipo_entrega == tipo_entrega)
    if cidade:
        query = query.filter(Registro.cidade_entrega.ilike(f'%{cidade}%'))

    # Adiciona filtro por em_separacao, se fornecido
    if em_separacao:
        query = query.filter(Registro.em_separacao == int(em_separacao)) # <--- APLICA O FILTRO DE EM_SEPARACAO

    # Filtro por data
    if data_inicio_str:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            query = query.filter(Registro.data_hora_login >= data_inicio)
        except ValueError:
            flash("Formato de data inicial inválido. Use💼-MM-DD.", 'danger')
            data_inicio_str = '' # Limpa para não preencher o campo no template
    if data_fim_str:
        try:
            # Inclui até o final do dia
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(Registro.data_hora_login <= data_fim)
        except ValueError:
            flash("Formato de data final inválido. Use💼-MM-DD.", 'danger')
            data_fim_str = '' # Limpa para não preencher o campo no template

    # Ordena os resultados (ex: mais recentes primeiro)
    query = query.order_by(Registro.data_hora_login.asc()) # Alterado para ordem ascendente (mais antigos primeiro)

    # Paginação
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Obtenha as cidades distintas para o filtro
    cidades_disponiveis = [c.cidade for c in Cidade.query.order_by(Cidade.cidade).all()]

    return render_template('registros.html',
                           registros=pagination.items,
                           pagina=pagination.page,
                           total_paginas=pagination.pages,
                           total_registros=pagination.total,
                           rota=rota or '',
                           tipo_entrega=tipo_entrega or '',
                           cidade=cidade or '',
                           em_separacao=em_separacao or '', # <--- PASSA O VALOR DE EM_SEPARACAO DE VOLTA PARA O TEMPLATE
                           data_inicio=data_inicio_str or '',
                           data_fim=data_fim_str or '',
                           cidades=cidades_disponiveis)

@app.route('/api/registros_data')
def api_registros_data():
    page = request.args.get('pagina', 1, type=int)
    per_page = REGISTROS_POR_PAGINA # Certifique-se de que REGISTROS_POR_PAGINA está definido

    rota_filtro = request.args.get('rota')
    tipo_entrega_filtro = request.args.get('tipo_entrega')
    cidade_filtro = request.args.get('cidade')
    em_separacao_filtro_str = request.args.get('em_separacao')

    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    query = Registro.query

    if rota_filtro:
        query = query.filter(Registro.rota.ilike(f'%{rota_filtro}%'))
    if tipo_entrega_filtro:
        query = query.filter(Registro.tipo_entrega == tipo_entrega_filtro)
    if cidade_filtro:
        query = query.filter(Registro.cidade_entrega.ilike(f'%{cidade_filtro}%'))

    # --- INÍCIO DA CORREÇÃO ---
    if not em_separacao_filtro_str:
        # Quando nenhum filtro de em_separacao é selecionado (opção "Todos" no frontend)
        # Excluir registros que estão "Aguardando Transferência" (em_separacao = 2)
        # E que não estão finalizados nem cancelados.
        query = query.filter(
            Registro.finalizada == 0,
            Registro.cancelado == 0,
            Registro.em_separacao != 2 # <--- ESTA É A LINHA CHAVE DA CORREÇÃO
        )
    else:
        # Se um filtro específico de em_separacao foi selecionado
        try:
            em_separacao_filtro_int = int(em_separacao_filtro_str)
            if em_separacao_filtro_int == 0:
                query = query.filter(
                    Registro.em_separacao == 0,
                    Registro.finalizada == 0,
                    Registro.cancelado == 0
                )
            elif em_separacao_filtro_int == 1:
                query = query.filter(
                    Registro.em_separacao == 1,
                    Registro.finalizada == 0,
                    Registro.cancelado == 0
                )
            elif em_separacao_filtro_int == 2:
                # Se o filtro "Aguardando Transferência" (valor 2) é selecionado,
                # então inclua esses registros.
                query = query.filter(
                    Registro.em_separacao == 2,
                    Registro.finalizada == 0,
                    Registro.cancelado == 0
                )
            elif em_separacao_filtro_int == 3:
                query = query.filter(Registro.finalizada == 1)
            elif em_separacao_filtro_int == 4:
                query = query.filter(Registro.cancelado == 1)
            # Adicione aqui se tiver o status 5 para "Finalizado" no backend
            # elif em_separacao_filtro_int == 5:
            #     query = query.filter(Registro.finalizada == 1)
        except ValueError:
            print(f"ATENÇÃO: Valor de filtro 'em_separacao' inválido: {em_separacao_filtro_str}")
            pass
    # --- FIM DA CORREÇÃO ---

    if data_inicio_str:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            query = query.filter(Registro.data_hora_login >= data_inicio)
        except ValueError:
            pass
    if data_fim_str:
        try:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(Registro.data_hora_login <= data_fim)
        except ValueError:
            pass

    query = query.order_by(Registro.data_hora_login.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # --- INÍCIO DA LÓGICA DE VERIFICAÇÃO E ATUALIZAÇÃO AUTOMÁTICA ---
    print("\n--- INÍCIO DA VERIFICAÇÃO DE AUTOMAÇÃO DE REGISTROS (API) ---")
    
    # Obtenha *todos* os registros NoShow que tem matrícula '0001' e estão aptos a serem transferidos
    no_shows_ativos = NoShow.query.filter_by(
        matricula='0001', # Adiciona filtro por matricula '0001'
        cancelado=0,
        finalizada=0
    ).all()
    print(f"DEBUG: Encontrados {len(no_shows_ativos)} registros NoShow ativos para possível correspondência (matricula 0001).")
    
    no_show_chaves_rota = set()
    for ns in no_shows_ativos:
        gaiola_clean = str(ns.gaiola).strip() if ns.gaiola is not None else None
        if gaiola_clean:
            no_show_chaves_rota.add(gaiola_clean)
    
    print(f"DEBUG: Rotas de NoShow ativos para correspondência: {no_show_chaves_rota}")

    registros_json = []

    for reg in pagination.items:
        print(f"\n--- Processando Registro ID: {reg.id} ---")
        print(f"DEBUG: Status atual de Registro.em_separacao: {reg.em_separacao}")
        print(f"DEBUG: Rota do Registro: '{reg.rota}'")
        print(f"DEBUG: Cidade de Entrega do Registro: '{reg.cidade_entrega}'")

        registro_rota_clean = str(reg.rota).strip() if reg.rota is not None else None
        
        # Condição de Elegibilidade para o Registro Principal
        # Só se o status atual for 0 E não for já 2
        if reg.em_separacao == 0 and reg.em_separacao != 2:
            print(f"DEBUG: Registro ID {reg.id} é elegível para automação (status 0).")
            
            # A correspondência agora é APENAS pela rota do Registro estar na lista de rotas dos NoShow ativos
            if registro_rota_clean in no_show_chaves_rota:
                print(f"DEBUG: CORRESPONDÊNCIA ENCONTRADA para Registro ID {reg.id} (Rota: '{registro_rota_clean}') com um NoShow ativo (Matricula 0001)!")
                print(f"DEBUG: Atualizando Registro ID {reg.id}. Status 'em_separacao' de {reg.em_separacao} para 2.")
                reg.em_separacao = 2 # <--- AGORA SETA PARA O NÚMERO 2
                db.session.add(reg)
            else:
                print(f"DEBUG: NENHUM No-Show correspondente ATIVO (Matricula 0001) encontrado para a Rota '{registro_rota_clean}' do Registro ID {reg.id}.")
        else:
            print(f"DEBUG: Registro ID {reg.id} (Status {reg.em_separacao}) NÃO elegível para automação (não está em 0 ou já está em 2).")

        registros_json.append({
            'id': reg.id,
            'data_hora_login': reg.data_hora_login.strftime('%Y-%m-%d %H:%M:%S') if reg.data_hora_login else None,
            'nome': reg.nome,
            'matricula': reg.matricula,
            'rota': reg.rota,
            'tipo_entrega': reg.tipo_entrega,
            'cidade_entrega': reg.cidade_entrega,
            'hora_finalizacao': reg.hora_finalizacao.strftime('%Y-%m-%d %H:%M:%S') if reg.hora_finalizacao else None,
            'em_separacao': reg.em_separacao,
            'finalizada': reg.finalizada,
            'cancelado': reg.cancelado
        })

    try:
        if db.session.dirty: 
            db.session.commit()
            print("\nDEBUG: Commits automáticos de status '2' para a página atual REALIZADOS.")
        else:
            print("\nDEBUG: NENHUMA alteração pendente para commitar para a página atual.")
    except Exception as e:
        db.session.rollback()
        print(f"\nERRO: Falha ao commitar atualizações automáticas de status na API: {e}")
        return jsonify({"error": "Erro interno ao processar registros."}), 500

    print("--- FIM DA VERIFICAÇÃO DE AUTOMAÇÃO DE REGISTROS (API) ---\n")

    return jsonify({
        'records': registros_json,
        'pagina': pagination.page,
        'total_paginas': pagination.pages,
        'total_registros': pagination.total
    })

@app.route('/api/current_active_records')
def api_current_active_records():
    """
    Retorna todos os registros considerados 'ativos' (não finalizados ou cancelados).
    Esta rota é usada para atualizações incrementais no frontend e não aplica
    filtros de data ou paginação.
    """
    try:
        # Filtra os registros que não foram finalizados (finalizada = 0)
        # e que não foram cancelados (cancelado = 0).
        # Agora, também exclui por padrão os registros com em_separacao = 2 (Aguardando Transferência)
        query = Registro.query.filter(
            Registro.finalizada == 0,
            Registro.cancelado == 0,
            Registro.em_separacao != 2 # <--- Adicionada esta linha para excluir por padrão
        )
        
        # Opcional: Ordenar os registros para garantir uma ordem consistente no frontend
        # Por exemplo, por data de login, do mais antigo para o mais novo
        query = query.order_by(Registro.data_hora_login.asc()) 

        active_registros = query.all()

        registros_json = []
        for reg in active_registros:
            registros_json.append({
                'id': reg.id,
                'data_hora_login': reg.data_hora_login.strftime('%Y-%m-%d %H:%M:%S') if reg.data_hora_login else None,
                'nome': reg.nome,
                'matricula': reg.matricula,
                'rota': reg.rota,
                'tipo_entrega': reg.tipo_entrega,
                'cidade_entrega': reg.cidade_entrega,
                'hora_finalizacao': reg.hora_finalizacao.strftime('%Y-%m-%d %H:%M:%S') if reg.hora_finalizacao else None,
                'em_separacao': reg.em_separacao,
                'finalizada': reg.finalizada,
                'cancelado': reg.cancelado
                # Não é necessário incluir 'updated_at' aqui, pois ele é para controle interno do BD
            })
        
        return jsonify(registros_json)
    
    except Exception as e:
        # Registra o erro no console do servidor para depuração
        print(f"Erro ao buscar registros ativos: {e}")
        # Retorna um erro 500 (Internal Server Error) para o frontend
        return jsonify({"error": "Erro interno do servidor ao buscar registros ativos."}), 500


#Fim da Rota Registros#
@app.route('/boas_vindas')
def boas_vindas():
    """Página de boas-vindas após login/cadastro."""
    return render_template('boas_vindas.html')

@app.route('/sucesso')
def sucesso():
    """Página de sucesso de cadastro."""
    return render_template('sucesso.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """
    Handles initial user registration and records data in the login table.
    Prevents re-registering an existing matricula.
    """
    erro = None
    sucesso = None
    if request.method == 'POST':
        nome = request.form['nome'].title()
        matricula = request.form['matricula']
        tipo_veiculo = request.form['tipo_veiculo'].title()
        
        # AQUI É A MUDANÇA! Não use strptime, já é um datetime.
        data_cadastro_obj = get_data_hora_brasilia() 

        with app.app_context():
            # Verificar se a matrícula já existe na tabela login.
            existente_matricula = db.session.query(Login).filter_by(matricula=matricula).first()
            if existente_matricula:
                erro = "Número de registro já cadastrado. Por favor, tente fazer login."
                print(f"Cadastro falhou para o número de registro {matricula}: Número de registro já existe na tabela login.")
                return render_template('cadastro.html', erro=erro)

            # Inserir os novos dados do usuário na tabela login.
            new_login = Login(
                nome=nome, 
                matricula=matricula, 
                tipo_veiculo=tipo_veiculo,
                data_cadastro=data_cadastro_obj # Use o objeto datetime diretamente aqui
            )
            db.session.add(new_login)
            db.session.commit()

            print(f"Número de registro {matricula} cadastrado com sucesso na tabela login.")
            return redirect(url_for('sucesso'))

    return render_template('cadastro.html', erro=erro)


#Rota Associacao #
@app.route('/associacao')
@login_required
@permission_required('associacao')
def associacao():
    registro_id = request.args.get('id', type=int) # Tenta obter o ID da URL
    registros_para_exibir = []
    filtro_id_aplicado = False

    per_page = 10 # Define quantos registros por página se não for um ID específico
    page = request.args.get('pagina', 1, type=int) # Paginação para quando não há ID específico

    # --- Nova variável para controlar a visibilidade do botão ---
    existe_registro_aguardando_carregamento = False
    # --- Fim da nova variável ---

    if registro_id:
        # >>>>>>>>>>> AQUI ESTÁ A MUDANÇA PRINCIPAL <<<<<<<<<<<
        # Substitua 'get_registro_by_id(registro_id)' por 'Registro.query.get(registro_id)'
        registro = Registro.query.get(registro_id)
        # >>>>>>>>>>> FIM DA MUDANÇA PRINCIPAL <<<<<<<<<<<

        if registro:
            # Apenas adiciona se não estiver finalizado
            if registro.finalizada == 0:
                registros_para_exibir.append(registro)
                # Se um registro específico foi encontrado e não está finalizado,
                # verificamos se ele está na condição 0 para o botão.
                if registro.em_separacao == 0:
                    existe_registro_aguardando_carregamento = True
            else:
                flash(f'O registro com ID {registro_id} já foi finalizado e não pode ser editado.', 'warning')
        else:
            flash(f'Registro com ID {registro_id} não encontrado.', 'danger')
        filtro_id_aplicado = True # Sinaliza que um ID específico foi procurado

        # Para um único registro, a paginação é sempre 1/1
        pagina = 1
        total_paginas = 1
    else:
        # Se nenhum ID foi passado, mostra os registros que estão 'prontos' para serem associados/finalizados.
        query = Registro.query.filter(Registro.finalizada == 0, Registro.cancelado == 0)
        query = query.filter(Registro.em_separacao.in_([0, 1, 2]))

        query = query.order_by(Registro.data_hora_login.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        registros_para_exibir = pagination.items
        pagina = pagination.page
        total_paginas = pagination.pages

        # --- Lógica para o botão quando não há filtro por ID ---
        # Verifique se existe qualquer registro na lista que está em 'em_separacao = 0'
        for reg in registros_para_exibir:
            if reg.em_separacao == 0:
                existe_registro_aguardando_carregamento = True
                break # Se encontrarmos um, já podemos definir a flag e sair do loop
        # --- Fim da lógica para o botão ---

    return render_template('associacao.html',
                           registros=registros_para_exibir,
                           filtro_id=registro_id if filtro_id_aplicado else None,
                           pagina=pagina,
                           total_paginas=total_paginas,
                           rota=request.args.get('rota', ''),
                           tipo_entrega=request.args.get('tipo_entrega', ''),
                           # --- Passa a nova flag para o template ---
                           existe_registro_aguardando_carregamento=existe_registro_aguardando_carregamento
                           # --- Fim da passagem da flag ---
                          )


## --- ROTA API para atualizar o status em_separacao ---
@app.route('/api/update_separacao_status/<int:registro_id>', methods=['POST'])
def api_update_separacao_status(registro_id):
    try:
        data = request.get_json()
        new_status = data.get('em_separacao_status') # Deve ser 1 para "Em Separação"

        if new_status is None:
            return jsonify({"error": "Status não fornecido."}), 400

        # Valide o status (0, 1, 2, 3) conforme sua lógica de negócios
        if not isinstance(new_status, int) or new_status not in [0, 1, 2, 3]:
            return jsonify({"error": "Status inválido. Deve ser 0, 1, 2 ou 3."}), 400

        # >>>>>>>>>>> AQUI ESTÁ A MUDANÇA PRINCIPAL <<<<<<<<<<<
        # Substitua qualquer chamada a 'get_registro_by_id' por Registro.query.get()
        registro = Registro.query.get(registro_id)
        # >>>>>>>>>>> FIM DA MUDANÇA PRINCIPAL <<<<<<<<<<<

        if not registro:
            return jsonify({"error": "Registro não encontrado."}), 404

        # **** ADICIONE ESTA VERIFICAÇÃO COM A NOVA MENSAGEM ****
        if registro.em_separacao == 1:
            return jsonify({"error": "Essa Rota ja esta em Separação por outro Operador!"}), 400
        # **** FIM DA VERIFICAÇÃO ADICIONADA ****

        # Impede a atualização se o registro já estiver finalizado ou cancelado
        if registro.finalizada == 1 or registro.cancelado == 1:
            return jsonify({"error": "Este registro já foi finalizado ou cancelado e não pode ser atualizado."}), 400

        # Atualiza o status 'em_separacao'
        registro.em_separacao = new_status
        db.session.commit() # Salva a mudança no banco de dados

        return jsonify({"message": f"Status do registro {registro_id} atualizado para {new_status} (Em Separação).", "status": new_status}), 200

    except Exception as e:
        # Registra o erro para depuração (opcional, mas recomendado)
        app.logger.error(f"Erro ao atualizar status de separação para registro {registro_id}: {e}")
        return jsonify({"error": "Ocorreu um erro interno ao processar a requisição."}), 500
    

# Rota para associar/salvar gaiola/estacao
# app.py

@app.route('/associar_id/<int:id>', methods=['POST'])
def associar_id(id):
    registro = Registro.query.get(id)

    if not registro:
        return jsonify({"error": "Registro não encontrado."}), 404

    # **** ADICIONE ESTA VERIFICAÇÃO ****
    if registro.em_separacao == 2:
        return jsonify({"error": "Essa Rota ja esta em Separação por outro Operador!"}), 400
    # **** FIM DA VERIFICAÇÃO ADICIONADA ****

    # Adicionando verificação para registros já finalizados ou cancelados
    # Usamos agora o status em_separacao para verificar isso
    if registro.em_separacao == 3 or registro.em_separacao == 4: # 3=Finalizado, 4=Cancelado
        return jsonify({"error": "Registro já está finalizado ou cancelado e não pode ser associado."}), 400

    gaiola = request.form.get('gaiola')
    estacao = request.form.get('estacao')
    rua = request.form.get('rua') # Para No-Show

    # Atualiza os campos
    registro.gaiola = gaiola
    registro.estacao = estacao

    if registro.tipo_entrega == 'No-Show':
        registro.rua = rua

    # Se o registro está em 'Aguardando Carregamento' (0) ou 'Em Separação' (1) e foi "salvo" com os dados,
    # ele agora passa para 'Carregamento Liberado' (2).
    # Esta é a principal mudança aqui.
    if registro.em_separacao in [0, 1]:
        registro.em_separacao = 2 # Define como Carregamento Liberado

    db.session.commit()

    return jsonify({"message": "Associação salva e Carregamento Liberado!"}), 200

# ... (Mantenha as outras rotas exatamente como te passei na última vez:
#     /marcar_como_finalizado_id/<int:id>
#     /desassociar_id/<int:id>
#     /finalizar_carregamento_id_status_separacao/<int:id>
#     /carregar_no_show/<int:id>
# ) ...


@app.route('/desassociar_id/<int:id>', methods=['POST'])
def desassociar_id(id):
    registro = Registro.query.get(id)
    if not registro:
        return jsonify({"error": "Registro não encontrado."}), 404

    # Verifica se o registro já foi finalizado ou cancelado
    # Usamos agora o status em_separacao para verificar isso
    if registro.em_separacao == 3 or registro.em_separacao == 4: # 3=Finalizado, 4=Cancelado
        return jsonify({"error": "Não é possível desassociar um registro finalizado ou cancelado."}), 400
    
    # Reseta os campos de associação
    registro.gaiola = None
    registro.estacao = None
    if registro.tipo_entrega == 'No-Show':
        registro.rua = None
    
    # Define em_separacao de volta para 1 (Em Separação)
    # Se estava em 2 (Carregamento Liberado), volta para 0
    registro.em_separacao = 0 
    
    db.session.commit()
    
    return jsonify({"message": "Registro desassociado e retornado para 'Em Separação'!"}), 200




@app.route('/marcar_como_finalizado_id/<int:id>', methods=['POST'])
def marcar_como_finalizado_id(id):
    registro = Registro.query.get(id)
    if not registro:
     return jsonify({"error": "Registro não encontrado."}), 404

    print(f"DEBUG: Tentando finalizar registro ID {id}, finalizada={registro.finalizada}, cancelado={registro.cancelado}") # Adicione esta linha

    if registro.finalizada == 1 or registro.cancelado == 1:
     return jsonify({"error": "O registro já está finalizado ou cancelado."}), 400

    registro.finalizada = 1
    registro.em_separacao = 3
    registro.hora_finalizacao = get_data_hora_brasilia()

    db.session.commit()
    return jsonify({"message": "Registro finalizado com sucesso!"}), 200
# app.py

@app.route('/cancelar_registro/<int:id>', methods=['POST'])
def cancelar_registro(id):
    registro = Registro.query.get(id)
    if not registro:
        return jsonify({"error": "Registro não encontrado."}), 404

    # Adicionando verificação para evitar cancelar registros já finalizados ou cancelados
    if registro.em_separacao == 3 or registro.em_separacao == 4:
        return jsonify({"error": "Registro já está finalizado ou cancelado."}), 400

    registro.em_separacao = 4  # Define como Cancelado (status 4)
    # Opcional: Você pode manter registro.cancelado = 1 se for útil para outros relatórios/filtros
    # ou remover esta linha se em_separacao for a única fonte da verdade para o status final.
    registro.cancelado = 1
    
    db.session.commit()
    
    return jsonify({"message": "Registro cancelado com sucesso!"}), 200


@app.route('/finalizar_carregamento_id_status_separacao/<int:id>', methods=['POST'])
def finalizar_carregamento_id_status_separacao(id):
    registro = get_registro_by_id(id)
    if not registro or registro.get('finalizada') == 1:
        flash('Registro não encontrado ou já finalizado.', 'danger')
        return redirect(url_for('associacao'))

    # Define em_separacao para 2 (Carregamento Concluído)
    # Ex: registro.em_separacao = 2
    # db.session.commit()
    print(f"DEBUG: Marcando carregamento como concluído para registro ID {id}. Setando em_separacao=2")
    registro['em_separacao'] = 2

    flash('Carregamento marcado como concluído!', 'info')
    return redirect(url_for('associacao', id=id))


# ---- Rotas No Show ----

# --- Sua Rota '/registro_no_show' Atualizada ---
# app.py

# ... (seus imports, definições de STATUS_EM_SEPARACAO, get_status_text, e o modelo NoShow) ...

@app.route('/registro_no_show', methods=['GET'])
@login_required
@permission_required('registro_no_show')
def registro_no_show():
    data_filtro_str = request.args.get('data')
    nome_filtro = request.args.get('nome')
    matricula_filtro = request.args.get('matricula')
    rota_filtro = request.args.get('rota')
    status_filtro_str = request.args.get('status') # Pega o valor do filtro de status
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = 10

    query = NoShow.query

    # --- NOVO AJUSTE: Filtra registros não finalizados por padrão ---
    # Somente se o filtro de status NÃO for 'finalizado',
    # adicionamos a condição de que o registro não deve ser finalizado.
    if status_filtro_str != 'finalizado':
        query = query.filter(NoShow.finalizada == 0) # Adiciona filtro para não finalizados

    if data_filtro_str:
        try:
            data_inicio = datetime.strptime(data_filtro_str, '%Y-%m-%d')
            # Para garantir que a data fim cubra o dia inteiro, use timezone-aware se estiver usando UTC
            # e converta para a data local para o cálculo do dia.
            # Se data_hora_login for UTC, ajuste data_fim para o final do dia UTC correspondente.
            # Exemplo (se data_hora_login está em UTC no DB):
            # TZ_BRASILIA = pytz.timezone('America/Sao_Paulo')
            # data_inicio_local = TZ_BRASILIA.localize(data_inicio)
            # data_fim_local = data_inicio_local + timedelta(days=1) - timedelta(microseconds=1)
            # data_inicio_utc = data_inicio_local.astimezone(pytz.utc).replace(tzinfo=None) # Remova tzinfo se DB é WITHOUT TIME ZONE
            # data_fim_utc = data_fim_local.astimezone(pytz.utc).replace(tzinfo=None) # Remova tzinfo se DB é WITHOUT TIME ZONE
            # query = query.filter(NoShow.data_hora_login.between(data_inicio_utc, data_fim_utc))
            #
            # No seu caso atual, se você está salvando em UTC e o DB é WITHOUT TIME ZONE,
            # sua lógica atual com `data_inicio = datetime.strptime(data_filtro_str, '%Y-%m-%d')`
            # e `data_fim = data_inicio + timedelta(days=1) - timedelta(microseconds=1)` funcionará,
            # pois estará filtrando em UTC sem problemas de conversão de fuso horário.
            data_fim = data_inicio + timedelta(days=1) - timedelta(microseconds=1)
            query = query.filter(NoShow.data_hora_login.between(data_inicio, data_fim))
        except ValueError:
            flash("Formato de data inválido. Use AAAA-MM-DD.", "error")
            data_filtro_str = None

    if nome_filtro:
        query = query.filter(NoShow.nome.ilike(f'%{nome_filtro}%'))

    if matricula_filtro:
        query = query.filter(NoShow.matricula.ilike(f'%{matricula_filtro}%'))

    if rota_filtro:
        query = query.filter(NoShow.gaiola.ilike(f'%{rota_filtro}%'))

    # --- Lógica de filtro de status existente, permanece a mesma ---
    if status_filtro_str:
        if status_filtro_str == 'aguardando_motorista':
            query = query.filter(NoShow.em_separacao == STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA'])
        elif status_filtro_str == 'separacao':
            query = query.filter(NoShow.em_separacao == STATUS_EM_SEPARACAO['SEPARACAO'])
        elif status_filtro_str == 'finalizado':
            # Quando 'finalizado' é solicitado, EXCLUÍMOS a condição padrão de 'finalizada == 0'
            # e buscamos especificamente os finalizados/cancelados.
            query = query.filter(or_(
                NoShow.em_separacao == STATUS_EM_SEPARACAO['FINALIZADO'], # Se você usa um valor numérico para 'FINALIZADO'
                NoShow.finalizada == 1
            ))
        elif status_filtro_str == 'cancelado':
            query = query.filter(or_(
                NoShow.em_separacao == STATUS_EM_SEPARACAO['CANCELADO'], # Se você usa um valor numérico para 'CANCELADO'
                NoShow.cancelado == 1
            ))
        elif status_filtro_str == 'transferido':
            query = query.filter(NoShow.em_separacao == STATUS_EM_SEPARACAO['TRANSFERIDO'])
        # Adicione outros filtros de status conforme necessário

    query = query.order_by(NoShow.data_hora_login.desc())

    paginated_results = query.paginate(page=pagina, per_page=por_pagina, error_out=False)
    registros_no_show = paginated_results.items
    total_paginas = paginated_results.pages

    return render_template('registro_no_show.html',
                           registros_no_show=registros_no_show,
                           data_filtro=data_filtro_str,
                           nome_filtro=nome_filtro,
                           matricula_filtro=matricula_filtro,
                           rota_filtro=rota_filtro,
                           status_filtro=status_filtro_str, # Passa o status_filtro para o template
                           pagina=pagina,
                           total_paginas=total_paginas,
                           get_status_text=get_status_text,
                           STATUS_EM_SEPARACAO=STATUS_EM_SEPARACAO
                           )


# --- ROTA UNIFICADA: Atualizar Status (para Associar, Finalizar, Cancelar, Transferir) ---
# Esta rota substituirá a lógica de 'marcar_como_finalizado_no_show_id', 'associar_no_show_id' e 'transferir_no_show_para_registro'
# --- A ROTA COMPLETA atualizar_status_no_show ---
@app.route('/atualizar_status_no_show/<int:registro_id>', methods=['POST'])
def atualizar_status_no_show(registro_id):
    registro = NoShow.query.get_or_404(registro_id)
    novo_status_code_str = request.form.get('novo_status')

    # Capturar dados do formulário de associação, se existirem
    gaiola = request.form.get('gaiola')
    estacao = request.form.get('estacao')
    rua = request.form.get('rua')

    try:
        novo_status_code = int(novo_status_code_str)

        # Validar se o novo_status_code é um dos valores permitidos
        if novo_status_code not in STATUS_EM_SEPARACAO.values():
            flash("Código de status inválido.", 'error')
            return redirect(url_for('registro_no_show', _anchor=f'registro-{registro_id}'))

        # Lógica para "Associar" (quando o status vai para AGUARDANDO_MOTORISTA = 0)
        if novo_status_code == STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA']:
            if not gaiola or not estacao or not rua:
                flash("Rota, Estação e Rua são obrigatórios para associar.", 'error')
                return redirect(url_for('registro_no_show', _anchor=f'registro-{registro_id}'))

            registro.gaiola = gaiola
            registro.estacao = estacao
            registro.rua = rua
            registro.em_separacao = STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA']
            registro.hora_finalizacao = None
            registro.finalizada = 0
            registro.cancelado = 0
            flash(f"Registro No-Show #{registro_id} associado e aguardando motorista.", 'success')

        # Lógica para 'Cancelar' (3)
        elif novo_status_code == STATUS_EM_SEPARACAO['CANCELADO']:
            registro.em_separacao = novo_status_code
            registro.cancelado = 1
            registro.finalizada = 0
            registro.hora_finalizacao = datetime.now()
            flash(f"Registro No-Show #{registro_id} cancelado com sucesso!", 'success')

        # Lógica para 'Finalizar' (2)
        elif novo_status_code == STATUS_EM_SEPARACAO['FINALIZADO']:
            registro.em_separacao = novo_status_code
            registro.finalizada = 1
            registro.cancelado = 0
            registro.hora_finalizacao = datetime.now()
            flash(f"Registro No-Show #{registro_id} finalizado com sucesso!", 'success')

        # --- Lógica para 'Transferir' (4) ---
        elif novo_status_code == STATUS_EM_SEPARACAO['TRANSFERIDO']:
            try:
                print(f"\n--- INÍCIO DA TRANSFERÊNCIA PARA O REGISTRO NoShow ID: {registro_id} ---")
                print(f"Dados do NoShow (para busca no Registros):")
                print(f"  Gaiola (Rota no Registros): '{registro.gaiola}'")
                print(f"  Estacao (Cidade de Entrega no Registros): '{registro.estacao}'")

                # **PASSO 1: ENCONTRAR E TENTAR FINALIZAR O REGISTRO PRINCIPAL NO REGISTROS**
                registro_principal_a_finalizar = Registros.query.filter_by(
                    rota=registro.gaiola,
                    cidade_entrega=registro.estacao,
                    tipo_entrega='No-Show',
                    finalizada=0
                ).first()

                if registro_principal_a_finalizar:
                    print(f"ACHOU O REGISTRO PRINCIPAL! ID: {registro_principal_a_finalizar.id}")
                    print(f"Status atual do Registro Principal: Finalizada={registro_principal_a_finalizar.finalizada}, Tipo de Entrega={registro_principal_a_finalizar.tipo_entrega}")

                    # ATUALIZAÇÃO E COMMIT IMEDIATO DO REGISTRO PRINCIPAL
                    registro_principal_a_finalizar.finalizada = 1  # <--- Marcar finalizada como 1
                    registro_principal_a_finalizar.hora_finalizacao = datetime.now()
                    db.session.add(registro_principal_a_finalizar)
                    db.session.commit() # Commit para garantir que esta alteração seja salva AGORA

                    print(f"Registro Principal ID {registro_principal_a_finalizar.id} ATUALIZADO: finalizada=1.")
                    flash(f"Registro No-Show #{registro_id} processado. **Registro principal (ID: {registro_principal_a_finalizar.id}) FINALIZADO** com sucesso.", 'success')

                else:
                    print(f"NÃO ENCONTRADO! Nenhum registro principal correspondente em 'Registros'.")
                    print(f"Verifique se existe um registro em 'Registros' com:")
                    print(f"  rota='{registro.gaiola}'")
                    print(f"  cidade_entrega='{registro.estacao}'")
                    print(f"  tipo_entrega='No-Show'")
                    print(f"  finalizada=0")
                    flash(f"Aviso: Não foi possível encontrar o registro principal em Registros para finalizar. Verifique os dados.", 'warning')

                # **PASSO 2: ATUALIZAR O REGISTRO NOSHOW**
                # Esta parte será commitada separadamente
                registro.em_separacao = novo_status_code  # Marcar como TRANSFERIDO (4)
                registro.finalizada = 1                   # NoShow também finalizado
                registro.hora_finalizacao = datetime.now()
                db.session.add(registro)
                db.session.commit() # Commit para as alterações no NoShow

                print(f"Registro NoShow ID {registro_id} atualizado para TRANSFERIDO e finalizado.")
                print(f"--- FIM DA TRANSFERÊNCIA PARA O REGISTRO NoShow ID: {registro_id} ---\n")

                return redirect(url_for('registro_no_show', _anchor=f'registro-{registro_id}'))

            except Exception as e:
                db.session.rollback() # Desfaz qualquer coisa caso haja um erro grave
                flash(f"Erro ao transferir Registro No-Show #{registro_id}: {str(e)}", 'error')
                print(f"ERRO CRÍTICO NA TRANSFERÊNCIA: {str(e)}")
                print(f"--- FIM DA TRANSFERÊNCIA COM ERRO PARA O REGISTRO NoShow ID: {registro_id} ---\n")
                return redirect(url_for('registro_no_show', _anchor=f'registro-{registro_id}'))
        # --- FIM DA LÓGICA DE TRANSFERÊNCIA ---

        # Lógica para outros status (não 'TRANSFERIDO')
        db.session.commit() # Commit para os outros status

    except ValueError:
        flash("Status inválido ou dados de associação incompletos.", 'error')
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao atualizar status do registro: {str(e)}", 'error')

    # Redireciona de volta para a página de registros, mantendo o filtro e focando no registro
    return redirect(url_for('registro_no_show', _anchor=f'registro-{registro_id}',
                             data=request.args.get('data'),
                             nome=request.args.get('nome'),
                             matricula=request.args.get('matricula'),
                             rota=request.args.get('rota'),
                             status=request.args.get('status')))



@app.route('/dessociar_no_show/<int:registro_id>', methods=['POST'])
def dessociar_no_show(registro_id):
    registro = NoShow.query.get_or_404(registro_id)

    try:
        # 1. Limpa os dados de Rota, Estação e Rua
        registro.gaiola = None
        registro.estacao = None
        registro.rua = None

        # 2. Muda o status em_separacao para 1 (SEPARACAO)
        registro.em_separacao = STATUS_EM_SEPARACAO['SEPARACAO']
        registro.hora_finalizacao = None # Se for dessassociado, não está mais finalizado

        # Limpa os campos legados de finalizado/cancelado se estiverem ativos
        registro.finalizada = 0
        registro.cancelado = 0

        db.session.commit()
        flash(f"Registro No-Show #{registro_id} dessassociado e em separação.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao dessassociar registro: {str(e)}", 'error')

    # Redireciona de volta para a página de registros, mantendo o filtro e focando no registro
    return redirect(url_for('registro_no_show', _anchor=f'registro-{registro_id}',
                             data=request.args.get('data'),
                             nome=request.args.get('nome'),
                             matricula=request.args.get('matricula'),
                             rota=request.args.get('rota'),
                             status=request.args.get('status')))

@app.route('/cancelar_no_show/<int:id>', methods=['POST'])
def cancelar_no_show(id):
    print(f"DEBUG: Requisição POST recebida para cancelar No-Show ID: {id}")
    try:
        no_show = NoShow.query.get(id)

        if not no_show:
            print(f"DEBUG: Registro No-Show ID {id} não encontrado no banco de dados.")
            return jsonify({"error": "Registro No-Show não encontrado."}), 404

        print(f"DEBUG: Registro encontrado. Status atual em_separacao={no_show.em_separacao}, cancelado={no_show.cancelado}")

        # Se o registro já está em um status de cancelado (3) ou transferido (4)
        # não permitimos outro cancelamento ou atualização.
        # Ajustei esta condição para verificar o 'cancelado' também, se aplicável,
        # mas o 'em_separacao' em 3 já indica cancelado.
        if no_show.em_separacao == 3 or no_show.cancelado == 1:
            print(f"DEBUG: Registro No-Show ID {id} já está cancelado (em_separacao=3 ou cancelado=1). Não será atualizado novamente.")
            return jsonify({"error": "Registro No-Show já está cancelado."}), 400
            
        # Se for status 4 (Transferido), você pode querer tratar de forma diferente
        # dependendo se um registro transferido pode ser "cancelado" posteriormente.
        # Por enquanto, assumimos que se for 4, ele também não pode ser cancelado via este botão.
        if no_show.em_separacao == 4:
            print(f"DEBUG: Registro No-Show ID {id} está transferido (em_separacao=4). Não será cancelado por esta ação.")
            return jsonify({"error": "Registro No-Show já está transferido e não pode ser cancelado diretamente."}), 400


        # --- ESSA É A LINHA QUE VOCÊ PRECISA ADICIONAR/AJUSTAR ---
        no_show.em_separacao = 3  # Define como Cancelado (status 3) na tabela no_show
        no_show.cancelado = 1     # <--- Adiciona esta linha para setar o campo 'cancelado' para 1
        # --- FIM DA LINHA A ADICIONAR/AJUSTAR ---
        
        # Registra a hora atual de Brasília
        no_show.hora_finalizacao = datetime.now(pytz.timezone('America/Sao_Paulo')) 

        print(f"DEBUG: Tentando commitar alterações para No-Show ID {id}. Novo em_separacao={no_show.em_separacao}, novo cancelado={no_show.cancelado}. Nova hora_finalizacao={no_show.hora_finalizacao}")
        
        db.session.commit()
        
        print(f"DEBUG: Commit realizado com sucesso para No-Show ID {id}.")

        return jsonify({"message": "Registro No-Show cancelado com sucesso!"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"ERRO: Falha inesperada ao cancelar registro No-Show ID {id}. Detalhes do erro: {e}")
        return jsonify({"error": f"Erro interno do servidor: {str(e)}"}), 500

@app.route('/finalizar_carregamento_no_show_id_status_separacao/<int:id>', methods=['POST'])
def finalizar_carregamento_no_show_id_status_separacao(id):
    registro = NoShow.query.get(id)
    if registro:
        # Se 'em_separacao' == 1 (Em Separação), muda para 2 (Aguardando Entregador)
        if registro.em_separacao == 1:
            registro.em_separacao = 2
            db.session.commit()
            flash('Status do registro No-Show alterado para Aguardando Entregador!', 'success')
        else:
            flash('Registro não está no status "Em Separação" para aguardar entregador.', 'warning')
    else:
        flash('Registro No-Show não encontrado.', 'error')
    return redirect(url_for('registro_no_show', _anchor=f'no-show-registro-{id}'))


# Adicione esta função em algum lugar acessível (ex: no seu arquivo principal app.py)
def verificar_e_atualizar_em_separacao_registro(registro_id):
    registro = Registro.query.get(registro_id)
    if not registro:
        print(f"DEBUG_ATUALIZAR_EM_SEPARACAO: Registro ID {registro_id} não encontrado.")
        return False

    print(f"DEBUG_ATUALIZAR_EM_SEPARACAO: Verificando Registro ID {registro.id}, Rota='{registro.rota}', Tipo='{registro.tipo_entrega}', Status atual em_separacao={registro.em_separacao}")

    # Condição para atualização:
    # 1. É um Registro do tipo 'No-Show'
    # 2. Seu em_separacao atual NÃO é 2 (ou 3, se 3 significa finalizado para carregamento)
    # 3. Existe um NoShow correspondente com em_separacao = 1 (SEPARACAO)
    
    # Assumindo que STATUS_EM_SEPARACAO['SEPARACAO'] é 1
    # Assumindo que STATUS_EM_SEPARACAO['CARREGAMENTO_LIBERADO'] é 2 (que estamos tentando alcançar)

    if registro.tipo_entrega == 'No-Show' and registro.em_separacao != 2:
        no_show_correspondente = NoShow.query.filter(
            NoShow.gaiola.ilike(registro.rota),
            NoShow.em_separacao == STATUS_EM_SEPARACAO['SEPARACAO']
        ).first()

        if no_show_correspondente:
            print(f"DEBUG_ATUALIZAR_EM_SEPARACAO: NoShow correspondente encontrado para Registro ID {registro.id}: NoShow ID {no_show_correspondente.id}.")
            
            # Atualiza o Registro principal
            registro.em_separacao = 2
            registro.status = STATUS_REGISTRO_PRINCIPAL['CARREGAMENTO_LIBERADO']
            db.session.add(registro)
            
            # Atualiza o NoShow para um status que indique que foi "encontrado" e liberado
            # Sugestão: AGUARDANDO_ENTREGADOR (3) para evitar que seja "encontrado" novamente
            no_show_correspondente.em_separacao = STATUS_EM_SEPARACAO['AGUARDANDO_ENTREGADOR']
            db.session.add(no_show_correspondente)
            
            try:
                db.session.commit()
                print(f"DEBUG_ATUALIZAR_EM_SEPARACAO: Registro ID {registro.id} e NoShow ID {no_show_correspondente.id} atualizados para em_separacao=2/3 com sucesso.")
                return True
            except Exception as e:
                db.session.rollback()
                print(f"DEBUG_ATUALIZAR_EM_SEPARACAO: Erro ao commitar atualização: {e}")
                return False
        else:
            print(f"DEBUG_ATUALIZAR_EM_SEPARACAO: Nenhum NoShow correspondente em 'SEPARACAO' encontrado para Registro ID {registro.id}.")
    else:
        print(f"DEBUG_ATUALIZAR_EM_SEPARACAO: Registro ID {registro.id} não atende aos critérios para atualização (Não é No-Show ou já está em 2).")
        
    return False

# Exemplo de como você chamaria essa função:
# Você pode chamá-la em uma rota de atualização de Registro, ou em uma nova rota.

# Opção 1: Chamar em uma rota de atualização de Registro existente
# Se você tiver uma rota tipo @app.route('/atualizar_registro/<int:registro_id>', methods=['POST'])
# após a atualização dos dados do Registro, você chamaria:
# verificar_e_atualizar_em_separacao_registro(registro_id)

# Opção 2: Criar uma rota específica para disparar a verificação/atualização
# Isso permitiria que você acione a verificação manualmente ou via JS na interface
@app.route('/verificar_status_e_atualizar/<int:registro_id>', methods=['POST'])
def rota_verificar_status_e_atualizar(registro_id):
    print(f"DEBUG: Rota /verificar_status_e_atualizar acessada para Registro ID: {registro_id}")
    sucesso = verificar_e_atualizar_em_separacao_registro(registro_id)
    if sucesso:
        return jsonify({"message": f"Status do Registro ID {registro_id} verificado e atualizado com sucesso.", "status": "ok"}), 200
    else:
        return jsonify({"message": f"Falha ao verificar/atualizar status do Registro ID {registro_id}.", "status": "error"}), 400

# Opção 3: Se houver uma rota para criar/atualizar NoShow, podemos chamar essa função lá também
# Por exemplo, se você tem @app.route('/no_shows', methods=['POST']) para criar um NoShow:
# Depois de criar/atualizar um NoShow, você pode buscar por Registros correspondentes
# e chamar verificar_e_atualizar_em_separacao_registro para cada um deles.


@app.route('/registros', methods=['GET', 'POST'])
@login_required
@permission_required('registros')
def criar_registro_principal():
    if request.method == 'POST':
        print(f"DEBUG_REG_CRIAR: [Passo 1] Rota de criação acessada via POST!")
        print(f"DEBUG_REG_CRIAR: [Passo 1.1] Conteúdo do formulário: {request.form}")

        nome = request.form.get('nome')
        matricula = request.form.get('matricula')
        data_hora_login_agora = datetime.now()

        rota_input = request.form.get('rota')
        tipo_entrega = request.form.get('tipo_entrega')
        cidade_entrega = request.form.get('cidade_entrega')

        # Inicializa novo_registro com valores padrão
        novo_registro = Registro(
            nome=nome,
            matricula=matricula,
            data_hora_login=data_hora_login_agora,
            rota=rota_input,
            tipo_entrega=tipo_entrega,
            cidade_entrega=cidade_entrega,
            rua='Aguarde',
            # CORREÇÃO: Usando 'estacao' conforme o modelo 'Registro'
            estacao='Aguarde', 
            em_separacao=0, # Valor padrão inicial
            finalizada=0,
            cancelado=0,
            status=STATUS_REGISTRO_PRINCIPAL['AGUARDANDO_CARREGAMENTO'] # Status inicial
        )

        if tipo_entrega == 'No-Show':
            print(f"DEBUG_REG_CRIAR: [Passo 2] Tipo de entrega é 'No-Show'. Tentando buscar NoShow.")
            print(f"DEBUG_REG_CRIAR: [Passo 2.1] Buscando NoShow com Gaiola LIKE '{rota_input}' e em_separacao = {STATUS_EM_SEPARACAO['SEPARACAO']}")

            no_show_encontrado = NoShow.query.filter(
                NoShow.gaiola.ilike(rota_input),
                NoShow.em_separacao == STATUS_EM_SEPARACAO['SEPARACAO']
            ).first()

            if no_show_encontrado:
                print(f"DEBUG_REG_CRIAR: [Passo 3] SUCESSO! NoShow encontrado: ID={no_show_encontrado.id}, Gaiola='{no_show_encontrado.gaiola}', Rua='{no_show_encontrado.rua}', Estacao='{no_show_encontrado.estacao}', Em_Separacao={no_show_encontrado.em_separacao}")

                novo_registro.rota = no_show_encontrado.gaiola
                novo_registro.rua = no_show_encontrado.rua
                # CORREÇÃO: Usando 'estacao' conforme o modelo 'Registro'
                novo_registro.estacao = no_show_encontrado.estacao 
                
                novo_registro.status = STATUS_REGISTRO_PRINCIPAL['CARREGAMENTO_LIBERADO']
                
                # --- MUDANÇA PRINCIPAL: Define em_separacao do NOVO Registro para 2 ---
                # Isso garante que o Registro principal nasça com status 'Carregamento Liberado'
                novo_registro.em_separacao = 2 
                # --- FIM DA MUDANÇA ---

                # Opcional: Ativar mensagem flash
                # flash(f"Registro criado! Rota '{rota_input}' do tipo No-Show associado a um carregamento liberado.", 'success') 

                # Atualiza o NoShow encontrado para evitar duplicidade
                no_show_encontrado.em_separacao = STATUS_EM_SEPARACAO['AGUARDANDO_ENTREGADOR'] # Ex: 3
                db.session.add(no_show_encontrado)

            else:
                print(f"DEBUG_REG_CRIAR: [Passo 3] FALHA! Nenhum NoShow correspondente encontrado para Rota '{rota_input}' com status 'SEPARACAO'.")
                # Opcional: Ativar mensagem flash
                # flash(f"Registro criado! Rota '{rota_input}' do tipo No-Show aguardando associação de carregamento.", 'warning') 
                
                novo_registro.status = STATUS_REGISTRO_PRINCIPAL['AGUARDANDO_CARREGAMENTO']
                # Se não encontrar NoShow, mantém o padrão ou define explicitamente 0 ou None
                novo_registro.em_separacao = 0 
        else:
            print(f"DEBUG_REG_CRIAR: [Passo 2] Tipo de entrega '{tipo_entrega}' não é 'No-Show'. Não buscar NoShow.")
            novo_registro.status = STATUS_REGISTRO_PRINCIPAL['AGUARDANDO_CARREGAMENTO']
            # Para outros tipos de entrega, define explicitamente 0
            novo_registro.em_separacao = 0 

        db.session.add(novo_registro)
        db.session.commit()
        # Opcional: Ativar mensagem flash
        # flash("Registro de chegada criado com sucesso!", 'success') 
        # Opcional: Redirecionar para outra página
        # return redirect(url_for('alguma_pagina_apos_registro')) 

        # Para fins de demonstração ou API, retorna um JSON
        return jsonify({"message": "Registro criado com sucesso!", "registro_id": novo_registro.id, "rota": novo_registro.rota}), 201

    else: # request.method == 'GET'
        mostrar_finalizados = request.args.get('finalizados', 'false').lower() == 'true'
        registros = []

        if mostrar_finalizados:
            registros = Registro.query.filter_by(finalizada=1).order_by(Registro.data_hora_login.asc()).all()
            print("DEBUG_GET: Mostrando registros finalizados.")
        else:
            registros = Registro.query.filter_by(finalizada=0).order_by(Registro.data_hora_login.asc()).all()
            print("DEBUG_GET: Mostrando registros não finalizados.")

        registros_data = []
        for reg in registros:
            # Formata a data/hora para JSON
            data_hora_login_str = reg.data_hora_login.strftime('%Y-%m-%d %H:%M:%S') if reg.data_hora_login else None
            
            registros_data.append({
                'id': reg.id,
                'nome': reg.nome,
                'matricula': reg.matricula,
                'rota': reg.rota,
                'tipo_entrega': reg.tipo_entrega,
                'cidade_entrega': reg.cidade_entrega,
                'data_hora_login': data_hora_login_str,
                'gaiola': reg.gaiola, # Assumindo que Registro pode ter gaiola
                'estacao': reg.estacao,
                'finalizada': bool(reg.finalizada),
                'cancelado': bool(reg.cancelado),
                'em_separacao': reg.em_separacao,
                'rua': reg.rua,
                'status': reg.status
            })

        return jsonify(registros_data)
    

@app.route('/transferir_no_show_para_registro/<int:no_show_id>', methods=['POST'])
def transferir_no_show_para_registro(no_show_id):
    no_show_original = NoShow.query.get_or_404(no_show_id)

    try:
        # 2. BUSCAR O REGISTRO CORRESPONDENTE NA TABELA 'REGISTROS' (DESTINO)
        registro_principal_correspondente = Registro.query.filter(
            Registro.rota == no_show_original.gaiola.strip(),
            Registro.tipo_entrega == 'No-Show',
            or_(Registro.estacao.is_(None), Registro.estacao == no_show_original.estacao.strip())
        ).first()

        flash_msg_registro = ""

        if registro_principal_correspondente:
            # 1. ATUALIZAR O REGISTRO NO-SHOW (ORIGEM)
            # Marca o NoShow original como 'TRANSFERIDO'
            no_show_original.em_separacao = STATUS_EM_SEPARACAO['TRANSFERIDO'] # Status 4
            no_show_original.hora_finalizacao = datetime.now() # Registra a hora da transferência
            db.session.add(no_show_original)

            # 3. TRANSFERIR OS DADOS DO NO_SHOW PARA O REGISTRO
            registro_principal_correspondente.gaiola = no_show_original.gaiola.strip().upper() # Transferir Rota para Gaiola
            registro_principal_correspondente.rua = no_show_original.rua.strip() # Transferir Rua
            registro_principal_correspondente.estacao = no_show_original.estacao.strip() # Atualizar a estação com o valor do No-Show
            registro_principal_correspondente.em_separacao = 3 # Mudar o valor de em_separacao para 3

            db.session.add(registro_principal_correspondente)
            flash_msg_registro = f" Dados do No-Show transferidos para o registro da rota '{no_show_original.gaiola}'."
            db.session.commit() # Salva as alterações em ambos os objetos
        else:
            # Caso não encontre um Registro principal correspondente
            print(f"ATENÇÃO: Nenhum Registro correspondente encontrado para NoShow ID {no_show_id} (Rota: {no_show_original.gaiola}, Estação (No-Show): {no_show_original.estacao}, Estação (Registro): NULL).")
            flash_msg_registro = f" Nenhum registro de carregamento correspondente encontrado para o No-Show da rota '{no_show_original.gaiola}' e estação '{no_show_original.estacao}'."

        flash(f"Registro No-Show #{no_show_id} transferido para carregamento." + flash_msg_registro, 'success')
        return redirect(url_for('registro_no_show', _anchor=f'no-show-registro-{no_show_id}',
                                                data=request.args.get('data'),
                                                nome=request.args.get('nome'),
                                                matricula=request.args.get('matricula'),
                                                rota=request.args.get('rota'),
                                                status=request.args.get('status')))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao transferir registro No-Show #{no_show_id}: {str(e)}", 'error')
        return redirect(url_for('registro_no_show', _anchor=f'no-show-registro-{no_show_id}',
                                                data=request.args.get('data'),
                                                nome=request.args.get('nome'),
                                                matricula=request.args.get('matricula'),
                                                rota=request.args.get('rota'),
                                                status=request.args.get('status')))
# ---- Criar Registro No Show ----

@app.route('/associacao_no_show', methods=['GET'])
@login_required
@permission_required('associacao_no_show')
def associacao_no_show():
    # Esta rota simplesmente renderiza o formulário
    return render_template('associacao_no_show.html')

@app.route('/criar_registro_no_show', methods=['POST'])
@login_required
@permission_required('associacao_no_show')
def criar_registro_no_show():
    from pytz import timezone
    fuso_brasil = timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_brasil)

    nome = capitalize_words(request.form.get('nome'))
    data = request.form

    nome = data.get('nome')
    matricula = data.get('matricula')
    cidade_entrega = data.get('cidade_entrega')
    tipo_entrega = data.get('tipo_entrega')
    rota = data.get('rota').upper() if data.get('rota') else None  # <-- Aqui transforma em maiúsculo
    estacao = data.get('estacao')
    rua = data.get('rua')

    if not all([nome, matricula, tipo_entrega, rota, estacao, rua]):
        flash('Todos os campos obrigatórios devem ser preenchidos.', 'error')
        return redirect(url_for('associacao_no_show'))

    if not (rua.isdigit() and 1 <= int(rua) <= 9):
        flash('O campo "Rua" deve ser um dígito de 1 a 9.', 'error')
        return redirect(url_for('associacao_no_show'))

    try:
        novo_registro = NoShow(
            data_hora_login=datetime.now(pytz.timezone('America/Sao_Paulo')),
            nome=nome,
            matricula=matricula,
            gaiola=rota,
            tipo_entrega=tipo_entrega,
            rua=rua,
            estacao=estacao,
            finalizada=0,
            cancelado=0,
            em_separacao=0
        )

        db.session.add(novo_registro)
        db.session.commit()

        flash('Registro No Show criado com sucesso!', 'success')
        return redirect(url_for('associacao_no_show'))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao criar registro No Show: {e}")
        flash('Erro interno ao criar registro.', 'error')
        return redirect(url_for('associacao_no_show'))
    
    # No seu app.py


@app.route('/transferir_para_carregamento_no_show/<int:registro_id>', methods=['POST'])
def transferir_para_carregamento_no_show(registro_id):
    no_show_original = NoShow.query.get_or_404(registro_id)
    print(f"Tentando transferir No-Show ID: {registro_id}, Gaiola: {no_show_original.gaiola}")

    try:
        registro_principal = Registros.query.filter_by(
            rota=no_show_original.gaiola,
            tipo_entrega='No-Show',
            finalizada=0
        ).first()

        if registro_principal:
            print(f"Registro PRINCIPAL encontrado: ID {registro_principal.id}")
            registro_principal.finalizada = 1
            db.session.add(registro_principal)

            no_show_original.em_separacao = STATUS_EM_SEPARACAO['TRANSFERIDO']
            no_show_original.hora_finalizacao = datetime.now(pytz.timezone('America/Sao_Paulo'))
            db.session.add(no_show_original)

            db.session.commit()
            flash(f"Registro No-Show #{registro_id} transferido para carregamento com sucesso.", 'success')
        else:
            print("Nenhum registro PRINCIPAL correspondente encontrado.")
            flash(f"❌ Nenhum registro de carregamento correspondente encontrado para a rota '{no_show_original.gaiola}' e estação '{no_show_original.estacao}'.", 'error')

        return redirect(url_for('registro_no_show', status='aguardando_motorista'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao transferir Registro No-Show #{registro_id}: {str(e)}", 'error')
        return redirect(url_for('registro_no_show', status='aguardando_motorista'))


@app.route('/finalizar_no_show/<int:id>', methods=['POST'])
def finalizar_no_show(id):
    """Função para finalizar um registro No Show e atualizar o registro correspondente em Registros."""
    no_show_original = NoShow.query.get_or_404(id)

    try:
        fuso_brasil = pytz.timezone('America/Sao_Paulo')
        no_show_original.finalizada = 1
        no_show_original.hora_finalizacao = datetime.now(fuso_brasil)
        db.session.add(no_show_original)

        # Buscar o registro correspondente na tabela 'Registros'
        registro_principal_correspondente = Registro.query.filter(
            Registro.rota == no_show_original.gaiola.strip(),
            Registro.tipo_entrega == 'No-Show',
            or_(Registro.estacao.is_(None), Registro.estacao == no_show_original.estacao.strip())
        ).first()

        if registro_principal_correspondente:
            registro_principal_correspondente.finalizada = 1
            registro_principal_correspondente.hora_finalizacao = datetime.now(fuso_brasil)
            db.session.add(registro_principal_correspondente)

        db.session.commit()
        flash(f'Registro No Show com ID {id} foi finalizado e o registro correspondente em Registros foi atualizado (se encontrado)!', 'success')
        return redirect(url_for('registro_no_show', _anchor=f'no-show-registro-{id}'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao finalizar registro No-Show #{id} ou atualizar o registro correspondente: {str(e)}", 'error')
        return redirect(url_for('registro_no_show', _anchor=f'no-show-registro-{id}'))
    
@app.route('/midia')
@login_required
@permission_required('midia')
def exibir_midia():
    """Renderiza a página HTML com a exibição de mídia (vídeos e slides)."""
    print("DEBUG: Rota /midia acessada. Renderizando midia.html")
    return render_template('midia.html')

# --- Rota para exibir o menu principal ---
@app.route('/menu_principal')
@login_required
def menu_principal():
    """Renderiza a página do menu principal."""
    print("DEBUG: /menu_principal - Rota acessada.")
    return render_template('menu_principal.html')




# ------ Painel Final - Fila de atendimento ------
# Agora acessível via /painel_final
@app.route('/painel_final')
def painel_final_page():
    """Renderiza a página do Painel de Atendimento."""
    return render_template('painel_final.html')


# --- Rota da API para Registros 'Em Separação' (Quadro 1) ---
# --- Rota da API para Registros 'Em Separação' (Quadro 1) ---
@app.route('/api/registros/em-separacao')
def get_registros_em_separacao():
    try:
        # Busca registros com 'em_separacao' igual a 2 (Em Separação),
        # que não estão finalizados nem cancelados,
        # E O CAMPO 'rota' NÃO É NULO.
        registros_em_separacao = Registro.query.filter(
            Registro.em_separacao == 2,
            Registro.finalizada == 0,
            Registro.cancelado == 0,
            Registro.gaiola.isnot(None) # Adiciona esta condição para filtrar rotas não nulas
        ).order_by(Registro.data_hora_login.asc()).all() # Ordena do mais antigo para o mais novo

        registros_json = []
        for reg in registros_em_separacao:
            registros_json.append({
                'id': reg.id,
                'nome': reg.nome,
                'matricula': reg.matricula,
                'rota': reg.rota,
                'tipo_entrega': reg.tipo_entrega,
                'cidade_entrega': reg.cidade_entrega,
                # Garante que as datas sejam serializadas para string
                'data_hora_login': reg.data_hora_login.strftime('%H:%M') if reg.data_hora_login else None,
                'gaiola': reg.gaiola if reg.gaiola else 'Aguardando',
                'estacao': reg.estacao if reg.estacao else 'Aguardando',
                'em_separacao_status': reg.em_separacao # Para depuração, se necessário
            })
        return jsonify(registros_json)
    except Exception as e:
        # app.logger.error(f"Erro ao buscar registros 'Em Separação': {e}") # Descomente se tiver app.logger configurado
        print(f"Erro ao buscar registros 'Em Separação': {e}") # Para depuração simples
        return jsonify({"error": "Erro interno do servidor ao buscar registros 'Em Separação'."}), 500


# --- Rota da API para Rotas No-Show (Quadro 2) ---
@app.route('/api/noshow/aguardando-motorista')
def get_noshow_aguardando_motorista():
    try:
        # Busca registros NoShow com 'em_separacao' igual a 0 (Aguardando Motorista)
        # e que não estão finalizados nem cancelados
        noshow_aguardando = NoShow.query.filter(
            NoShow.em_separacao == 0,
            NoShow.finalizada == 0,
            NoShow.cancelado == 0
        ).order_by(NoShow.data_hora_login.asc()).all() # Ordena do mais antigo para o mais novo

        noshow_json = []
        for ns in noshow_aguardando:
            noshow_json.append({
                'id': ns.id,
                'nome': ns.nome,
                'matricula': ns.matricula,
                'gaiola': ns.gaiola, # 'gaiola' em NoShow corresponde à 'rota' principal
                'tipo_entrega': ns.tipo_entrega,
                'rua': ns.rua,
                'estacao': ns.estacao,
                # Garante que as datas sejam serializadas para string
                'data_hora_login': ns.data_hora_login.strftime('%H:%M') if ns.data_hora_login else None,
                'em_separacao_status': ns.em_separacao # Para depuração, se necessário
            })
        return jsonify(noshow_json)
    except Exception as e:
        app.logger.error(f"Erro ao buscar rotas No-Show Aguardando Motorista: {e}")
        return jsonify({"error": "Erro interno do servidor ao buscar rotas No-Show."}), 500

# --- Rota da API para Notícias (Letreiro Superior) ---

# --- ROTA AJUSTADA PARA BUSCAR NOTÍCIAS DA CNN BRASIL ---
@app.route('/api/get_news_headlines', methods=['GET'])
def get_news_headlines():
    # URL do feed RSS da CNN Brasil
    # Verificado em 2025-05-15, mas URLs de feed podem mudar.
    # Se parar de funcionar, pode ser necessário buscar a nova URL do feed RSS da CNN Brasil.
    cnn_brasil_feed_url = 'https://www.cnnbrasil.com.br/feed/'

    all_headlines = []

    # --- Buscar notícias da CNN Brasil (usando RSS) ---
    try:
        print(f"DEBUG Flask: Buscando feed da CNN Brasil em: {cnn_brasil_feed_url}")
        feed = feedparser.parse(cnn_brasil_feed_url)

        if feed.entries:
            print(f"DEBUG Flask: Feed da CNN Brasil encontrado com {len(feed.entries)} entradas.")
            # Limita o número de manchetes da CNN Brasil (ex: as 10 mais recentes)
            for entry in feed.entries[:10]: # Pega as 10 primeiras manchetes
                # Pode adicionar formatação ou limpar o título se necessário
                headline = entry.title
                # Exemplo: remover HTML básico se houver (feedparser geralmente limpa)
                # from bs4 import BeautifulSoup
                # headline = BeautifulSoup(headline, 'html.parser').get_text()

                all_headlines.append(f"CNN Brasil: {headline}") # Adiciona prefixo

        else:
            all_headlines.append("CNN Brasil: Não foi possível carregar manchetes do feed.")
            print("DEBUG Flask: Feed da CNN Brasil não retornou entradas.")

    except Exception as e:
        print(f"DEBUG Flask: Erro ao buscar feed da CNN Brasil: {e}")
        all_headlines.append("CNN Brasil: Erro ao carregar notícias.")

    # --- Seção para outras fontes (como Shopee) ---
    # Mantenha ou remova esta seção dependendo se você quer incluir outras fontes aqui.
    # Se você remover, o letreiro superior só mostrará a CNN Brasil.
    # Se você quiser adicionar outras fontes, implemente a busca aqui e adicione
    # as manchetes à lista `all_headlines`.
    # ... (Seu código para buscar outras fontes, se houver) ...


    # Adiciona uma mensagem padrão caso nenhuma manchete tenha sido carregada com sucesso
    if not all_headlines or all(msg.startswith("CNN Brasil: Erro") for msg in all_headlines):
         all_headlines = ["Erro ao carregar notícias da CNN Brasil ou fontes indisponíveis."]
         print("DEBUG Flask: Nenhuma manchete válida da CNN Brasil coletada, retornando mensagem de erro/fallback.")


    # Retorna as manchetes em formato JSON
    return jsonify({"headlines": all_headlines})
# --- FIM DA ROTA AJUSTADA ---

# --- Rota da API para Informações Operacionais (Letreiro Inferior) ---
# --- Rota da API para Informações Operacionais (Letreiro Inferior) ---
@app.route('/api/operational_info')
def get_operational_info():
    # Estas são as informações que você quer exibir em sequência.
    # Cada item da lista será uma "informação" no letreiro.
    operational_texts = [
        "HUB Muriaé Informa: Rotas No-Show já estão liberadas para carregamento imediato! Procure o Analista de Transporte para mais orientações. | Carregamento Mercadão! As rotas liberadas para Carregamento já estão disponíveis, dirija-se até sua Estação.",
        "Atenção motoristas: Verifiquem documentação antes de se dirigir aos pátios de carregamento. | Prioridade de carregamento para veículos com agendamento prévio. Mantenha-se informado via rádio.",
        "Atenção: Nova Rota disponível. Várias cidades para atendimento . | HUB Muriaé: Todos os motoristas devem realizar o check-in na entrada.",
        "Atenção logística: Motorista só movimente o veículo após a liberação. | Informamos: Acompanhe sua liberação de carregamento através da página de Status de Carregamento.",
        "Segurança em primeiro lugar: Use sempre EPIs nas áreas de carregamento. | HUB Muriaé Informa: Acompanhe a Fila de Carregamento pela TV ou diretamente em seu celular.", # O '|' aqui agora está dentro da string, não como um operador no final.
        "HUB Muriaé: Verifique o quadro de avisos para informações importantes. | Atenção motoristas: Utilize sempre os equipamentos de segurança.",   # O '|' aqui agora está dentro da string, não como um operador no final.
        "Atenção motoristas: Utilize sempre os equipamentos de segurança. | Comunique-se com a equipe para otimizar seu carregamento.",   # O '|' aqui agora está dentro da string, não como um operador no final.
        "Previsão do tempo: Fique atento às condições climáticas."
    ]

    # Retornamos a lista completa de informações.
    return jsonify({"info": operational_texts})

# -------- FIM DA ROTA PAINEL --------
# --- NOVA ROTA: Adicionar Etapa ---
@app.route('/adicionar_etapa', methods=['GET', 'POST'])
@login_required
@permission_required('adicionar_etapa')
def adicionar_etapa():
    if request.method == 'POST':
        nome_etapa = request.form.get('nome_etapa')
        descricao = request.form.get('descricao')

        if nome_etapa:
            nova_etapa = Etapa(nome_etapa=nome_etapa, descricao=descricao)
            try:
                db.session.add(nova_etapa)
                db.session.commit()
                flash(f'Etapa "{nome_etapa}" adicionada com sucesso!', 'success')
                # No need to redirect, we'll display on the same page
                # return redirect(url_for('adicionar_etapa'))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao adicionar etapa: {str(e)}', 'danger')
        else:
            flash('Nome da etapa é obrigatório.', 'warning')

    # Query all existing etapas to display them
    etapas = Etapa.query.order_by(Etapa.nome_etapa).all()
    return render_template('adicionar_etapa.html', etapas=etapas)


@app.route('/apagar_etapa/<int:etapa_id>', methods=['POST'])
@login_required
@permission_required('adicionar_etapa')
def apagar_etapa(etapa_id):
    etapa = Etapa.query.get_or_404(etapa_id)
    try:
        db.session.delete(etapa)
        db.session.commit()
        flash(f'Etapa "{etapa.nome_etapa}" apagada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao apagar etapa: {str(e)}', 'danger')
    return redirect(url_for('adicionar_etapa'))

# --- ROTAS: Editar Etapa ---
@app.route('/editar_etapa/<int:etapa_id>', methods=['GET', 'POST'])
@login_required
@permission_required('adicionar_etapa')
def editar_etapa(etapa_id):
    etapa = Etapa.query.get_or_404(etapa_id)
    if request.method == 'POST':
        nome_etapa = request.form.get('nome_etapa')
        descricao = request.form.get('descricao')

        if nome_etapa:
            etapa.nome_etapa = nome_etapa
            etapa.descricao = descricao
            try:
                db.session.commit()
                flash(f'Etapa "{nome_etapa}" atualizada com sucesso!', 'success')
                return redirect(url_for('adicionar_etapa'))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao atualizar etapa: {str(e)}', 'danger')
        else:
            flash('Nome da etapa é obrigatório.', 'warning')
    return render_template('editar_etapa.html', etapa=etapa)



# --- ROTA: Apagar Situação do Pedido ---
@app.route('/apagar_situacao_pedido/<int:situacao_id>', methods=['POST'])
def apagar_situacao_pedido(situacao_id):
    situacao = SituacaoPedido.query.get_or_404(situacao_id)
    try:
        db.session.delete(situacao)
        db.session.commit()
        flash(f'Situação do Pedido "{situacao.nome_situacao}" apagada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao apagar situação do pedido: {str(e)}', 'danger')
    return redirect(url_for('adicionar_situacao_pedido'))

# --- ROTAS: Editar Situação do Pedido ---
@app.route('/editar_situacao_pedido/<int:situacao_id>', methods=['GET', 'POST'])
def editar_situacao_pedido(situacao_id):
    situacao = SituacaoPedido.query.get_or_404(situacao_id)
    if request.method == 'POST':
        nome_situacao = request.form.get('nome_situacao')
        descricao = request.form.get('descricao')

        if nome_situacao:
            situacao.nome_situacao = nome_situacao
            situacao.descricao = descricao
            try:
                db.session.commit()
                flash(f'Situação do Pedido "{nome_situacao}" atualizada com sucesso!', 'success')
                return redirect(url_for('adicionar_situacao_pedido'))
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao atualizar situação do pedido: {str(e)}', 'danger')
        else:
            flash('Nome da situação é obrigatório.', 'warning')
    return render_template('editar_situacao_pedido.html', situacao=situacao)

# --- NOVA ROTA: Adicionar Situação do Pedido (MODIFICADA para exibir existing) ---
@app.route('/adicionar_situacao_pedido', methods=['GET', 'POST'])
@login_required
@permission_required('adicionar_situacao_pedido')
def adicionar_situacao_pedido():
    if request.method == 'POST':
        nome_situacao = request.form.get('nome_situacao')
        descricao = request.form.get('descricao')

        if nome_situacao:
            nova_situacao = SituacaoPedido(nome_situacao=nome_situacao, descricao=descricao)
            try:
                db.session.add(nova_situacao)
                db.session.commit()
                flash(f'Situação do Pedido "{nome_situacao}" adicionada com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao adicionar situação do pedido: {str(e)}', 'danger')
        else:
            flash('Nome da situação é obrigatório.', 'warning')

    # Query all existing situações de pedido to display them
    situacoes = SituacaoPedido.query.order_by(SituacaoPedido.nome_situacao).all()
    return render_template('adicionar_situacao_pedido.html', situacoes=situacoes)



# ------ Registros Finalizados ------

@app.route('/registros_finalizados', methods=['GET'])
@login_required
@permission_required('registros_finalizados')
def registros_finalizados():
    # Parâmetro para selecionar o banco de dados
    db_name = request.args.get('db_name', 'all') # Padrão: 'all' para exibir ambos

    data_filtro_str = request.args.get('data', '')
    tipo_entrega_filtro = request.args.get('tipo_entrega', '')
    rota_filtro = request.args.get('rota', '')
    finalizado_filtro_str = request.args.get('finalizado', '')
    
    pagina = request.args.get('pagina', 1, type=int)
    
    # **NOTA:** Certifique-se de que REGISTROS_POR_PAGINA está definida em algum lugar do seu código.
    # Exemplo (coloque no topo do seu arquivo, junto com as outras constantes):
    # REGISTROS_POR_PAGINA = 10 
    per_page = REGISTROS_POR_PAGINA

    registros_items = []
    no_show_items = []
    display_db_name = "Todos os Registros" # Padrão

    # Condicionalmente consulta a tabela 'registros' (Modelo Registro)
    if db_name == 'registros' or db_name == 'all':
        query_registros = Registro.query

        if data_filtro_str:
            try:
                data_filtro_dt = datetime.strptime(data_filtro_str, '%Y-%m-%d').date()
                query_registros = query_registros.filter(db.func.date(Registro.data_hora_login) == data_filtro_dt)
            except ValueError:
                pass

        if tipo_entrega_filtro:
            query_registros = query_registros.filter(Registro.tipo_entrega.ilike(f'%{tipo_entrega_filtro}%'))

        if rota_filtro:
            query_registros = query_registros.filter(Registro.rota.ilike(f'%{rota_filtro}%'))

        if finalizado_filtro_str != '':
            finalizado_int = int(finalizado_filtro_str)
            query_registros = query_registros.filter(Registro.finalizada == finalizado_int)
        
        registros_items = query_registros.all()

    # Condicionalmente consulta a tabela 'no_show' (Modelo NoShow)
    if db_name == 'no_show' or db_name == 'all':
        query_no_show = NoShow.query

        if data_filtro_str:
            try:
                data_filtro_dt = datetime.strptime(data_filtro_str, '%Y-%m-%d').date()
                query_no_show = query_no_show.filter(db.func.date(NoShow.data_hora_login) == data_filtro_dt)
            except ValueError:
                pass

        if tipo_entrega_filtro:
            query_no_show = query_no_show.filter(NoShow.tipo_entrega.ilike(f'%{tipo_entrega_filtro}%'))

        if rota_filtro:
            # Para NoShow, a coluna de rota é 'gaiola'
            query_no_show = query_no_show.filter(NoShow.gaiola.ilike(f'%{rota_filtro}%'))

        if finalizado_filtro_str != '':
            finalizado_int = int(finalizado_filtro_str)
            query_no_show = query_no_show.filter(NoShow.finalizada == finalizado_int)

        no_show_items = query_no_show.all()

    # --- Combina ou seleciona os resultados com base em db_name ---
    if db_name == 'registros':
        all_records = registros_items
        display_db_name = "Registros Principais"
    elif db_name == 'no_show':
        all_records = no_show_items
        display_db_name = "Registros de No-Show"
    else: # 'all' ou qualquer outro valor
        all_records = registros_items + no_show_items
        display_db_name = "Todos os Registros"


    # --- Ordena os resultados ---
    all_records = sorted(all_records, key=lambda x: x.data_hora_login, reverse=True)

    # --- Paginação manual da lista combinada ---
    total_registros = len(all_records)
    total_paginas = ceil(total_registros / per_page) if total_registros > 0 else 1
    
    start_index = (pagina - 1) * per_page
    end_index = start_index + per_page
    paginated_records = all_records[start_index:end_index]

    return render_template('registros_finalizados.html',
                            registros=paginated_records, # Passa a lista combinada e paginada
                            total_paginas=total_paginas,
                            pagina=pagina,
                            data=data_filtro_str,
                            tipo_entrega=tipo_entrega_filtro,
                            rota=rota_filtro,
                            finalizado=finalizado_filtro_str,
                            db_name=db_name, # Passa o nome do DB selecionado para o template
                            display_db_name=display_db_name) # Nome amigável para exibição



# app.py
# --- NOVA ROTA: Painel Gerencial ---
# --- Rota: Painel Gerencial (AGORA COM TODOS OS FILTROS) ---

from sqlalchemy import func, distinct
from datetime import datetime, timedelta

# ... (seu código de importação e configuração do Flask/SQLAlchemy)

from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
from sqlalchemy import distinct, func, or_ # Certifique-se de importar 'or_'
from sqlalchemy.dialects import sqlite # Importar o dialeto correto para SQLite

# Importe seus modelos e utilitários (ajuste o caminho conforme sua estrutura)
# from seu_app.models import db, Registro, Etapa, SituacaoPedido, PacoteRastreado
# from seu_app.utils import get_data_hora_brasilia

# ... (sua instância do app Flask e db) ...

# --- ROTA /painel_gerencial (COM DECORADOR @login_required) ---
# --- Rota para o Painel Gerencial (Ajustada) ---
@app.route('/painel_gerencial')
@login_required
@permission_required('painel_gerencial')
def painel_gerencial():
    """
    Renderiza o Painel Gerencial, exibindo apenas registros do dia atual.
    Se não houver registros para o dia, a lista estará vazia.
    """
    print(f"\nDEBUG: Acessando /painel_gerencial. Usuário atual: {current_user.username if current_user.is_authenticated else 'Não Autenticado'}")
    
    data_hoje = get_data_hora_brasilia().date()

    # Coleta os valores dos filtros da URL
    data_hora_login_filtro = request.args.get('data_hora_login', '')
    matricula_filtro = request.args.get('matricula', '')
    nome_filtro = request.args.get('nome', '')
    cidade_selecionada = request.args.get('cidade_filtro', 'todos')
    rota_selecionada = request.args.get('rota_filtro', '')
    tipo_entrega_selecionada = request.args.get('tipo_entrega_filtro', 'todos')
    etapa_selecionada_id_str = request.args.get('etapa_id_filtro', 'todos')
    situacao_pedido_selecionada_id_str = request.args.get('situacao_pedido_id_filtro', 'todos')

    # Coleta os dados para os dropdowns dos filtros
    rotas_registros_query = db.session.query(distinct(Registro.rota)).filter(Registro.rota != None).all()
    rotas_pacotes_query = db.session.query(distinct(PacoteRastreado.rota_vinculada)).filter(PacoteRastreado.rota_vinculada != None).all()
    todas_rotas = sorted(list(set([r[0] for r in rotas_registros_query] + [r[0] for r in rotas_pacotes_query if r[0]])))

    cidades_unicas = sorted([c[0] for c in db.session.query(distinct(Registro.cidade_entrega)).filter(Registro.cidade_entrega != None).order_by(Registro.cidade_entrega).all() if c[0]])
    tipos_entrega_unicos = sorted([t[0] for t in db.session.query(distinct(Registro.tipo_entrega)).filter(Registro.tipo_entrega != None).order_by(Registro.tipo_entrega).all() if t[0]])
    etapas = Etapa.query.order_by(Etapa.nome_etapa).all()
    situacoes_pedido = SituacaoPedido.query.order_by(SituacaoPedido.nome_situacao).all()

    # Construção da query principal
    query = db.session.query(
        Registro,
        Etapa.nome_etapa.label('etapa_nome'),
        SituacaoPedido.nome_situacao.label('situacao_pedido_nome')
    ).join(Etapa, Registro.etapa, isouter=True)\
     .join(SituacaoPedido, Registro.situacao_pedido, isouter=True)

    # Aplicação dos filtros
    if data_hora_login_filtro:
        try:
            data_filtro_dt = datetime.strptime(data_hora_login_filtro, '%Y-%m-%d').date()
            query = query.filter(func.date(Registro.data_hora_login) == data_filtro_dt)
        except ValueError:
            flash("Formato de data inválido.", 'danger')
            # Se a data do filtro for inválida, não devemos exibir nada (ou talvez a data de hoje, dependendo da UX)
            # Para o requisito de "não exibir nada", uma data inválida fará com que a query não retorne resultados.
            registros_filtrados = [] # Garante que a lista de registros fique vazia
            dados_painel_ordenados = [] # E a lista de dados do painel também
            # Renderiza o template com listas vazias
            return render_template('painel_gerencial.html',
                                   dados_painel=dados_painel_ordenados,
                                   data_hora_login_filtro=data_hora_login_filtro,
                                   matricula_filtro=matricula_filtro,
                                   nome_filtro=nome_filtro,
                                   cidades_unicas=cidades_unicas,
                                   cidade_selecionada=cidade_selecionada,
                                   rotas_ordenadas=todas_rotas,
                                   rota_selecionada=rota_selecionada,
                                   tipos_entrega_unicos=tipos_entrega_unicos,
                                   tipo_entrega_selecionada=tipo_entrega_selecionada,
                                   etapas=etapas,
                                   etapa_selecionada_id=int(etapa_selecionada_id_str) if etapa_selecionada_id_str.isdigit() else 'todos',
                                   situacoes_pedido=situacoes_pedido,
                                   situacao_pedido_selecionada_id=int(situacao_pedido_selecionada_id_str) if situacao_pedido_selecionada_id_str.isdigit() else 'todos',
                                   today=data_hoje # Passa a data de hoje para o template
                                   )
    else: # Sempre filtra pela data de hoje se nenhuma data específica for selecionada
        query = query.filter(func.date(Registro.data_hora_login) == data_hoje)

    if matricula_filtro:
        query = query.filter(Registro.matricula.ilike(f'%{matricula_filtro}%'))

    if nome_filtro:
        query = query.filter(Registro.nome.ilike(f'%{nome_filtro}%'))

    if cidade_selecionada != 'todos':
        if cidade_selecionada == 'N/A_VALUE':
            query = query.filter(Registro.cidade_entrega == None)
        else:
            query = query.filter(Registro.cidade_entrega.ilike(cidade_selecionada))

    if rota_selecionada: 
        query = query.filter(Registro.rota.ilike(f'%{rota_selecionada}%'))

    if tipo_entrega_selecionada != 'todos':
        if tipo_entrega_selecionada == 'N/A_VALUE':
            query = query.filter(Registro.tipo_entrega == None)
        else:
            query = query.filter(Registro.tipo_entrega == tipo_entrega_selecionada)

    if etapa_selecionada_id_str != 'todos':
        try:
            etapa_id = int(etapa_selecionada_id_str)
            query = query.filter(Etapa.id == etapa_id)
        except (ValueError, TypeError):
            flash("ID de etapa inválido.", 'danger')

    if situacao_pedido_selecionada_id_str != 'todos':
        try:
            situacao_id = int(situacao_pedido_selecionada_id_str)
            query = query.filter(SituacaoPedido.id == situacao_id)
        except (ValueError, TypeError):
            flash("ID de situação inválido.", 'danger')

    # --- INÍCIO DO BLOCO DE DEPURAÇÃO (útil para ver os filtros aplicados) ---
    print("\n--- VALORES DOS FILTROS RECEBIDOS ---")
    print(f"data_hora_login_filtro: '{data_hora_login_filtro}'")
    print(f"matricula_filtro: '{matricula_filtro}'")
    print(f"nome_filtro: '{nome_filtro}'")
    print(f"cidade_selecionada: '{cidade_selecionada}'")
    print(f"rota_selecionada: '{rota_selecionada}'")
    print(f"tipo_entrega_selecionada: '{tipo_entrega_selecionada}'")
    print(f"etapa_selecionada_id_str: '{etapa_selecionada_id_str}'")
    print(f"situacao_pedido_selecionada_id_str: '{situacao_pedido_selecionada_id_str}'")
    print("-------------------------------------\n")

    # Importa o dialeto SQLite para depuração, se ainda não estiver importado
    from sqlalchemy.dialects import sqlite
    print("\n--- DEPURANDO A QUERY SQL (Dialeto SQLite) ---")
    try:
        compiled_query = query.statement.compile(dialect=sqlite.dialect())
        print("SQL Gerado:", compiled_query)
        print("Parâmetros:", compiled_query.params)
    except Exception as e:
        print(f"Erro ao compilar a query: {e}")
    print("--------------------------------------------\n")
    # --- FIM DO BLOCO DE DEPURAÇÃO ---

    registros_filtrados = query.order_by(Registro.rota, Registro.data_hora_login).all()

    print("\n--- REGISTROS RETORNADOS DA CONSULTA ---")
    if registros_filtrados:
        for r, etapa_nome, situacao_nome in registros_filtrados:
            print(f"ID: {r.id}, Matrícula: {r.matricula}, Rota: {r.rota}, Cidade: {r.cidade_entrega}, Data Login: {r.data_hora_login}, Etapa: {etapa_nome}, Situação: {situacao_nome}")
    else:
        print("Nenhum registro encontrado com os filtros aplicados.")
    print("----------------------------------------\n")

    # Contagem de pacotes otimizada (uma única query)
    contagem_pacotes_query = db.session.query(
        PacoteRastreado.rota_vinculada,
        func.count(PacoteRastreado.id)
    ).filter(PacoteRastreado.rota_vinculada.in_(todas_rotas))\
     .group_by(PacoteRastreado.rota_vinculada).all()
    pacotes_por_rota = dict(contagem_pacotes_query)

    # Montagem dos dados do painel
    dados_painel = []
    # Não vamos mais adicionar rotas vazias com 'N/A' se não houver registros reais
    # Apenas processa os registros filtrados
    for r, etapa_nome, situacao_nome in registros_filtrados:
        rota_nome = r.rota if r.rota else 'N/A'

        previsao_entrega = (r.data_hora_login + timedelta(days=1)).strftime('%d-%m-%Y %H:%M:%S') if r.data_hora_login else 'N/A'
        data_de_entrega = r.data_de_entrega.strftime('%d-%m-%Y') if r.data_de_entrega else 'N/A'

        dados_painel.append({
            'id': r.id,
            'data_hora_login': r.data_hora_login.strftime('%d-%m-%Y %H:%M:%S') if r.data_hora_login else 'N/A',
            'matricula': r.matricula,
            'nome': r.nome,
            'cidade': r.cidade_entrega,
            'rota': rota_nome,
            'qtde_pacotes': pacotes_por_rota.get(rota_nome, 0),
            'tipo_entrega': r.tipo_entrega,
            'previsao_entrega': previsao_entrega,
            'etapa': etapa_nome if etapa_nome else 'N/A',
            'data_de_entrega': data_de_entrega,
            'situacao_pedido': situacao_nome if situacao_nome else 'N/A',
        })

    # Ordenação final por rota (garante que 'N/A' venha por último, se houver)
    dados_painel_ordenados = sorted(dados_painel, key=lambda x: (x['rota'] == 'N/A', x['rota']))

    # Renderiza o template
    return render_template('painel_gerencial.html',
                           dados_painel=dados_painel_ordenados,
                           data_hora_login_filtro=data_hora_login_filtro,
                           matricula_filtro=matricula_filtro,
                           nome_filtro=nome_filtro,
                           cidades_unicas=cidades_unicas,
                           cidade_selecionada=cidade_selecionada,
                           rotas_ordenadas=todas_rotas,
                           rota_selecionada=rota_selecionada,
                           tipos_entrega_unicos=tipos_entrega_unicos,
                           tipo_entrega_selecionada=tipo_entrega_selecionada,
                           etapas=etapas,
                           etapa_selecionada_id=int(etapa_selecionada_id_str) if etapa_selecionada_id_str.isdigit() else 'todos',
                           situacoes_pedido=situacoes_pedido,
                           situacao_pedido_selecionada_id=int(situacao_pedido_selecionada_id_str) if situacao_pedido_selecionada_id_str.isdigit() else 'todos',
                           today=data_hoje # Passa a data de hoje para o template
                           )


# --- NOVA ROTA API: Atualizar Situação do Pedido de um Registro (POST) ---
@app.route('/api/atualizar_situacao_pedido/<int:registro_id>', methods=['POST'])
def api_atualizar_situacao_pedido(registro_id):
    registro = Registro.query.get(registro_id)
    if not registro:
        return jsonify({"success": False, "message": "Registro não encontrado."}), 404

    nova_situacao_id = request.json.get('nova_situacao_id')
    if nova_situacao_id is None:
        return jsonify({"success": False, "message": "ID da nova situação não fornecido."}), 400

    situacao = SituacaoPedido.query.get(nova_situacao_id)
    if not situacao:
        return jsonify({"success": False, "message": "Situação inválida."}), 400

    try:
        registro.situacao_pedido = situacao
        db.session.commit()
        return jsonify({"success": True, "message": "Situação do pedido atualizada com sucesso!", "situacao_nome": situacao.nome_situacao}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar situação do pedido do registro {registro_id}: {e}")
        return jsonify({"success": False, "message": f"Erro ao atualizar situação do pedido: {str(e)}"}), 500

# --- NOVA ROTA API: Atualizar Data de Entrega de um Registro (POST) ---
@app.route('/api/atualizar_data_entrega/<int:registro_id>', methods=['POST'])
def api_atualizar_data_entrega(registro_id):
    registro = Registro.query.get(registro_id)
    if not registro:
        return jsonify({"success": False, "message": "Registro não encontrado."}), 404

    nova_data_str = request.json.get('nova_data') # Espera "YYYY-MM-DD HH:MM:SS" ou "YYYY-MM-DD"
    
    if not nova_data_str:
        # Se for nulo ou vazio, limpa o campo
        registro.data_de_entrega = None
    else:
        try:
            # Tenta converter para datetime.datetime
            # Pode ser necessário um parser mais robusto se o formato variar muito
            registro.data_de_entrega = datetime.strptime(nova_data_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                registro.data_de_entrega = datetime.strptime(nova_data_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({"success": False, "message": "Formato de data inválido. Use YYYY-MM-DD HH:MM:SS ou YYYY-MM-DD."}), 400

    try:
        db.session.commit()
        return jsonify({"success": True, "message": "Data de entrega atualizada com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar data de entrega do registro {registro_id}: {e}")
        return jsonify({"success": False, "message": f"Erro ao atualizar data de entrega: {str(e)}"}), 500
    
    # --- Nova Rota para Importar Pacotes de TXT ---
@app.route('/importar_pacotes_txt', methods=['POST'])
@login_required
@permission_required('pacotes_rota')
def importar_pacotes_txt():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('pacotes_rota'))

    file = request.files['file']
    rota_selecionada_do_form = request.form.get('rota_para_importar') # A rota virá do formulário de upload

    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('pacotes_rota'))

    if not rota_selecionada_do_form: # Agora verificamos se a rota do form é válida
        flash('A rota para importação é obrigatória.', 'danger')
        return redirect(url_for('pacotes_rota'))

    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        pacotes_importados_com_sucesso = 0
        pacotes_duplicados = 0
        erros_importacao = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                next(f) # Pular a primeira linha (cabeçalho)

                for line_num, line in enumerate(f, 2):
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue

                    parts = line_stripped.split(',')
                    # Esperamos pelo menos ID Pacote, Rota, Etapa, Observação, Data
                    if len(parts) < 5:
                        erros_importacao.append(f'Linha {line_num}: Formato inválido (menos de 5 campos). Linha ignorada: "{line_stripped}"')
                        continue

                    id_pacote = parts[0].strip()
                    rota_pacote = parts[1].strip() # Assume que a rota está na segunda coluna
                    nome_etapa_do_arquivo = parts[2].strip()
                    observacao = parts[3].strip() if parts[3].strip().lower() != 'null' else None
                    data_cadastro_str = parts[4].strip()
                    acoes_do_arquivo = parts[5].strip() if len(parts) > 5 else None

                    etapa_obj = Etapa.query.filter_by(nome_etapa=nome_etapa_do_arquivo).first()
                    etapa_id = etapa_obj.id if etapa_obj else None

                    situacao_pedido_obj = SituacaoPedido.query.filter_by(nome_situacao=nome_etapa_do_arquivo).first()
                    situacao_pedido_id = situacao_pedido_obj.id if situacao_pedido_obj else None

                    data_cadastro = None
                    try:
                        data_cadastro = get_data_hora_brasilia().replace(
                            year=datetime.strptime(data_cadastro_str, '%d/%m/%Y').year,
                            month=datetime.strptime(data_cadastro_str, '%d/%m/%Y').month,
                            day=datetime.strptime(data_cadastro_str, '%d/%m/%Y').day
                        )
                    except ValueError:
                        erros_importacao.append(f'Linha {line_num}: Formato de data inválido para "{data_cadastro_str}". Usando data/hora atual de Brasília.')
                        data_cadastro = get_data_hora_brasilia()

                    existing_pacote = PacoteRastreado.query.filter_by(
                        id_pacote=id_pacote,
                        rota_vinculada=rota_selecionada_do_form # Usa a rota do FORMULÁRIO para verificação
                    ).first()

                    if not existing_pacote:
                        try:
                            novo_pacote = PacoteRastreado(
                                id_pacote=id_pacote,
                                rota_vinculada=rota_selecionada_do_form,
                                etapa_id=etapa_id,
                                observacao=observacao,
                                data_cadastro=data_cadastro,
                                acoes=acoes_do_arquivo # Incluindo o valor de Ações
                            )
                            db.session.add(novo_pacote)
                            pacotes_importados_com_sucesso += 1

                            # Encontra ou cria o registro correspondente (usando a rota do arquivo)
                            data_hoje = get_data_hora_brasilia().date()
                            registro_principal = Registro.query.filter(
                                Registro.rota == rota_pacote,
                                func.date(Registro.data_hora_login) == data_hoje
                            ).first()
                            if registro_principal:
                                registro_principal.etapa_id = etapa_id
                                registro_principal.situacao_pedido_id = situacao_pedido_id
                                db.session.add(registro_principal)

                        except Exception as e:
                            db.session.rollback()
                            erros_importacao.append(f'Linha {line_num}: Erro ao adicionar pacote "{id_pacote}": {str(e)}')
                    else:
                        pacotes_duplicados += 1
                        erros_importacao.append(f'Linha {line_num}: Pacote "{id_pacote}" já existe para a rota "{rota_selecionada_do_form}".')

            db.session.commit()

            flash(f'Importação concluída: {pacotes_importados_com_sucesso} pacotes novos importados. {pacotes_duplicados} pacotes duplicados ignorados.', 'success')
            for erro in erros_importacao:
                flash(erro, 'warning')

        except Exception as e:
            db.session.rollback()
            flash(f'Erro geral durante a leitura ou importação do arquivo: {str(e)}', 'danger')
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"Valor de acoes_do_arquivo: '{acoes_do_arquivo}'")

    return redirect(url_for('pacotes_rota', rota_selecionada_importacao=rota_selecionada_do_form))

# --- Rota /pacotes_rota (Mantenha o código existente, mas adicione rotas_existentes ao render_template) ---
@app.route('/pacotes_rota', methods=['GET', 'POST'])
@login_required
@permission_required('pacotes_rota')
def pacotes_rota():
    etapas = Etapa.query.order_by(Etapa.nome_etapa).all()

    # CORREÇÃO: Mude a forma de acessar a rota para a primeira (e única) coluna da tupla
    # ou use .scalars() se estiver disponível e você quiser apenas os valores
    rotas_existentes_query = db.session.query(distinct(Registro.rota)).filter(Registro.rota != None).order_by(Registro.rota).all()
    rotas_existentes = [r[0] for r in rotas_existentes_query if r[0] is not None]
    # Ou, uma forma mais moderna e que retorna os valores diretamente:
    # rotas_existentes = db.session.query(distinct(Registro.rota)).filter(Registro.rota != None).order_by(Registro.rota).scalars().all()

    situacoes_pedido = SituacaoPedido.query.order_by(SituacaoPedido.nome_situacao).all() # Adicione esta linha

    if request.method == 'POST':
        # ... (sua lógica existente para adicionar pacote manualmente) ...
        id_pacote = request.form.get('id_pacote')
        etapa_id = request.form.get('etapa')
        observacao = request.form.get('observacao')
        rota_selecionada = request.form.get('rota_selecionada_importacao')
        acoes = request.form.get('acoes') # O valor virá do select agora

        if id_pacote and rota_selecionada:
            existing_pacote = PacoteRastreado.query.filter_by(id_pacote=id_pacote, rota_vinculada=rota_selecionada).first()
            if existing_pacote:
                flash(f'Pacote com ID "{id_pacote}" já existe para a rota "{existing_pacote.rota_vinculada}".', 'warning')
            else:
                try:
                    novo_pacote = PacoteRastreado(
                        id_pacote=id_pacote,
                        etapa_id=int(etapa_id) if etapa_id and etapa_id != 'None' else None,
                        observacao=observacao,
                        rota_vinculada=rota_selecionada,
                        acoes=acoes if acoes else None # Salva o ID da situação de pedido
                    )
                    db.session.add(novo_pacote)
                    db.session.commit()
                    flash(f'Pacote "{id_pacote}" adicionado com sucesso para a rota "{rota_selecionada}"!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Erro ao adicionar pacote: {str(e)}', 'danger')
        else:
            flash('ID Pacote e Rota são campos obrigatórios para adicionar um pacote.', 'danger')

        return redirect(url_for('pacotes_rota', rota_selecionada_importacao=rota_selecionada))

    rota_para_exibir = request.args.get('rota_selecionada_importacao')
    pacotes = []
    if rota_para_exibir and rota_para_exibir != 'todos':
        pacotes = PacoteRastreado.query.filter_by(rota_vinculada=rota_para_exibir).order_by(PacoteRastreado.data_cadastro.desc()).all()
    else:
        pacotes = PacoteRastreado.query.order_by(PacoteRastreado.data_cadastro.desc()).all()

    return render_template(
        'pacotes_rota.html',
        etapas=etapas,
        rotas_existentes=rotas_existentes,
        pacotes=pacotes,
        rota_selecionada_no_form=rota_para_exibir,
        situacoes_pedido=situacoes_pedido # Passe a lista de situações para o template
    )
    
# --- Nova Rota API: Buscar Pacotes por Rota (para importação) ---
@app.route('/api/pacotes_por_rota/<string:rota_nome>')
def get_pacotes_por_rota(rota_nome):
    if rota_nome == 'todos':
        pacotes_data = PacoteRastreado.query.all()
    else:
        pacotes_data = PacoteRastreado.query.filter_by(rota_vinculada=rota_nome).all()

    pacotes_json = []
    for p in pacotes_data:
        etapa = p.etapa_texto if hasattr(p, 'etapa_texto') else (p.etapa.nome_etapa if p.etapa else 'Não definida')
        acoes = ''
        if etapa == 'Entregue 100%':
            acoes = 'Entregue no prazo'
        elif etapa == 'In Sucesso' or etapa == 'Atrasado' or etapa == 'Devolvido' or etapa == 'Recusado entrega':
            acoes = 'Não Entregue'
        elif etapa == 'Entregue com Atraso':
            acoes = 'Entregue com Atraso'

        brasil_tz = pytz.timezone('America/Sao_Paulo')
        data_cadastro_brasil = p.data_cadastro.astimezone(brasil_tz)

        pacotes_json.append({
            'id': p.id,
            'id_pacote': p.id_pacote,
            'etapa': etapa,
            'observacao': p.observacao,
            'data_cadastro': formata_data_hora(data_cadastro_brasil),
            'rota_vinculada': p.rota_vinculada,
            'acoes': acoes
        })
    return jsonify(pacotes_json)

    #### ----- DashBoard ------

@app.route('/dashboard')
@login_required # Protege a rota, exigindo login
@permission_required('dashboard') # Exige a permissão 'dashboard'
def dashboard():
    """Renderiza a página principal do dashboard."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    return render_template('dashboard.html', start_date=start_date, end_date=end_date)

@app.route('/api/dashboard_data')
def get_dashboard_data():
    """
    Retorna os dados para o dashboard em formato JSON, buscando do Supabase PostgreSQL.
    """
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Base para filtros de data
    date_filters = {}
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').isoformat() + "Z" # ISO format para Supabase
            date_filters['gte'] = start_date
        except ValueError:
            pass

    if end_date_str:
        try:
            # Para incluir o dia inteiro, adicionamos 1 dia e subtraímos 1 microssegundo
            end_date = (datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(microseconds=1)).isoformat() + "Z" # ISO format para Supabase
            date_filters['lte'] = end_date
        except ValueError:
            pass

    # --- Funções Auxiliares para Reutilização de Lógica de Filtro ---
    # Tornando a coluna de data configurável
    def apply_date_filters(query_builder, date_column_name):
        """Aplica filtros de data a um query builder do Supabase para uma coluna específica."""
        if 'gte' in date_filters:
            query_builder = query_builder.gte(date_column_name, date_filters['gte'])
        if 'lte' in date_filters:
            query_builder = query_builder.lte(date_column_name, date_filters['lte'])
        return query_builder

    # 1. CONTA O TOTAL DE PEDIDOS (TODOS OS REGISTROS FILTRADOS POR DATA)
    try:
        query_total_pedidos = supabase.table('PacoteRastreado').select('id', count='exact')
        query_total_pedidos = apply_date_filters(query_total_pedidos, 'data_cadastro')
        response_total_pedidos = query_total_pedidos.execute()
        total_pedidos = response_total_pedidos.count if response_total_pedidos.count is not None else 0
        print(f"DEBUG: Total Pedidos - Query: {query_total_pedidos.get_url()}, Count: {total_pedidos}")
    except Exception as e:
        print(f"Erro ao buscar total de pedidos: {e}")
        total_pedidos = 0


    # 2. CONTA A QUANTIDADE DE PACOTES ENTREGUES (EXCLUINDO 'Não Entregue')
    try:
        query_pacotes_entregues_realizadas = supabase.table('PacoteRastreado').select('id', count='exact')
        query_pacotes_entregues_realizadas = apply_date_filters(query_pacotes_entregues_realizadas, 'data_cadastro')
        query_pacotes_entregues_realizadas = query_pacotes_entregues_realizadas.neq('acoes', 'Não Entregue')
        response_entregues_realizadas = query_pacotes_entregues_realizadas.execute()
        qtd_pacotes_entregues_realizadas = response_entregues_realizadas.count if response_entregues_realizadas.count is not None else 0
        print(f"DEBUG: Pacotes Entregues - Query: {query_pacotes_entregues_realizadas.get_url()}, Count: {qtd_pacotes_entregues_realizadas}")
    except Exception as e:
        print(f"Erro ao buscar pacotes entregues: {e}")
        qtd_pacotes_entregues_realizadas = 0

    # 3. CONTA A QUANTIDADE DE ROTAS CARREGADAS (NA TABELA REGISTRO)
    try:
        query_rotas_carregadas = supabase.table('Registro').select('id', count='exact')
        query_rotas_carregadas = apply_date_filters(query_rotas_carregadas, 'data_hora_login') # <-- Correção AQUI!
        query_rotas_carregadas = query_rotas_carregadas.eq('finalizada', 1)
        response_rotas_carregadas = query_rotas_carregadas.execute()
        qtd_rotas_carregadas = response_rotas_carregadas.count if response_rotas_carregadas.count is not None else 0
        print(f"DEBUG: Rotas Carregadas (Registro) - Query: {query_rotas_carregadas.get_url()}, Count: {qtd_rotas_carregadas}")
    except Exception as e:
        print(f"Erro ao buscar rotas carregadas: {e}")
        qtd_rotas_carregadas = 0

    # 4. CONTA PEDIDOS ENTREGUES 100% (etapa_id = 12 na tabela PacoteRastreado)
    try:
        query_pedidos_entregues_100 = supabase.table('PacoteRastreado').select('id', count='exact')
        query_pedidos_entregues_100 = apply_date_filters(query_pedidos_entregues_100, 'data_cadastro')
        query_pedidos_entregues_100 = query_pedidos_entregues_100.eq('etapa_id', 12)
        response_pedidos_entregues_100 = query_pedidos_entregues_100.execute()
        pedidos_entregues_100 = response_pedidos_entregues_100.count if response_pedidos_entregues_100.count is not None else 0
        print(f"DEBUG: Pedidos Entregues 100% - Query: {query_pedidos_entregues_100.get_url()}, Count: {pedidos_entregues_100}")
    except Exception as e:
        print(f"Erro ao buscar pedidos entregues 100%: {e}")
        pedidos_entregues_100 = 0

    # 5. CONTA PEDIDOS NA ETAPA 11 (nova variável)
    try:
        query_pedidos_etapa_11 = supabase.table('PacoteRastreado').select('id', count='exact')
        query_pedidos_etapa_11 = apply_date_filters(query_pedidos_etapa_11, 'data_cadastro')
        query_pedidos_etapa_11 = query_pedidos_etapa_11.eq('etapa_id', 11)
        response_pedidos_etapa_11 = query_pedidos_etapa_11.execute()
        pedidos_etapa_11 = response_pedidos_etapa_11.count if response_pedidos_etapa_11.count is not None else 0
        print(f"DEBUG: Pedidos Etapa 11 - Query: {query_pedidos_etapa_11.get_url()}, Count: {pedidos_etapa_11}")
    except Exception as e:
        print(f"Erro ao buscar pedidos etapa 11: {e}")
        pedidos_etapa_11 = 0

    # 6. CALCULA ON TIME (OTD)
    try:
        query_on_time = supabase.table('PacoteRastreado').select('id', count='exact')
        query_on_time = apply_date_filters(query_on_time, 'data_cadastro')
        query_on_time = query_on_time.eq('acoes', 'Entregue no prazo')
        response_on_time = query_on_time.execute()
        on_time_deliveries_count = response_on_time.count if response_on_time.count is not None else 0
        print(f"DEBUG: On Time Deliveries - Query: {query_on_time.get_url()}, Count: {on_time_deliveries_count}")
    except Exception as e:
        print(f"Erro ao buscar entregas no prazo: {e}")
        on_time_deliveries_count = 0

    on_time_percentage = 0.0
    if total_pedidos > 0:
        on_time_percentage = (float(on_time_deliveries_count) / total_pedidos) * 100

    # 7. CALCULA IN FULL
    in_full_numerator = pedidos_entregues_100
    in_full_percentage = 0.0
    if total_pedidos > 0:
        in_full_percentage = (float(in_full_numerator) / total_pedidos) * 100

    # 8. CALCULA OTIF (On Time In Full)
    otif_percentage = 0.0
    if on_time_percentage > 0 and in_full_percentage > 0:
        otif_percentage = (on_time_percentage * in_full_percentage) / 100

    # 9. CALCULA TX. ATRASO (utilizando etapa_id = 11)
    taxa_atraso_formatted = str(pedidos_etapa_11)

    # 10. CALCULA TX. AVARIA
    try:
        query_damaged = supabase.table('PacoteRastreado').select('id', count='exact')
        query_damaged = apply_date_filters(query_damaged, 'data_cadastro')
        query_damaged = query_damaged.eq('etapa_id', 13)
        response_damaged = query_damaged.execute()
        damaged_deliveries_count = response_damaged.count if response_damaged.count is not None else 0
        print(f"DEBUG: Damaged Deliveries - Query: {query_damaged.get_url()}, Count: {damaged_deliveries_count}")
    except Exception as e:
        print(f"Erro ao buscar entregas com avaria: {e}")
        damaged_deliveries_count = 0

    taxa_avaria_percentage = 0.0
    if total_pedidos > 0:
        taxa_avaria_percentage = (float(damaged_deliveries_count) / total_pedidos) * 100

    # 11. CALCULA % IN SUCESSO
    try:
        query_in_sucesso_etapa = supabase.table('PacoteRastreado').select('id', count='exact')
        query_in_sucesso_etapa = apply_date_filters(query_in_sucesso_etapa, 'data_cadastro')
        query_in_sucesso_etapa = query_in_sucesso_etapa.eq('etapa_id', 2)
        response_in_sucesso_etapa = query_in_sucesso_etapa.execute()
        in_sucesso_etapa_count = response_in_sucesso_etapa.count if response_in_sucesso_etapa.count is not None else 0
        print(f"DEBUG: In Sucesso (Etapa 2) - Query: {query_in_sucesso_etapa.get_url()}, Count: {in_sucesso_etapa_count}")
    except Exception as e:
        print(f"Erro ao buscar in sucesso: {e}")
        in_sucesso_etapa_count = 0

    percentual_in_sucesso_calculated = 0.0
    if total_pedidos > 0:
        percentual_in_sucesso_calculated = (float(in_sucesso_etapa_count) / total_pedidos) * 100

    # 12. CALCULA % DEVOLVIDOS
    try:
        query_devolvidos_etapa = supabase.table('PacoteRastreado').select('id', count='exact')
        query_devolvidos_etapa = apply_date_filters(query_devolvidos_etapa, 'data_cadastro')
        query_devolvidos_etapa = query_devolvidos_etapa.eq('etapa_id', 14)
        response_devolvidos_etapa = query_devolvidos_etapa.execute()
        devolvidos_etapa_count = response_devolvidos_etapa.count if response_devolvidos_etapa.count is not None else 0
        print(f"DEBUG: Devolvidos (Etapa 14) - Query: {query_devolvidos_etapa.get_url()}, Count: {devolvidos_etapa_count}")
    except Exception as e:
        print(f"Erro ao buscar devolvidos: {e}")
        devolvidos_etapa_count = 0

    percentual_devolvidos_calculated = 0.0
    if total_pedidos > 0:
        percentual_devolvidos_calculated = (float(devolvidos_etapa_count) / total_pedidos) * 100

    # 13. NOVO DADO: Total de Entregas no Prazo
    total_entregas_no_prazo = on_time_deliveries_count

    # 14. NOVO DADO: Total Devolvidos (valor absoluto)
    total_devolvidos_count = devolvidos_etapa_count

    # 15. NOVO DADO: Total Não Entregue (valor absoluto)
    try:
        query_nao_entregue = supabase.table('PacoteRastreado').select('id', count='exact')
        query_nao_entregue = apply_date_filters(query_nao_entregue, 'data_cadastro')
        query_nao_entregue = query_nao_entregue.eq('acoes', 'Não Entregue')
        response_nao_entregue = query_nao_entregue.execute()
        total_nao_entregue_count = response_nao_entregue.count if response_nao_entregue.count is not None else 0
        print(f"DEBUG: Não Entregues - Query: {query_nao_entregue.get_url()}, Count: {total_nao_entregue_count}")
    except Exception as e:
        print(f"Erro ao buscar não entregues: {e}")
        total_nao_entregue_count = 0


    # Formata ON TIME
    if on_time_percentage % 1 == 0:
        on_time_formatted = f"{int(on_time_percentage)}%"
    else:
        on_time_formatted = f"{on_time_percentage:.1f}%".replace('.', ',')

    # Formata IN FULL
    if in_full_percentage % 1 == 0:
        in_full_formatted = f"{int(in_full_percentage)}%"
    else:
        in_full_formatted = f"{in_full_percentage:.1f}%".replace('.', ',')

    # Formata OTIF
    otif_formatted = f"{otif_percentage:.2f}%".replace('.', ',')

    # Formata TX. AVARIA
    if taxa_avaria_percentage % 1 == 0:
        taxa_avaria_formatted = f"{int(taxa_avaria_percentage)}%"
    else:
        taxa_avaria_formatted = f"{taxa_avaria_percentage:.1f}%".replace('.', ',')

    # Formata % IN SUCESSO
    if percentual_in_sucesso_calculated % 1 == 0:
        percentual_in_sucesso_formatted = f"{int(percentual_in_sucesso_calculated)}%"
    else:
        percentual_in_sucesso_formatted = f"{percentual_in_sucesso_calculated:.1f}%".replace('.', ',')

    # Formata % DEVOLVIDOS
    if percentual_devolvidos_calculated % 1 == 0:
        percentual_devolvidos_formatted = f"{int(percentual_devolvidos_calculated)}%"
    else:
        percentual_devolvidos_formatted = f"{percentual_devolvidos_calculated:.1f}%".replace('.', ',')

    total_in_sucesso_count = in_sucesso_etapa_count


    # --- Dados para Gráficos (agora calculados dinamicamente) ---

    # Gráfico de Status (Painel Gerencial)
    painel_gerencial_labels = [
        'Total de Pacotes', 'Qtd. Pacotes Entregues', 'Total de Entregas no Prazo',
        'Pedidos Entregues 100%', 'Qtd. Pacotes Entregues com Atraso',
        'Total de In Sucesso', 'Total Devolvidos', 'Total Avaria Motorista'
    ]
    painel_gerencial_counts = [
        total_pedidos,
        qtd_pacotes_entregues_realizadas,
        on_time_deliveries_count,
        pedidos_entregues_100,
        pedidos_etapa_11,
        in_sucesso_etapa_count,
        devolvidos_etapa_count,
        damaged_deliveries_count
    ]

    # Gráfico de Entregas por Mês (Barra)
    try:
        entregas_mes_query = supabase.table('PacoteRastreado').select("data_cadastro,id").neq('acoes', 'Não Entregue').not_.is_('data_cadastro', 'NULL')
        entregas_mes_query = apply_date_filters(entregas_mes_query, 'data_cadastro')
        response_entregas_mes = entregas_mes_query.execute()
        entregas_mes_data_raw = response_entregas_mes.data if response_entregas_mes.data is not None else []
        print(f"DEBUG: Entregas Mês (Raw) - Data size: {len(entregas_mes_data_raw)}")

        entregas_mes_agregado = {}
        for item in entregas_mes_data_raw:
            if item.get('data_cadastro'):
                mes_ano = datetime.fromisoformat(item['data_cadastro'].replace('Z', '')).strftime('%Y-%m')
                entregas_mes_agregado[mes_ano] = entregas_mes_agregado.get(mes_ano, 0) + 1

        entregas_mes_labels = sorted(entregas_mes_agregado.keys())
        entregas_mes_counts = [entregas_mes_agregado[label] for label in entregas_mes_labels]
        print(f"DEBUG: Entregas Mês (Aggregated) - Labels: {entregas_mes_labels}, Counts: {entregas_mes_counts}")

    except Exception as e:
        print(f"Erro ao buscar entregas por mês: {e}")
        entregas_mes_labels = []
        entregas_mes_counts = []

    # Gráfico de Entregas por Dia (Rosca)
    try:
        entregas_dia_query = supabase.table('PacoteRastreado').select("data_cadastro,id").neq('acoes', 'Não Entregue').not_.is_('data_cadastro', 'NULL')
        entregas_dia_query = apply_date_filters(entregas_dia_query, 'data_cadastro')
        response_entregas_dia = entregas_dia_query.execute()
        entregas_dia_data_raw = response_entregas_dia.data if response_entregas_dia.data is not None else []
        print(f"DEBUG: Entregas Dia (Raw) - Data size: {len(entregas_dia_data_raw)}")

        entregas_dia_agregado = {}
        for item in entregas_dia_data_raw:
            if item.get('data_cadastro'):
                dia_mes_ano = datetime.fromisoformat(item['data_cadastro'].replace('Z', '')).strftime('%Y-%m-%d')
                entregas_dia_agregado[dia_mes_ano] = entregas_dia_agregado.get(dia_mes_ano, 0) + 1

        entregas_dia_labels = sorted(entregas_dia_agregado.keys())
        entregas_dia_counts = [entregas_dia_agregado[label] for label in entregas_dia_labels]
        print(f"DEBUG: Entregas Dia (Aggregated) - Labels: {entregas_dia_labels}, Counts: {entregas_dia_counts}")

    except Exception as e:
        print(f"Erro ao buscar entregas por dia: {e}")
        entregas_dia_labels = []
        entregas_dia_counts = []


    # Gráfico 'In Sucesso' por Mês
    try:
        in_sucesso_mes_query = supabase.table('PacoteRastreado').select("data_cadastro,id").eq('etapa_id', 2).not_.is_('data_cadastro', 'NULL')
        in_sucesso_mes_query = apply_date_filters(in_sucesso_mes_query, 'data_cadastro')
        response_in_sucesso_mes = in_sucesso_mes_query.execute()
        in_sucesso_mes_data_raw = response_in_sucesso_mes.data if response_in_sucesso_mes.data is not None else []
        print(f"DEBUG: In Sucesso Mês (Raw) - Data size: {len(in_sucesso_mes_data_raw)}")

        in_sucesso_mes_agregado = {}
        for item in in_sucesso_mes_data_raw:
            if item.get('data_cadastro'):
                mes_ano = datetime.fromisoformat(item['data_cadastro'].replace('Z', '')).strftime('%Y-%m')
                in_sucesso_mes_agregado[mes_ano] = in_sucesso_mes_agregado.get(mes_ano, 0) + 1

        in_sucesso_mes_labels = sorted(in_sucesso_mes_agregado.keys())
        in_sucesso_mes_counts = [in_sucesso_mes_agregado[label] for label in in_sucesso_mes_labels]
        print(f"DEBUG: In Sucesso Mês (Aggregated) - Labels: {in_sucesso_mes_labels}, Counts: {in_sucesso_mes_counts}")

    except Exception as e:
        print(f"Erro ao buscar in sucesso por mês: {e}")
        in_sucesso_mes_labels = []
        in_sucesso_mes_counts = []


    return jsonify({
        'kpis': {
            'totalPedidos': total_pedidos,
            'qtdPacotesEntregues': qtd_pacotes_entregues_realizadas,
            'qtdRotasCarregadas': qtd_rotas_carregadas,
            'pedidosEntregues100': pedidos_entregues_100,
            'onTime': on_time_formatted,
            'inFull': in_full_formatted,
            'otif': otif_formatted,
            'taxaAtraso': taxa_atraso_formatted,
            'taxaAvaria': taxa_avaria_formatted,
            'percentualInSucesso': percentual_in_sucesso_formatted,
            'percentualDevolvidos': percentual_devolvidos_formatted,
            'totalInSucesso': total_in_sucesso_count,
            'totalEntregasNoPrazo': total_entregas_no_prazo,
            'totalDevolvidos': total_devolvidos_count,
            'totalNaoEntregue': total_nao_entregue_count
        },
        'charts': {
            'painelGerencialLabels': painel_gerencial_labels,
            'painelGerencialCounts': painel_gerencial_counts,
            'entregasMesLabels': entregas_mes_labels,
            'entregasMesCounts': entregas_mes_counts,
            'entregasDiaLabels': entregas_dia_labels,
            'entregasDiaCounts': entregas_dia_counts,
            'inSucessoMesLabels': in_sucesso_mes_labels,
            'inSucessoMes_counts': in_sucesso_mes_counts
        }
    })





@app.route('/gerenciar_usuarios')
@login_required
@permission_required('gerenciar_usuarios')
# @login_required # Descomente se estiver usando Flask-Login
# @admin_required # Descomente se estiver usando o decorator admin_required
def gerenciar_usuarios():
    # Verifica se o usuário atual é um administrador
    # Assumindo que permission_required('Gerenciar Usuários') já faz essa verificação
    # if not current_user.is_admin:
    #    flash('Você não tem permissão para acessar a página de gerenciamento de usuários.', 'danger')
    #    abort(403) # Retorna um erro 403 (Acesso Negado)

    # Inicializa a consulta base de usuários
    query = User.query # CORRIGIDO: de Usuario.query para User.query

    # Obtém os parâmetros de filtro da URL
    filter_matricula = request.args.get('matricula', '').strip()
    filter_username = request.args.get('username', '').strip()

    # Aplica os filtros se eles existirem
    if filter_matricula:
        # Use .ilike() para busca case-insensitive e % para correspondência parcial
        query = query.filter(User.matricula.ilike(f'%{filter_matricula}%'))
    if filter_username:
        query = query.filter(User.username.ilike(f'%{filter_username}%'))

    # Executa a consulta e obtém os usuários filtrados
    usuarios = query.all()

    return render_template('gerenciar_usuarios.html', usuarios=usuarios)


@app.route('/alterar_senha/<int:user_id>', methods=['GET', 'POST'])
# @login_required # Descomente se estiver usando Flask-Login
def alterar_senha(user_id):
    user_to_edit = User.query.get_or_404(user_id)

    # Opcional: Verifique se o usuário atual tem permissão para alterar esta senha
    # if not current_user.is_admin and current_user.id != user_to_edit.id:
    #     flash('Você não tem permissão para alterar a senha deste usuário.', 'danger')
    #     return redirect(url_for('dashboard'))

    form = ChangePasswordForm()

    if form.validate_on_submit():
        user_to_edit.set_password(form.new_password.data) # Criptografa e salva a nova senha
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('gerenciar_usuarios')) # Redireciona para a página de gerenciamento

    return render_template('alterar_senha.html', form=form, user=user_to_edit) # Passa 'user' para o template


# Rota para alternar o status do usuário (ativar/desativar)
@app.route('/alternar_status_usuario/<int:user_id>', methods=['GET', 'POST'])
@login_required
@permission_required('gerenciar_usuarios')
# @login_required # Descomente se estiver usando Flask-Login
# @admin_required # Considere adicionar um decorador para garantir que apenas admins possam fazer isso
def alternar_status_usuario(user_id):
    """
    Alterna o status (ativo/inativo) de um usuário.
    """
    user = User.query.get_or_404(user_id) # Busca o usuário pelo ID ou retorna 404

    # Evita que um admin desative a própria conta por acidente (opcional)
    # if current_user.is_authenticated and user.id == current_user.id and user.is_admin:
    #    flash('Você não pode desativar sua própria conta de administrador.', 'danger')
    #    return redirect(url_for('gerenciar_usuarios'))

    user.ativo = not user.ativo # Inverte o status atual
    try:
        db.session.commit()
        flash(f'Usuário {user.username} foi {"ativado" if user.ativo else "desativado"} com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        # current_app.logger.error(f"Erro ao alternar status do usuário {user.username}: {e}") # Usar current_app requer estar dentro de um app_context
        app.logger.error(f"Erro ao alternar status do usuário {user.username}: {e}")
        flash('Erro ao alternar o status do usuário.', 'danger')

    return redirect(url_for('gerenciar_usuarios')) # Redireciona de volta para a página de gerenciamento

# Apenas UMA definição final da rota editar_usuario
@app.route('/editar_usuario/<int:usuario_id>', methods=['GET', 'POST'])
@login_required # Garante que apenas usuários logados podem acessar
# @admin_required # Considere adicionar este decorador para garantir que só admins podem editar usuários
def editar_usuario(usuario_id):
    user_to_edit = User.query.get_or_404(usuario_id)

    # === CORREÇÃO CRÍTICA AQUI: Passe os valores originais para o construtor do formulário ===
    form = EditarUsuarioForm(
        obj=user_to_edit, # Pré-popula os campos do formulário com os dados do usuário
        original_username=user_to_edit.username,
        original_email=user_to_edit.email,
        original_matricula=user_to_edit.matricula
    )

    # Preenche as escolhas do campo de permissões a partir do seu dicionário PERMISSIONS
    # A coerção para string (`coerce=str`) já deve estar em forms.py
    form.paginas_acesso.choices = [(key, value) for key, value in PERMISSIONS.items()]

    if form.validate_on_submit():
        # A lógica de validação de unicidade agora funcionará,
        # pois o formulário conhece os valores originais.

        # Atualiza os dados básicos do usuário
        user_to_edit.username = form.username.data
        user_to_edit.email = form.email.data
        user_to_edit.matricula = form.matricula.data
        user_to_edit.nome_completo = form.nome_completo.data
        user_to_edit.is_admin = form.is_admin.data
        user_to_edit.ativo = form.ativo.data

        # Lógica para alterar a senha, SE fornecida no formulário
        # RECOMENDAÇÃO IMPORTANTE: Sempre faça hashing da senha.
        # Se você reintroduzir o 'set_password' no modelo User (com hashing), use-o aqui.
        if form.password.data:
            # EXEMPLO COM HASHING (RECOMENDADO):
            # from werkzeug.security import generate_password_hash # Importe isso no topo
            # user_to_edit.password = generate_password_hash(form.password.data)
            #
            # SE VOCÊ REALMENTE QUER TEXTO PURO (NÃO RECOMENDADO):
            user_to_edit.password = form.password.data # CUIDADO: Senha em texto puro no DB!

        # Lógica para salvar as permissões de acesso
        if user_to_edit.is_admin:
            # Se for admin, o campo JSON 'permissions' pode ficar vazio,
            # pois o método has_permission no modelo User já retorna True para admins.
            user_to_edit.set_permissions_list([]) # Usa o método do modelo para lidar com JSON
            # E, se você também usa a relação many-to-many 'permissoes_objeto', limpe-a:
            user_to_edit.permissoes_objeto = []
        else:
            # Salva as permissões selecionadas no campo JSON 'permissions'
            user_to_edit.set_permissions_list(form.paginas_acesso.data)
            # E, se você usa a relação many-to-many 'permissoes_objeto', atualize-a:
            selected_perm_names = form.paginas_acesso.data
            selected_perm_objects = Permissao.query.filter(Permissao.nome_pagina.in_(selected_perm_names)).all()
            user_to_edit.permissoes_objeto = selected_perm_objects


        try:
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('gerenciar_usuarios'))
        except Exception as e:
            db.session.rollback()
            # Use current_app.logger para logar erros em Flask
            current_app.logger.error(f"Erro ao atualizar usuário: {e}", exc_info=True)
            flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')
    else:
        # Se for uma requisição GET (primeira vez carregando a página)
        # ou se a validação do formulário falhou no POST:
        # Pré-popula os checkboxes de permissão com as permissões atuais do usuário.
        if user_to_edit.is_admin:
            form.is_admin.data = True
            form.paginas_acesso.data = [] # Desmarcar tudo, o JS no template irá desabilitar
        else:
            form.is_admin.data = False
            # Carrega as permissões do campo JSON 'permissions' do usuário
            form.paginas_acesso.data = user_to_edit.get_permissions_list()

    return render_template('editar_usuario.html', form=form, user=user_to_edit)



import pytz # Importe pytz para manipulação de fuso horário


@app.route('/log_de_atividades')
@login_required # Garante que apenas usuários logados podem acessar
# @permission_required('log_atividades') # Considere adicionar esta permissão se tiver um sistema granular
def log_atividades():
    """
    Exibe uma lista de todas as atividades registradas no sistema,
    com opção de filtro por intervalo de datas e exibição em fuso horário de Brasília.
    """
    # 1. Captura dos parâmetros de filtro de data da requisição GET
    data_inicial_str = request.args.get('data_inicial')
    data_final_str = request.args.get('data_final')

    # Inicia a consulta ao banco de dados, carregando o relacionamento 'user'
    # --- CORREÇÃO AQUI: 'LogAtatividade' corrigido para 'LogAtividade' ---
    query = LogAtividade.query.options(joinedload(LogAtividade.user))

    # Variáveis para armazenar os objetos datetime das datas filtradas
    data_inicial_dt = None
    data_final_dt = None

    # 2. Converte as strings de data para objetos datetime e trata erros
    if data_inicial_str:
        try:
            # Converte a string para datetime e define a hora para o início do dia (00:00:00)
            data_inicial_dt = datetime.strptime(data_inicial_str, '%Y-%m-%d').replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        except ValueError:
            flash('Data inicial inválida. Por favor, use o formato AAAA-MM-DD.', 'danger')
            data_inicial_dt = None # Reseta para não aplicar um filtro inválido

    if data_final_str:
        try:
            # Converte a string para datetime e define a hora para o final do dia (23:59:59.999999)
            # Isso garante que todos os logs do dia final sejam incluídos.
            data_final_dt = datetime.strptime(data_final_str, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        except ValueError:
            flash('Data final inválida. Por favor, use o formato AAAA-MM-DD.', 'danger')
            data_final_dt = None # Reseta para não aplicar um filtro inválido

    # 3. Aplica os filtros de data à consulta
    if data_inicial_dt:
        # Filtra logs onde o timestamp é maior ou igual à data inicial
        query = query.filter(LogAtividade.timestamp >= data_inicial_dt)
    if data_final_dt:
        # Filtra logs onde o timestamp é menor ou igual à data final
        query = query.filter(LogAtividade.timestamp <= data_final_dt)

    try:
        # 4. Ordena os logs (do mais recente para o mais antigo) e executa a consulta
        logs = query.order_by(LogAtividade.timestamp.desc()).all()

        # Define o fuso horário de Brasília para conversão
        tz_brasilia = pytz.timezone('America/Sao_Paulo')
        
        # Itera sobre os logs para ajustar o fuso horário para exibição
        for log in logs:
            if log.timestamp:
                # --- Lógica de conversão de fuso horário ---
                # Se o timestamp do DB for um datetime ingênuo (sem tzinfo),
                # assumimos que ele foi salvo em UTC (como corrigimos nas rotas de escrita).
                if log.timestamp.tzinfo is None:
                    # Primeiro, localize-o como UTC.
                    log.timestamp = pytz.utc.localize(log.timestamp)
                
                # Em seguida, converta para o fuso horário de Brasília.
                log.timestamp = log.timestamp.astimezone(tz_brasilia)

    except Exception as e:
        # Certifique-se de que app.logger ou current_app.logger está configurado
        # para que os erros sejam registrados adequadamente em produção.
        print(f"Erro ao buscar logs de atividades: {e}") # Para depuração rápida
        logs = [] # Retorna uma lista vazia em caso de erro
        flash('Não foi possível carregar os logs de atividades.', 'danger')

    # 5. Renderiza o template, passando os logs e as strings de data para manter os filtros nos campos
    return render_template('log_atividades.html', 
                            logs=logs,
                            data_inicial=data_inicial_str, # Passa para pré-preencher o campo de filtro
                            data_final=data_final_str) # Passa para pré-preencher o campo de filtro



# --- Bloco de inicialização (no final do app.py) ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        print("Banco de dados SQLite local inicializado e tabelas criadas/atualizadas.")

        # Popula etapas iniciais, se necessário
        if not Etapa.query.first():
            print("Populando tabela de etapas...")
            etapas_iniciais = [
                Etapa(nome_etapa="Aguardando Carregamento", descricao="O veículo está aguardando para ser carregado."),
                Etapa(nome_etapa="Carregamento Iniciado", descricao="O carregamento do veículo está em andamento."),
                Etapa(nome_etapa="Carregamento Finalizado", descricao="O veículo foi carregado e está pronto para sair."),
                Etapa(nome_etapa="Em Trânsito", descricao="O veículo está a caminho do destino."),
                Etapa(nome_etapa="Em Entrega", descricao="O veículo está realizando entregas."),
                Etapa(nome_etapa="Entregue", descricao="Todas as entregas foram realizadas."),
                Etapa(nome_etapa="Retorno ao HUB", descricao="O veículo está retornando à base."),
                Etapa(nome_etapa="Finalizado HUB", descricao="O veículo retornou e foi finalizado no HUB."),
                Etapa(nome_etapa="Cancelado", descricao="A entrega ou carregamento foi cancelado.")
            ]
            db.session.add_all(etapas_iniciais)
            db.session.commit()
            print("Etapas populadas com sucesso!")
        else:
            print("Tabela de etapas já contém dados.")

        # Popula situações de pedido iniciais, se necessário
        if not SituacaoPedido.query.first():
            print("Populando tabela de situações de pedido...")
            situacoes_iniciais = [
                SituacaoPedido(nome_situacao="Em Processamento", descricao="O pedido foi recebido e está sendo preparado."),
                SituacaoPedido(nome_situacao="Em Separação", descricao="Os itens do pedido estão sendo separados no estoque."),
                SituacaoPedido(nome_situacao="Pronto para Envio", descricao="O pedido está embalado e aguardando coleta da transportadora."),
                SituacaoPedido(nome_situacao="Em Trânsito", descricao="O pedido está a caminho do destino."),
                SituacaoPedido(nome_situacao="Saiu para Entrega", descricao="O pedido saiu para entrega final ao cliente."),
                SituacaoPedido(nome_situacao="Entregue", descricao="O pedido foi entregue com sucesso."),
                SituacaoPedido(nome_situacao="Cancelado", descricao="O pedido foi cancelado pelo cliente ou empresa."),
                SituacaoPedido(nome_situacao="Problema na Entrega", descricao="Ocorreu um problema durante a tentativa de entrega (ex: endereço incorreto)."),
                SituacaoPedido(nome_situacao="Devolvido", descricao="O pedido foi devolvido ao remetente.")
            ]
            db.session.add_all(situacoes_iniciais)
            db.session.commit()
            print("Situações de pedido populadas com sucesso!")
        else:
            print("Tabela de situações de pedido já contém dados.")

    app.run(debug=True, port=5000)
