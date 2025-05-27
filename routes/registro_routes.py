# routes/registro_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from models import db, Registro, Login # Importe seus modelos e db
from config import STATUS_REGISTRO_PRINCIPAL, STATUS_EM_SEPARACAO, get_data_hora_brasilia
from utils import formatar_texto_title

registro_bp = Blueprint('registro_bp', __name__)

@registro_bp.route('/registros', methods=['GET'])
def registros():
    # Lógica de listagem e filtragem de registros principais
    # Certifique-se de que o usuário está logado
    if 'matricula' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('auth.login'))

    # ... (Sua lógica de filtragem, paginação, etc.) ...
    # Exemplo:
    registros_query = Registro.query
    # Aplique os filtros conforme sua lógica atual
    registros_principais = registros_query.order_by(Registro.data_hora_login.desc()).all()
    
    return render_template('seus_templates_registros.html', registros=registros_principais)

@registro_bp.route('/criar_registro', methods=['POST'])
def criar_registro_principal():
    # Lógica de criação de registro principal (normal ou associando No-Show)
    nome = request.form.get('nome')
    matricula = request.form.get('matricula')
    data_hora_login_agora = get_data_hora_brasilia()
    rota_input = request.form.get('rota')
    tipo_entrega = request.form.get('tipo_entrega')
    cidade_entrega = request.form.get('cidade_entrega')

    # Aplica a formatação title
    nome = formatar_texto_title(nome)
    rota_input = formatar_texto_title(rota_input)
    tipo_entrega = formatar_texto_title(tipo_entrega)
    cidade_entrega = formatar_texto_title(cidade_entrega)

    # Restante da lógica de criação do Registro, incluindo a busca por No-Show
    # (Copie e cole a parte POST da sua rota /registros do app.py original aqui)
    # Lembre-se de importar o modelo NoShow se precisar dele aqui
    
    # ... (Seu código existente da rota /registros POST aqui) ...
    # Exemplo:
    novo_registro = Registro(
        nome=nome,
        matricula=matricula,
        data_hora_login=data_hora_login_agora,
        rota=rota_input,
        tipo_entrega=tipo_entrega,
        cidade_entrega=cidade_entrega,
        rua=None,
        estacao=None,
        status=STATUS_REGISTRO_PRINCIPAL['AGUARDANDO_CARREGAMENTO']
    )
    db.session.add(novo_registro)
    db.session.commit()
    flash("Registro de chegada criado com sucesso!", 'success')
    return redirect(url_for('registro_bp.registros'))

# Outras rotas relacionadas a registros principais, como associar_id, desassociar_id,
# marcar_como_finalizado_id, cancelar_registro, finalizar_carregamento_id_status_separacao
# (se você mantiver essa) devem ser movidas para este arquivo.
# Exemplo:
@registro_bp.route('/associar/<int:id>', methods=['POST'])
def associar_id(id):
    # ... (Sua lógica de associar registro aqui) ...
    return redirect(url_for('registro_bp.registros'))