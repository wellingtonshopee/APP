from flask import Flask, render_template, request, redirect, url_for, jsonify,current_app, flash
from supabase import create_client, Client
from sqlalchemy import or_ # Importar 'or_' para filtros OR
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta # Adicione ', timedelta' aqui
import pytz
from dateutil import tz # Para a função tz.gettz()
import requests
import feedparser
from math import ceil
from io import BytesIO
from sqlalchemy import func
import psycopg2
import os
from sqlalchemy import or_
import threading 
import random # <--- ADICIONE ESTA LINHA
from bs4 import BeautifulSoup


app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.fjurmbfvfuzhyrwkduav:Qaz241059%23MLP140308@aws-0-us-east-2.pooler.supabase.com:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Definição dos Modelos do Banco de Dados --- # SISTEMA CRIADO E DESENVOLVIDO POR WELLINGTON CAMPOS: E-MAIL: WCAMPOS241059@GMAIL.COM
# ====================================================================
# DEFINIÇÃO DAS CONSTANTES DE STATUS (ADICIONE OU VERIFIQUE ESTAS)
# ====================================================================
STATUS_REGISTRO_PRINCIPAL = {
    'AGUARDANDO_CARREGAMENTO': 'Aguardando Carregamento',
    'CARREGAMENTO_LIBERADO': 'Carregamento Liberado',
    'EM_CARREGAMENTO': 'Em Carregamento',
    'FINALIZADO': 'Finalizado',
    'CANCELADO': 'Cancelado'
}

# Constantes para os estados de 'em_separacao'
# --- Definições dos Status de 'em_separacao' ---
STATUS_EM_SEPARACAO = {
    'AGUARDANDO_MOTORISTA': 0,
    'SEPARACAO': 1,
    'FINALIZADO': 2, # Manter Finalizado com valor 2
    'CANCELADO': 3,
    'TRANSFERIDO': 4,
    'AGUARDANDO_ENTREGADOR': 5 # Nova chave adicionada
}


# --- Função Auxiliar para Traduzir o Status (para exibir no HTML) ---
def get_status_text(status_code):
    """Traduz o código numérico do status 'em_separacao' para texto amigável."""
    # Criar um mapeamento inverso para facilitar a busca
    status_map = {v: k for k, v in STATUS_EM_SEPARACAO.items()}
    text = status_map.get(status_code, 'DESCONHECIDO')
    return text.replace('_', ' ').title() # Ex: 'AGUARDANDO_MOTORISTA' -> 'Aguardando Motorista'

# --- Seu Modelo NoShow (certifique-se de que está como abaixo) ---
class NoShow(db.Model):
    __tablename__ = 'no_show'
    id = db.Column(db.Integer, primary_key=True)
    # **Ajuste:** Garante que o default é UTC e ciente do fuso horário.
    data_hora_login = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.utcnow().replace(tzinfo=pytz.utc))
    nome = db.Column(db.String(100))
    matricula = db.Column(db.String(50))
    gaiola = db.Column(db.String(50)) # Rota
    tipo_entrega = db.Column(db.String(50))
    rua = db.Column(db.String(200))
    estacao = db.Column(db.String(50))
    finalizada = db.Column(db.Integer, default=0)
    cancelado = db.Column(db.Integer, default=0)
    em_separacao = db.Column(db.Integer, default=STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA'])
    # **Ajuste:** A coluna está correta. A atribuição da hora_finalizacao deve usar UTC.
    hora_finalizacao = db.Column(db.DateTime(timezone=True)) 

    def __repr__(self):
        return f"<NoShow {self.id} - {self.nome} - Rota: {self.gaiola}>"

class Registro(db.Model):
    __tablename__ = 'registros'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    matricula = db.Column(db.String(20), nullable=False)
    rota = db.Column(db.String(80))
    tipo_entrega = db.Column(db.String(80))
    cidade_entrega = db.Column(db.String(80))
    rua = db.Column(db.String(80))
    # **Ajuste:** Garante que o default é UTC e ciente do fuso horário.
    data_hora_login = db.Column(db.DateTime(timezone=True), default=lambda: datetime.utcnow().replace(tzinfo=pytz.utc))
    tipo_veiculo = db.Column(db.String(80))
    em_separacao = db.Column(db.Integer, default=0)
    gaiola = db.Column(db.String(80))
    estacao = db.Column(db.String(80))
    finalizada = db.Column(db.Integer, default=0)
    # **Ajuste:** A coluna está correta. A atribuição da hora_finalizacao deve usar UTC.
    hora_finalizacao = db.Column(db.DateTime(timezone=True)) 
    cancelado = db.Column(db.Integer, default=0)
    login_id = db.Column(db.Integer, db.ForeignKey('login.id'))
    login = db.relationship('Login', backref=db.backref('registros', lazy=True))

    def __repr__(self):
        return f'<Registro {self.matricula} - {self.nome}>'

class Login(db.Model):
    __tablename__ = 'login'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    tipo_veiculo = db.Column(db.String(80))
    data_cadastro = db.Column(db.DateTime) # Este pode ser naive se não for importante ter TZ

class Cidade(db.Model):
    __tablename__ = 'cidades' # Nome da tabela no banco de dados
    id = db.Column(db.Integer, primary_key=True) # Mapeia para SERIAL PRIMARY KEY
    cidade = db.Column(db.String(80), unique=True, nullable=False)
    # ... outras colunas ...


# --- Inicializar Base de Dados (com Flask-SQLAlchemy) ---
def init_db():
    with app.app_context():
        db.create_all()
        print("Banco de dados PostgreSQL inicializado (com Flask-SQLAlchemy).")

# --- Suas funções utilitárias (get_data_hora_brasilia, formata_data_hora) ---
def get_data_hora_brasilia():
    """
    Obtém a data e hora atuais no fuso horário de São Paulo (Brasil)
    como um objeto datetime ciente do fuso horário.
    """
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz_brasilia) # Retorna o objeto datetime diretamente

def formata_data_hora(data_hora):
    if not data_hora:
        return 'Não Finalizado' 

    # Defina o fuso horário de exibição (Brasil/São Paulo)
    tz_destino = pytz.timezone('America/Sao_Paulo')

    if isinstance(data_hora, datetime):
        # Se o objeto datetime NÃO tiver informações de fuso horário (tzinfo is None),
        # assumimos que ele já está no fuso horário de Muriaé (America/Sao_Paulo),
        # pois o SQLAlchemy pode retornar datetime 'naive' já ajustado para a timezone da conexão.
        if data_hora.tzinfo is None:
            # Torna o datetime 'aware' localizando-o no fuso horário de Muriaé.
            data_hora_aware = tz_destino.localize(data_hora)
        else:
            # Se já tem tzinfo, significa que ele já é 'aware'.
            # Apenas converte para o fuso horário de destino se ainda não estiver.
            data_hora_aware = data_hora.astimezone(tz_destino)
        
        # Como data_hora_aware já está no tz_destino, podemos formatar diretamente.
        return data_hora_aware.strftime('%d/%m/%Y %H:%M:%S')
    
    # Se ainda chegar algo que não seja datetime, é um erro.
    return 'Erro de Formato Inesperado'

app.jinja_env.filters['formata_data_hora'] = formata_data_hora
# --- Suas rotas ---
def capitalize_words(text):
    if text:
        return ' '.join(word.capitalize() for word in text.split())
    return None

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
@app.route('/registros')
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
def associacao_no_show():
    # Esta rota simplesmente renderiza o formulário
    return render_template('associacao_no_show.html')

@app.route('/criar_registro_no_show', methods=['POST'])
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
def exibir_midia():
    """Renderiza a página HTML com a exibição de mídia (vídeos e slides)."""
    print("DEBUG: Rota /midia acessada. Renderizando midia.html")
    return render_template('midia.html')

# --- Rota para exibir o menu principal ---
@app.route('/menu_principal')
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




# ------ Registros Finalizados ------

@app.route('/registros_finalizados', methods=['GET'])
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

# ... o restante do seu app.py ...
# (Todas as suas outras rotas aqui: /sucesso, /boas_vindas, /todos_registros, /registros, /historico, /associacao, etc.)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)