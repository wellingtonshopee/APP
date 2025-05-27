# routes/auth_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from models import db, Login # Importe seus modelos e a instância db
from utils import formatar_texto_title # Importe a função utilitária
from config import get_data_hora_brasilia # Importe a função de data/hora de Brasília

# Crie um Blueprint para as rotas de autenticação
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        matricula = request.form.get('matricula')
        senha = request.form.get('senha') # Se você for implementar senha no futuro

        # Sua lógica de login aqui
        login_user = Login.query.filter_by(matricula=matricula).first()
        
        # Por enquanto, sem verificação de senha. Apenas matrícula.
        if login_user:
            session['matricula'] = login_user.matricula
            session['nome'] = login_user.nome
            session['logged_in'] = True # Defina como True ao logar
            flash(f'Bem-vindo, {login_user.nome}!', 'success')
            # Redireciona para a página principal de registros após o login
            return redirect(url_for('registro_bp.registros'))

        flash('Matrícula inválida ou não encontrada.', 'error')
    return render_template('login.html', erro=None)

@auth_bp.route('/logout')
def logout():
    session.pop('matricula', None)
    session.pop('nome', None)
    session['logged_in'] = False # Defina como False ao deslogar
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        matricula = request.form.get('matricula')
        tipo_veiculo = request.form.get('tipo_veiculo')

        # Capitaliza o nome e tipo_veiculo antes de salvar
        nome = formatar_texto_title(nome)
        tipo_veiculo = formatar_texto_title(tipo_veiculo)

        if not nome or not matricula:
            flash('Nome e Matrícula são obrigatórios!', 'error')
            return render_template('cadastro.html', erro="Nome e Matrícula são obrigatórios!")

        # Verifica se a matrícula já existe
        existing_login = Login.query.filter_by(matricula=matricula).first()
        if existing_login:
            flash('Matrícula já cadastrada!', 'error')
            return render_template('cadastro.html', erro="Matrícula já cadastrada!")

        try:
            # Cria um novo registro de Login
            novo_login = Login(nome=nome, matricula=matricula, tipo_veiculo=tipo_veiculo, data_cadastro=get_data_hora_brasilia())
            db.session.add(novo_login)
            db.session.commit()
            flash('Motorista cadastrado com sucesso!', 'success')
            return redirect(url_for('auth.login')) # Redireciona para a página de login após o cadastro
        except Exception as e:
            db.session.rollback() # Reverte a transação em caso de erro
            flash(f"Erro ao cadastrar motorista: {str(e)}", 'error')
            return render_template('cadastro.html', erro=f"Erro ao cadastrar: {str(e)}")
    return render_template('cadastro.html', erro=None)